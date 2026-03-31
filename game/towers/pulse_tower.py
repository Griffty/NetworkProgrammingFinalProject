import math
from collections.abc import Sequence

from game.towers.abstract_tower import AbstractTower, TowerPresentation
from shared.models.game_rules import TowerKind
from shared.models.state import EnemyState, TowerState


class PulseTower(AbstractTower):
    tower_kind = TowerKind.PULSE
    cost = 50
    upgrade_costs = (35, 55)
    presentation = TowerPresentation(color=(192, 132, 255), shape="square")

    def range_tiles(self, tower: TowerState) -> float:
        return 7.0 + (0.75 * (tower.level - 1))

    def damage(self, tower: TowerState) -> float:
        return 14.0 * (1.0 + (0.30 * (tower.level - 1)))

    def shots_per_second(self, tower: TowerState) -> float:
        return 1.2 * (1.0 + (0.10 * (tower.level - 1)))

    def collect_hit_enemies(
        self,
        tower: TowerState,
        target: EnemyState,
        enemies: Sequence[EnemyState],
    ) -> Sequence[EnemyState]:
        splash_radius = 1.5 + (0.40 * (tower.level - 1))
        return [
            enemy
            for enemy in enemies
            if math.dist(enemy.position, target.position) <= splash_radius
        ]
