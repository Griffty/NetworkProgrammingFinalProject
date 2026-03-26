from dataclasses import dataclass

from network.packets import Packet, PacketId


@dataclass(slots=True)
class GameOverPacket(Packet):
    winner_player_id: str
    is_draw: bool

    @classmethod
    def version(cls) -> int:
        return 1

    @classmethod
    def packet_id(cls) -> PacketId:
        return PacketId("GAME_OVER")

    def to_payload(self) -> dict:
        return {"winner_player_id": self.winner_player_id, "is_draw": self.is_draw}

    @classmethod
    def from_payload(cls, payload: dict) -> "GameOverPacket":
        return cls(
            winner_player_id=str(payload["winner_player_id"]),
            is_draw=bool(payload["is_draw"]),
        )
