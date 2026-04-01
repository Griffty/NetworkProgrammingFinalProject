from __future__ import annotations

from dataclasses import dataclass

import pygame

from game.match_state import MatchState
from game.towers.abstract_tower import TowerShape
from game.towers.registry import get_tower
from shared.models.board import DEFAULT_BOARD_LAYOUT
from shared.models.game_rules import (
    ENEMY_DEFINITIONS,
    MODIFIER_DEFINITIONS,
    EnemyKind,
    MatchPhase,
    OffensiveModifier,
    TowerKind,
)
from shared.models.state import PlayerState

Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class BoardView:
    player_id: str
    left: int
    top: int
    size: int

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.left, self.top, self.size, self.size)


@dataclass(frozen=True, slots=True)
class PlaceTowerAction:
    tower_type: TowerKind
    tile_x: int
    tile_y: int


@dataclass(frozen=True, slots=True)
class SellTowerAction:
    tile_x: int
    tile_y: int


@dataclass(frozen=True, slots=True)
class SkipBuildAction:
    pass


@dataclass(frozen=True, slots=True)
class AdjustPressureUnitsAction:
    enemy_kind: EnemyKind
    delta: int


@dataclass(frozen=True, slots=True)
class TogglePressureModifierAction:
    modifier: OffensiveModifier


ClientAction = (
    PlaceTowerAction
    | SellTowerAction
    | SkipBuildAction
    | AdjustPressureUnitsAction
    | TogglePressureModifierAction
)


@dataclass(frozen=True, slots=True)
class UiFonts:
    title: pygame.font.Font
    section: pygame.font.Font
    body: pygame.font.Font
    small: pygame.font.Font
    mono: pygame.font.Font


class PygameClientView:
    _BACKGROUND = (11, 16, 22)
    _PANEL = (21, 30, 40)
    _PANEL_BORDER = (43, 58, 72)
    _BOARD = (38, 50, 63)
    _GRID = (57, 71, 86)
    _PATH = (141, 104, 56)
    _PATH_EDGE = (197, 151, 89)
    _TEXT = (233, 239, 244)
    _SUBTEXT = (166, 180, 194)
    _ACCENT = (88, 164, 255)
    _ERROR = (214, 88, 88)
    _SUCCESS = (98, 200, 134)
    _WAITING = (210, 179, 94)
    _OVERLAY_SCRIM = (8, 12, 18, 178)
    _OVERLAY_PANEL = (20, 30, 40)
    _OVERLAY_BORDER = (68, 96, 122)
    _OVERLAY_BUTTON = (54, 110, 170)
    _OVERLAY_BUTTON_HOVER = (75, 136, 196)
    _OVERLAY_DANGER = (118, 62, 62)
    _OVERLAY_DANGER_HOVER = (148, 78, 78)
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
    _PRESSURE_UNIT_ORDER = (
        EnemyKind.RUNNER,
        EnemyKind.BRUTE,
        EnemyKind.GUARD,
    )
    _PRESSURE_MODIFIER_ORDER = (
        OffensiveModifier.REINFORCE,
        OffensiveModifier.HASTE,
        OffensiveModifier.REINFORCEMENTS,
    )
    _PRESSURE_MODIFIER_LABELS = {
        OffensiveModifier.REINFORCE: "Reinforce",
        OffensiveModifier.HASTE: "Haste",
        OffensiveModifier.REINFORCEMENTS: "+10 Units",
    }
    _PRESSURE_UNIT_KEYS = {
        pygame.K_q: (EnemyKind.RUNNER, +1),
        pygame.K_a: (EnemyKind.RUNNER, -1),
        pygame.K_w: (EnemyKind.BRUTE, +1),
        pygame.K_s: (EnemyKind.BRUTE, -1),
        pygame.K_e: (EnemyKind.GUARD, +1),
        pygame.K_d: (EnemyKind.GUARD, -1),
    }
    _PRESSURE_MODIFIER_KEYS = {
        pygame.K_z: OffensiveModifier.REINFORCE,
        pygame.K_x: OffensiveModifier.HASTE,
        pygame.K_c: OffensiveModifier.REINFORCEMENTS,
    }

    def __init__(self) -> None:
        self.selected_tower = TowerKind.MINIGUN
        self.tile_size = 8
        self.board_layout = DEFAULT_BOARD_LAYOUT
        self.board_size = self.board_layout.width * self.tile_size
        self.left_board = BoardView("player_1", 24, 172, self.board_size)
        self.right_board = BoardView(
            "player_2",
            self.left_board.left + self.board_size + 28,
            172,
            self.board_size,
        )
        self.base_window_size = (
            self.right_board.left + self.board_size + 24,
            self.left_board.top + self.board_size + 252,
        )
        self.window_size = self.base_window_size
        self.status_message = ""
        self.status_color = self._SUBTEXT
        self.status_timeout = 0.0
        self._screen: pygame.Surface | None = None
        self._scene_surface: pygame.Surface | None = None
        self._clock: pygame.time.Clock | None = None
        self._fonts: UiFonts | None = None

    def open(self, player_name: str, my_player_id: str | None) -> None:
        pygame.init()
        pygame.display.set_caption(
            f"Space Legion TD - {player_name} ({my_player_id or '?'})"
        )
        self._screen = pygame.display.set_mode(self.base_window_size, pygame.RESIZABLE)
        self.window_size = self._screen.get_size()
        self._scene_surface = pygame.Surface(self.base_window_size)
        self._clock = pygame.time.Clock()
        self._fonts = UiFonts(
            title=pygame.font.SysFont("dejavusans", 42, bold=True),
            section=pygame.font.SysFont("dejavusans", 26, bold=True),
            body=pygame.font.SysFont("dejavusans", 22),
            small=pygame.font.SysFont("dejavusans", 18),
            mono=pygame.font.SysFont("dejavusansmono", 17),
        )

    def close(self) -> None:
        pygame.quit()

    def next_frame(self) -> float:
        assert self._clock is not None
        return self._clock.tick(60) / 1000.0

    def update(self, frame_seconds: float) -> None:
        if self.status_timeout > 0.0:
            self.status_timeout = max(0.0, self.status_timeout - frame_seconds)
            if self.status_timeout == 0.0:
                self.status_message = ""

    def handle_events(
        self,
        state: MatchState | None,
        my_player_id: str | None,
    ) -> tuple[bool, list[ClientAction]]:
        actions: list[ClientAction] = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, actions

            if event.type == pygame.VIDEORESIZE:
                self.window_size = (event.w, event.h)
                current_screen = pygame.display.get_surface()
                if current_screen is not None:
                    self._screen = current_screen
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False, actions
                if event.key == pygame.K_SPACE:
                    if state is not None and state.phase == MatchPhase.BUILD:
                        actions.append(SkipBuildAction())
                        self.set_status("Ready! Waiting for opponent...", self._SUCCESS)
                elif event.key in self._TOWER_LABELS:
                    self.selected_tower = self._TOWER_LABELS[event.key]
                    self.set_status(
                        f"Selected {self.selected_tower.value} tower.",
                        self._SUCCESS,
                    )
                elif (
                    state is not None
                    and state.phase == MatchPhase.BUILD
                    and event.key in self._PRESSURE_UNIT_KEYS
                ):
                    enemy_kind, delta = self._PRESSURE_UNIT_KEYS[event.key]
                    actions.append(AdjustPressureUnitsAction(enemy_kind=enemy_kind, delta=delta))
                elif (
                    state is not None
                    and state.phase == MatchPhase.BUILD
                    and event.key in self._PRESSURE_MODIFIER_KEYS
                ):
                    actions.append(
                        TogglePressureModifierAction(
                            modifier=self._PRESSURE_MODIFIER_KEYS[event.key]
                        )
                    )

            if event.type == pygame.MOUSEBUTTONDOWN:
                virtual_mouse = self._screen_to_virtual(event.pos)
                if virtual_mouse is None:
                    continue

                if event.button == 1:
                    pressure_action = self._pressure_action_from_click(
                        virtual_mouse,
                        state,
                        my_player_id,
                    )
                    if pressure_action is not None:
                        actions.append(pressure_action)
                        continue

                placement = self._mouse_to_board(virtual_mouse)
                if placement is None:
                    continue

                board_player_id, tile_x, tile_y = placement
                if my_player_id is None:
                    self.set_status("Waiting for player assignment.", self._ERROR)
                    continue

                if board_player_id != my_player_id:
                    self.set_status("You can only build on your own board.", self._ERROR)
                    continue

                if event.button == 1:
                    actions.append(
                        PlaceTowerAction(
                            tower_type=self.selected_tower,
                            tile_x=tile_x,
                            tile_y=tile_y,
                        )
                    )
                elif event.button == 3:
                    actions.append(SellTowerAction(tile_x=tile_x, tile_y=tile_y))

        return True, actions

    def render(
        self,
        player_name: str,
        my_player_id: str | None,
        state: MatchState | None,
        match_end_state: tuple[str, str] | None = None,
    ) -> None:
        assert self._screen is not None
        assert self._scene_surface is not None
        assert self._fonts is not None

        screen = self._screen
        self.window_size = screen.get_size()
        scene = self._scene_surface
        fonts = self._fonts

        scene.fill(self._BACKGROUND)

        if state is None:
            self._draw_text(
                scene,
                "Waiting for game state...",
                (40, 220),
                fonts.title,
                self._WAITING,
            )
        else:
            self._draw_header(scene, state, player_name, my_player_id, fonts)

            player_1 = state.players.get("player_1")
            player_2 = state.players.get("player_2")
            if player_1 is not None:
                self._draw_board(scene, self.left_board, player_1, my_player_id, fonts)
            if player_2 is not None:
                self._draw_board(scene, self.right_board, player_2, my_player_id, fonts)
            self._draw_pressure_panel(scene, state, my_player_id, fonts)

        if match_end_state is not None:
            self._draw_match_end_overlay(
                scene=scene,
                title=match_end_state[0],
                detail=match_end_state[1],
                fonts=fonts,
            )

        self._present_scene(scene, screen)

    def handle_post_match_events(self) -> tuple[bool, bool]:
        play_again = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, False

            if event.type == pygame.VIDEORESIZE:
                self.window_size = (event.w, event.h)
                current_screen = pygame.display.get_surface()
                if current_screen is not None:
                    self._screen = current_screen
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False, False
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    play_again = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                virtual_mouse = self._screen_to_virtual(event.pos)
                if virtual_mouse is None:
                    continue

                if self._overlay_play_again_button_rect().collidepoint(virtual_mouse):
                    play_again = True
                elif self._overlay_exit_button_rect().collidepoint(virtual_mouse):
                    return False, False

        return True, play_again

    def set_status(self, message: str, color: Color) -> None:
        self.status_message = message
        self.status_color = color
        self.status_timeout = 3.0

    def show_error(self, message: str) -> None:
        self.set_status(message, self._ERROR)

    def _mouse_to_board(self, mouse_position: tuple[int, int]) -> tuple[str, int, int] | None:
        mouse_x, mouse_y = mouse_position
        for board_view in (self.left_board, self.right_board):
            if not board_view.rect.collidepoint(mouse_position):
                continue
            tile_x = (mouse_x - board_view.left) // self.tile_size
            tile_y = (mouse_y - board_view.top) // self.tile_size
            return board_view.player_id, tile_x, tile_y
        return None

    def _draw_header(
        self,
        screen: pygame.Surface,
        state: MatchState,
        player_name: str,
        my_player_id: str | None,
        fonts: UiFonts,
    ) -> None:
        header_rect = pygame.Rect(20, 14, self.base_window_size[0] - 40, 94)
        pygame.draw.rect(screen, self._PANEL, header_rect, border_radius=12)
        pygame.draw.rect(
            screen,
            self._PANEL_BORDER,
            header_rect,
            width=1,
            border_radius=12,
        )

        self._draw_text(
            screen,
            "SPACE LEGION TD",
            (34, 22),
            fonts.section,
            self._TEXT,
        )
        self._draw_text(
            screen,
            f"Commander: {player_name}",
            (36, 53),
            fonts.small,
            self._SUBTEXT,
        )

        chip_x = 320
        self._draw_chip(
            screen,
            f"PHASE  {state.phase.value.upper()}",
            chip_x,
            24,
            self._ACCENT,
            fonts.small,
        )
        chip_x += 190
        self._draw_chip(
            screen,
            f"WAVE  {state.current_wave_number}",
            chip_x,
            24,
            (114, 170, 255),
            fonts.small,
        )
        chip_x += 140
        if state.phase == MatchPhase.BUILD:
            timer_label = f"BUILD  {state.phase_time_remaining_seconds:0.1f}s"
            timer_color = self._WAITING
        elif state.phase == MatchPhase.FINISHED:
            timer_label = "MATCH ENDED"
            timer_color = self._ERROR if not state.is_draw else self._WAITING
        else:
            timer_label = "COMBAT"
            timer_color = self._SUCCESS
        self._draw_chip(screen, timer_label, chip_x, 24, timer_color, fonts.small)

        header_hint = (
            f"Selected: {self.selected_tower.value.upper()}   "
            f"You: {my_player_id or '?'}   [1/2/3] towers, [Space] ready"
        )
        hint_surface = fonts.small.render(header_hint, True, self._SUBTEXT)
        min_hint_x = header_rect.left + 16
        preferred_hint_x = 500
        max_hint_x = header_rect.right - hint_surface.get_width() - 18
        hint_x = max(min_hint_x, min(preferred_hint_x, max_hint_x))
        hint_y = 66
        self._draw_text(screen, header_hint, (hint_x, hint_y), fonts.small, self._SUBTEXT)

        selected_label = f"Selected: {self.selected_tower.value.upper()}"
        self._draw_text(
            screen,
            selected_label,
            (hint_x, hint_y),
            fonts.small,
            self._SUCCESS,
        )

        if self.status_message:
            self._draw_text(
                screen,
                self.status_message,
                (34, 82),
                fonts.small,
                self.status_color,
            )

    def _draw_board(
        self,
        screen: pygame.Surface,
        board_view: BoardView,
        player: PlayerState,
        my_player_id: str | None,
        fonts: UiFonts,
    ) -> None:
        board_rect = board_view.rect
        is_mine = board_view.player_id == my_player_id
        panel_rect = board_rect.inflate(16, 72)
        panel_color = (29, 43, 55) if is_mine else self._PANEL

        pygame.draw.rect(
            screen,
            panel_color,
            panel_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            screen,
            self._PANEL_BORDER if not is_mine else self._ACCENT,
            panel_rect,
            width=2,
            border_radius=10,
        )
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

        if is_mine:
            self._draw_text(
                screen,
                f"{player.name} (YOU)",
                (board_view.left + 8, board_view.top - 34),
                fonts.small,
                self._TEXT,
            )
            self._draw_player_stats_with_icons(
                screen=screen,
                left=board_view.left + 148,
                baseline_y=board_view.top - 34,
                gold=player.gold,
                lives=player.lives,
                kills=player.total_kills,
                font=fonts.small,
            )
        else:
            self._draw_text(
                screen,
                "Opponent",
                (board_view.left + 8, board_view.top - 30),
                fonts.body,
                self._SUBTEXT,
            )

    def _draw_hover(self, screen: pygame.Surface, board_view: BoardView) -> None:
        mouse_position = self._screen_to_virtual(pygame.mouse.get_pos())
        if mouse_position is None:
            return
        placement = self._mouse_to_board(mouse_position)
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
            tower_model = get_tower(tower.tower_type)
            self._draw_tower_icon(
                screen=screen,
                center_x=center_x,
                center_y=center_y,
                shape=tower_model.presentation.shape,
                color=tower_model.presentation.color,
            )

    @staticmethod
    def _draw_tower_icon(
        screen: pygame.Surface,
        center_x: int,
        center_y: int,
        shape: TowerShape,
        color: Color,
    ) -> None:
        if shape == "circle":
            pygame.draw.circle(screen, color, (center_x, center_y), 3)
            return

        if shape == "triangle":
            points = [
                (center_x, center_y - 4),
                (center_x - 4, center_y + 4),
                (center_x + 4, center_y + 4),
            ]
            pygame.draw.polygon(screen, color, points)
            return

        if shape == "square":
            rect = pygame.Rect(center_x - 4, center_y - 4, 8, 8)
            pygame.draw.rect(screen, color, rect, border_radius=2)
            return

        raise ValueError(f"Unsupported tower shape: {shape}")

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

    def _draw_pressure_panel(
        self,
        screen: pygame.Surface,
        state: MatchState,
        my_player_id: str | None,
        fonts: UiFonts,
    ) -> None:
        panel = self._pressure_panel_rect()
        pygame.draw.rect(screen, self._PANEL, panel, border_radius=10)
        pygame.draw.rect(screen, self._PANEL_BORDER, panel, width=1, border_radius=10)

        self._draw_text(
            screen,
            "PRESSURE CONTROLS - NEXT WAVE",
            (panel.left + 12, panel.top + 7),
            fonts.small,
            self._TEXT,
        )

        player = state.players.get(my_player_id) if my_player_id is not None else None
        if player is None:
            self._draw_text(
                screen,
                "Waiting for player assignment...",
                (panel.left + 12, panel.top + 34),
                fonts.small,
                self._SUBTEXT,
            )
            return

        pressure = player.outgoing_pressure
        controls_enabled = state.phase == MatchPhase.BUILD
        unit_controls_top = panel.top + 74
        modifier_controls_top = unit_controls_top

        for index, enemy_kind in enumerate(self._PRESSURE_UNIT_ORDER):
            minus_rect, count_rect, plus_rect = self._pressure_unit_control_rects(
                panel,
                index,
                unit_controls_top,
            )
            enemy_label = enemy_kind.value.title()
            enemy_color = self._ENEMY_COLORS[enemy_kind.value]
            count = pressure.unit_counts.get(enemy_kind, 0)
            cost = ENEMY_DEFINITIONS[enemy_kind].point_cost

            self._draw_text(
                screen,
                f"{enemy_label} ({cost}pt)",
                (minus_rect.left, unit_controls_top - 26),
                fonts.small,
                enemy_color,
            )
            self._draw_pressure_button(
                screen=screen,
                rect=minus_rect,
                label="-",
                font=fonts.body,
                enabled=controls_enabled,
                active=False,
            )
            pygame.draw.rect(screen, (24, 42, 58), count_rect, border_radius=6)
            pygame.draw.rect(screen, self._PANEL_BORDER, count_rect, width=1, border_radius=6)
            count_text = fonts.small.render(str(count), True, self._TEXT)
            screen.blit(
                count_text,
                (
                    count_rect.centerx - (count_text.get_width() // 2),
                    count_rect.centery - (count_text.get_height() // 2),
                ),
            )
            self._draw_pressure_button(
                screen=screen,
                rect=plus_rect,
                label="+",
                font=fonts.body,
                enabled=controls_enabled,
                active=False,
            )

        for index, modifier in enumerate(self._PRESSURE_MODIFIER_ORDER):
            button_rect = self._pressure_modifier_rect(panel, index, modifier_controls_top)
            is_active = modifier in pressure.modifiers
            modifier_cost = MODIFIER_DEFINITIONS[modifier].cost
            label = f"{self._PRESSURE_MODIFIER_LABELS[modifier]} ({modifier_cost})"
            self._draw_pressure_button(
                screen=screen,
                rect=button_rect,
                label=label,
                font=fonts.small,
                enabled=controls_enabled,
                active=is_active,
            )

        next_wave_number = state.current_wave_number + 1
        spent_points = pressure.spent_points()
        available_points = pressure.available_points(next_wave_number)
        modifier_gold_cost = pressure.gold_cost()
        points_color = self._ERROR if spent_points > available_points else self._SUBTEXT

        info_left = panel.left + 12
        if controls_enabled:
            summary_text = f"Pts {spent_points}/{available_points}   Mod Gold {modifier_gold_cost}"
            self._draw_text(
                screen,
                summary_text,
                (info_left, panel.top + 146),
                fonts.small,
                points_color,
            )
            self._draw_text(
                screen,
                "Hotkeys: Q/A W/S E/D  |  Modifiers: Z/X/C",
                (info_left, panel.top + 168),
                fonts.small,
                self._SUBTEXT,
            )
        else:
            self._draw_text(
                screen,
                "Pressure editing is disabled outside BUILD phase.",
                (info_left, panel.top + 146),
                fonts.small,
                self._WAITING,
            )
            summary_text = f"Current plan: {spent_points}/{available_points} pts, Mod Gold {modifier_gold_cost}"
            self._draw_text(
                screen,
                summary_text,
                (info_left, panel.top + 168),
                fonts.small,
                self._SUBTEXT,
            )

    def _pressure_action_from_click(
        self,
        mouse_position: tuple[int, int],
        state: MatchState | None,
        my_player_id: str | None,
    ) -> ClientAction | None:
        if (
            state is None
            or my_player_id is None
            or state.phase != MatchPhase.BUILD
            or my_player_id not in state.players
        ):
            return None

        panel = self._pressure_panel_rect()
        if not panel.collidepoint(mouse_position):
            return None

        unit_controls_top = panel.top + 64
        modifier_controls_top = panel.top + 114

        for index, enemy_kind in enumerate(self._PRESSURE_UNIT_ORDER):
            minus_rect, _, plus_rect = self._pressure_unit_control_rects(
                panel,
                index,
                unit_controls_top,
            )
            if minus_rect.collidepoint(mouse_position):
                return AdjustPressureUnitsAction(enemy_kind=enemy_kind, delta=-1)
            if plus_rect.collidepoint(mouse_position):
                return AdjustPressureUnitsAction(enemy_kind=enemy_kind, delta=+1)

        for index, modifier in enumerate(self._PRESSURE_MODIFIER_ORDER):
            button_rect = self._pressure_modifier_rect(panel, index, modifier_controls_top)
            if button_rect.collidepoint(mouse_position):
                return TogglePressureModifierAction(modifier=modifier)

        return None

    def _pressure_panel_rect(self) -> pygame.Rect:
        top = self.left_board.top + self.board_size + 42
        height = self.base_window_size[1] - top - 10
        return pygame.Rect(20, top, self.base_window_size[0] - 40, height)

    @staticmethod
    def _pressure_unit_control_rects(
        panel: pygame.Rect,
        index: int,
        control_top: int,
    ) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        block_left = panel.left + 12 + (index * 166)
        minus_rect = pygame.Rect(block_left, control_top, 24, 24)
        count_rect = pygame.Rect(block_left + 30, control_top, 64, 24)
        plus_rect = pygame.Rect(block_left + 100, control_top, 24, 24)
        return minus_rect, count_rect, plus_rect

    @staticmethod
    def _pressure_modifier_rect(
        panel: pygame.Rect,
        index: int,
        control_top: int,
    ) -> pygame.Rect:
        return pygame.Rect(panel.left + 518 + (index * 156), control_top, 150, 26)

    def _draw_pressure_button(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        enabled: bool,
        active: bool,
    ) -> None:
        if not enabled:
            fill_color = (26, 34, 44)
            border_color = (58, 70, 82)
            text_color = (116, 128, 140)
        elif active:
            fill_color = (39, 84, 126)
            border_color = self._ACCENT
            text_color = self._TEXT
        else:
            fill_color = (24, 42, 58)
            border_color = self._PANEL_BORDER
            text_color = self._TEXT

        pygame.draw.rect(screen, fill_color, rect, border_radius=6)
        pygame.draw.rect(screen, border_color, rect, width=1, border_radius=6)
        label_surface = font.render(label, True, text_color)
        screen.blit(
            label_surface,
            (
                rect.centerx - (label_surface.get_width() // 2),
                rect.centery - (label_surface.get_height() // 2),
            ),
        )

    def _draw_player_stats_with_icons(
        self,
        screen: pygame.Surface,
        left: int,
        baseline_y: int,
        gold: int,
        lives: int,
        kills: int,
        font: pygame.font.Font,
    ) -> None:
        x = left
        x = self._draw_coin_stat(screen, x, baseline_y + 11, gold, font)
        x += 14
        x = self._draw_heart_stat(screen, x, baseline_y + 11, lives, font)
        x += 14
        self._draw_skull_stat(screen, x, baseline_y + 11, kills, font)

    def _draw_coin_stat(
        self,
        screen: pygame.Surface,
        left: int,
        center_y: int,
        value: int,
        font: pygame.font.Font,
    ) -> int:
        icon_center = (left + 7, center_y)
        pygame.draw.circle(screen, (218, 175, 66), icon_center, 7)
        pygame.draw.circle(screen, (255, 221, 120), icon_center, 4)
        label = font.render(str(value), True, self._TEXT)
        text_x = left + 18
        screen.blit(label, (text_x, center_y - (label.get_height() // 2)))
        return text_x + label.get_width()

    def _draw_heart_stat(
        self,
        screen: pygame.Surface,
        left: int,
        center_y: int,
        value: int,
        font: pygame.font.Font,
    ) -> int:
        base_y = center_y - 7
        pygame.draw.circle(screen, (229, 88, 102), (left + 5, base_y + 5), 5)
        pygame.draw.circle(screen, (229, 88, 102), (left + 11, base_y + 5), 5)
        pygame.draw.polygon(
            screen,
            (229, 88, 102),
            ((left, base_y + 7), (left + 16, base_y + 7), (left + 8, base_y + 15)),
        )
        label = font.render(str(value), True, self._TEXT)
        text_x = left + 20
        screen.blit(label, (text_x, center_y - (label.get_height() // 2)))
        return text_x + label.get_width()

    def _draw_skull_stat(
        self,
        screen: pygame.Surface,
        left: int,
        center_y: int,
        value: int,
        font: pygame.font.Font,
    ) -> int:
        base_y = center_y - 8
        skull_color = (210, 216, 224)
        pygame.draw.circle(screen, skull_color, (left + 8, base_y + 7), 7)
        pygame.draw.rect(screen, skull_color, pygame.Rect(left + 3, base_y + 10, 10, 6), border_radius=2)
        pygame.draw.circle(screen, (26, 35, 46), (left + 6, base_y + 7), 1)
        pygame.draw.circle(screen, (26, 35, 46), (left + 10, base_y + 7), 1)
        label = font.render(str(value), True, self._TEXT)
        text_x = left + 20
        screen.blit(label, (text_x, center_y - (label.get_height() // 2)))
        return text_x + label.get_width()

    @staticmethod
    def _draw_text(
        screen: pygame.Surface,
        text: str,
        position: tuple[int, int],
        font: pygame.font.Font,
        color: Color,
    ) -> None:
        surface = font.render(text, True, color)
        screen.blit(surface, position)

    def _draw_chip(
        self,
        screen: pygame.Surface,
        label: str,
        left: int,
        top: int,
        accent_color: Color,
        font: pygame.font.Font,
    ) -> None:
        text_surface = font.render(label, True, self._TEXT)
        chip_rect = pygame.Rect(
            left,
            top,
            text_surface.get_width() + 22,
            text_surface.get_height() + 10,
        )
        pygame.draw.rect(screen, (24, 40, 54), chip_rect, border_radius=8)
        pygame.draw.rect(screen, accent_color, chip_rect, width=1, border_radius=8)
        screen.blit(text_surface, (chip_rect.left + 11, chip_rect.top + 5))

    def _present_scene(
        self,
        scene: pygame.Surface,
        screen: pygame.Surface,
    ) -> None:
        viewport = self._virtual_viewport()
        screen.fill(self._BACKGROUND)
        scaled_scene = pygame.transform.scale(scene, viewport.size)
        screen.blit(scaled_scene, viewport.topleft)
        pygame.display.flip()

    def _virtual_viewport(self) -> pygame.Rect:
        base_width, base_height = self.base_window_size
        window_width, window_height = self.window_size
        if window_width <= 0 or window_height <= 0:
            return pygame.Rect(0, 0, base_width, base_height)

        scale = min(window_width / base_width, window_height / base_height)
        width = max(1, int(base_width * scale))
        height = max(1, int(base_height * scale))
        left = (window_width - width) // 2
        top = (window_height - height) // 2
        return pygame.Rect(left, top, width, height)

    def _screen_to_virtual(
        self,
        screen_position: tuple[int, int],
    ) -> tuple[int, int] | None:
        viewport = self._virtual_viewport()
        if not viewport.collidepoint(screen_position):
            return None

        base_width, base_height = self.base_window_size
        scale = viewport.width / base_width
        if scale <= 0:
            return None

        virtual_x = int((screen_position[0] - viewport.left) / scale)
        virtual_y = int((screen_position[1] - viewport.top) / scale)
        virtual_x = max(0, min(base_width - 1, virtual_x))
        virtual_y = max(0, min(base_height - 1, virtual_y))
        return virtual_x, virtual_y

    def _draw_match_end_overlay(
        self,
        scene: pygame.Surface,
        title: str,
        detail: str,
        fonts: UiFonts,
    ) -> None:
        overlay = pygame.Surface(self.base_window_size, pygame.SRCALPHA)
        overlay.fill(self._OVERLAY_SCRIM)
        scene.blit(overlay, (0, 0))

        panel_rect = self._overlay_panel_rect()
        pygame.draw.rect(scene, self._OVERLAY_PANEL, panel_rect, border_radius=14)
        pygame.draw.rect(scene, self._OVERLAY_BORDER, panel_rect, width=2, border_radius=14)

        title_surface = fonts.title.render(title, True, self._TEXT)
        scene.blit(
            title_surface,
            (
                panel_rect.centerx - (title_surface.get_width() // 2),
                panel_rect.top + 28,
            ),
        )

        detail_surface = fonts.body.render(detail, True, self._SUBTEXT)
        scene.blit(
            detail_surface,
            (
                panel_rect.centerx - (detail_surface.get_width() // 2),
                panel_rect.top + 92,
            ),
        )

        hint_surface = fonts.small.render(
            "Press Enter or click Play Again to return to lobby",
            True,
            self._SUBTEXT,
        )
        scene.blit(
            hint_surface,
            (
                panel_rect.centerx - (hint_surface.get_width() // 2),
                panel_rect.top + 122,
            ),
        )

        mouse_position = self._screen_to_virtual(pygame.mouse.get_pos())
        play_rect = self._overlay_play_again_button_rect()
        exit_rect = self._overlay_exit_button_rect()
        play_hovered = mouse_position is not None and play_rect.collidepoint(mouse_position)
        exit_hovered = mouse_position is not None and exit_rect.collidepoint(mouse_position)

        self._draw_overlay_button(
            scene=scene,
            rect=play_rect,
            label="Play Again",
            font=fonts.body,
            fill_color=self._OVERLAY_BUTTON_HOVER if play_hovered else self._OVERLAY_BUTTON,
        )
        self._draw_overlay_button(
            scene=scene,
            rect=exit_rect,
            label="Exit",
            font=fonts.body,
            fill_color=self._OVERLAY_DANGER_HOVER if exit_hovered else self._OVERLAY_DANGER,
        )

    def _overlay_panel_rect(self) -> pygame.Rect:
        width = 560
        height = 230
        left = (self.base_window_size[0] - width) // 2
        top = (self.base_window_size[1] - height) // 2
        return pygame.Rect(left, top, width, height)

    def _overlay_play_again_button_rect(self) -> pygame.Rect:
        panel = self._overlay_panel_rect()
        return pygame.Rect(panel.left + 86, panel.bottom - 62, 176, 40)

    def _overlay_exit_button_rect(self) -> pygame.Rect:
        panel = self._overlay_panel_rect()
        return pygame.Rect(panel.right - 86 - 176, panel.bottom - 62, 176, 40)

    @staticmethod
    def _draw_overlay_button(
        scene: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        fill_color: Color,
    ) -> None:
        pygame.draw.rect(scene, fill_color, rect, border_radius=8)
        pygame.draw.rect(scene, (212, 222, 232), rect, width=1, border_radius=8)
        text_surface = font.render(label, True, (235, 240, 245))
        scene.blit(
            text_surface,
            (
                rect.centerx - (text_surface.get_width() // 2),
                rect.centery - (text_surface.get_height() // 2),
            ),
        )
