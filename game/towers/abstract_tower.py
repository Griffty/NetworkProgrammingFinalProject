"""Abstract tower contract and shared tower combat helpers."""

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from shared.models.game_rules import TowerKind
from shared.models.state import EnemyState, TowerState

TowerShape = Literal["circle", "triangle", "square"]


@dataclass(frozen=True, slots=True)
class TowerShot:
    """Result of a single tower attack resolution."""

    damage: float
    hit_enemies: tuple[EnemyState, ...]


@dataclass(frozen=True, slots=True)
class TowerPresentation:
    """Minimal visual metadata used by the pygame client."""

    color: tuple[int, int, int]
    shape: TowerShape


class AbstractTower(ABC):
    """Base class implemented by each tower type."""

    tower_kind: TowerKind
    cost: int
    upgrade_costs: tuple[int, ...]
    presentation: TowerPresentation
    max_level: int = 3

    def create_state(self, tower_id: int, tile_x: int, tile_y: int) -> TowerState:
        """Create runtime state for a newly placed tower."""

        return TowerState(
            tower_id=tower_id,
            tower_type=self.tower_kind,
            tile_x=tile_x,
            tile_y=tile_y,
            level=1,
            total_gold_spent=self.cost,
        )

    def can_upgrade(self, tower: TowerState) -> bool:
        """Return whether the tower can gain another level."""

        return tower.level < self.max_level

    def upgrade_cost(self, tower: TowerState) -> int:
        """Return the gold cost of the next upgrade level."""

        if not self.can_upgrade(tower):
            raise ValueError("Tower is already at max level.")
        return self.upgrade_costs[tower.level - 1]

    def apply_upgrade(self, tower: TowerState) -> None:
        """Apply an upgrade to the runtime tower state."""

        upgrade_cost = self.upgrade_cost(tower)
        tower.level += 1
        tower.total_gold_spent += upgrade_cost

    def attack(
        self,
        tower: TowerState,
        enemies: Sequence[EnemyState],
    ) -> TowerShot | None:
        """Pick targets and build a tower shot for the current tick."""

        target = self.find_target(tower, enemies)
        if target is None:
            return None

        hit_enemies = tuple(self.collect_hit_enemies(tower, target, enemies))
        if not hit_enemies:
            return None

        return TowerShot(
            damage=self.damage(tower),
            hit_enemies=hit_enemies,
        )

    def cooldown_seconds(self, tower: TowerState) -> float:
        """Return the time until the tower can attack again."""

        return 1.0 / self.shots_per_second(tower)

    def find_target(
        self,
        tower: TowerState,
        enemies: Sequence[EnemyState],
    ) -> EnemyState | None:
        """Pick the furthest-progressed enemy within range."""

        enemies_in_range = self.enemies_in_range(tower, enemies)
        if not enemies_in_range:
            return None

        return max(enemies_in_range, key=lambda enemy: enemy.distance_travelled_tiles)

    def enemies_in_range(
        self,
        tower: TowerState,
        enemies: Sequence[EnemyState],
    ) -> list[EnemyState]:
        """Return all enemies currently inside tower range."""

        tower_x, tower_y = tower.center
        range_tiles = self.range_tiles(tower)
        return [
            enemy
            for enemy in enemies
            if math.dist((tower_x, tower_y), enemy.position) <= range_tiles
        ]

    @abstractmethod
    def range_tiles(self, tower: TowerState) -> float:
        """Return tower range in board tiles."""

        raise NotImplementedError

    @abstractmethod
    def damage(self, tower: TowerState) -> float:
        """Return damage dealt by a single attack."""

        raise NotImplementedError

    @abstractmethod
    def shots_per_second(self, tower: TowerState) -> float:
        """Return attack rate in shots per second."""

        raise NotImplementedError

    @abstractmethod
    def collect_hit_enemies(
        self,
        tower: TowerState,
        target: EnemyState,
        enemies: Sequence[EnemyState],
    ) -> Sequence[EnemyState]:
        """Return the enemies hit by this tower's attack pattern."""

        raise NotImplementedError
