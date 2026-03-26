import socket
import threading

from game.match_state import MatchState
from network import register_packets
from network.PlaceTowerPacket import PlaceTowerPacket
from network.configure_pressure_packet import ConfigurePressurePacket
from network.error_packet import ErrorPacket
from network.game_over_packet import GameOverPacket
from network.game_start_packet import GameStartPacket
from network.game_state_packet import GameStatePacket
from network.hello_packet import HelloPacket
from network.packets import PacketCodec
from network.sell_tower_packet import SellTowerPacket
from network.skip_build_packet import SkipBuildPacket
from network.upgrade_tower_packet import UpgradeTowerPacket
from network.welcome_packet import WelcomePacket
from shared.models.game_rules import EnemyKind, OffensiveModifier, TowerKind
from shared.serialization import deserialize_match_state
from shared.settings import DEFAULT_HOST, DEFAULT_PORT, SOCKET_TIMEOUT_SECONDS


class GameClient:
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

        self._socket: socket.socket | None = None
        self._recv_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()

        self.my_player_id: str | None = None
        self.opponent_name: str | None = None
        self.latest_state: MatchState | None = None
        self.error_messages: list[str] = []
        self.game_over: bool = False
        self.game_over_winner: str | None = None
        self.game_over_is_draw: bool = False
        self.connected: bool = False
        self.welcome_message: str = ""

    def connect(self) -> bool:
        try:
            self._socket = socket.create_connection(
                (self.host, self.port), timeout=SOCKET_TIMEOUT_SECONDS
            )
            self._socket.settimeout(SOCKET_TIMEOUT_SECONDS)

            PacketCodec.send(self._socket, HelloPacket(player_name=self.player_name))

            response = PacketCodec.recv(self._socket)
            if not isinstance(response, WelcomePacket):
                raise ValueError(
                    f"Expected welcome packet, received {response.packet_id()!r}."
                )

            self.welcome_message = response.message
            self.connected = True
            print(f"Server: {response.message}")

            if "full" in response.message.lower():
                self.disconnect()
                return False

            self._socket.settimeout(None)

            self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._recv_thread.start()
            return True

        except (ConnectionError, OSError, TimeoutError, ValueError) as error:
            print(f"Failed to connect: {error}")
            self.disconnect()
            return False

    def disconnect(self) -> None:
        self.connected = False
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    def send_place_tower(self, tower_type: TowerKind, tile_x: int, tile_y: int) -> None:
        self._send(PlaceTowerPacket(tower_type=tower_type.value, tile_x=tile_x, tile_y=tile_y))

    def send_upgrade_tower(self, tower_id: int) -> None:
        self._send(UpgradeTowerPacket(tower_id=tower_id))

    def send_sell_tower(self, tower_id: int) -> None:
        self._send(SellTowerPacket(tower_id=tower_id))

    def send_configure_pressure(
        self,
        unit_counts: dict[EnemyKind, int],
        modifiers: set[OffensiveModifier] | None = None,
    ) -> None:
        counts = {k.value: v for k, v in unit_counts.items()}
        mods = [m.value for m in (modifiers or set())]
        self._send(ConfigurePressurePacket(unit_counts=counts, modifiers=mods))

    def send_skip_build(self) -> None:
        self._send(SkipBuildPacket())

    def pop_errors(self) -> list[str]:
        with self._lock:
            errors = list(self.error_messages)
            self.error_messages.clear()
            return errors

    def _send(self, packet: object) -> None:
        if self._socket is None:
            return
        try:
            with self._write_lock:
                PacketCodec.send(self._socket, packet)
        except (ConnectionError, OSError):
            self.connected = False

    def _receive_loop(self) -> None:
        while self.connected and self._socket is not None:
            try:
                packet = PacketCodec.recv(self._socket)

                if isinstance(packet, GameStartPacket):
                    self.my_player_id = packet.your_player_id
                    self.opponent_name = packet.opponent_name
                    print(f"Match started! You are {packet.your_player_id}, opponent: {packet.opponent_name}")

                elif isinstance(packet, GameStatePacket):
                    state = deserialize_match_state(packet.state)
                    with self._lock:
                        self.latest_state = state

                elif isinstance(packet, GameOverPacket):
                    self.game_over = True
                    self.game_over_winner = packet.winner_player_id or None
                    self.game_over_is_draw = packet.is_draw
                    print(f"Game over! Winner: {packet.winner_player_id}, Draw: {packet.is_draw}")

                elif isinstance(packet, ErrorPacket):
                    with self._lock:
                        self.error_messages.append(packet.message)
                        if len(self.error_messages) > 10:
                            self.error_messages = self.error_messages[-10:]

                elif isinstance(packet, WelcomePacket):
                    self.welcome_message = packet.message

            except (ConnectionError, OSError):
                break
            except Exception as error:
                print(f"Error in receive loop: {error}")
                break

        self.connected = False
