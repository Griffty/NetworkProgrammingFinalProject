from dataclasses import dataclass, field

from network.packets import Packet, PacketId


@dataclass(slots=True)
class ConfigurePressurePacket(Packet):
    unit_counts: dict[str, int]
    modifiers: list[str]

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("CONFIGURE_PRESSURE")

    def to_payload(self) -> dict:
        return {"unit_counts": self.unit_counts, "modifiers": self.modifiers}

    @classmethod
    def from_payload(cls, payload: dict) -> "ConfigurePressurePacket":
        return cls(
            unit_counts={str(k): int(v) for k, v in payload["unit_counts"].items()},
            modifiers=[str(m) for m in payload["modifiers"]],
        )
