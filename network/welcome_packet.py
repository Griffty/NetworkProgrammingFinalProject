from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class WelcomePacket(Packet):
    message: str

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("WELCOME")

    def to_payload(self) -> dict[str, str]:
        return {"message": self.message}

    @classmethod
    def from_payload(cls, payload: dict[str, str]) -> "WelcomePacket":
        return cls(message=str(payload["message"]))
