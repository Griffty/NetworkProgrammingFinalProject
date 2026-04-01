from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from shared.models.game_rules import EnemyKind, OffensiveModifier, TowerKind


@dataclass(frozen=True, slots=True)
class PlaceTowerCommand:
    tower_type: TowerKind
    tile_x: int
    tile_y: int


@dataclass(frozen=True, slots=True)
class UpgradeTowerCommand:
    tower_id: int


@dataclass(frozen=True, slots=True)
class SellTowerCommand:
    tower_id: int


@dataclass(frozen=True, slots=True)
class ConfigurePressureCommand:
    unit_counts: dict[EnemyKind, int]
    modifiers: set[OffensiveModifier]


@dataclass(frozen=True, slots=True)
class SkipBuildCommand:
    pass


GameCommand: TypeAlias = (
    PlaceTowerCommand
    | UpgradeTowerCommand
    | SellTowerCommand
    | ConfigurePressureCommand
    | SkipBuildCommand
)
