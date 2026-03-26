import queue
import socket
import threading
import time

from game.systems import MatchEngine
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
from shared.models.game_rules import (
    EnemyKind,
    MatchPhase,
    OffensiveModifier,
    TowerKind,
)
from shared.serialization import serialize_match_state
from shared.settings import DEFAULT_HOST, DEFAULT_PORT


class GameServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        register_packets()
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._running = threading.Event()
        self._state_lock = threading.Lock()

        self._player_sockets: dict[str, socket.socket] = {}
        self._socket_write_locks: dict[str, threading.Lock] = {}
        self._player_names: dict[str, str] = {}
        self._engine: MatchEngine | None = None
        self._command_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._game_thread: threading.Thread | None = None
        self._match_started = threading.Event()

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            self._socket = server_socket
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            server_socket.settimeout(0.5)
            self._running.set()

            print(f"Server listening on {self.host}:{self.port}")

            try:
                while self._running.is_set():
                    try:
                        client_socket, client_address = server_socket.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        if self._running.is_set():
                            raise
                        break

                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True,
                    )
                    thread.start()
            finally:
                self._running.clear()
                self._socket = None
                print("Server stopped.")

    def stop(self) -> None:
        self._running.clear()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass

    def _handle_client(
        self, client_socket: socket.socket, client_address: tuple[str, int]
    ) -> None:
        player_id: str | None = None

        with client_socket:
            client_socket.settimeout(10.0)
            try:
                packet = PacketCodec.recv(client_socket)
                if not isinstance(packet, HelloPacket):
                    raise ValueError(
                        f"Expected hello packet, received {packet.packet_id()!r}."
                    )

                player_name = packet.player_name

                with self._state_lock:
                    if len(self._player_sockets) >= 2:
                        PacketCodec.send(
                            client_socket,
                            WelcomePacket(message="Server is full. Try again later."),
                        )
                        return

                    player_id = (
                        "player_1" if "player_1" not in self._player_sockets else "player_2"
                    )
                    self._player_sockets[player_id] = client_socket
                    self._socket_write_locks[player_id] = threading.Lock()
                    self._player_names[player_id] = player_name

                    player_count = len(self._player_sockets)

                print(
                    f"Client connected from {client_address[0]}:{client_address[1]} "
                    f"as {player_name} ({player_id})"
                )

                if player_count < 2:
                    self._send_to_player(
                        player_id,
                        WelcomePacket(message=f"Welcome {player_name}. Waiting for opponent..."),
                    )
                    self._match_started.wait()
                else:
                    self._send_to_player(
                        player_id,
                        WelcomePacket(message=f"Welcome {player_name}. Match starting!"),
                    )
                    self._start_match()

                client_socket.settimeout(None)
                self._receive_loop(player_id, client_socket)

            except (ConnectionError, OSError, TimeoutError, ValueError) as error:
                print(f"Connection error for {player_id or client_address}: {error}")
            finally:
                if player_id is not None:
                    self._handle_disconnect(player_id)

    def _start_match(self) -> None:
        with self._state_lock:
            names = [
                self._player_names.get("player_1", "Player1"),
                self._player_names.get("player_2", "Player2"),
            ]
            self._engine = MatchEngine(player_names=names)

        for pid in ("player_1", "player_2"):
            opponent_id = "player_2" if pid == "player_1" else "player_1"
            opponent_name = self._player_names.get(opponent_id, "Unknown")
            self._send_to_player(
                pid,
                GameStartPacket(your_player_id=pid, opponent_name=opponent_name),
            )

        self._match_started.set()

        self._game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self._game_thread.start()
        print("Match started!")

    def _game_loop(self) -> None:
        engine = self._engine
        if engine is None:
            return

        tick_interval = 1.0 / engine.state.tick_rate_hz

        while self._running.is_set() and engine.state.phase != MatchPhase.FINISHED:
            start = time.monotonic()

            while not self._command_queue.empty():
                try:
                    player_id, packet = self._command_queue.get_nowait()
                except queue.Empty:
                    break
                self._apply_command(player_id, packet)

            with self._state_lock:
                engine.tick(1)
                state_data = serialize_match_state(engine.state)

            self._broadcast(GameStatePacket(state=state_data))

            elapsed = time.monotonic() - start
            sleep_time = tick_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        if engine.state.phase == MatchPhase.FINISHED:
            with self._state_lock:
                state_data = serialize_match_state(engine.state)
            self._broadcast(GameStatePacket(state=state_data))
            self._broadcast(
                GameOverPacket(
                    winner_player_id=engine.state.winner_player_id or "",
                    is_draw=engine.state.is_draw,
                )
            )
            print("Match finished.")

    def _apply_command(self, player_id: str, packet: object) -> None:
        engine = self._engine
        if engine is None:
            return

        try:
            with self._state_lock:
                if isinstance(packet, PlaceTowerPacket):
                    engine.place_tower(
                        player_id,
                        TowerKind(packet.tower_type),
                        packet.tile_x,
                        packet.tile_y,
                    )
                elif isinstance(packet, UpgradeTowerPacket):
                    engine.upgrade_tower(player_id, packet.tower_id)
                elif isinstance(packet, SellTowerPacket):
                    engine.sell_tower(player_id, packet.tower_id)
                elif isinstance(packet, ConfigurePressurePacket):
                    unit_counts = {
                        EnemyKind(k): v for k, v in packet.unit_counts.items()
                    }
                    modifiers = {OffensiveModifier(m) for m in packet.modifiers}
                    engine.configure_pressure(player_id, unit_counts, modifiers)
                elif isinstance(packet, SkipBuildPacket):
                    player = engine.state.players.get(player_id)
                    if player is not None:
                        player.ready_for_next_wave = True
                        all_ready = all(
                            p.ready_for_next_wave
                            for p in engine.state.players.values()
                        )
                        if all_ready and engine.state.phase == MatchPhase.BUILD:
                            engine.advance(engine.state.phase_time_remaining_seconds)
        except ValueError as error:
            self._send_to_player(player_id, ErrorPacket(message=str(error)))

    def _receive_loop(self, player_id: str, client_socket: socket.socket) -> None:
        while self._running.is_set():
            try:
                packet = PacketCodec.recv(client_socket)
                self._command_queue.put((player_id, packet))
            except (ConnectionError, OSError):
                break
            except Exception as error:
                print(f"Error receiving from {player_id}: {error}")
                break

    def _send_to_player(self, player_id: str, packet: object) -> None:
        sock = self._player_sockets.get(player_id)
        lock = self._socket_write_locks.get(player_id)
        if sock is None or lock is None:
            return
        try:
            with lock:
                PacketCodec.send(sock, packet)
        except (ConnectionError, OSError):
            pass

    def _broadcast(self, packet: object) -> None:
        for player_id in list(self._player_sockets.keys()):
            self._send_to_player(player_id, packet)

    def _handle_disconnect(self, player_id: str) -> None:
        print(f"{self._player_names.get(player_id, player_id)} disconnected.")
        with self._state_lock:
            self._player_sockets.pop(player_id, None)
            self._socket_write_locks.pop(player_id, None)
            self._player_names.pop(player_id, None)

            if self._engine is not None and self._engine.state.phase != MatchPhase.FINISHED:
                remaining = [
                    pid for pid in self._engine.state.players
                    if pid in self._player_sockets
                ]
                self._engine.state.phase = MatchPhase.FINISHED
                if len(remaining) == 1:
                    self._engine.state.winner_player_id = remaining[0]
                    self._engine.state.record_event(
                        f"{self._engine.state.players[remaining[0]].name} wins by disconnect."
                    )
                else:
                    self._engine.state.is_draw = True
                    self._engine.state.record_event("Match ended due to disconnection.")
