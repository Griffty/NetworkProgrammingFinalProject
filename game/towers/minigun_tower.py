"""Fast, cheap single-target tower definition."""

from collections.abc import Sequence

from game.towers.abstract_tower import AbstractTower, TowerPresentation
from shared.models.game_rules import TowerKind
from shared.models.state import EnemyState, TowerState


class MinigunTower(AbstractTower):
    """Rapid-fire single-target tower with short range."""

    tower_kind = TowerKind.MINIGUN
    cost = 35
    upgrade_costs = (25, 40)
    presentation = TowerPresentation(color=(80, 196, 120), shape="circle")

    def range_tiles(self, tower: TowerState) -> float:
        return 5.0 + (0.5 * (tower.level - 1))

    def damage(self, tower: TowerState) -> float:
        return 4.0 * (1.0 + (0.25 * (tower.level - 1)))

    def shots_per_second(self, tower: TowerState) -> float:
        return 5.0 * (1.0 + (0.20 * (tower.level - 1)))

    def collect_hit_enemies(
        self,
        tower: TowerState,
        target: EnemyState,
        enemies: Sequence[EnemyState],
    ) -> Sequence[EnemyState]:
        return (target,)
