"""Top-level pygame client flow controller."""

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
from game.match_state import MatchState
from shared.models.game_rules import MatchPhase


class PygameClient:
    """Coordinate lobby UI, gameplay UI, and the network client."""

    def __init__(self, host: str, port: int, player_name: str = "Player1") -> None:
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
        """Run the lobby and match loops until the user exits."""

        while True:
            if not self._run_lobby():
                return

            assert self.network_client is not None
            self.lobby_view.close()
            self.view.open(
                player_name=self.network_client.player_name,
                my_player_id=self.network_client.player_id,
            )
            try:
                go_back_to_lobby = self._run_main_loop()
            finally:
                self.view.close()
                self._disconnect_network_client()

            if not go_back_to_lobby:
                return

    def _run_lobby(self) -> bool:
        """Process the connect lobby until a match starts or the user quits."""

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
        """Apply a lobby connect action and create a fresh network client."""

        if self.network_client is not None and self.network_client.is_connected:
            self._disconnect_network_client()
            self.lobby_view.set_status(
                "Disconnected active session. Press Connect to join again.",
                self.lobby_view.waiting_color,
            )
            return

        self._disconnect_network_client()

        candidate = GameClient(
            host=action.host,
            port=action.port,
            player_name=action.player_name,
        )
        if not candidate.connect():
            error_message = candidate.connect_error_message.strip()
            self.lobby_view.set_status(
                error_message or f"Failed to connect to {action.host}:{action.port}.",
                self.lobby_view.error_color,
            )
            return

        self.network_client = candidate
        self.lobby_view.set_status(
            f"Connected to {action.host}:{action.port}",
            self.lobby_view.success_color,
        )

    def _run_main_loop(self) -> bool:
        """Run the in-match UI until exit or return-to-lobby."""

        assert self.network_client is not None
        running = True
        last_state: MatchState | None = None

        while running:
            frame_seconds = self.view.next_frame()
            self.view.update(frame_seconds)
            self._flush_network_errors()

            state = self.network_client.match_state
            if state is not None:
                last_state = state

            match_end_state = self._resolve_match_end_state(last_state)
            if match_end_state is not None:
                running, play_again = self.view.handle_post_match_events()
                self.view.render(
                    player_name=self.network_client.player_name,
                    my_player_id=self.network_client.player_id,
                    state=last_state,
                    match_end_state=match_end_state,
                )
                if not running:
                    return False
                if play_again:
                    return True
                continue

            running, actions = self.view.handle_events(
                state=state,
                my_player_id=self.network_client.player_id,
            )
            if not running:
                return False

            if self.network_client.is_connected:
                self._apply_actions(actions)
            self.view.render(
                player_name=self.network_client.player_name,
                my_player_id=self.network_client.player_id,
                state=state,
            )

        return False

    def _flush_network_errors(self) -> None:
        """Move queued network errors into the view status area."""

        for error in self.network_client.pop_errors():
            self.view.show_error(error)

    def _apply_actions(self, actions: list[ClientAction]) -> None:
        """Translate view actions into network requests."""

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
        """Update the current outgoing pressure unit counts locally."""

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
        """Toggle one outgoing pressure modifier for the active player."""

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
        """Disconnect and discard the current network client, if any."""

        if self.network_client is None:
            return
        self.network_client.disconnect()
        self.network_client = None

    def _resolve_match_end_state(
        self,
        last_state: MatchState | None,
    ) -> tuple[str, str] | None:
        """Return the post-match overlay text for the current session state."""

        assert self.network_client is not None

        is_finished = self.network_client.game_over
        winner_player_id = self.network_client.game_over_winner
        is_draw = self.network_client.game_over_is_draw

        if last_state is not None and last_state.phase == MatchPhase.FINISHED:
            is_finished = True
            winner_player_id = winner_player_id or last_state.winner_player_id
            is_draw = is_draw or last_state.is_draw

        if is_finished:
            if is_draw:
                return ("Draw", "Match ended in a draw. Play again?")

            if winner_player_id is not None and last_state is not None:
                winner_player = last_state.players.get(winner_player_id)
                winner_name = winner_player.name if winner_player is not None else winner_player_id
            else:
                winner_name = winner_player_id or "Unknown"

            if winner_player_id == self.network_client.player_id:
                return ("You Win", "You won the match. Play again?")

            return ("You Lose", f"{winner_name} won the match. Play again?")

        if not self.network_client.is_connected:
            return ("Disconnected", "Connection closed. Return to lobby?")

        return None
