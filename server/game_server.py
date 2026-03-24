import socket
import threading

from network import register_packets
from network.hello_packet import HelloPacket
from network.packets import PacketCodec
from network.welcome_packet import WelcomePacket
from shared.settings import DEFAULT_HOST, DEFAULT_PORT, SOCKET_TIMEOUT_SECONDS


class GameServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        register_packets()
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._running = threading.Event()
        self._connected_players: set[str] = set()
        self._state_lock = threading.Lock()

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
        player_name: str | None = None

        with client_socket:
            client_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
            try:
                packet = PacketCodec.recv(client_socket)
                if not isinstance(packet, HelloPacket):
                    raise ValueError(
                        f"Expected hello packet, received {packet.packet_id()!r}."
                    )

                player_name = packet.player_name
                with self._state_lock:
                    self._connected_players.add(player_name)
                    player_count = len(self._connected_players)

                print(
                    f"Client connected from {client_address[0]}:{client_address[1]} "
                    f"as {player_name}"
                )

                PacketCodec.send(
                    client_socket,
                    WelcomePacket(
                        message=(
                            f"Welcome {player_name}. Connected players: {player_count}"
                        )
                    ),
                )
            except (ConnectionError, OSError, TimeoutError, ValueError) as error:
                print(
                    f"Connection error from {client_address[0]}:{client_address[1]}: "
                    f"{error}"
                )
            finally:
                if player_name is not None:
                    with self._state_lock:
                        self._connected_players.discard(player_name)
