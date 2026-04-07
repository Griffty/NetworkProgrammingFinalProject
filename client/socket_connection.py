"""Thin socket wrapper used by the client network layer."""

from __future__ import annotations

import socket
import threading

from network.packets import PacketCodec


class SocketConnection:
    """Owns a TCP socket and serializes packet reads/writes."""

    def __init__(self, host: str, port: int, timeout_seconds: float) -> None:
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self._socket: socket.socket | None = None
        self._write_lock = threading.Lock()

    def open(self) -> None:
        """Open a fresh socket connection to the configured host."""

        self.close()
        self._socket = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout_seconds,
        )
        self._socket.settimeout(self.timeout_seconds)

    def set_timeout(self, timeout_seconds: float | None) -> None:
        """Update the socket timeout if the connection is open."""

        if self._socket is not None:
            self._socket.settimeout(timeout_seconds)

    def send(self, packet: object) -> None:
        """Send a packet using the shared packet codec."""

        if self._socket is None:
            raise ConnectionError("Socket is not connected.")

        with self._write_lock:
            PacketCodec.send(self._socket, packet)

    def receive(self) -> object:
        """Block until the next packet is received."""

        if self._socket is None:
            raise ConnectionError("Socket is not connected.")
        return PacketCodec.recv(self._socket)

    def close(self) -> None:
        """Close the socket if it is currently open."""

        if self._socket is None:
            return
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._socket.close()
        except OSError:
            pass
        finally:
            self._socket = None

    @property
    def is_open(self) -> bool:
        """Return whether a socket is currently attached."""

        return self._socket is not None
