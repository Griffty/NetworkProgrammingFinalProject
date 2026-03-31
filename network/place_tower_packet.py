from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class PlaceTowerPacket(Packet):
    tower_type: str
    tile_x: int
    tile_y: int

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("PLACE_TOWER")

    def to_payload(self) -> dict:
        return {
            "tower_type": self.tower_type,
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "PlaceTowerPacket":
        return cls(
            tower_type=str(payload["tower_type"]),
            tile_x=int(payload["tile_x"]),
            tile_y=int(payload["tile_y"]),
        )
