from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class JoinRejectedPacket(Packet):
    reason: str

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("JOIN_REJECTED")

    def to_payload(self) -> dict[str, str]:
        return {"reason": self.reason}

    @classmethod
    def from_payload(cls, payload: dict[str, str]) -> "JoinRejectedPacket":
        return cls(reason=str(payload["reason"]))
