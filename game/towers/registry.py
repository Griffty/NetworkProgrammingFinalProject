from game.towers.abstract_tower import AbstractTower
from game.towers.minigun_tower import MinigunTower
from game.towers.pulse_tower import PulseTower
from game.towers.railgun_tower import RailgunTower
from shared.models.game_rules import TowerKind

TOWER_REGISTRY: dict[TowerKind, type[AbstractTower]] = {
    TowerKind.MINIGUN: MinigunTower,
    TowerKind.RAILGUN: RailgunTower,
    TowerKind.PULSE: PulseTower,
}

_TOWER_INSTANCES = {
    tower_kind: tower_class()
    for tower_kind, tower_class in TOWER_REGISTRY.items()
}


def get_tower(tower_kind: TowerKind) -> AbstractTower:
    return _TOWER_INSTANCES[tower_kind]
