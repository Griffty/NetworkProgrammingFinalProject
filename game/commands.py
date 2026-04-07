"""Simple command objects sent from the network layer into the engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from shared.models.game_rules import EnemyKind, OffensiveModifier, TowerKind


@dataclass(frozen=True, slots=True)
class PlaceTowerCommand:
    """Command requesting tower placement."""

    tower_type: TowerKind
    tile_x: int
    tile_y: int


@dataclass(frozen=True, slots=True)
class UpgradeTowerCommand:
    """Command requesting tower upgrade."""

    tower_id: int


@dataclass(frozen=True, slots=True)
class SellTowerCommand:
    """Command requesting tower sale."""

    tower_id: int


@dataclass(frozen=True, slots=True)
class ConfigurePressureCommand:
    """Command carrying an updated pressure plan."""

    unit_counts: dict[EnemyKind, int]
    modifiers: set[OffensiveModifier]


@dataclass(frozen=True, slots=True)
class SkipBuildCommand:
    """Command marking the player as ready for the next wave."""

    pass


GameCommand: TypeAlias = (
    PlaceTowerCommand
    | UpgradeTowerCommand
    | SellTowerCommand
    | ConfigurePressureCommand
    | SkipBuildCommand
)
