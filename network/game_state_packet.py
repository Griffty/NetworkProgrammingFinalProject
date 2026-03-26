from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class GameStatePacket(Packet):
    state: dict

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("GAME_STATE")

    def to_payload(self) -> dict:
        return {"state": self.state}

    @classmethod
    def from_payload(cls, payload: dict) -> "GameStatePacket":
        return cls(state=payload["state"])
