import math
from dataclasses import dataclass
from enum import StrEnum


class MatchPhase(StrEnum):
    WAITING_FOR_PLAYERS = "waiting_for_players"
    BUILD = "build"
    WAVE = "wave"
    FINISHED = "finished"


class EnemyKind(StrEnum):
    RUNNER = "runner"
    BRUTE = "brute"
    GUARD = "guard"


class TowerKind(StrEnum):
    MINIGUN = "minigun"
    RAILGUN = "railgun"
    PULSE = "pulse"


class OffensiveModifier(StrEnum):
    REINFORCE = "reinforce"
    HASTE = "haste"
    REINFORCEMENTS = "reinforcements"


@dataclass(frozen=True, slots=True)
class GameRules:
    map_width: int = 64
    map_height: int = 64
    path_length_tiles: float = 64.0
    starting_gold: int = 100
    starting_lives: int = 25
    build_phase_seconds: float = 20.0
    sell_refund_ratio: float = 0.70
    tick_rate_hz: int = 10
    max_players: int = 2
    spawn_interval_seconds: float = 0.35
    base_wave_points: int = 30
    wave_point_growth: int = 8
    enemy_hp_growth_per_wave: float = 0.10
    modifier_budget_ratio: float = 0.66
    wave_clear_bonus_base: int = 20
    wave_clear_bonus_per_wave: int = 5


@dataclass(frozen=True, slots=True)
class EnemyDefinition:
    enemy_type: EnemyKind
    point_cost: int
    base_hp: int
    speed_tiles_per_second: float
    leak_damage: int
    kill_reward: int


@dataclass(frozen=True, slots=True)
class OffensiveModifierDefinition:
    modifier: OffensiveModifier
    cost: int
    hp_multiplier: float = 1.0
    speed_multiplier: float = 1.0
    extra_modifier_points: int = 0


GAME_RULES = GameRules()

ENEMY_DEFINITIONS: dict[EnemyKind, EnemyDefinition] = {
    EnemyKind.RUNNER: EnemyDefinition(
        enemy_type=EnemyKind.RUNNER,
        point_cost=1,
        base_hp=20,
        speed_tiles_per_second=3.4,
        leak_damage=1,
        kill_reward=1,
    ),
    EnemyKind.BRUTE: EnemyDefinition(
        enemy_type=EnemyKind.BRUTE,
        point_cost=3,
        base_hp=70,
        speed_tiles_per_second=1.7,
        leak_damage=2,
        kill_reward=3,
    ),
    EnemyKind.GUARD: EnemyDefinition(
        enemy_type=EnemyKind.GUARD,
        point_cost=4,
        base_hp=90,
        speed_tiles_per_second=2.2,
        leak_damage=3,
        kill_reward=4,
    ),
}

MODIFIER_DEFINITIONS: dict[OffensiveModifier, OffensiveModifierDefinition] = {
    OffensiveModifier.REINFORCE: OffensiveModifierDefinition(
        modifier=OffensiveModifier.REINFORCE,
        cost=12,
        hp_multiplier=1.25,
    ),
    OffensiveModifier.HASTE: OffensiveModifierDefinition(
        modifier=OffensiveModifier.HASTE,
        cost=12,
        speed_multiplier=1.20,
    ),
    OffensiveModifier.REINFORCEMENTS: OffensiveModifierDefinition(
        modifier=OffensiveModifier.REINFORCEMENTS,
        cost=15,
        extra_modifier_points=10,
    ),
}


def base_wave_points_for_wave(wave_number: int) -> int:
    return GAME_RULES.base_wave_points + ((wave_number - 1) * GAME_RULES.wave_point_growth)


def modifier_points_for_wave(wave_number: int) -> int:
    return math.floor(
        base_wave_points_for_wave(wave_number) * GAME_RULES.modifier_budget_ratio
    )


def wave_clear_bonus_for_wave(wave_number: int) -> int:
    return GAME_RULES.wave_clear_bonus_base + (
        wave_number * GAME_RULES.wave_clear_bonus_per_wave
    )


def base_wave_mix_for_wave(wave_number: int) -> dict[EnemyKind, float]:
    if wave_number <= 2:
        return {
            EnemyKind.RUNNER: 0.85,
            EnemyKind.BRUTE: 0.15,
        }
    if wave_number <= 4:
        return {
            EnemyKind.RUNNER: 0.65,
            EnemyKind.BRUTE: 0.35,
        }
    return {
        EnemyKind.RUNNER: 0.45,
        EnemyKind.BRUTE: 0.30,
        EnemyKind.GUARD: 0.25,
    }
