from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from game.commands import GameCommand
from game.systems.match_engine import MatchEngine
from network.game_over_packet import GameOverPacket
from network.game_state_packet import GameStatePacket
from shared.models.game_rules import MatchPhase
from shared.serialization import serialize_match_state


class MatchRunner:
    def __init__(
        self,
        player_names: list[str],
        broadcaster: Callable[[object], None],
        send_error: Callable[[str, str], None],
    ) -> None:
        self._engine = MatchEngine(player_names=player_names)
        self._broadcast = broadcaster
        self._send_error = send_error
        self._command_queue: queue.Queue[tuple[str, GameCommand]] = queue.Queue()
        self._state_lock = threading.Lock()
        self._game_thread: threading.Thread | None = None

    @property
    def is_finished(self) -> bool:
        with self._state_lock:
            return self._engine.state.phase == MatchPhase.FINISHED

    def start(self, running_event: threading.Event) -> None:
        if self._game_thread is not None and self._game_thread.is_alive():
            return

        self._game_thread = threading.Thread(
            target=self._game_loop,
            args=(running_event,),
            daemon=True,
        )
        self._game_thread.start()

    def enqueue_command(self, player_id: str, command: GameCommand) -> None:
        self._command_queue.put((player_id, command))

    def finish_due_to_disconnect(self, connected_player_ids: list[str]) -> None:
        with self._state_lock:
            self._engine.finish_due_to_disconnect(connected_player_ids)

    def _game_loop(self, running_event: threading.Event) -> None:
        tick_interval = 1.0 / self._engine.state.tick_rate_hz

        while running_event.is_set() and not self.is_finished:
            frame_start = time.monotonic()
            self._drain_commands()

            with self._state_lock:
                if self._engine.state.phase == MatchPhase.FINISHED:
                    break

                self._engine.tick(1)
                state_data = serialize_match_state(self._engine.state)

            self._broadcast(GameStatePacket(state=state_data))

            elapsed = time.monotonic() - frame_start
            sleep_time = tick_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        if self.is_finished:
            with self._state_lock:
                state_data = serialize_match_state(self._engine.state)
                winner_player_id = self._engine.state.winner_player_id or ""
                is_draw = self._engine.state.is_draw

            self._broadcast(GameStatePacket(state=state_data))
            self._broadcast(
                GameOverPacket(
                    winner_player_id=winner_player_id,
                    is_draw=is_draw,
                )
            )
            print("Match finished.")

    def _drain_commands(self) -> None:
        while True:
            try:
                player_id, command = self._command_queue.get_nowait()
            except queue.Empty:
                return

            try:
                with self._state_lock:
                    self._engine.apply_command(player_id, command)
            except ValueError as error:
                error_message = str(error)
                self._send_error(player_id, error_message)
