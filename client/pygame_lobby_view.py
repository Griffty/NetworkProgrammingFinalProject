from __future__ import annotations

from dataclasses import dataclass

import pygame

from shared.models.game_rules import GAME_RULES

Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class ConnectAction:
    host: str
    port: int
    player_name: str


@dataclass(frozen=True, slots=True)
class LobbyLayout:
    panel_rect: pygame.Rect
    name_field_rect: pygame.Rect
    host_field_rect: pygame.Rect
    port_field_rect: pygame.Rect
    connect_button_rect: pygame.Rect


class PygameLobbyView:
    _BACKGROUND = (16, 20, 24)
    _PANEL = (27, 34, 40)
    _INPUT_BG = (18, 24, 30)
    _INPUT_ACTIVE = (60, 132, 214)
    _INPUT_IDLE = (74, 84, 94)
    _TEXT = (225, 230, 235)
    _SUBTEXT = (170, 178, 188)
    _ERROR = (214, 88, 88)
    _SUCCESS = (96, 184, 122)
    _WAITING = (190, 170, 90)
    _BUTTON = (54, 110, 170)
    _BUTTON_HOVER = (68, 128, 191)

    def __init__(
        self,
        default_host: str,
        default_port: int,
        player_name: str,
    ) -> None:
        self.name_text = player_name
        self.host_text = default_host
        self.port_text = str(default_port)

        self.active_field = "name"
        self.status_message = "Enter name, IP/port and press Connect."
        self.status_color = self._SUBTEXT
        self.window_size = (960, 680)

        self._screen: pygame.Surface | None = None
        self._clock: pygame.time.Clock | None = None
        self._title_font: pygame.font.Font | None = None
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None

    def open(self) -> None:
        pygame.init()
        pygame.display.set_caption("Space Legion TD - Lobby")
        self._screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self._clock = pygame.time.Clock()
        self._title_font = pygame.font.Font(None, 46)
        self._font = pygame.font.Font(None, 30)
        self._small_font = pygame.font.Font(None, 24)

    def close(self) -> None:
        pygame.quit()

    def next_frame(self) -> float:
        assert self._clock is not None
        return self._clock.tick(60) / 1000.0

    def set_status(self, message: str, color: Color) -> None:
        self.status_message = message
        self.status_color = color

    def handle_events(self) -> tuple[bool, ConnectAction | None]:
        layout = self._layout()
        connect_action: ConnectAction | None = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, None

            if event.type == pygame.VIDEORESIZE:
                self.window_size = (max(760, event.w), max(560, event.h))
                current_screen = pygame.display.get_surface()
                if current_screen is not None:
                    self._screen = current_screen
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False, None

                if event.key == pygame.K_TAB:
                    if self.active_field == "name":
                        self.active_field = "host"
                    elif self.active_field == "host":
                        self.active_field = "port"
                    else:
                        self.active_field = "name"
                    continue

                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    connect_action = self._try_build_connect_action()
                    continue

                self._handle_key_input(event)
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if layout.name_field_rect.collidepoint(event.pos):
                    self.active_field = "name"
                elif layout.host_field_rect.collidepoint(event.pos):
                    self.active_field = "host"
                elif layout.port_field_rect.collidepoint(event.pos):
                    self.active_field = "port"
                elif layout.connect_button_rect.collidepoint(event.pos):
                    connect_action = self._try_build_connect_action()

        return True, connect_action

    def render(
        self,
        *,
        connected: bool,
        waiting_for_match: bool,
        welcome_message: str,
    ) -> None:
        assert self._screen is not None
        assert self._title_font is not None
        assert self._font is not None
        assert self._small_font is not None

        screen = self._screen
        title_font = self._title_font
        font = self._font
        small_font = self._small_font

        layout = self._layout()
        screen.fill(self._BACKGROUND)
        pygame.draw.rect(screen, self._PANEL, layout.panel_rect, border_radius=10)

        title_surface = title_font.render("Space Legion TD", True, self._TEXT)
        title_x = layout.panel_rect.left + 28
        title_y = layout.panel_rect.top + 24
        screen.blit(title_surface, (title_x, title_y))

        subtitle = "Prepare your commander and connect to server"
        screen.blit(small_font.render(subtitle, True, self._SUBTEXT), (title_x, title_y + 56))

        screen.blit(
            font.render("Name", True, self._TEXT),
            (layout.name_field_rect.left, layout.name_field_rect.top - 30),
        )

        screen.blit(
            font.render("Server IP", True, self._TEXT),
            (layout.host_field_rect.left, layout.host_field_rect.top - 30),
        )
        screen.blit(
            font.render("Port", True, self._TEXT),
            (layout.port_field_rect.left, layout.port_field_rect.top - 30),
        )

        self._draw_input(screen, layout.name_field_rect, self.name_text, self.active_field == "name")
        self._draw_input(screen, layout.host_field_rect, self.host_text, self.active_field == "host")
        self._draw_input(screen, layout.port_field_rect, self.port_text, self.active_field == "port")

        mouse_pos = pygame.mouse.get_pos()
        button_color = (
            self._BUTTON_HOVER
            if layout.connect_button_rect.collidepoint(mouse_pos)
            else self._BUTTON
        )
        pygame.draw.rect(screen, button_color, layout.connect_button_rect, border_radius=8)
        button_label = font.render("Connect", True, self._TEXT)
        button_label_x = layout.connect_button_rect.centerx - (button_label.get_width() // 2)
        button_label_y = layout.connect_button_rect.centery - (button_label.get_height() // 2)
        screen.blit(button_label, (button_label_x, button_label_y))

        status_text = self.status_message
        if connected and waiting_for_match:
            status_text = "Connected. Waiting for server to start match..."
        elif connected and not waiting_for_match:
            status_text = "Match starting..."

        screen.blit(
            small_font.render(status_text, True, self.status_color),
            (layout.host_field_rect.left, layout.connect_button_rect.bottom + 18),
        )

        if welcome_message:
            screen.blit(
                small_font.render(f"Server: {welcome_message}", True, self._SUBTEXT),
                (layout.host_field_rect.left, layout.connect_button_rect.bottom + 44),
            )

        rules_title = font.render("General Rules", True, self._TEXT)
        rules_left = layout.panel_rect.left + 28
        rules_top = layout.connect_button_rect.bottom + 86
        screen.blit(rules_title, (rules_left, rules_top))

        for index, line in enumerate(self._rules_lines()):
            line_surface = small_font.render(line, True, self._SUBTEXT)
            screen.blit(line_surface, (rules_left, rules_top + 32 + (index * 24)))

        pygame.display.flip()

    @property
    def success_color(self) -> Color:
        return self._SUCCESS

    @property
    def error_color(self) -> Color:
        return self._ERROR

    @property
    def waiting_color(self) -> Color:
        return self._WAITING

    def _layout(self) -> LobbyLayout:
        width, height = self.window_size
        panel_margin_x = 40
        panel_margin_y = 30
        panel_rect = pygame.Rect(
            panel_margin_x,
            panel_margin_y,
            width - (panel_margin_x * 2),
            height - (panel_margin_y * 2),
        )

        name_top = panel_rect.top + 150
        name_field_rect = pygame.Rect(panel_rect.left + 28, name_top, 280, 46)

        connection_top = name_top + 84
        host_field_rect = pygame.Rect(panel_rect.left + 28, connection_top, 430, 46)
        port_field_rect = pygame.Rect(host_field_rect.right + 18, connection_top, 140, 46)
        connect_button_rect = pygame.Rect(port_field_rect.right + 18, connection_top, 170, 46)

        return LobbyLayout(
            panel_rect=panel_rect,
            name_field_rect=name_field_rect,
            host_field_rect=host_field_rect,
            port_field_rect=port_field_rect,
            connect_button_rect=connect_button_rect,
        )

    def _draw_input(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        text: str,
        is_active: bool,
    ) -> None:
        assert self._font is not None
        border_color = self._INPUT_ACTIVE if is_active else self._INPUT_IDLE
        pygame.draw.rect(screen, self._INPUT_BG, rect, border_radius=6)
        pygame.draw.rect(screen, border_color, rect, width=2, border_radius=6)

        content = text if text else ("..." if is_active else "")
        text_surface = self._font.render(content, True, self._TEXT)
        text_x = rect.left + 10
        text_y = rect.centery - (text_surface.get_height() // 2)
        screen.blit(text_surface, (text_x, text_y))

    def _handle_key_input(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_BACKSPACE:
            if self.active_field == "name":
                self.name_text = self.name_text[:-1]
            elif self.active_field == "host":
                self.host_text = self.host_text[:-1]
            else:
                self.port_text = self.port_text[:-1]
            return

        if not event.unicode or not event.unicode.isprintable():
            return

        char = event.unicode
        if self.active_field == "name":
            if len(self.name_text) < 20:
                self.name_text += char
            return

        if self.active_field == "host":
            if char.isspace():
                return
            if len(self.host_text) < 64:
                self.host_text += char
            return

        if char.isdigit() and len(self.port_text) < 5:
            self.port_text += char

    def _try_build_connect_action(self) -> ConnectAction | None:
        player_name = self.name_text.strip()
        host = self.host_text.strip()
        port_text = self.port_text.strip()

        if not player_name:
            self.set_status("Player name cannot be empty.", self._ERROR)
            return None

        if not host:
            self.set_status("Host/IP cannot be empty.", self._ERROR)
            return None

        if not port_text.isdigit():
            self.set_status("Port must be a number.", self._ERROR)
            return None

        port = int(port_text)
        if port < 1 or port > 65535:
            self.set_status("Port must be between 1 and 65535.", self._ERROR)
            return None

        self.set_status("Connecting...", self._WAITING)
        return ConnectAction(host=host, port=port, player_name=player_name)

    def _rules_lines(self) -> tuple[str, ...]:
        return (
            f"Map size: {GAME_RULES.map_width}x{GAME_RULES.map_height} tiles",
            f"Starting gold: {GAME_RULES.starting_gold}",
            f"Starting lives: {GAME_RULES.starting_lives}",
            "Leak rule: enemy reaching end deals damage to lives",
            f"Build starts each wave, then wave phase after {GAME_RULES.build_phase_seconds:.0f}s",
            "Win condition: last player with lives remaining",
        )
