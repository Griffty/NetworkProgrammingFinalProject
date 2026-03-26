from __future__ import annotations

import time

import pygame

from client.game_client import GameClient
from client.pixel_text import PixelTextRenderer
from shared.models import MatchPhase, PlayerState, TowerKind
from shared.models.board import DEFAULT_BOARD_LAYOUT


class BoardView:
    def __init__(self, player_id: str, left: int, top: int, size: int) -> None:
        self.player_id = player_id
        self.left = left
        self.top = top
        self.size = size

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.left, self.top, self.size, self.size)


class PygameNetworkClient:
    _BACKGROUND = (18, 22, 26)
    _PANEL = (28, 34, 40)
    _BOARD = (48, 56, 64)
    _GRID = (60, 68, 76)
    _PATH = (120, 84, 48)
    _PATH_EDGE = (170, 128, 76)
    _TEXT = (225, 230, 235)
    _SUBTEXT = (170, 178, 188)
    _ERROR = (214, 88, 88)
    _SUCCESS = (96, 184, 122)
    _WAITING = (180, 180, 100)
    _PLAYER_COLORS = {
        "player_1": (94, 176, 255),
        "player_2": (255, 138, 92),
    }
    _TOWER_COLORS = {
        TowerKind.MINIGUN: (80, 196, 120),
        TowerKind.RAILGUN: (242, 214, 84),
        TowerKind.PULSE: (192, 132, 255),
    }
    _ENEMY_COLORS = {
        "runner": (244, 105, 105),
        "brute": (222, 143, 66),
        "guard": (130, 212, 212),
    }
    _TOWER_LABELS = {
        pygame.K_1: TowerKind.MINIGUN,
        pygame.K_2: TowerKind.RAILGUN,
        pygame.K_3: TowerKind.PULSE,
    }

    def __init__(
        self,
        host: str,
        port: int,
        player_name: str,
    ) -> None:
        self.client = GameClient(host=host, port=port, player_name=player_name)
        self.selected_tower = TowerKind.MINIGUN
        self.tile_size = 8
        self.board_layout = DEFAULT_BOARD_LAYOUT
        self.board_size = self.board_layout.width * self.tile_size

        self.left_board = BoardView("player_1", 24, 96, self.board_size)
        self.right_board = BoardView(
            "player_2",
            self.left_board.left + self.board_size + 28,
            96,
            self.board_size,
        )
        self.window_size = (
            self.right_board.left + self.board_size + 24,
            self.left_board.top + self.board_size + 210,
        )
        self.status_message = ""
        self.status_color = self._SUBTEXT
        self.status_timeout = 0.0

    def run(self) -> None:
        if not self.client.connect():
            print("Failed to connect to server.")
            return

        print("Connected. Waiting for match to start...")

        # Wait for GameStartPacket
        timeout = 120.0
        start = time.monotonic()
        while self.client.my_player_id is None and self.client.connected:
            time.sleep(0.1)
            if time.monotonic() - start > timeout:
                print("Timed out waiting for match to start.")
                self.client.disconnect()
                return

        if not self.client.connected:
            print("Disconnected while waiting.")
            return

        print(f"Match started! Playing as {self.client.my_player_id}")

        pygame.init()
        pygame.display.set_caption(
            f"Space Legion TD - {self.client.player_name} ({self.client.my_player_id})"
        )
        screen = pygame.display.set_mode(self.window_size)
        clock = pygame.time.Clock()
        small_text = PixelTextRenderer(pixel_size=2, letter_spacing=1)
        large_text = PixelTextRenderer(pixel_size=3, letter_spacing=1)

        running = True
        while running and self.client.connected:
            frame_seconds = clock.tick(60) / 1000.0

            if self.status_timeout > 0.0:
                self.status_timeout = max(0.0, self.status_timeout - frame_seconds)
                if self.status_timeout == 0.0:
                    self.status_message = ""

            errors = self.client.pop_errors()
            for err in errors:
                self._set_status(err, self._ERROR)

            running = self._handle_events()
            self._draw(screen, small_text, large_text)
            pygame.display.flip()

        pygame.quit()
        self.client.disconnect()

    def _handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_SPACE:
                    state = self.client.latest_state
                    if state is not None and state.phase == MatchPhase.BUILD:
                        self.client.send_skip_build()
                        self._set_status("Ready! Waiting for opponent...", self._SUCCESS)
                elif event.key in self._TOWER_LABELS:
                    self.selected_tower = self._TOWER_LABELS[event.key]
                    self._set_status(
                        f"Selected {self.selected_tower.value} tower.",
                        self._SUCCESS,
                    )

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_position = pygame.mouse.get_pos()
                placement = self._mouse_to_board(mouse_position)
                if placement is None:
                    continue

                board_player_id, tile_x, tile_y = placement

                # Only allow actions on your own board
                if board_player_id != self.client.my_player_id:
                    self._set_status("You can only build on your own board.", self._ERROR)
                    continue

                if event.button == 1:
                    self.client.send_place_tower(self.selected_tower, tile_x, tile_y)
                elif event.button == 3:
                    self._handle_sell_tower(tile_x, tile_y)

        return True

    def _handle_sell_tower(self, tile_x: int, tile_y: int) -> None:
        state = self.client.latest_state
        if state is None or self.client.my_player_id is None:
            return

        player = state.players.get(self.client.my_player_id)
        if player is None:
            return

        tower_id = next(
            (
                t.tower_id
                for t in player.towers.values()
                if t.tile_x == tile_x and t.tile_y == tile_y
            ),
            None,
        )
        if tower_id is None:
            self._set_status("No tower on that tile to sell.", self._ERROR)
            return

        self.client.send_sell_tower(tower_id)

    def _mouse_to_board(self, mouse_position: tuple[int, int]) -> tuple[str, int, int] | None:
        mouse_x, mouse_y = mouse_position
        for board_view in (self.left_board, self.right_board):
            if not board_view.rect.collidepoint(mouse_position):
                continue
            tile_x = (mouse_x - board_view.left) // self.tile_size
            tile_y = (mouse_y - board_view.top) // self.tile_size
            return (board_view.player_id, tile_x, tile_y)
        return None

    def _draw(
        self,
        screen: pygame.Surface,
        small_text: PixelTextRenderer,
        large_text: PixelTextRenderer,
    ) -> None:
        screen.fill(self._BACKGROUND)

        state = self.client.latest_state
        if state is None:
            large_text.draw(
                screen,
                "Waiting for game state...",
                (24, 200),
                self._WAITING,
                scale=1,
            )
            return

        self._draw_header(screen, state, small_text, large_text)

        p1 = state.players.get("player_1")
        p2 = state.players.get("player_2")
        if p1 is not None:
            self._draw_board(screen, self.left_board, p1, small_text)
        if p2 is not None:
            self._draw_board(screen, self.right_board, p2, small_text)

        self._draw_footer(screen, state, small_text)

    def _draw_header(
        self,
        screen: pygame.Surface,
        state,
        small_text: PixelTextRenderer,
        large_text: PixelTextRenderer,
    ) -> None:
        header_lines = [
            f"Space Legion TD - {self.client.player_name}",
            f"Phase: {state.phase.value}",
            f"Wave: {state.current_wave_number}",
        ]
        if state.phase == MatchPhase.BUILD:
            header_lines.append(
                f"Build timer: {state.phase_time_remaining_seconds:0.1f}s"
            )
        if state.phase == MatchPhase.FINISHED:
            if state.winner_player_id is not None:
                winner = state.players.get(state.winner_player_id)
                winner_name = winner.name if winner else state.winner_player_id
                header_lines.append(f"Winner: {winner_name}")
            elif state.is_draw:
                header_lines.append("Winner: draw")

        x = 24
        y = 18
        large_text.draw(screen, header_lines[0], (x, y), self._TEXT, scale=1)
        y += 30
        for line in header_lines[1:]:
            small_text.draw(screen, line, (x, y), self._TEXT, scale=1)
            y += 24

        controls = "1 2 3 SELECT  LEFT PLACE  RIGHT SELL  SPACE SKIP  ESC QUIT"
        small_text.draw(screen, controls, (24, 74), self._SUBTEXT, scale=1)

        tower_label = f"Selected tower: {self.selected_tower.value}"
        small_text.draw(screen, tower_label, (820, 24), self._SUCCESS, scale=1)

        my_id = self.client.my_player_id or "?"
        small_text.draw(screen, f"You: {my_id}", (820, 48), self._SUBTEXT, scale=1)

        if self.status_message:
            small_text.draw(screen, self.status_message, (820, 74), self.status_color, scale=1)

    def _draw_board(
        self,
        screen: pygame.Surface,
        board_view: BoardView,
        player: PlayerState,
        small_text: PixelTextRenderer,
    ) -> None:
        board_rect = board_view.rect
        is_mine = board_view.player_id == self.client.my_player_id
        panel_rect = board_rect.inflate(12, 44)

        if is_mine:
            pygame.draw.rect(screen, (35, 45, 55), panel_rect, border_radius=6)
        else:
            pygame.draw.rect(screen, self._PANEL, panel_rect, border_radius=6)

        pygame.draw.rect(screen, self._BOARD, board_rect)

        for tile_x in range(self.board_layout.width):
            for tile_y in range(self.board_layout.height):
                pixel_x = board_view.left + (tile_x * self.tile_size)
                pixel_y = board_view.top + (tile_y * self.tile_size)
                tile_rect = pygame.Rect(pixel_x, pixel_y, self.tile_size, self.tile_size)
                if self.board_layout.is_path_tile(tile_x, tile_y):
                    pygame.draw.rect(screen, self._PATH, tile_rect)
                    pygame.draw.rect(screen, self._PATH_EDGE, tile_rect, 1)
                else:
                    pygame.draw.rect(screen, self._GRID, tile_rect, 1)

        if is_mine:
            self._draw_hover(screen, board_view)

        self._draw_spawn_markers(screen, board_view)
        self._draw_towers(screen, board_view, player)
        self._draw_enemies(screen, board_view, player)

        label = f"{player.name} {'(YOU)' if is_mine else ''}"
        small_text.draw(screen, label, (board_view.left, board_view.top - 28), self._TEXT, scale=1)
        small_text.draw(
            screen,
            f"GOLD {player.gold}  LIVES {player.lives}  KILLS {player.total_kills}",
            (board_view.left + 120, board_view.top - 28),
            self._SUBTEXT,
            scale=1,
        )

    def _draw_hover(self, screen: pygame.Surface, board_view: BoardView) -> None:
        placement = self._mouse_to_board(pygame.mouse.get_pos())
        if placement is None or placement[0] != board_view.player_id:
            return

        _, tile_x, tile_y = placement
        color = (
            self._SUCCESS
            if self.board_layout.is_buildable_tile(tile_x, tile_y)
            else self._ERROR
        )
        hover_rect = pygame.Rect(
            board_view.left + (tile_x * self.tile_size),
            board_view.top + (tile_y * self.tile_size),
            self.tile_size,
            self.tile_size,
        )
        pygame.draw.rect(screen, color, hover_rect, 2)

    def _draw_spawn_markers(self, screen: pygame.Surface, board_view: BoardView) -> None:
        spawn_x, spawn_y = self.board_layout.spawn_tile
        leak_x, leak_y = self.board_layout.leak_tile
        spawn_rect = pygame.Rect(
            board_view.left + (spawn_x * self.tile_size),
            board_view.top + (spawn_y * self.tile_size),
            self.tile_size,
            self.tile_size,
        )
        leak_rect = pygame.Rect(
            board_view.left + (leak_x * self.tile_size),
            board_view.top + (leak_y * self.tile_size),
            self.tile_size,
            self.tile_size,
        )
        pygame.draw.rect(screen, (90, 200, 110), spawn_rect, 2)
        pygame.draw.rect(screen, (220, 84, 84), leak_rect, 2)

    def _draw_towers(
        self,
        screen: pygame.Surface,
        board_view: BoardView,
        player: PlayerState,
    ) -> None:
        for tower in player.towers.values():
            center_x = board_view.left + int((tower.tile_x + 0.5) * self.tile_size)
            center_y = board_view.top + int((tower.tile_y + 0.5) * self.tile_size)
            color = self._TOWER_COLORS[tower.tower_type]

            if tower.tower_type == TowerKind.MINIGUN:
                pygame.draw.circle(screen, color, (center_x, center_y), 3)
            elif tower.tower_type == TowerKind.RAILGUN:
                points = [
                    (center_x, center_y - 4),
                    (center_x - 4, center_y + 4),
                    (center_x + 4, center_y + 4),
                ]
                pygame.draw.polygon(screen, color, points)
            else:
                rect = pygame.Rect(center_x - 4, center_y - 4, 8, 8)
                pygame.draw.rect(screen, color, rect, border_radius=2)

    def _draw_enemies(
        self,
        screen: pygame.Surface,
        board_view: BoardView,
        player: PlayerState,
    ) -> None:
        for enemy in player.current_wave.active_enemies:
            color = self._ENEMY_COLORS[enemy.enemy_type.value]
            center = (
                board_view.left + int(enemy.position_x * self.tile_size),
                board_view.top + int(enemy.position_y * self.tile_size),
            )
            pygame.draw.circle(screen, color, center, 4)
            self._draw_enemy_health(screen, center, enemy.current_hp, enemy.max_hp)

    def _draw_enemy_health(
        self,
        screen: pygame.Surface,
        center: tuple[int, int],
        current_hp: float,
        max_hp: float,
    ) -> None:
        if max_hp <= 0:
            return
        bar_width = 10
        bar_height = 2
        left = center[0] - (bar_width // 2)
        top = center[1] - 8
        background = pygame.Rect(left, top, bar_width, bar_height)
        pygame.draw.rect(screen, (38, 42, 46), background)
        fill_ratio = max(0.0, min(1.0, current_hp / max_hp))
        foreground = pygame.Rect(left, top, int(bar_width * fill_ratio), bar_height)
        pygame.draw.rect(screen, (110, 230, 140), foreground)

    def _draw_footer(
        self,
        screen: pygame.Surface,
        state,
        small_text: PixelTextRenderer,
    ) -> None:
        footer_top = self.left_board.top + self.board_size + 22
        footer_rect = pygame.Rect(24, footer_top, self.window_size[0] - 48, 160)
        pygame.draw.rect(screen, self._PANEL, footer_rect, border_radius=6)

        # Player summaries
        y = footer_top + 14
        for pid, player in state.players.items():
            is_mine = pid == self.client.my_player_id
            marker = " (YOU)" if is_mine else ""
            line = f"{player.name}{marker}: Gold {player.gold}  Lives {player.lives}  Kills {player.total_kills}  Waves {player.completed_waves}"
            small_text.draw(screen, line, (36, y), self._TEXT, scale=1)
            y += 22

        small_text.draw(screen, "RECENT EVENTS", (520, footer_top + 14), self._TEXT, scale=1)
        for index, event in enumerate(state.recent_events[-6:]):
            small_text.draw(
                screen,
                event,
                (520, footer_top + 40 + (index * 20)),
                self._SUBTEXT,
                scale=1,
            )

    def _set_status(self, message: str, color: tuple[int, int, int]) -> None:
        self.status_message = message
        self.status_color = color
        self.status_timeout = 3.0
