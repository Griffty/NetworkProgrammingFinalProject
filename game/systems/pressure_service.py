"""Validation and bookkeeping for outgoing pressure plans."""

from game.match_state import MatchState
from shared.models.game_rules import EnemyKind, OffensiveModifier
from shared.models.state import OutgoingPressureState, PlayerState, zero_enemy_counts


class PressureService:
    """Apply player-selected pressure unit counts and modifiers."""

    def configure_pressure(
        self,
        state: MatchState,
        player_id: str,
        unit_counts: dict[EnemyKind, int],
        modifiers: set[OffensiveModifier] | None = None,
    ) -> OutgoingPressureState:
        """Validate and store a player's next outgoing pressure plan."""

        player = self._require_player(state, player_id)
        modifiers = set(modifiers or set())
        wave_number = state.current_wave_number + 1

        normalized_counts = zero_enemy_counts()
        for enemy_kind, count in unit_counts.items():
            normalized_counts[enemy_kind] = count

        if any(count < 0 for count in normalized_counts.values()):
            raise ValueError("Pressure unit counts cannot be negative.")

        previous_plan = player.outgoing_pressure.copy()
        player.gold += previous_plan.gold_cost()

        new_plan = OutgoingPressureState(
            unit_counts=normalized_counts,
            modifiers=modifiers,
        )

        available_points = new_plan.available_points(wave_number)
        if new_plan.spent_points() > available_points:
            player.outgoing_pressure = previous_plan
            player.gold -= previous_plan.gold_cost()
            raise ValueError("Pressure plan exceeds the available modifier points.")

        gold_cost = new_plan.gold_cost()
        if player.gold < gold_cost:
            player.outgoing_pressure = previous_plan
            player.gold -= previous_plan.gold_cost()
            raise ValueError("Not enough gold for the selected pressure modifiers.")

        player.gold -= gold_cost
        player.outgoing_pressure = new_plan
        state.record_event(
            f"{player.name} updated outgoing pressure for wave {wave_number}."
        )
        return new_plan

    @staticmethod
    def _require_player(state: MatchState, player_id: str) -> PlayerState:
        if player_id not in state.players:
            raise ValueError(f"Unknown player id: {player_id}")
        return state.players[player_id]
