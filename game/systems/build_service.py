import math
from collections.abc import Callable

from game.match_state import MatchState
from game.towers.registry import get_tower
from shared.models.game_rules import TowerKind
from shared.models.state import PlayerState, TowerState


class BuildService:
    def __init__(
        self,
        starting_gold: int,
        starting_lives: int,
        sell_refund_ratio: float,
        next_tower_id: Callable[[], int],
    ) -> None:
        self._starting_gold = starting_gold
        self._starting_lives = starting_lives
        self._sell_refund_ratio = sell_refund_ratio
        self._next_tower_id = next_tower_id

    def add_player(
        self,
        state: MatchState,
        player_id: str,
        player_name: str,
    ) -> PlayerState:
        player = PlayerState(
            player_id=player_id,
            name=player_name,
            gold=self._starting_gold,
            lives=self._starting_lives,
        )
        state.add_player(player)
        state.record_event(f"{player_name} joined the match.")
        return player

    def place_tower(
        self,
        state: MatchState,
        player_id: str,
        tower_type: TowerKind,
        tile_x: int,
        tile_y: int,
    ) -> TowerState:
        player = self._require_player(state, player_id)
        tower_model = get_tower(tower_type)

        if not player.board_layout.is_buildable_tile(tile_x, tile_y):
            raise ValueError("That tile is not buildable.")

        if any(
            tower.tile_x == tile_x and tower.tile_y == tile_y
            for tower in player.towers.values()
        ):
            raise ValueError("A tower already occupies that tile.")

        if player.gold < tower_model.cost:
            raise ValueError("Not enough gold to place that tower.")

        player.gold -= tower_model.cost
        tower = tower_model.create_state(self._next_tower_id(), tile_x, tile_y)
        player.towers[tower.tower_id] = tower
        state.record_event(
            f"{player.name} placed {tower_type.value} at ({tile_x}, {tile_y})."
        )
        return tower

    def upgrade_tower(
        self,
        state: MatchState,
        player_id: str,
        tower_id: int,
    ) -> TowerState:
        player = self._require_player(state, player_id)
        tower = self._require_tower(player, tower_id)
        tower_model = get_tower(tower.tower_type)

        if not tower_model.can_upgrade(tower):
            raise ValueError("Tower is already at max level.")

        upgrade_cost = tower_model.upgrade_cost(tower)
        if player.gold < upgrade_cost:
            raise ValueError("Not enough gold to upgrade that tower.")

        player.gold -= upgrade_cost
        tower_model.apply_upgrade(tower)
        state.record_event(
            f"{player.name} upgraded tower {tower.tower_id} to level {tower.level}."
        )
        return tower

    def sell_tower(
        self,
        state: MatchState,
        player_id: str,
        tower_id: int,
    ) -> int:
        player = self._require_player(state, player_id)
        tower = self._require_tower(player, tower_id)

        refund = math.floor(tower.total_gold_spent * self._sell_refund_ratio)
        player.gold += refund
        del player.towers[tower_id]
        state.record_event(
            f"{player.name} sold tower {tower.tower_id} for {refund} gold."
        )
        return refund

    @staticmethod
    def _require_player(state: MatchState, player_id: str) -> PlayerState:
        if player_id not in state.players:
            raise ValueError(f"Unknown player id: {player_id}")
        return state.players[player_id]

    @staticmethod
    def _require_tower(player: PlayerState, tower_id: int) -> TowerState:
        if tower_id not in player.towers:
            raise ValueError(f"Unknown tower id: {tower_id}")
        return player.towers[tower_id]
