"""Phase transitions and end-of-wave/end-of-match rules."""

from collections.abc import Callable

from game.match_state import MatchState
from shared.models.game_rules import MatchPhase, wave_clear_bonus_for_wave


class PhaseService:
    """Own phase timing and match resolution logic."""

    def __init__(self, build_phase_seconds: float) -> None:
        self._build_phase_seconds = build_phase_seconds

    def begin_build_phase(self, state: MatchState) -> None:
        """Enter the build phase and reset ready flags."""

        state.phase = MatchPhase.BUILD
        state.phase_time_remaining_seconds = self._build_phase_seconds
        for player in state.players.values():
            player.ready_for_next_wave = False
        state.record_event("Build phase started.")

    def update_build_phase(
        self,
        state: MatchState,
        delta_seconds: float,
        start_next_wave: Callable[[], None],
    ) -> None:
        """Advance build timer and start the next wave when it expires."""

        state.phase_time_remaining_seconds = max(
            0.0,
            state.phase_time_remaining_seconds - delta_seconds,
        )
        if state.phase_time_remaining_seconds == 0.0:
            start_next_wave()

    def finish_current_wave(self, state: MatchState) -> None:
        """Award wave-clear bonuses and return the match to build phase."""

        wave_number = state.current_wave_number
        bonus_gold = wave_clear_bonus_for_wave(wave_number)

        for player in state.alive_players():
            player.gold += bonus_gold
            player.completed_waves = wave_number

        state.record_event(
            f"Wave {wave_number} cleared. Each surviving player earned {bonus_gold} gold."
        )
        self.begin_build_phase(state)

    def update_win_state(self, state: MatchState) -> None:
        """Check whether the match has reached a win or draw condition."""

        alive_players = state.alive_players()
        if len(alive_players) == 2:
            return

        if len(alive_players) == 1:
            winner = alive_players[0]
            self.finish_match(
                state,
                winner_player_id=winner.player_id,
                is_draw=False,
                event_message=f"{winner.name} won the match.",
            )
            return

        self.finish_match(
            state,
            winner_player_id=None,
            is_draw=True,
            event_message="The match ended in a draw.",
        )

    def finish_match(
        self,
        state: MatchState,
        winner_player_id: str | None,
        is_draw: bool,
        event_message: str,
    ) -> None:
        """Mark the match finished and clear remaining wave activity."""

        state.phase = MatchPhase.FINISHED
        state.phase_time_remaining_seconds = 0.0
        state.winner_player_id = winner_player_id
        state.is_draw = is_draw
        for player in state.players.values():
            player.current_wave.active_enemies.clear()
            player.current_wave.queued_enemies.clear()
        state.record_event(event_message)
