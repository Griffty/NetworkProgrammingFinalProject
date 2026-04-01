from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class UpgradeTowerPacket(Packet):
    tower_id: int

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("UPGRADE_TOWER")

    def to_payload(self) -> dict:
        return {"tower_id": self.tower_id}

    @classmethod
    def from_payload(cls, payload: dict) -> "UpgradeTowerPacket":
        return cls(tower_id=int(payload["tower_id"]))
