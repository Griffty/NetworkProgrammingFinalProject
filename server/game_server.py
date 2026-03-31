from __future__ import annotations

import socket
import threading

from network.error_packet import ErrorPacket
from network.game_start_packet import GameStartPacket
from network.hello_packet import HelloPacket
from network.join_rejected_packet import JoinRejectedPacket
from network.register_packets import register_packets
from network.packets import PacketCodec
from network.join_accepted_packet import JoinAcceptedPacket
from shared.settings import DEFAULT_HOST, DEFAULT_PORT

from server.command_dispatcher import ServerCommandDispatcher
from server.match_runner import MatchRunner
from server.player_lobby import PlayerConnection, PlayerLobby


class GameServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        register_packets()
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._running = threading.Event()
        self._server_lock = threading.Lock()
        self._lobby = PlayerLobby()
        self._dispatcher = ServerCommandDispatcher()
        self._match_runner: MatchRunner | None = None

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
        self,
        client_socket: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        connection: PlayerConnection | None = None

        with client_socket:
            client_socket.settimeout(10.0)
            try:
                packet = PacketCodec.recv(client_socket)
                if not isinstance(packet, HelloPacket):
                    raise ValueError(
                        f"Expected hello packet, received {packet.packet_id()!r}."
                    )

                connection = self._register_player(client_socket, packet.player_name)
                if connection is None:
                    return

                print(
                    f"Client connected from {client_address[0]}:{client_address[1]} "
                    f"as {connection.player_name} ({connection.player_id})"
                )

                client_socket.settimeout(None)
                self._receive_loop(connection.player_id, client_socket)

            except (ConnectionError, OSError, TimeoutError, ValueError) as error:
                target = connection.player_id if connection is not None else client_address
                print(f"Connection error for {target}: {error}")
            finally:
                if connection is not None:
                    self._handle_disconnect(connection.player_id)

    def _register_player(
        self,
        client_socket: socket.socket,
        player_name: str,
    ) -> PlayerConnection | None:
        if self._has_started_match():
            PacketCodec.send(
                client_socket,
                JoinRejectedPacket(reason="Match already in progress. Try again later."),
            )
            return None

        connection = self._lobby.add_player(client_socket, player_name)
        if connection is None:
            PacketCodec.send(
                client_socket,
                JoinRejectedPacket(reason="Server is full. Try again later."),
            )
            return None

        if self._lobby.player_count() < 2:
            self._lobby.send_to_player(
                connection.player_id,
                JoinAcceptedPacket(message=f"Welcome {player_name}. Waiting for opponent..."),
            )
        else:
            self._lobby.send_to_player(
                connection.player_id,
                JoinAcceptedPacket(message=f"Welcome {player_name}. Match starting!"),
            )
            self._start_match()

        return connection

    def _start_match(self) -> None:
        with self._server_lock:
            if self._match_runner is not None:
                return

            self._match_runner = MatchRunner(
                player_names=self._lobby.player_names_for_match(),
                broadcaster=self._lobby.broadcast,
                send_error=self._send_error,
            )
            match_runner = self._match_runner

        for player_id in self._lobby.player_ids():
            self._lobby.send_to_player(
                player_id,
                GameStartPacket(
                    your_player_id=player_id,
                    opponent_name=self._lobby.opponent_name_for(player_id),
                ),
            )

        match_runner.start(self._running)
        print("Match started!")

    def _receive_loop(self, player_id: str, client_socket: socket.socket) -> None:
        while self._running.is_set():
            try:
                packet = PacketCodec.recv(client_socket)
                self._queue_command(player_id, packet)
            except (ConnectionError, OSError):
                break
            except Exception as error:
                print(f"Error receiving from {player_id}: {error}")
                break

    def _queue_command(self, player_id: str, packet: object) -> None:
        match_runner = self._match_runner
        if match_runner is None:
            self._send_error(player_id, "Match has not started yet.")
            return
        if match_runner.is_finished:
            self._send_error(player_id, "Match has already finished.")
            return

        try:
            command = self._dispatcher.parse_packet(packet)
        except ValueError as error:
            self._send_error(player_id, str(error))
            return

        match_runner.enqueue_command(player_id, command)

    def _send_error(self, player_id: str, message: str) -> None:
        self._lobby.send_to_player(player_id, ErrorPacket(message=message))

    def _handle_disconnect(self, player_id: str) -> None:
        print(f"{self._lobby.display_name(player_id)} disconnected.")
        remaining_player_ids = self._lobby.remove_player(player_id)

        match_runner = self._match_runner
        if match_runner is not None:
            match_runner.finish_due_to_disconnect(remaining_player_ids)

    def _has_started_match(self) -> bool:
        with self._server_lock:
            return self._match_runner is not None
