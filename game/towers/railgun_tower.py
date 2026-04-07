"""Long-range penetrating beam tower definition."""

import math
from collections.abc import Sequence

from game.towers.abstract_tower import AbstractTower, TowerPresentation
from shared.models.game_rules import TowerKind
from shared.models.state import EnemyState, TowerState


class RailgunTower(AbstractTower):
    """Slow tower whose beam can hit multiple enemies in a line."""

    tower_kind = TowerKind.RAILGUN
    cost = 80
    upgrade_costs = (45, 65)
    presentation = TowerPresentation(color=(242, 214, 84), shape="triangle")

    def range_tiles(self, tower: TowerState) -> float:
        return 12.0 + (1.0 * (tower.level - 1))

    def damage(self, tower: TowerState) -> float:
        return 20.0 * (1.0 + (0.4 * (tower.level - 1)))

    def shots_per_second(self, tower: TowerState) -> float:
        return 0.7 * (1.0 + (0.10 * (tower.level - 1)))

    def collect_hit_enemies(
        self,
        tower: TowerState,
        target: EnemyState,
        enemies: Sequence[EnemyState],
    ) -> Sequence[EnemyState]:
        beam_width = 0.45 + (0.15 * (tower.level - 1))
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

            if along_distance < 0.0 or along_distance > self.range_tiles(tower):
                continue
            if perpendicular_distance > beam_width:
                continue
            hit_enemies.append(enemy)

        return hit_enemies or [target]
