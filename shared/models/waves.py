import math
from dataclasses import dataclass

from shared.models.game_rules import (
    ENEMY_DEFINITIONS,
    GAME_RULES,
    EnemyKind,
    base_wave_mix_for_wave,
    base_wave_points_for_wave,
)


@dataclass(frozen=True, slots=True)
class WaveDefinition:
    wave_number: int
    point_budget: int
    spawn_interval_seconds: float
    unit_counts: tuple[tuple[EnemyKind, int], ...]
    enemy_sequence: tuple[EnemyKind, ...]

    def counts_map(self) -> dict[EnemyKind, int]:
        return {enemy_kind: count for enemy_kind, count in self.unit_counts}


def build_base_wave_definition(wave_number: int) -> WaveDefinition:
    point_budget = base_wave_points_for_wave(wave_number)
    unit_counts = _build_counts_from_points(point_budget, wave_number)
    enemy_sequence = _build_enemy_sequence(unit_counts)

    return WaveDefinition(
        wave_number=wave_number,
        point_budget=point_budget,
        spawn_interval_seconds=_spawn_interval_for_wave(wave_number),
        unit_counts=tuple(unit_counts.items()),
        enemy_sequence=tuple(enemy_sequence),
    )


def _build_counts_from_points(
    points: int,
    wave_number: int,
) -> dict[EnemyKind, int]:
    ratios = base_wave_mix_for_wave(wave_number)
    counts = _empty_enemy_counts()
    remaining_points = points

    for enemy_kind, ratio in ratios.items():
        definition = ENEMY_DEFINITIONS[enemy_kind]
        budget = math.floor(points * ratio)
        count = budget // definition.point_cost
        counts[enemy_kind] += count
        remaining_points -= count * definition.point_cost

    available_types = list(ratios.keys())
    index = 0
    while remaining_points > 0 and available_types:
        enemy_kind = available_types[index % len(available_types)]
        definition = ENEMY_DEFINITIONS[enemy_kind]
        if definition.point_cost <= remaining_points:
            counts[enemy_kind] += 1
            remaining_points -= definition.point_cost
        index += 1
        if index > 1000:
            break

    return counts


def _build_enemy_sequence(unit_counts: dict[EnemyKind, int]) -> list[EnemyKind]:
    remaining_counts = unit_counts.copy()
    enemy_sequence: list[EnemyKind] = []

    while any(count > 0 for count in remaining_counts.values()):
        available_types = [
            enemy_kind
            for enemy_kind, count in remaining_counts.items()
            if count > 0
        ]
        available_types.sort(
            key=lambda enemy_kind: (
                remaining_counts[enemy_kind],
                ENEMY_DEFINITIONS[enemy_kind].point_cost,
            ),
            reverse=True,
        )

        for enemy_kind in available_types:
            if remaining_counts[enemy_kind] <= 0:
                continue
            enemy_sequence.append(enemy_kind)
            remaining_counts[enemy_kind] -= 1

    return enemy_sequence


def _spawn_interval_for_wave(wave_number: int) -> float:
    reduced_interval = GAME_RULES.spawn_interval_seconds - ((wave_number - 1) * 0.01)
    return max(0.18, reduced_interval)


def _empty_enemy_counts() -> dict[EnemyKind, int]:
    return {enemy_kind: 0 for enemy_kind in EnemyKind}
