from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class GameStartPacket(Packet):
    your_player_id: str
    opponent_name: str

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("GAME_START")

    def to_payload(self) -> dict:
        return {"your_player_id": self.your_player_id, "opponent_name": self.opponent_name}

    @classmethod
    def from_payload(cls, payload: dict) -> "GameStartPacket":
        return cls(
            your_player_id=str(payload["your_player_id"]),
            opponent_name=str(payload["opponent_name"]),
        )
