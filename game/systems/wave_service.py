from collections.abc import Callable

from game.match_state import MatchState
from game.systems.combat_service import CombatService
from game.systems.phase_service import PhaseService
from shared.models.board import BoardLayout
from shared.models.game_rules import (
    ENEMY_DEFINITIONS,
    MODIFIER_DEFINITIONS,
    EnemyKind,
    MatchPhase,
    modifier_points_for_wave,
)
from shared.models.state import EnemyState, OutgoingPressureState, PlayerState, WaveState
from shared.models.waves import WaveDefinition, build_base_wave_definition


class WaveService:
    def __init__(
        self,
        enemy_hp_growth_per_wave: float,
        next_enemy_id: Callable[[], int],
        combat_service: CombatService,
        phase_service: PhaseService,
    ) -> None:
        self._enemy_hp_growth_per_wave = enemy_hp_growth_per_wave
        self._next_enemy_id = next_enemy_id
        self._combat_service = combat_service
        self._phase_service = phase_service

    def start_next_wave(self, state: MatchState) -> None:
        state.current_wave_number += 1
        wave_number = state.current_wave_number
        base_wave_definition = build_base_wave_definition(wave_number)
        pressure_by_target: dict[str, tuple[str | None, OutgoingPressureState]] = {}

        for defending_player_id in state.players:
            attacker_id = state.opponent_id_for(defending_player_id)
            pressure_plan = (
                state.players[attacker_id].outgoing_pressure.copy()
                if attacker_id is not None
                else OutgoingPressureState()
            )
            pressure_by_target[defending_player_id] = (attacker_id, pressure_plan)

        for defending_player_id, player in state.players.items():
            attacker_id, pressure_plan = pressure_by_target[defending_player_id]
            player.current_wave = self._build_wave_for_player(
                state=state,
                player_id=defending_player_id,
                attacker_id=attacker_id,
                base_wave_definition=base_wave_definition,
                pressure_plan=pressure_plan,
            )

        for player in state.players.values():
            player.outgoing_pressure.reset()

        state.phase = MatchPhase.WAVE
        state.phase_time_remaining_seconds = 0.0
        state.record_event(
            f"Wave {wave_number} started with {base_wave_definition.point_budget} base points."
        )

    def update_wave_phase(self, state: MatchState, delta_seconds: float) -> None:
        for player in state.alive_players():
            wave = player.current_wave
            board_layout = player.board_layout
            self._spawn_queued_enemies(wave, delta_seconds)
            self._combat_service.update_tower_combat(player, wave, delta_seconds)

            leaked_enemies: list[EnemyState] = []
            for enemy in wave.active_enemies:
                enemy.advance(delta_seconds, board_layout)
                if enemy.distance_travelled_tiles >= board_layout.total_path_length_tiles:
                    leaked_enemies.append(enemy)

            for enemy in leaked_enemies:
                self._resolve_leak(state, player, enemy)
                wave.active_enemies.remove(enemy)

        alive_players = state.alive_players()
        if not alive_players:
            return

        if all(player.current_wave.is_cleared for player in alive_players):
            self._phase_service.finish_current_wave(state)

    def _build_wave_for_player(
        self,
        state: MatchState,
        player_id: str,
        attacker_id: str | None,
        base_wave_definition: WaveDefinition,
        pressure_plan: OutgoingPressureState,
    ) -> WaveState:
        wave_number = base_wave_definition.wave_number
        board_layout = state.players[player_id].board_layout
        wave = WaveState(
            wave_number=wave_number,
            base_points=base_wave_definition.point_budget,
            modifier_budget=modifier_points_for_wave(wave_number),
            spawn_interval_seconds=base_wave_definition.spawn_interval_seconds,
        )

        base_counts = base_wave_definition.counts_map()
        wave.base_unit_counts = base_counts.copy()
        for enemy_kind in base_wave_definition.enemy_sequence:
            wave.queued_enemies.append(
                self._create_enemy(
                    enemy_kind=enemy_kind,
                    wave_number=wave_number,
                    defending_player_id=player_id,
                    reward_player_id=attacker_id,
                    board_layout=board_layout,
                    hp_multiplier=1.0,
                    speed_multiplier=1.0,
                )
            )

        hp_multiplier = 1.0
        speed_multiplier = 1.0
        extra_modifier_points = 0
        for modifier in pressure_plan.modifiers:
            modifier_definition = MODIFIER_DEFINITIONS[modifier]
            hp_multiplier *= modifier_definition.hp_multiplier
            speed_multiplier *= modifier_definition.speed_multiplier
            extra_modifier_points += modifier_definition.extra_modifier_points

        wave.modifier_budget += extra_modifier_points
        wave.added_unit_counts = pressure_plan.unit_counts.copy()
        for enemy_kind, count in pressure_plan.unit_counts.items():
            for _ in range(count):
                wave.queued_enemies.append(
                    self._create_enemy(
                        enemy_kind=enemy_kind,
                        wave_number=wave_number,
                        defending_player_id=player_id,
                        reward_player_id=attacker_id,
                        board_layout=board_layout,
                        hp_multiplier=hp_multiplier,
                        speed_multiplier=speed_multiplier,
                    )
                )

        return wave

    def _create_enemy(
        self,
        enemy_kind: EnemyKind,
        wave_number: int,
        defending_player_id: str,
        reward_player_id: str | None,
        board_layout: BoardLayout,
        hp_multiplier: float,
        speed_multiplier: float,
    ) -> EnemyState:
        definition = ENEMY_DEFINITIONS[enemy_kind]
        wave_hp_multiplier = 1.0 + (
            (wave_number - 1) * self._enemy_hp_growth_per_wave
        )
        max_hp = definition.base_hp * wave_hp_multiplier * hp_multiplier

        return EnemyState(
            enemy_id=self._next_enemy_id(),
            enemy_type=enemy_kind,
            defending_player_id=defending_player_id,
            reward_player_id=reward_player_id,
            max_hp=max_hp,
            current_hp=max_hp,
            speed_tiles_per_second=definition.speed_tiles_per_second * speed_multiplier,
            leak_damage=definition.leak_damage,
            kill_reward=definition.kill_reward,
            position_x=board_layout.path_waypoints[0][0],
            position_y=board_layout.path_waypoints[0][1],
        )

    @staticmethod
    def _spawn_queued_enemies(wave: WaveState, delta_seconds: float) -> None:
        wave.spawn_cooldown_seconds -= delta_seconds

        while wave.queued_enemies and wave.spawn_cooldown_seconds <= 0.0:
            wave.active_enemies.append(wave.queued_enemies.pop(0))
            wave.spawned_enemies += 1
            wave.spawn_cooldown_seconds += wave.spawn_interval_seconds

    @staticmethod
    def _resolve_leak(
        state: MatchState,
        defending_player: PlayerState,
        enemy: EnemyState,
    ) -> None:
        defending_player.lives = max(0, defending_player.lives - enemy.leak_damage)
        defending_player.total_leaks_taken += enemy.leak_damage
        defending_player.current_wave.leaked_enemies += 1

        if enemy.reward_player_id is not None and enemy.reward_player_id in state.players:
            reward_player = state.players[enemy.reward_player_id]
            reward_player.gold += enemy.leak_damage

        state.record_event(
            (
                f"{defending_player.name} leaked a {enemy.enemy_type.value} "
                f"for {enemy.leak_damage} damage."
            )
        )
