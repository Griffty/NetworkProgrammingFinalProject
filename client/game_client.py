import socket

from network import register_packets
from network.hello_packet import HelloPacket
from network.packets import PacketCodec
from network.welcome_packet import WelcomePacket
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

    def connect(self) -> str:
        with socket.create_connection(
            (self.host, self.port), timeout=SOCKET_TIMEOUT_SECONDS
        ) as client_socket:
            client_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
            PacketCodec.send(client_socket, HelloPacket(player_name=self.player_name))
            response = PacketCodec.recv(client_socket)

        if not isinstance(response, WelcomePacket):
            raise ValueError(
                f"Expected welcome packet, received {response.packet_id()!r} instead."
            )

        print(f"Server response: {response.message}")
        return response.message
