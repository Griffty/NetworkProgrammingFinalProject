import json
import socket
import struct
from abc import ABC, abstractmethod
from typing import Any, NewType

PacketId = NewType("PacketId", str)


class Packet(ABC):
    @classmethod
    @abstractmethod
    def version(cls) -> int:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def packet_id(cls) -> PacketId:
        raise NotImplementedError

    @abstractmethod
    def to_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Packet":
        raise NotImplementedError

    @classmethod
    def register(cls) -> None:
        PacketRegistry.register(cls)


class PacketRegistry:
    _by_id: dict[PacketId, type[Packet]] = {}

    @classmethod
    def register(cls, packet_cls: type[Packet]) -> None:
        packet_id = packet_cls.packet_id()
        if packet_id in cls._by_id:
            raise ValueError(f"Duplicate packet id: {packet_id}")
        cls._by_id[packet_id] = packet_cls

    @classmethod
    def get(cls, packet_id: PacketId) -> type[Packet]:
        if packet_id not in cls._by_id:
            raise KeyError(f"Unknown packet id: {packet_id}")
        return cls._by_id[packet_id]

    @classmethod
    def is_registered(cls, packet_id: PacketId) -> bool:
        return packet_id in cls._by_id


class PacketCodec:
    _HEADER_SIZE = 4

    @classmethod
    def send(cls, sock: socket.socket, packet: Packet) -> None:
        sock.sendall(cls._encode(packet))

    @classmethod
    def recv(cls, sock: socket.socket) -> Packet:
        header = cls._read_exact(sock, cls._HEADER_SIZE)
        payload_size = struct.unpack("!I", header)[0]
        body = cls._read_exact(sock, payload_size)

        envelope = json.loads(body.decode("utf-8"))
        packet_cls = PacketRegistry.get(PacketId(envelope["packet_id"]))

        if envelope["version"] != packet_cls.version():
            raise ValueError(
                f"Packet version mismatch for {envelope['packet_id']}: "
                f"{envelope['version']} != {packet_cls.version()}"
            )

        return packet_cls.from_payload(envelope["payload"])

    @classmethod
    def _encode(cls, packet: Packet) -> bytes:
        envelope = {
            "packet_id": packet.packet_id(),
            "version": packet.version(),
            "payload": packet.to_payload(),
        }
        body = json.dumps(envelope).encode("utf-8")
        return struct.pack("!I", len(body)) + body

    @staticmethod
    def _read_exact(sock: socket.socket, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size

        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                raise ConnectionError("Socket closed while reading packet data.")
            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)