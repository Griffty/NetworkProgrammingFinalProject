from dataclasses import dataclass, field

from shared.models.board import BoardLayout, DEFAULT_BOARD_LAYOUT
from shared.models.game_rules import (
    MODIFIER_DEFINITIONS,
    EnemyKind,
    OffensiveModifier,
    TowerKind,
    modifier_points_for_wave,
)


def zero_enemy_counts() -> dict[EnemyKind, int]:
    return {enemy_kind: 0 for enemy_kind in EnemyKind}


@dataclass(slots=True)
class TowerState:
    tower_id: int
    tower_type: TowerKind
    tile_x: int
    tile_y: int
    level: int
    total_gold_spent: int
    cooldown_seconds: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        return (self.tile_x + 0.5, self.tile_y + 0.5)


@dataclass(slots=True)
class EnemyState:
    enemy_id: int
    enemy_type: EnemyKind
    defending_player_id: str
    reward_player_id: str | None
    max_hp: float
    current_hp: float
    speed_tiles_per_second: float
    leak_damage: int
    kill_reward: int
    distance_travelled_tiles: float = 0.0
    position_x: float = 0.0
    position_y: float = 0.0

    def advance(self, delta_seconds: float, board_layout: BoardLayout) -> None:
        self.distance_travelled_tiles += self.speed_tiles_per_second * delta_seconds
        self.position_x, self.position_y = board_layout.position_for_distance(
            self.distance_travelled_tiles
        )

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def position(self) -> tuple[float, float]:
        return (self.position_x, self.position_y)


@dataclass(slots=True)
class OutgoingPressureState:
    unit_counts: dict[EnemyKind, int] = field(default_factory=zero_enemy_counts)
    modifiers: set[OffensiveModifier] = field(default_factory=set)

    def spent_points(self) -> int:
        return sum(
            enemy_kind_definition.point_cost * self.unit_counts[enemy_kind]
            for enemy_kind, enemy_kind_definition in _enemy_definitions_in_order()
        )

    def gold_cost(self) -> int:
        return sum(
            MODIFIER_DEFINITIONS[modifier].cost for modifier in self.modifiers
        )

    def available_points(self, wave_number: int) -> int:
        available = modifier_points_for_wave(wave_number)
        for modifier in self.modifiers:
            available += MODIFIER_DEFINITIONS[modifier].extra_modifier_points
        return available

    def reset(self) -> None:
        self.unit_counts = zero_enemy_counts()
        self.modifiers = set()

    def copy(self) -> "OutgoingPressureState":
        return OutgoingPressureState(
            unit_counts=self.unit_counts.copy(),
            modifiers=set(self.modifiers),
        )


@dataclass(slots=True)
class WaveState:
    wave_number: int = 0
    base_points: int = 0
    modifier_budget: int = 0
    queued_enemies: list[EnemyState] = field(default_factory=list)
    active_enemies: list[EnemyState] = field(default_factory=list)
    spawn_interval_seconds: float = 0.35
    spawn_cooldown_seconds: float = 0.0
    spawned_enemies: int = 0
    killed_enemies: int = 0
    leaked_enemies: int = 0
    base_unit_counts: dict[EnemyKind, int] = field(default_factory=zero_enemy_counts)
    added_unit_counts: dict[EnemyKind, int] = field(default_factory=zero_enemy_counts)

    @property
    def is_cleared(self) -> bool:
        return not self.queued_enemies and not self.active_enemies


@dataclass(slots=True)
class PlayerState:
    player_id: str
    name: str
    gold: int
    lives: int
    board_layout: BoardLayout = DEFAULT_BOARD_LAYOUT
    towers: dict[int, TowerState] = field(default_factory=dict)
    current_wave: WaveState = field(default_factory=WaveState)
    outgoing_pressure: OutgoingPressureState = field(default_factory=OutgoingPressureState)
    ready_for_next_wave: bool = False
    total_kills: int = 0
    total_leaks_taken: int = 0
    completed_waves: int = 0

    @property
    def is_alive(self) -> bool:
        return self.lives > 0


def _enemy_definitions_in_order():
    from shared.models.game_rules import ENEMY_DEFINITIONS

    return tuple((enemy_kind, ENEMY_DEFINITIONS[enemy_kind]) for enemy_kind in EnemyKind)
