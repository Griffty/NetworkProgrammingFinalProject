from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class PlaceTowerPacket(Packet):
    x: int
    y: int
    tower_type: str

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("PLACE_TOWER")

    def to_payload(self) -> dict[str, int | str]:
        return {"x": self.x, "y": self.y, "tower_type": self.tower_type}

    @classmethod
    def from_payload(cls, payload: dict[str, int | str]) -> "PlaceTowerPacket":
        return cls(
            x=int(payload["x"]),
            y=int(payload["y"]),
            tower_type=str(payload["tower_type"]),
        )
