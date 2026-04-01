import math
from itertools import count
from typing import Sequence

from game.commands import (
    ConfigurePressureCommand,
    GameCommand,
    PlaceTowerCommand,
    SellTowerCommand,
    SkipBuildCommand,
    UpgradeTowerCommand,
)
from game.match_state import MatchState
from game.systems.build_service import BuildService
from game.systems.combat_service import CombatService
from game.systems.phase_service import PhaseService
from game.systems.pressure_service import PressureService
from game.systems.wave_service import WaveService
from shared.models.game_rules import (
    GAME_RULES,
    EnemyKind,
    MatchPhase,
    OffensiveModifier,
    TowerKind,
)
from shared.models.state import OutgoingPressureState, PlayerState, TowerState


class MatchEngine:
    def __init__(
        self,
        player_names: Sequence[str] | None = None,
        tick_rate_hz: int | None = None,
    ) -> None:
        self.rules = GAME_RULES
        self.state = MatchState(
            tick_rate_hz=tick_rate_hz or self.rules.tick_rate_hz,
        )
        self._tower_ids = count(1)
        self._enemy_ids = count(1)
        self._build_service = BuildService(
            starting_gold=self.rules.starting_gold,
            starting_lives=self.rules.starting_lives,
            sell_refund_ratio=self.rules.sell_refund_ratio,
            next_tower_id=lambda: next(self._tower_ids),
        )
        self._combat_service = CombatService()
        self._phase_service = PhaseService(
            build_phase_seconds=self.rules.build_phase_seconds,
        )
        self._pressure_service = PressureService()
        self._wave_service = WaveService(
            enemy_hp_growth_per_wave=self.rules.enemy_hp_growth_per_wave,
            next_enemy_id=lambda: next(self._enemy_ids),
            combat_service=self._combat_service,
            phase_service=self._phase_service,
        )

        for index, player_name in enumerate(player_names or (), start=1):
            self.add_player(player_id=f"player_{index}", player_name=player_name)

    def add_player(self, player_id: str, player_name: str) -> PlayerState:
        player = self._build_service.add_player(self.state, player_id, player_name)

        if self.state.phase == MatchPhase.WAITING_FOR_PLAYERS and self.state.can_start():
            self._phase_service.begin_build_phase(self.state)

        return player

    def place_tower(
        self, player_id: str, tower_type: TowerKind, tile_x: int, tile_y: int
    ) -> TowerState:
        self._require_phase(MatchPhase.BUILD)
        return self._build_service.place_tower(
            self.state,
            player_id,
            tower_type,
            tile_x,
            tile_y,
        )

    def upgrade_tower(self, player_id: str, tower_id: int) -> TowerState:
        self._require_phase(MatchPhase.BUILD)
        return self._build_service.upgrade_tower(
            self.state,
            player_id,
            tower_id,
        )

    def sell_tower(self, player_id: str, tower_id: int) -> int:
        self._require_phase(MatchPhase.BUILD)
        return self._build_service.sell_tower(self.state, player_id, tower_id)

    def configure_pressure(
        self,
        player_id: str,
        unit_counts: dict[EnemyKind, int],
        modifiers: set[OffensiveModifier] | None = None,
    ) -> OutgoingPressureState:
        self._require_phase(MatchPhase.BUILD)
        return self._pressure_service.configure_pressure(
            self.state,
            player_id,
            unit_counts,
            modifiers,
        )

    def apply_command(self, player_id: str, command: GameCommand) -> None:
        if isinstance(command, PlaceTowerCommand):
            self.place_tower(
                player_id,
                command.tower_type,
                command.tile_x,
                command.tile_y,
            )
            return

        if isinstance(command, UpgradeTowerCommand):
            self.upgrade_tower(player_id, command.tower_id)
            return

        if isinstance(command, SellTowerCommand):
            self.sell_tower(player_id, command.tower_id)
            return

        if isinstance(command, ConfigurePressureCommand):
            self.configure_pressure(player_id, command.unit_counts, command.modifiers)
            return

        if isinstance(command, SkipBuildCommand):
            self.skip_build(player_id)
            return

        raise ValueError(f"Unsupported command: {type(command).__name__}")

    def skip_build(self, player_id: str) -> None:
        player = self.state.players.get(player_id)
        if player is None:
            raise ValueError(f"Unknown player id: {player_id}")

        if self.state.phase != MatchPhase.BUILD:
            raise ValueError(
                f"Action is only allowed during {MatchPhase.BUILD.value}, "
                f"but match is in {self.state.phase.value}."
            )

        player.ready_for_next_wave = True
        all_ready = all(
            candidate.ready_for_next_wave for candidate in self.state.players.values()
        )
        if all_ready:
            self.advance(self.state.phase_time_remaining_seconds)

    def finish_due_to_disconnect(self, connected_player_ids: list[str]) -> None:
        if self.state.phase == MatchPhase.FINISHED:
            return

        if len(connected_player_ids) == 1:
            winner_player_id = connected_player_ids[0]
            if winner_player_id not in self.state.players:
                self._phase_service.finish_match(
                    self.state,
                    winner_player_id=None,
                    is_draw=True,
                    event_message="Match ended due to disconnection.",
                )
                return

            winner_name = self.state.players[winner_player_id].name
            self._phase_service.finish_match(
                self.state,
                winner_player_id=winner_player_id,
                is_draw=False,
                event_message=f"{winner_name} wins by disconnect.",
            )
            return

        self._phase_service.finish_match(
            self.state,
            winner_player_id=None,
            is_draw=True,
            event_message="Match ended due to disconnection.",
        )

    def tick(self, steps: int = 1) -> MatchState:
        if steps < 1:
            raise ValueError("Tick steps must be at least 1.")

        tick_duration = 1.0 / self.state.tick_rate_hz
        for _ in range(steps):
            if self.state.phase == MatchPhase.FINISHED:
                break

            self.state.tick_count += 1
            self.state.elapsed_seconds += tick_duration

            if self.state.phase == MatchPhase.WAITING_FOR_PLAYERS:
                if self.state.can_start():
                    self._phase_service.begin_build_phase(self.state)
                continue

            if self.state.phase == MatchPhase.BUILD:
                self._phase_service.update_build_phase(
                    self.state,
                    tick_duration,
                    self._start_next_wave,
                )
            elif self.state.phase == MatchPhase.WAVE:
                self._wave_service.update_wave_phase(self.state, tick_duration)

            if self.state.phase != MatchPhase.FINISHED:
                self._phase_service.update_win_state(self.state)

        return self.state

    def advance(self, seconds: float) -> MatchState:
        if seconds < 0:
            raise ValueError("Advance duration cannot be negative.")

        steps = math.ceil(seconds * self.state.tick_rate_hz)
        if steps == 0:
            return self.state
        return self.tick(steps)

    def _start_next_wave(self) -> None:
        self._wave_service.start_next_wave(self.state)

    def _require_phase(self, expected_phase: MatchPhase) -> None:
        if self.state.phase != expected_phase:
            raise ValueError(
                f"Action is only allowed during {expected_phase.value}, "
                f"but match is in {self.state.phase.value}."
            )
