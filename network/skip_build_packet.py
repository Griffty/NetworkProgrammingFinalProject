"""Client command packet used to mark build phase as ready."""

from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class SkipBuildPacket(Packet):
    """Request to finish the local build phase early."""

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("SKIP_BUILD")

    def to_payload(self) -> dict:
        return {}

    @classmethod
    def from_payload(cls, payload: dict) -> "SkipBuildPacket":
        return cls()
