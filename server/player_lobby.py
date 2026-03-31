from __future__ import annotations

import socket
import threading
from dataclasses import dataclass, field

from network.packets import PacketCodec


@dataclass(slots=True)
class PlayerConnection:
    player_id: str
    player_name: str
    socket: socket.socket
    write_lock: threading.Lock = field(default_factory=threading.Lock)


class PlayerLobby:
    def __init__(self, max_players: int = 2) -> None:
        self.max_players = max_players
        self._connections: dict[str, PlayerConnection] = {}
        self._lock = threading.Lock()

    def add_player(
        self,
        client_socket: socket.socket,
        player_name: str,
    ) -> PlayerConnection | None:
        with self._lock:
            if len(self._connections) >= self.max_players:
                return None

            player_id = "player_1" if "player_1" not in self._connections else "player_2"
            connection = PlayerConnection(
                player_id=player_id,
                player_name=player_name,
                socket=client_socket,
            )
            self._connections[player_id] = connection
            return connection

    def remove_player(self, player_id: str) -> list[str]:
        with self._lock:
            self._connections.pop(player_id, None)
            return self._ordered_player_ids_locked()

    def player_count(self) -> int:
        with self._lock:
            return len(self._connections)

    def player_ids(self) -> list[str]:
        with self._lock:
            return self._ordered_player_ids_locked()

    def player_names_for_match(self) -> list[str]:
        with self._lock:
            return [
                self._connections[player_id].player_name
                for player_id in self._ordered_player_ids_locked()
            ]

    def opponent_name_for(self, player_id: str) -> str:
        with self._lock:
            for candidate_id in self._ordered_player_ids_locked():
                if candidate_id != player_id:
                    return self._connections[candidate_id].player_name
        return "Unknown"

    def display_name(self, player_id: str) -> str:
        with self._lock:
            connection = self._connections.get(player_id)
            return connection.player_name if connection is not None else player_id

    def send_to_player(self, player_id: str, packet: object) -> None:
        connection = self._get_connection(player_id)
        if connection is None:
            return

        try:
            with connection.write_lock:
                PacketCodec.send(connection.socket, packet)
        except (ConnectionError, OSError):
            pass

    def broadcast(self, packet: object) -> None:
        for player_id in self.player_ids():
            self.send_to_player(player_id, packet)

    def _get_connection(self, player_id: str) -> PlayerConnection | None:
        with self._lock:
            return self._connections.get(player_id)

    def _ordered_player_ids_locked(self) -> list[str]:
        return [
            player_id
            for player_id in ("player_1", "player_2")
            if player_id in self._connections
        ]
