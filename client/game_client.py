"""Headless client-side network adapter used by the pygame UI."""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass, field

from client.socket_connection import SocketConnection
from game.match_state import MatchState
from network.configure_pressure_packet import ConfigurePressurePacket
from network.disconnect_packet import DisconnectPacket
from network.error_packet import ErrorPacket
from network.game_over_packet import GameOverPacket
from network.game_start_packet import GameStartPacket
from network.game_state_packet import GameStatePacket
from network.hello_packet import HelloPacket
from network.join_rejected_packet import JoinRejectedPacket
from network.place_tower_packet import PlaceTowerPacket
from network.register_packets import register_packets
from network.sell_tower_packet import SellTowerPacket
from network.skip_build_packet import SkipBuildPacket
from network.upgrade_tower_packet import UpgradeTowerPacket
from network.join_accepted_packet import JoinAcceptedPacket
from shared.models.game_rules import EnemyKind, OffensiveModifier, TowerKind
from shared.serialization import deserialize_match_state
from shared.settings import DEFAULT_HOST, DEFAULT_PORT, SOCKET_TIMEOUT_SECONDS


@dataclass(slots=True)
class ClientSessionState:
    """Client-side snapshot of session and match-related state."""

    player_id: str | None = None
    opponent_name: str | None = None
    match_state: MatchState | None = None
    error_messages: list[str] = field(default_factory=list)
    game_over: bool = False
    game_over_winner: str | None = None
    game_over_is_draw: bool = False
    connected: bool = False
    welcome_message: str = ""
    connect_error_message: str = ""


class GameClient:
    """Manage the client socket, handshake, and incoming server state."""

    _MAX_ERROR_MESSAGES = 10

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        player_name: str = "Player1",
    ) -> None:
        register_packets()
        self.host = host
        self.port = port
        self.player_name = player_name

        self.session = ClientSessionState()
        self._connection = SocketConnection(
            host=host,
            port=port,
            timeout_seconds=SOCKET_TIMEOUT_SECONDS,
        )
        self._recv_thread: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._ready_event = threading.Event()
        self._connect_attempted = False

    def connect(self) -> bool:
        """Open a connection, send the hello packet, and start the receive loop."""

        if self._connect_attempted:
            self._set_connect_error("Reconnect is disabled. Return to lobby and connect again.")
            print(self.connect_error_message)
            return False

        self._connect_attempted = True
        self._reset_session()

        try:
            self._connection.open()
            self._connection.send(HelloPacket(player_name=self.player_name))

            response = self._connection.receive()
            if isinstance(response, JoinRejectedPacket):
                reason = self._normalize_reject_reason(response.reason)
                self._set_connect_error(reason)
                print(f"Connection rejected: {reason}")
                self.disconnect()
                return False

            if not isinstance(response, JoinAcceptedPacket):
                raise ValueError(
                    "Expected join-accepted or join-rejected packet, "
                    f"received {response.packet_id()!r}."
                )

            self._handle_welcome(response)
            self._set_connected(True)

            print(f"Server: {self.welcome_message}")

            self._connection.set_timeout(None)
            self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._recv_thread.start()
            return True

        except (ConnectionError, OSError, TimeoutError, ValueError) as error:
            message = self._format_connect_error(error)
            self._set_connect_error(message)
            print(f"Failed to connect: {message}")
            self.disconnect()
            return False

    def disconnect(self) -> None:
        """Disconnect from the server and tear down the local socket state."""

        if self._connection.is_open:
            try:
                self._connection.send(DisconnectPacket())
            except (ConnectionError, OSError):
                pass
        self._set_connected(False)
        self._ready_event.set()
        self._connection.close()

    def wait_until_ready(self, timeout: float = 120.0) -> bool:
        """Block until the server assigns the local player to a match."""

        if self.player_id is not None:
            return True

        if not self.is_connected:
            print("Disconnected while waiting.")
            return False

        if not self._ready_event.wait(timeout):
            print("Timed out waiting for match to start.")
            return False

        if not self.is_connected:
            print("Disconnected while waiting.")
            return False

        return self.player_id is not None

    def place_tower(self, tower_type: TowerKind, tile_x: int, tile_y: int) -> None:
        """Send a tower placement request."""

        self._send(PlaceTowerPacket(tower_type=tower_type.value, tile_x=tile_x, tile_y=tile_y))

    def upgrade_tower(self, tower_id: int) -> None:
        """Send a tower upgrade request."""

        self._send(UpgradeTowerPacket(tower_id=tower_id))

    def sell_tower(self, tower_id: int) -> None:
        """Send a tower sell request."""

        self._send(SellTowerPacket(tower_id=tower_id))

    def sell_tower_at(self, tile_x: int, tile_y: int) -> None:
        """Look up a tower by tile and send a sell request for it."""

        match_state = self.match_state
        player_id = self.player_id
        if match_state is None or player_id is None:
            raise ValueError("Player state is not ready yet.")

        player = match_state.players.get(player_id)
        if player is None:
            raise ValueError("Could not find your player state.")

        tower_id = next(
            (
                tower.tower_id
                for tower in player.towers.values()
                if tower.tile_x == tile_x and tower.tile_y == tile_y
            ),
            None,
        )
        if tower_id is None:
            raise ValueError("No tower on that tile to sell.")

        self.sell_tower(tower_id)

    def configure_pressure(
        self,
        unit_counts: dict[EnemyKind, int],
        modifiers: set[OffensiveModifier] | None = None,
    ) -> None:
        """Send an updated outgoing pressure plan to the server."""

        counts = {kind.value: count for kind, count in unit_counts.items()}
        modifier_values = [modifier.value for modifier in (modifiers or set())]
        self._send(
            ConfigurePressurePacket(
                unit_counts=counts,
                modifiers=modifier_values,
            )
        )

    def skip_build(self) -> None:
        """Mark the local player as ready for the next wave."""

        self._send(SkipBuildPacket())

    def pop_errors(self) -> list[str]:
        """Return and clear queued server-side error messages."""

        with self._state_lock:
            errors = list(self.session.error_messages)
            self.session.error_messages.clear()
            return errors

    @property
    def player_id(self) -> str | None:
        with self._state_lock:
            return self.session.player_id

    @property
    def opponent_name(self) -> str | None:
        with self._state_lock:
            return self.session.opponent_name

    @property
    def match_state(self) -> MatchState | None:
        with self._state_lock:
            return self.session.match_state

    @property
    def is_connected(self) -> bool:
        with self._state_lock:
            return self.session.connected

    @property
    def welcome_message(self) -> str:
        with self._state_lock:
            return self.session.welcome_message

    @property
    def game_over(self) -> bool:
        with self._state_lock:
            return self.session.game_over

    @property
    def game_over_winner(self) -> str | None:
        with self._state_lock:
            return self.session.game_over_winner

    @property
    def game_over_is_draw(self) -> bool:
        with self._state_lock:
            return self.session.game_over_is_draw

    @property
    def connect_error_message(self) -> str:
        with self._state_lock:
            return self.session.connect_error_message

    def _reset_session(self) -> None:
        """Reset local session data before a fresh connect attempt."""

        with self._state_lock:
            self.session = ClientSessionState()
        self._ready_event.clear()

    def _send(self, packet: object) -> None:
        """Send a packet and disconnect on transport failure."""

        if not self._connection.is_open:
            return

        try:
            self._connection.send(packet)
        except (ConnectionError, OSError):
            self.disconnect()

    def _receive_loop(self) -> None:
        """Continuously receive packets until the connection closes."""

        while self.is_connected and self._connection.is_open:
            try:
                self._handle_packet(self._connection.receive())
            except (ConnectionError, OSError):
                break
            except Exception as error:
                print(f"Error in receive loop: {error}")
                break

        self.disconnect()

    def _handle_packet(self, packet: object) -> None:
        """Dispatch a received packet to the appropriate handler."""

        if isinstance(packet, GameStartPacket):
            self._handle_game_start(packet)
        elif isinstance(packet, GameStatePacket):
            self._handle_game_state(packet)
        elif isinstance(packet, GameOverPacket):
            self._handle_game_over(packet)
        elif isinstance(packet, ErrorPacket):
            self._handle_error(packet)
        elif isinstance(packet, JoinAcceptedPacket):
            self._handle_welcome(packet)

    def _handle_game_start(self, packet: GameStartPacket) -> None:
        """Store match assignment data from the server."""

        with self._state_lock:
            self.session.player_id = packet.your_player_id
            self.session.opponent_name = packet.opponent_name
        self._ready_event.set()
        print(
            f"Match started! You are {packet.your_player_id}, opponent: {packet.opponent_name}"
        )

    def _handle_game_state(self, packet: GameStatePacket) -> None:
        """Replace the local match snapshot with the latest server state."""

        match_state = deserialize_match_state(packet.state)
        with self._state_lock:
            self.session.match_state = match_state

    def _handle_game_over(self, packet: GameOverPacket) -> None:
        """Store final match result metadata."""

        with self._state_lock:
            self.session.game_over = True
            self.session.game_over_winner = packet.winner_player_id or None
            self.session.game_over_is_draw = packet.is_draw
        print(f"Game over! Winner: {packet.winner_player_id}, Draw: {packet.is_draw}")

    def _handle_error(self, packet: ErrorPacket) -> None:
        """Queue an error message received from the server."""

        with self._state_lock:
            self.session.error_messages.append(packet.message)
            if len(self.session.error_messages) > self._MAX_ERROR_MESSAGES:
                self.session.error_messages = self.session.error_messages[
                    -self._MAX_ERROR_MESSAGES :
                ]

    def _handle_welcome(self, packet: JoinAcceptedPacket) -> None:
        """Store the server welcome message shown in the lobby."""

        with self._state_lock:
            self.session.welcome_message = packet.message

    def _set_connected(self, connected: bool) -> None:
        """Update the local connection flag."""

        with self._state_lock:
            self.session.connected = connected

    def _set_connect_error(self, message: str) -> None:
        """Store the latest user-facing connect error message."""

        with self._state_lock:
            self.session.connect_error_message = message

    @staticmethod
    def _normalize_reject_reason(reason: str) -> str:
        """Map server rejection reasons to cleaner lobby messages."""

        lowered = reason.lower()
        if "already running" in lowered or "in progress" in lowered:
            return "Server is full and already running a match. Try again later."
        if "server is full" in lowered:
            return "Server lobby is full. Try again later."
        return reason

    @staticmethod
    def _format_connect_error(error: Exception) -> str:
        """Convert low-level socket errors into UI-friendly text."""

        if isinstance(error, socket.gaierror):
            return "Could not resolve server address. Check IP/hostname."

        if isinstance(error, (TimeoutError, socket.timeout)):
            return "Connection timed out. Server did not respond."

        if isinstance(error, ConnectionRefusedError):
            return "Connection refused. Server is offline or port is closed."

        if isinstance(error, OSError):
            if error.errno == 1:
                return "Connection blocked by OS or firewall permissions."
            if error.errno in {101, 113}:
                return "Network is unreachable. Check internet/VPN routing."
            if error.errno == 111:
                return "Connection refused. Server is offline or port is closed."

        if isinstance(error, ValueError):
            return (
                "Protocol mismatch with server. "
                "Make sure both client and server use the same build."
            )

        if isinstance(error, ConnectionError):
            return "Connection was closed during handshake."

        return f"Connection failed: {error}"
