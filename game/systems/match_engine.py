import math
from itertools import count
from typing import Sequence

from game.match_state import MatchState
from shared.models import (
    BoardLayout,
    ENEMY_DEFINITIONS,
    GAME_RULES,
    MODIFIER_DEFINITIONS,
    TOWER_DEFINITIONS,
    EnemyKind,
    EnemyState,
    MatchPhase,
    OffensiveModifier,
    OutgoingPressureState,
    PlayerState,
    TowerKind,
    TowerState,
    WaveDefinition,
    WaveState,
    base_wave_points_for_wave,
    build_base_wave_definition,
    modifier_points_for_wave,
    wave_clear_bonus_for_wave,
    zero_enemy_counts,
)


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

        for index, player_name in enumerate(player_names or (), start=1):
            self.add_player(player_id=f"player_{index}", player_name=player_name)

    def add_player(self, player_id: str, player_name: str) -> PlayerState:
        player = PlayerState(
            player_id=player_id,
            name=player_name,
            gold=self.rules.starting_gold,
            lives=self.rules.starting_lives,
        )
        self.state.add_player(player)
        self.state.record_event(f"{player_name} joined the match.")

        if self.state.phase == MatchPhase.WAITING_FOR_PLAYERS and self.state.can_start():
            self._begin_build_phase()

        return player

    def place_tower(
        self, player_id: str, tower_type: TowerKind, tile_x: int, tile_y: int
    ) -> TowerState:
        self._require_phase(MatchPhase.BUILD)
        player = self._require_player(player_id)
        tower_definition = TOWER_DEFINITIONS[tower_type]

        if not player.board_layout.contains_tile(tile_x, tile_y):
            raise ValueError("Tower placement is outside the map bounds.")

        if not player.board_layout.is_buildable_tile(tile_x, tile_y):
            raise ValueError("That tile is not buildable.")

        if any(
            tower.tile_x == tile_x and tower.tile_y == tile_y
            for tower in player.towers.values()
        ):
            raise ValueError("A tower already occupies that tile.")

        if player.gold < tower_definition.cost:
            raise ValueError("Not enough gold to place that tower.")

        player.gold -= tower_definition.cost
        tower = TowerState(
            tower_id=next(self._tower_ids),
            tower_type=tower_type,
            tile_x=tile_x,
            tile_y=tile_y,
            level=1,
            total_gold_spent=tower_definition.cost,
        )
        player.towers[tower.tower_id] = tower
        self.state.record_event(
            f"{player.name} placed {tower_type.value} at ({tile_x}, {tile_y})."
        )
        return tower

    def upgrade_tower(self, player_id: str, tower_id: int) -> TowerState:
        self._require_phase(MatchPhase.BUILD)
        player = self._require_player(player_id)
        tower = self._require_tower(player, tower_id)
        tower_definition = TOWER_DEFINITIONS[tower.tower_type]

        if tower.level >= tower_definition.max_level:
            raise ValueError("Tower is already at max level.")

        upgrade_cost = tower_definition.upgrade_costs[tower.level - 1]
        if player.gold < upgrade_cost:
            raise ValueError("Not enough gold to upgrade that tower.")

        player.gold -= upgrade_cost
        tower.level += 1
        tower.total_gold_spent += upgrade_cost
        self.state.record_event(
            f"{player.name} upgraded tower {tower.tower_id} to level {tower.level}."
        )
        return tower

    def sell_tower(self, player_id: str, tower_id: int) -> int:
        self._require_phase(MatchPhase.BUILD)
        player = self._require_player(player_id)
        tower = self._require_tower(player, tower_id)

        refund = math.floor(tower.total_gold_spent * self.rules.sell_refund_ratio)
        player.gold += refund
        del player.towers[tower_id]
        self.state.record_event(
            f"{player.name} sold tower {tower.tower_id} for {refund} gold."
        )
        return refund

    def configure_pressure(
        self,
        player_id: str,
        unit_counts: dict[EnemyKind, int],
        modifiers: set[OffensiveModifier] | None = None,
    ) -> OutgoingPressureState:
        self._require_phase(MatchPhase.BUILD)
        player = self._require_player(player_id)
        modifiers = set(modifiers or set())
        wave_number = self.state.current_wave_number + 1

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
        self.state.record_event(
            f"{player.name} updated outgoing pressure for wave {wave_number}."
        )
        return new_plan

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
                    self._begin_build_phase()
                continue

            if self.state.phase == MatchPhase.BUILD:
                self._update_build_phase(tick_duration)
            elif self.state.phase == MatchPhase.WAVE:
                self._update_wave_phase(tick_duration)

            if self.state.phase != MatchPhase.FINISHED:
                self._update_win_state()

        return self.state

    def advance(self, seconds: float) -> MatchState:
        if seconds < 0:
            raise ValueError("Advance duration cannot be negative.")

        steps = math.ceil(seconds * self.state.tick_rate_hz)
        if steps == 0:
            return self.state
        return self.tick(steps)

    def summary_lines(self) -> list[str]:
        lines = [
            f"Phase: {self.state.phase.value}",
            f"Wave: {self.state.current_wave_number}",
            f"Elapsed: {self.state.elapsed_seconds:.1f}s",
        ]

        if self.state.phase == MatchPhase.BUILD:
            lines.append(
                f"Build timer: {self.state.phase_time_remaining_seconds:.1f}s"
            )

        if self.state.winner_player_id is not None:
            winner = self.state.players[self.state.winner_player_id]
            lines.append(f"Winner: {winner.name}")
        elif self.state.is_draw:
            lines.append("Winner: draw")

        for player in self.state.players.values():
            lines.append(
                (
                    f"{player.name}: gold={player.gold}, lives={player.lives}, "
                    f"towers={len(player.towers)}, kills={player.total_kills}, "
                    f"queued={len(player.current_wave.queued_enemies)}, "
                    f"active={len(player.current_wave.active_enemies)}"
                )
            )

        return lines

    def _update_build_phase(self, delta_seconds: float) -> None:
        self.state.phase_time_remaining_seconds = max(
            0.0,
            self.state.phase_time_remaining_seconds - delta_seconds,
        )
        if self.state.phase_time_remaining_seconds == 0.0:
            self._start_next_wave()

    def _update_wave_phase(self, delta_seconds: float) -> None:
        for player in self.state.alive_players():
            wave = player.current_wave
            board_layout = player.board_layout
            wave.spawn_cooldown_seconds = max(
                0.0,
                wave.spawn_cooldown_seconds - delta_seconds,
            )

            while wave.queued_enemies and wave.spawn_cooldown_seconds == 0.0:
                wave.active_enemies.append(wave.queued_enemies.pop(0))
                wave.spawned_enemies += 1
                wave.spawn_cooldown_seconds = wave.spawn_interval_seconds

            self._update_tower_combat(player, wave, delta_seconds)

            leaked_enemies: list[EnemyState] = []
            for enemy in wave.active_enemies:
                enemy.advance(delta_seconds, board_layout)
                if enemy.distance_travelled_tiles >= board_layout.total_path_length_tiles:
                    leaked_enemies.append(enemy)

            for enemy in leaked_enemies:
                self._resolve_leak(player, enemy)
                wave.active_enemies.remove(enemy)

        alive_players = self.state.alive_players()
        if not alive_players:
            return

        if all(player.current_wave.is_cleared for player in alive_players):
            self._finish_current_wave()

    def _begin_build_phase(self) -> None:
        self.state.phase = MatchPhase.BUILD
        self.state.phase_time_remaining_seconds = self.rules.build_phase_seconds
        for player in self.state.players.values():
            player.ready_for_next_wave = False
        self.state.record_event("Build phase started.")

    def _start_next_wave(self) -> None:
        self.state.current_wave_number += 1
        wave_number = self.state.current_wave_number
        base_wave_definition = build_base_wave_definition(wave_number)
        pressure_by_target: dict[str, tuple[str | None, OutgoingPressureState]] = {}

        for defending_player_id in self.state.players:
            attacker_id = self.state.opponent_id_for(defending_player_id)
            pressure_plan = (
                self.state.players[attacker_id].outgoing_pressure.copy()
                if attacker_id is not None
                else OutgoingPressureState()
            )
            pressure_by_target[defending_player_id] = (attacker_id, pressure_plan)

        for defending_player_id, player in self.state.players.items():
            attacker_id, pressure_plan = pressure_by_target[defending_player_id]
            player.current_wave = self._build_wave_for_player(
                player_id=defending_player_id,
                attacker_id=attacker_id,
                base_wave_definition=base_wave_definition,
                pressure_plan=pressure_plan,
            )

        for player in self.state.players.values():
            player.outgoing_pressure.reset()

        self.state.phase = MatchPhase.WAVE
        self.state.phase_time_remaining_seconds = 0.0
        self.state.record_event(
            f"Wave {wave_number} started with {base_wave_definition.point_budget} base points."
        )

    def _finish_current_wave(self) -> None:
        wave_number = self.state.current_wave_number
        bonus_gold = wave_clear_bonus_for_wave(wave_number)

        for player in self.state.alive_players():
            player.gold += bonus_gold
            player.completed_waves = wave_number

        self.state.record_event(
            f"Wave {wave_number} cleared. Each surviving player earned {bonus_gold} gold."
        )
        self._begin_build_phase()

    def _build_wave_for_player(
        self,
        player_id: str,
        attacker_id: str | None,
        base_wave_definition: WaveDefinition,
        pressure_plan: OutgoingPressureState,
    ) -> WaveState:
        wave_number = base_wave_definition.wave_number
        board_layout = self.state.players[player_id].board_layout
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
            (wave_number - 1) * self.rules.enemy_hp_growth_per_wave
        )
        max_hp = definition.base_hp * wave_hp_multiplier * hp_multiplier

        return EnemyState(
            enemy_id=next(self._enemy_ids),
            enemy_type=enemy_kind,
            defending_player_id=defending_player_id,
            reward_player_id=reward_player_id,
            max_hp=max_hp,
            current_hp=max_hp,
            speed_tiles_per_second=(
                definition.speed_tiles_per_second * speed_multiplier
            ),
            leak_damage=definition.leak_damage,
            kill_reward=definition.kill_reward,
            position_x=board_layout.path_waypoints[0][0],
            position_y=board_layout.path_waypoints[0][1],
        )

    def _resolve_leak(self, defending_player: PlayerState, enemy: EnemyState) -> None:
        defending_player.lives = max(0, defending_player.lives - enemy.leak_damage)
        defending_player.total_leaks_taken += enemy.leak_damage
        defending_player.current_wave.leaked_enemies += 1

        if enemy.reward_player_id is not None and enemy.reward_player_id in self.state.players:
            reward_player = self.state.players[enemy.reward_player_id]
            reward_player.gold += enemy.leak_damage

        self.state.record_event(
            (
                f"{defending_player.name} leaked a {enemy.enemy_type.value} "
                f"for {enemy.leak_damage} damage."
            )
        )

    def _update_tower_combat(
        self,
        player: PlayerState,
        wave: WaveState,
        delta_seconds: float,
    ) -> None:
        if not player.towers or not wave.active_enemies:
            return

        for tower in player.towers.values():
            tower.cooldown_seconds = max(0.0, tower.cooldown_seconds - delta_seconds)
            if tower.cooldown_seconds > 0.0:
                continue

            active_enemies = [enemy for enemy in wave.active_enemies if enemy.is_alive]
            if not active_enemies:
                break

            tower_stats = self._tower_stats(tower)
            target = self._find_target(tower, active_enemies, tower_stats["range"])
            if target is None:
                continue

            hit_enemies = self._collect_hit_enemies(
                tower=tower,
                target=target,
                enemies=active_enemies,
                range_tiles=tower_stats["range"],
                splash_radius=tower_stats["splash_radius"],
                beam_width=tower_stats["beam_width"],
            )

            for enemy in hit_enemies:
                enemy.current_hp -= tower_stats["damage"]

            tower.cooldown_seconds = 1.0 / tower_stats["shots_per_second"]
            self._cleanup_destroyed_enemies(player, wave)

    def _cleanup_destroyed_enemies(self, player: PlayerState, wave: WaveState) -> None:
        destroyed_enemies = [enemy for enemy in wave.active_enemies if not enemy.is_alive]
        for enemy in destroyed_enemies:
            wave.active_enemies.remove(enemy)
            wave.killed_enemies += 1
            player.total_kills += 1
            player.gold += enemy.kill_reward

    def _find_target(
        self,
        tower: TowerState,
        enemies: list[EnemyState],
        range_tiles: float,
    ) -> EnemyState | None:
        tower_x, tower_y = tower.center
        enemies_in_range = [
            enemy
            for enemy in enemies
            if math.dist((tower_x, tower_y), enemy.position) <= range_tiles
        ]
        if not enemies_in_range:
            return None

        return max(enemies_in_range, key=lambda enemy: enemy.distance_travelled_tiles)

    def _collect_hit_enemies(
        self,
        tower: TowerState,
        target: EnemyState,
        enemies: list[EnemyState],
        range_tiles: float,
        splash_radius: float,
        beam_width: float,
    ) -> list[EnemyState]:
        if tower.tower_type == TowerKind.MINIGUN:
            return [target]

        if tower.tower_type == TowerKind.PULSE:
            return [
                enemy
                for enemy in enemies
                if math.dist(enemy.position, target.position) <= splash_radius
            ]

        tower_x, tower_y = tower.center
        target_x, target_y = target.position
        direction_x = target_x - tower_x
        direction_y = target_y - tower_y
        direction_length = math.hypot(direction_x, direction_y)
        if direction_length == 0.0:
            return [target]

        norm_x = direction_x / direction_length
        norm_y = direction_y / direction_length
        hit_enemies: list[EnemyState] = []

        for enemy in enemies:
            rel_x = enemy.position_x - tower_x
            rel_y = enemy.position_y - tower_y
            along_distance = (rel_x * norm_x) + (rel_y * norm_y)
            perpendicular_distance = abs((rel_x * norm_y) - (rel_y * norm_x))

            if along_distance < 0.0 or along_distance > range_tiles:
                continue
            if perpendicular_distance > beam_width:
                continue
            hit_enemies.append(enemy)

        return hit_enemies or [target]

    def _tower_stats(self, tower: TowerState) -> dict[str, float]:
        definition = TOWER_DEFINITIONS[tower.tower_type]
        level_bonus = tower.level - 1

        if tower.tower_type == TowerKind.MINIGUN:
            return {
                "range": definition.range_tiles + (0.5 * level_bonus),
                "damage": definition.damage * (1.0 + (0.25 * level_bonus)),
                "shots_per_second": definition.shots_per_second * (1.0 + (0.20 * level_bonus)),
                "splash_radius": 0.0,
                "beam_width": 0.0,
            }

        if tower.tower_type == TowerKind.RAILGUN:
            return {
                "range": definition.range_tiles + (1.0 * level_bonus),
                "damage": definition.damage * (1.0 + (0.45 * level_bonus)),
                "shots_per_second": definition.shots_per_second * (1.0 + (0.10 * level_bonus)),
                "splash_radius": 0.0,
                "beam_width": 0.45 + (0.15 * level_bonus),
            }

        return {
            "range": definition.range_tiles + (0.75 * level_bonus),
            "damage": definition.damage * (1.0 + (0.30 * level_bonus)),
            "shots_per_second": definition.shots_per_second * (1.0 + (0.10 * level_bonus)),
            "splash_radius": definition.splash_radius + (0.40 * level_bonus),
            "beam_width": 0.0,
        }

    def _update_win_state(self) -> None:
        alive_players = self.state.alive_players()
        if len(alive_players) == 2:
            return

        self.state.phase = MatchPhase.FINISHED
        self.state.phase_time_remaining_seconds = 0.0
        for player in self.state.players.values():
            player.current_wave.active_enemies.clear()
            player.current_wave.queued_enemies.clear()

        if len(alive_players) == 1:
            self.state.winner_player_id = alive_players[0].player_id
            self.state.record_event(f"{alive_players[0].name} won the match.")
        else:
            self.state.is_draw = True
            self.state.record_event("The match ended in a draw.")

    def _require_phase(self, expected_phase: MatchPhase) -> None:
        if self.state.phase != expected_phase:
            raise ValueError(
                f"Action is only allowed during {expected_phase.value}, "
                f"but match is in {self.state.phase.value}."
            )

    def _require_player(self, player_id: str) -> PlayerState:
        if player_id not in self.state.players:
            raise ValueError(f"Unknown player id: {player_id}")
        return self.state.players[player_id]

    @staticmethod
    def _require_tower(player: PlayerState, tower_id: int) -> TowerState:
        if tower_id not in player.towers:
            raise ValueError(f"Unknown tower id: {tower_id}")
        return player.towers[tower_id]
