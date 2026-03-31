from __future__ import annotations

from client.game_client import GameClient
from client.pygame_lobby_view import ConnectAction, PygameLobbyView
from client.pygame_view import (
    AdjustPressureUnitsAction,
    ClientAction,
    PlaceTowerAction,
    PygameClientView,
    SkipBuildAction,
    SellTowerAction,
    TogglePressureModifierAction,
)
from shared.models.game_rules import MatchPhase


class PygameClient:
    def __init__(self, host: str, port: int, player_name: str) -> None:
        self.player_name = player_name
        self.default_host = host
        self.default_port = port
        self.network_client: GameClient | None = None
        self.lobby_view = PygameLobbyView(
            default_host=host,
            default_port=port,
            player_name=player_name,
        )
        self.view = PygameClientView()

    def run(self) -> None:
        if not self._run_lobby():
            return

        assert self.network_client is not None
        self.lobby_view.close()
        self.view.open(
            player_name=self.network_client.player_name,
            my_player_id=self.network_client.player_id,
        )
        try:
            self._run_main_loop()
        finally:
            self.view.close()
            self._disconnect_network_client()

    def _run_lobby(self) -> bool:
        self.lobby_view.open()
        running = True

        while running:
            self.lobby_view.next_frame()
            running, connect_action = self.lobby_view.handle_events()
            if not running:
                self._disconnect_network_client()
                self.lobby_view.close()
                return False

            if connect_action is not None:
                self._attempt_connect(connect_action)

            network_client = self.network_client
            if network_client is not None:
                if not network_client.is_connected:
                    self.lobby_view.set_status(
                        "Disconnected from server.",
                        self.lobby_view.error_color,
                    )
                    self._disconnect_network_client()
                elif network_client.player_id is not None:
                    return True

            network_client = self.network_client
            self.lobby_view.render(
                connected=network_client is not None and network_client.is_connected,
                waiting_for_match=network_client is not None and network_client.player_id is None,
                welcome_message=(
                    network_client.welcome_message if network_client is not None else ""
                ),
            )

        self._disconnect_network_client()
        self.lobby_view.close()
        return False

    def _attempt_connect(self, action: ConnectAction) -> None:
        self._disconnect_network_client()

        candidate = GameClient(
            host=action.host,
            port=action.port,
            player_name=self.player_name,
        )
        if not candidate.connect():
            self.lobby_view.set_status(
                f"Failed to connect to {action.host}:{action.port}.",
                self.lobby_view.error_color,
            )
            return

        self.network_client = candidate
        self.lobby_view.set_status(
            f"Connected to {action.host}:{action.port}",
            self.lobby_view.success_color,
        )

    def _run_main_loop(self) -> None:
        assert self.network_client is not None
        running = True

        while running and self.network_client.is_connected:
            frame_seconds = self.view.next_frame()
            self.view.update(frame_seconds)
            self._flush_network_errors()

            running, actions = self.view.handle_events(
                state=self.network_client.match_state,
                my_player_id=self.network_client.player_id,
            )
            self._apply_actions(actions)
            self.view.render(
                player_name=self.network_client.player_name,
                my_player_id=self.network_client.player_id,
                state=self.network_client.match_state,
            )

    def _flush_network_errors(self) -> None:
        for error in self.network_client.pop_errors():
            self.view.show_error(error)

    def _apply_actions(self, actions: list[ClientAction]) -> None:
        for action in actions:
            if isinstance(action, PlaceTowerAction):
                self.network_client.place_tower(
                    action.tower_type,
                    action.tile_x,
                    action.tile_y,
                )
            elif isinstance(action, SellTowerAction):
                try:
                    self.network_client.sell_tower_at(action.tile_x, action.tile_y)
                except ValueError as error:
                    self.view.show_error(str(error))
            elif isinstance(action, SkipBuildAction):
                self.network_client.skip_build()
            elif isinstance(action, AdjustPressureUnitsAction):
                self._apply_pressure_units_delta(action)
            elif isinstance(action, TogglePressureModifierAction):
                self._apply_pressure_modifier_toggle(action)

    def _apply_pressure_units_delta(self, action: AdjustPressureUnitsAction) -> None:
        state = self.network_client.match_state
        player_id = self.network_client.player_id
        if state is None or player_id is None:
            return
        if state.phase != MatchPhase.BUILD:
            return

        player = state.players.get(player_id)
        if player is None:
            return

        unit_counts = player.outgoing_pressure.unit_counts.copy()
        modifiers = set(player.outgoing_pressure.modifiers)
        current_count = unit_counts.get(action.enemy_kind, 0)
        unit_counts[action.enemy_kind] = max(0, current_count + action.delta)
        self.network_client.configure_pressure(unit_counts, modifiers)

    def _apply_pressure_modifier_toggle(self, action: TogglePressureModifierAction) -> None:
        state = self.network_client.match_state
        player_id = self.network_client.player_id
        if state is None or player_id is None:
            return
        if state.phase != MatchPhase.BUILD:
            return

        player = state.players.get(player_id)
        if player is None:
            return

        unit_counts = player.outgoing_pressure.unit_counts.copy()
        modifiers = set(player.outgoing_pressure.modifiers)
        if action.modifier in modifiers:
            modifiers.remove(action.modifier)
        else:
            modifiers.add(action.modifier)
        self.network_client.configure_pressure(unit_counts, modifiers)

    def _disconnect_network_client(self) -> None:
        if self.network_client is None:
            return
        self.network_client.disconnect()
        self.network_client = None
