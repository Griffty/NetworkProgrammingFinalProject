from dataclasses import dataclass, field

from shared.models.game_rules import GAME_RULES, MatchPhase
from shared.models.state import PlayerState


@dataclass(slots=True)
class MatchState:
    match_id: str = "local-match"
    phase: MatchPhase = MatchPhase.WAITING_FOR_PLAYERS
    current_wave_number: int = 0
    tick_rate_hz: int = GAME_RULES.tick_rate_hz
    tick_count: int = 0
    elapsed_seconds: float = 0.0
    phase_time_remaining_seconds: float = 0.0
    players: dict[str, PlayerState] = field(default_factory=dict)
    winner_player_id: str | None = None
    is_draw: bool = False
    recent_events: list[str] = field(default_factory=list)

    def add_player(self, player: PlayerState) -> None:
        if player.player_id in self.players:
            raise ValueError(f"Duplicate player id: {player.player_id}")
        self.players[player.player_id] = player

    def remove_player(self, player_id: str) -> None:
        if player_id in self.players:
            del self.players[player_id]

    def can_start(self) -> bool:
        return len(self.players) == GAME_RULES.max_players

    def alive_players(self) -> list[PlayerState]:
        return [player for player in self.players.values() if player.is_alive]

    def opponent_id_for(self, player_id: str) -> str | None:
        for candidate_id in self.players:
            if candidate_id != player_id:
                return candidate_id
        return None

    def record_event(self, message: str) -> None:
        timestamp = f"[{self.elapsed_seconds:06.1f}s] "
        self.recent_events.append(timestamp + message)
        if len(self.recent_events) > 100:
            self.recent_events = self.recent_events[-100:]
