from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class HelloPacket(Packet):
    player_name: str

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("HELLO")

    def to_payload(self) -> dict[str, str]:
        return {"player_name": self.player_name}

    @classmethod
    def from_payload(cls, payload: dict[str, str]) -> "HelloPacket":
        return cls(player_name=str(payload["player_name"]))
