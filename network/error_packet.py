from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class ErrorPacket(Packet):
    message: str

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("ERROR")

    def to_payload(self) -> dict:
        return {"message": self.message}

    @classmethod
    def from_payload(cls, payload: dict) -> "ErrorPacket":
        return cls(message=str(payload["message"]))
