from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class DisconnectPacket(Packet):
    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("DISCONNECT")

    def to_payload(self) -> dict:
        return {}

    @classmethod
    def from_payload(cls, payload: dict) -> "DisconnectPacket":
        return cls()
