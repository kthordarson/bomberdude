# panels.py
import argparse
import asyncio
import dataclasses
import json
import socket
from collections import OrderedDict

import pygame
from loguru import logger

from config import Config, save_config

# Global text render cache to avoid repeated Font.render() work every frame.
# Keyed by (font_id, text, antialias, color, background).
_TEXT_CACHE_MAX = 512
_TEXT_CACHE: "OrderedDict[tuple[int, str, bool, tuple[int, int, int, int] | tuple[int, int, int], tuple[int, int, int, int] | tuple[int, int, int] | None], pygame.Surface]" = OrderedDict()


def _render_text_cached(font: pygame.font.Font, text: str, antialias: bool, color, background=None) -> pygame.Surface:
    key = (id(font), text, antialias, tuple(color), tuple(background) if background is not None else None)
    surf = None
    if key:
        surf = _TEXT_CACHE.get(key)
    if surf:
        # LRU refresh
        _TEXT_CACHE.move_to_end(key)
        return surf
    # Render and insert
    surf = font.render(text, antialias, color, background)
    _TEXT_CACHE[key] = surf
    _TEXT_CACHE.move_to_end(key)
    # Trim
    while len(_TEXT_CACHE) > _TEXT_CACHE_MAX:
        _TEXT_CACHE.popitem(last=False)
    return surf

INGAME_MENU_SCALE = 0.7
INGAME_MENU_ALPHA = 170

class MainMenu:
    def __init__(self, screen: pygame.Surface, args: argparse.Namespace, config: Config | None = None):
        self.screen = screen
        self.args = args
        self.config = config if config is not None else Config()
        # Add server management options
        self.options = ["Start", "Start Server", "Stop Server", "Find server", "Setup", "Quit"]
        self.selected_option = 0
        self.font = pygame.font.Font(None, 36)
        self.running = True
        self.option_rects = []
        self.setup_panel = SetupMenu(screen, args)
        self.discovery_panel = ServerDiscoveryPanel(self.screen, args)
        self.configure_panel = ConfigureMenu(screen, self.config)
        self.server_running = False
        self.bgcolor = (0, 0, 0)
        self.ingame = False
        # Snapshot of the game frame behind an in-game (pause) menu, and a
        # cache of the smaller fonts used to render that menu.
        self.background_snapshot: pygame.Surface | None = None
        self._ingame_font_cache: dict[int, pygame.font.Font] = {}

    def enter_ingame(self, options: list[str]) -> None:
        """Switch to the paused, in-game overlay style: options limited to
        the given list, drawn semi-transparent and scaled down over a
        snapshot of the current game frame."""
        self.ingame = True
        self.options = options
        self.selected_option = 0
        self.bgcolor = (50, 50, 50)
        self.background_snapshot = self.screen.copy()
        self.configure_panel.background_snapshot = self.screen.copy()

    def exit_ingame(self, options: list[str]) -> None:
        """Return to the normal, full-screen main menu."""
        self.ingame = False
        self.options = options
        self.selected_option = 0
        self.bgcolor = (0, 0, 0)
        self.background_snapshot = None

    def _get_ingame_font(self, size: int) -> pygame.font.Font:
        font = self._ingame_font_cache.get(size)
        if font is None:
            font = pygame.font.Font(None, size)
            self._ingame_font_cache[size] = font
        return font

    def draw(self):
        if self.ingame and self.background_snapshot is not None:
            self._draw_ingame_overlay()
        else:
            self._draw_full_menu()
        pygame.display.flip()

    def _draw_full_menu(self):
        self.screen.fill(self.bgcolor)
        self.option_rects = []

        for i, option in enumerate(self.options):
            color = (255, 0, 0) if i == self.selected_option else (255, 255, 255)

            # Add status indicator for server
            if option == "Start" and self.server_running:
                option = "Start (Server Running)"

            text = _render_text_cached(self.font, option, True, color)
            rect = text.get_rect(center=(self.screen.get_width() // 2, 150 + i * 50))
            self.screen.blit(text, rect)
            self.option_rects.append(rect)

    def _draw_ingame_overlay(self):
        # Keep the frozen game frame visible behind the menu.
        if self.background_snapshot is not None:
            self.screen.blit(self.background_snapshot, (0, 0))

        font_size = max(12, int(36 * INGAME_MENU_SCALE))
        spacing = max(20, int(50 * INGAME_MENU_SCALE))
        small_font = self._get_ingame_font(font_size)

        sw, sh = self.screen.get_size()
        title_h = spacing
        panel_w = int(sw * INGAME_MENU_SCALE)
        panel_h = title_h + spacing * len(self.options) + spacing // 2
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2

        # Per-pixel alpha surface so the game frame shows through the panel.
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*self.bgcolor, INGAME_MENU_ALPHA))
        self.screen.blit(panel, (panel_x, panel_y))

        title = _render_text_cached(small_font, "PAUSED", True, (255, 255, 255))
        title_rect = title.get_rect(center=(sw // 2, panel_y + title_h // 2))
        self.screen.blit(title, title_rect)

        self.option_rects = []
        for i, option in enumerate(self.options):
            color = (255, 80, 80) if i == self.selected_option else (255, 255, 255)
            text = _render_text_cached(small_font, option, True, color)
            rect = text.get_rect(center=(sw // 2, panel_y + title_h + spacing // 2 + i * spacing))
            self.screen.blit(text, rect)
            self.option_rects.append(rect)

    def handle_input(self):
        action = 'noinput'
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w, 119):
                    self.selected_option = (self.selected_option - 1) % len(self.options)
                elif event.key in (pygame.K_DOWN, pygame.K_s, 115):
                    self.selected_option = (self.selected_option + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    action = self.select_option()
                elif event.key == pygame.K_q:
                    action = 'Quit'
                elif event.key == pygame.K_ESCAPE:
                    action = 'Back'
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    action = self.handle_mouse_click(event.pos)
        return action

    def handle_mouse_click(self, mouse_pos):
        action = 'nomouseaction'
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected_option = i
                action = self.select_option()
        return action

    def select_option(self):
        current_option = self.options[self.selected_option]
        action = 'noaction'
        if current_option == "Start":
            action = "Start"
        if current_option == "Resume":
            action = "Resume"
        elif current_option == "Start Server":
            action = "Start Server"
        elif current_option == "Stop Server":
            action = "Stop Server"
        elif current_option == "Find server":
            action = "Find server"
        elif current_option == "Setup":
            action = self.setup_panel.run()
        elif current_option == "Configure":
            action = "Configure"
        elif current_option == "Quit":
            self.running = False
            action = 'Quit'
        return action

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            self.draw()
            action = self.handle_input()
            if action:
                return action
            clock.tick(30)
        return None

class SetupMenu:
    def __init__(self, screen: pygame.Surface, args: argparse.Namespace):
        self.screen = screen
        self.args = args
        self.options = ["option1", "option2", "option3", "Back"]
        self.selected_option = 0
        self.font = pygame.font.Font(None, 26)
        self.running = True
        self.option_rects = []

    def draw(self):
        self.screen.fill((0, 0, 0, 150))
        self.option_rects = []
        for i, option in enumerate(self.options):
            color = (255, 0, 0) if i == self.selected_option else (255, 255, 255)
            text = _render_text_cached(self.font, option, True, color)
            rect = text.get_rect(center=(self.screen.get_width() // 2, 150 + i * 50))
            self.screen.blit(text, rect)
            self.option_rects.append(rect)
        pygame.display.flip()

    def handle_input(self):
        action = 'noinput'
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w, 119):
                    self.selected_option = (self.selected_option - 1) % len(self.options)
                elif event.key in (pygame.K_DOWN, pygame.K_s, 115):
                    self.selected_option = (self.selected_option + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    action = self.select_option()
                elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                    action = 'Back'
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    action = self.handle_mouse_click(event.pos)
        return action

    def handle_mouse_click(self, mouse_pos):
        action = 'noinput'
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected_option = i
                action = self.select_option()
        return action

    def select_option(self):
        return self.options[self.selected_option]

    def run(self):
        action = 'noaction'
        clock = pygame.time.Clock()
        while self.running:
            self.draw()
            action = self.handle_input()
            if action:
                return action
            clock.tick(30)
        return action

RESOLUTION_PRESETS = [
    (800, 600),
    (1024, 768),
    (1280, 720),
    (1366, 768),
    (1600, 900),
    (1920, 1080),
]

BULLET_COLOR_PRESETS = [
    ("Red", (255, 0, 0)),
    ("Orange", (255, 140, 0)),
    ("Yellow", (255, 255, 0)),
    ("Green", (0, 200, 0)),
    ("Cyan", (0, 220, 220)),
    ("Blue", (60, 120, 255)),
    ("Magenta", (255, 0, 200)),
    ("White", (255, 255, 255)),
]

PARTICLE_COUNT_MIN = 5
PARTICLE_COUNT_MAX = 200
PARTICLE_COUNT_STEP = 5

FOG_COLOR_PRESETS = [
    ("Black", (0, 0, 0)),
    ("Dark Gray", (40, 40, 40)),
    ("Navy", (10, 10, 40)),
    ("Dark Red", (40, 0, 0)),
    ("Dark Green", (0, 40, 0)),
    ("Purple", (40, 0, 40)),
]

FOG_RADIUS_MIN = 50
FOG_RADIUS_MAX = 500
FOG_RADIUS_STEP = 10

FOG_ALPHA_MIN = 0
FOG_ALPHA_MAX = 255
FOG_ALPHA_STEP = 5

MINIMAP_SIZE_MIN = 80
MINIMAP_SIZE_MAX = 300
MINIMAP_SIZE_STEP = 10

MINIMAP_ALPHA_MIN = 40
MINIMAP_ALPHA_MAX = 255
MINIMAP_ALPHA_STEP = 5

MINIMAP_ANCHOR_PRESETS = [
    ("Top Left", "top_left"),
    ("Top Right", "top_right"),
    ("Bottom Left", "bottom_left"),
    ("Bottom Right", "bottom_right"),
]

NAME_MAX_LENGTH = 20


class ConfigureMenu:
    """In-game settings screen: player name, resolution, bullet color,
    explosion particle count, fog-of-war radius/color/alpha, and minimap
    size/opacity/position. Fog and minimap rows apply live as they're
    changed; all changes persist to disk when the player selects "Save".
    "Cancel" discards any changes made during the session."""

    def __init__(self, screen: pygame.Surface, config: Config):
        self.screen = screen
        self.config = config
        self.rows = ["Player Name", "Resolution", "Bullet Color", "Particle Count", "Fog Radius", "Fog Color", "Fog Alpha", "Minimap Size", "Minimap Opacity", "Minimap Position", "Save", "Cancel"]
        self.selected_row = 0
        self.font = pygame.font.Font(None, 20)
        self.hint_font = pygame.font.Font(None, 16)
        self.running = True
        self.row_rects: list[pygame.Rect] = []
        self.editing_name = False
        self._name_buffer = ""
        self._snapshot: Config | None = None
        self.background_snapshot = None

    def _resolution_index(self) -> int:
        target = (self.config.screen_width, self.config.screen_height)
        for i, res in enumerate(RESOLUTION_PRESETS):
            if res == target:
                return i
        return 0

    def _bullet_color_index(self) -> int:
        target = tuple(self.config.bullet_color)
        for i, (_, color) in enumerate(BULLET_COLOR_PRESETS):
            if color == target:
                return i
        return 0

    def _fog_color_index(self) -> int:
        target = tuple(self.config.fog_color)
        for i, (_, color) in enumerate(FOG_COLOR_PRESETS):
            if color == target:
                return i
        return 0

    def _minimap_anchor_index(self) -> int:
        for i, (_, anchor) in enumerate(MINIMAP_ANCHOR_PRESETS):
            if anchor == self.config.minimap_anchor:
                return i
        return 0

    def _cycle_resolution(self, step: int) -> None:
        i = (self._resolution_index() + step) % len(RESOLUTION_PRESETS)
        self.config.screen_width, self.config.screen_height = RESOLUTION_PRESETS[i]

    def _cycle_bullet_color(self, step: int) -> None:
        i = (self._bullet_color_index() + step) % len(BULLET_COLOR_PRESETS)
        self.config.bullet_color = BULLET_COLOR_PRESETS[i][1]

    def _cycle_fog_color(self, step: int) -> None:
        i = (self._fog_color_index() + step) % len(FOG_COLOR_PRESETS)
        self.config.fog_color = FOG_COLOR_PRESETS[i][1]

    def _adjust_particle_count(self, step: int) -> None:
        self.config.particle_count = max(PARTICLE_COUNT_MIN, min(PARTICLE_COUNT_MAX, self.config.particle_count + step))

    def _adjust_fog_radius(self, step: int) -> None:
        self.config.fog_radius = max(FOG_RADIUS_MIN, min(FOG_RADIUS_MAX, self.config.fog_radius + step))

    def _adjust_fog_alpha(self, step: int) -> None:
        self.config.fog_alpha = max(FOG_ALPHA_MIN, min(FOG_ALPHA_MAX, self.config.fog_alpha + step))

    def _adjust_minimap_size(self, step: int) -> None:
        self.config.minimap_size = max(MINIMAP_SIZE_MIN, min(MINIMAP_SIZE_MAX, self.config.minimap_size + step))

    def _adjust_minimap_alpha(self, step: int) -> None:
        self.config.minimap_alpha = max(MINIMAP_ALPHA_MIN, min(MINIMAP_ALPHA_MAX, self.config.minimap_alpha + step))

    def _cycle_minimap_anchor(self, step: int) -> None:
        i = (self._minimap_anchor_index() + step) % len(MINIMAP_ANCHOR_PRESETS)
        self.config.minimap_anchor = MINIMAP_ANCHOR_PRESETS[i][1]

    def _row_value_text(self, row: str) -> str:
        if row == "Player Name":
            return self._name_buffer if self.editing_name else self.config.player_name
        elif row == "Resolution":
            return f"{self.config.screen_width}x{self.config.screen_height}"
        elif row == "Bullet Color":
            return BULLET_COLOR_PRESETS[self._bullet_color_index()][0]
        elif row == "Particle Count":
            return str(self.config.particle_count)
        elif row == "Fog Radius":
            return str(self.config.fog_radius)
        elif row == "Fog Color":
            return FOG_COLOR_PRESETS[self._fog_color_index()][0]
        elif row == "Fog Alpha":
            return str(self.config.fog_alpha)
        elif row == "Minimap Size":
            return f"{self.config.minimap_size}px"
        elif row == "Minimap Opacity":
            return str(self.config.minimap_alpha)
        elif row == "Minimap Position":
            return MINIMAP_ANCHOR_PRESETS[self._minimap_anchor_index()][0]
        return ""

    def draw(self):
        self.screen.fill((15, 15, 25, 150))
        self.row_rects = []
        sw = self.screen.get_width()

        if self.background_snapshot is not None:
            self.screen.blit(self.background_snapshot, (0, 0))

        title = _render_text_cached(self.font, "Configure", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(sw // 2, 80)))

        rows_top = 130
        rows_bottom = self.screen.get_height() - 70
        row_step = min(50, (rows_bottom - rows_top) / max(1, len(self.rows) - 1))

        for i, row in enumerate(self.rows):
            is_selected = i == self.selected_row
            label_color = (255, 220, 80) if is_selected else (255, 255, 255)
            y = int(rows_top + i * row_step)

            if row in ("Save", "Cancel"):
                text = _render_text_cached(self.font, row, True, label_color)
                rect = text.get_rect(center=(sw // 2, y))
                self.screen.blit(text, rect)
                self.row_rects.append(rect)
                continue

            value_text = self._row_value_text(row)
            if is_selected and row != "Player Name":
                value_text = f"< {value_text} >"
            elif is_selected and self.editing_name:
                value_text = f"{value_text}_"

            label = _render_text_cached(self.font, f"{row}:", True, label_color)
            value = _render_text_cached(self.font, value_text, True, label_color)
            label_rect = label.get_rect(midright=(sw // 2 - 20, y))
            value_rect = value.get_rect(midleft=(sw // 2 + 20, y))
            self.screen.blit(label, label_rect)
            self.screen.blit(value, value_rect)

            if row == "Bullet Color":
                swatch = pygame.Rect(0, 0, 24, 24)
                swatch.center = (value_rect.right + 30, y)
                pygame.draw.rect(self.screen, self.config.bullet_color, swatch)
                pygame.draw.rect(self.screen, (255, 255, 255), swatch, 1)

            if row == "Fog Color":
                swatch = pygame.Rect(0, 0, 24, 24)
                swatch.center = (value_rect.right + 30, y)
                pygame.draw.rect(self.screen, self.config.fog_color, swatch)
                pygame.draw.rect(self.screen, (255, 255, 255), swatch, 1)

            # Combined rect for mouse hit-testing.
            self.row_rects.append(label_rect.union(value_rect))

        hint = "Enter: edit name  |  Esc: cancel edit" if self.editing_name else "Up/Down: select  Left/Right: change  Enter: confirm  Esc: cancel"
        hint_surf = _render_text_cached(self.hint_font, hint, True, (170, 170, 170))
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(sw // 2, self.screen.get_height() - 40)))

        pygame.display.flip()

    def _handle_name_edit_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_RETURN:
            self.config.player_name = self._name_buffer.strip() or self.config.player_name
            self.editing_name = False
        elif event.key == pygame.K_ESCAPE:
            self.editing_name = False
        elif event.key == pygame.K_BACKSPACE:
            self._name_buffer = self._name_buffer[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self._name_buffer) < NAME_MAX_LENGTH:
            self._name_buffer += event.unicode

    def handle_input(self, cb_apply_config_changes) -> str | None:
        apply_needed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return "Cancel"
            elif event.type == pygame.KEYDOWN:
                if self.editing_name:
                    self._handle_name_edit_key(event)
                    continue
                current_row = self.rows[self.selected_row]
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_row = (self.selected_row - 1) % len(self.rows)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_row = (self.selected_row + 1) % len(self.rows)
                elif event.key == pygame.K_LEFT:
                    if current_row == "Resolution":
                        self._cycle_resolution(-1)
                    elif current_row == "Bullet Color":
                        self._cycle_bullet_color(-1)
                    elif current_row == "Particle Count":
                        self._adjust_particle_count(-PARTICLE_COUNT_STEP)
                    elif current_row == "Fog Radius":
                        self._adjust_fog_radius(-FOG_RADIUS_STEP)
                        apply_needed = True
                    elif current_row == "Fog Color":
                        self._cycle_fog_color(-1)
                        apply_needed = True
                    elif current_row == "Fog Alpha":
                        self._adjust_fog_alpha(-FOG_ALPHA_STEP)
                        apply_needed = True
                    elif current_row == "Minimap Size":
                        self._adjust_minimap_size(-MINIMAP_SIZE_STEP)
                        apply_needed = True
                    elif current_row == "Minimap Opacity":
                        self._adjust_minimap_alpha(-MINIMAP_ALPHA_STEP)
                        apply_needed = True
                    elif current_row == "Minimap Position":
                        self._cycle_minimap_anchor(-1)
                        apply_needed = True
                elif event.key == pygame.K_RIGHT:
                    if current_row == "Resolution":
                        self._cycle_resolution(1)
                    elif current_row == "Bullet Color":
                        self._cycle_bullet_color(1)
                    elif current_row == "Particle Count":
                        self._adjust_particle_count(PARTICLE_COUNT_STEP)
                    elif current_row == "Fog Radius":
                        self._adjust_fog_radius(FOG_RADIUS_STEP)
                        apply_needed = True
                    elif current_row == "Fog Color":
                        self._cycle_fog_color(1)
                        apply_needed = True
                    elif current_row == "Fog Alpha":
                        self._adjust_fog_alpha(FOG_ALPHA_STEP)
                        apply_needed = True
                    elif current_row == "Minimap Size":
                        self._adjust_minimap_size(MINIMAP_SIZE_STEP)
                        apply_needed = True
                    elif current_row == "Minimap Opacity":
                        self._adjust_minimap_alpha(MINIMAP_ALPHA_STEP)
                        apply_needed = True
                    elif current_row == "Minimap Position":
                        self._cycle_minimap_anchor(1)
                        apply_needed = True
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if current_row == "Player Name":
                        self.editing_name = True
                        self._name_buffer = self.config.player_name
                    elif current_row == "Save":
                        return "Save"
                    elif current_row == "Cancel":
                        return "Cancel"
                elif event.key in (pygame.K_ESCAPE, pygame.K_F3):
                    return "Cancel"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(self.row_rects):
                    if rect.collidepoint(event.pos):
                        self.selected_row = i
                        row = self.rows[i]
                        if row == "Save":
                            return "Save"
                        elif row == "Cancel":
                            return "Cancel"
                        elif row == "Player Name":
                            self.editing_name = True
                            self._name_buffer = self.config.player_name
        if apply_needed:
            cb_apply_config_changes()
            apply_needed = False
        return None

    def run(self, cb_apply_config_changes) -> bool:
        """Show the settings screen. Returns True if the player saved changes,
        False if they cancelled (any in-session edits are reverted)."""
        self._snapshot = dataclasses.replace(self.config)
        self.selected_row = 0
        self.editing_name = False
        self.running = True
        clock = pygame.time.Clock()
        while self.running:
            self.draw()
            action = self.handle_input(cb_apply_config_changes)
            if action == "Save":
                save_config(self.config)
                return True
            elif action == "Cancel":
                if self._snapshot is not None:
                    for f in dataclasses.fields(self.config):
                        setattr(self.config, f.name, getattr(self._snapshot, f.name))
                return False
            clock.tick(30)
        return False

class Panel:
    def __init__(self, screen: pygame.Surface, position, size, color):
        self.screen = screen
        self.position = position
        self.size = size
        self.color = color

    def draw(self):
        pygame.draw.rect(self.screen, self.color, (*self.position, *self.size))

class ServerDiscoveryPanel:
    def __init__(self, screen: pygame.Surface, args: argparse.Namespace):
        self.screen = screen
        self.args = args
        self.rect = pygame.Rect(0, 0, screen.get_width(), screen.get_height())
        self.discovery_port = 12345
        self.servers = {}  # {addr: server_info}
        self.server_rows: list[tuple[pygame.Rect, str, dict]] = []
        self.discovery_running = False
        self.last_discovery = 0
        self.discovery_interval = 2.0  # seconds between broadcasts
        self.font = pygame.font.Font(None, 26)
        self.title_font = pygame.font.Font(None, 36)
        self._task: asyncio.Task | None = None

    async def discover_servers(self):
        """Broadcast discovery packets and collect responses"""
        self.discovery_running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)
        loop = asyncio.get_event_loop()
        # loop = asyncio.get_running_loop()

        while self.discovery_running:
            try:
                # Broadcast discovery packet
                await loop.sock_sendto(sock, b'BOMBERDUDE_DISCOVERY', ('255.255.255.255', self.discovery_port))

                # Collect responses for ~1s
                end_time = loop.time() + 1.0
                while self.discovery_running and loop.time() < end_time:
                    try:
                        data, addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 1024), timeout=0.15)
                    except asyncio.TimeoutError:
                        continue
                    except (OSError, asyncio.CancelledError) as e:
                        self.discovery_running = False
                        logger.warning(f"{e} {type(e)}")
                        break
                    if not data:
                        continue
                    try:
                        server_info = json.loads(data.decode('utf-8'))
                        self.servers[addr[0]] = server_info
                    except Exception as e:
                        logger.error(f"Error parsing discovery response from {addr}: {e} {type(e)}")
                        continue

                await asyncio.sleep(self.discovery_interval)

            except asyncio.CancelledError:
                sock.close()
                break
            except Exception as e:
                logger.error(f"Error in server discovery: {e} {type(e)}")
                sock.close()
                break

    def connect_to_server(self, addr, info):
        """Connect to selected server"""
        self.discovery_running = False
        logger.info(f"Connecting to server {info.get('listen')}")
        try:
            self.args.server = addr
            info['host'] = info.get('listen')
            self.args.server_port = info.get('server_port')
            self.args.api_port = info.get('api_port')
        except Exception as e:
            logger.error(f"Error setting selected server: {e} {type(e)}")
            pass

    def show(self):
        # super().show()
        self.servers.clear()
        self.discovery_running = True
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.discover_servers())

    def hide(self):
        # super().hide()
        self.discovery_running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def run(self) -> dict | None:
        """Show the panel until the user selects a server or exits.

        - Click a server row to select it (sets args.server)
        - ESC/Q to go back
        """
        self.show()
        selected: dict | None = None
        clock = pygame.time.Clock()
        logger.info("Server discovery panel running...")
        while self.discovery_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.hide()
                    logger.info(f"{event} Server discovery panel quitting...")
                    return None
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.hide()
                    logger.info(f"{event} Server discovery panel quitting...")
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    for rect, addr, info in self.server_rows:
                        if rect.collidepoint((mx, my)):
                            self.connect_to_server(addr, info)
                            selected = info
                            break
            self.draw(self.screen)
            pygame.display.flip()
            clock.tick(30)
            await asyncio.sleep(1)
            logger.debug(f"Server discovery panel running... {len(self.servers)} servers found")
        logger.info(f"Server discovery panel returning {selected=}")
        return selected

    def draw(self, surface):
        try:
            self.rect = pygame.Rect(0, 0, surface.get_width(), surface.get_height())
            surface.fill((30, 30, 30), self.rect)
            # Draw title
            title = _render_text_cached(self.title_font, "Find Local Servers", True, (255, 255, 255))
            surface.blit(title, (self.rect.centerx - title.get_width()//2, 20))

            hint = _render_text_cached(self.font, "Click a server to select, ESC/Q to go back", True, (200, 200, 200))
            surface.blit(hint, (self.rect.centerx - hint.get_width()//2, 70))

            self.server_rows = []
            y = 120
            if not self.servers:
                none_text = _render_text_cached(self.font, "No servers found yet...", True, (255, 255, 255))
                surface.blit(none_text, (self.rect.centerx - none_text.get_width()//2, y))
                return

            for addr, info in sorted(self.servers.items()):
                name = info.get('name', 'server')
                players = info.get('players', '?')
                m = info.get('map', '')
                info_string = f"{name} ({addr}) - {players} players - {m}"
                text = _render_text_cached(self.font, info_string, True, (255, 255, 255))
                rect = text.get_rect(center=(self.rect.centerx, y))
                # Expand to a click target
                click_rect = pygame.Rect(rect.left - 10, rect.top - 6, rect.width + 20, rect.height + 12)
                pygame.draw.rect(surface, (60, 60, 60), click_rect, border_radius=6)
                surface.blit(text, rect)
                self.server_rows.append((click_rect, addr, info))
                y += 50
        except Exception as e:
            logger.error(f"Error drawing server discovery panel: {e} {type(e)}")

class PlayerInfoPanel:
    def __init__(self, screen:pygame.Surface, game_state, height=110, bg_color=(30, 30, 40, 180)):
        """
        Create a panel showing player information at the bottom of the screen

        Args:
            screen: The pygame surface to draw on
            game_state: The game state containing player information
            height: Height of the panel in pixels
            bg_color: Background color with optional alpha (transparency)
        """
        self.screen = screen
        self.game_state = game_state
        self.height = height
        self.bg_color = bg_color

        # Panel position at the bottom of the screen
        self.rect = pygame.Rect(0, screen.get_height() - height, screen.get_width(), height)

        # Create fonts for different text elements
        self.title_font = pygame.font.Font(None, 20)
        self.player_font = pygame.font.Font(None, 16)
        self.stats_font = pygame.font.Font(None, 14)

        # Player colors (local player = green, remote players = different colors)
        self.local_color = (100, 255, 100)
        self.remote_colors = [(255, 100, 100), (100, 100, 255), (255, 255, 100), (255, 100, 255)]

        # Health bar colors
        self.health_bg = (60, 60, 60)
        self.health_fg = (220, 50, 50)

        # Header height
        self.header_height = 25

        # Player card dimensions
        self.card_width = 180
        self.card_height = self.height - self.header_height - 10  # 5px padding top and bottom
        self.card_spacing = 10

        # Create a semi-transparent surface for the background
        self.surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)

        # Cache per-player rendered text (only update when values change)
        self._player_text_cache: dict[str, tuple[tuple[str, int, int, int, int], pygame.Surface, pygame.Surface, pygame.Surface, pygame.Surface]] = {}

    def draw(self):
        """Draw the player info panel"""
        # Clear the surface with semi-transparent background
        self.surface.fill(self.bg_color)

        # Draw panel title
        title = _render_text_cached(self.title_font, "PLAYERS", True, (255, 255, 255))
        title_rect = title.get_rect(midtop=(self.rect.width // 2, 5))
        self.surface.blit(title, title_rect)

        # Draw horizontal separator
        pygame.draw.line(self.surface, (200, 200, 200), (10, self.header_height), (self.rect.width - 10, self.header_height), 1)

        # Get all players to display
        local_player = self.game_state.get_playerone()
        # if local_player:
        #     name_text = _render_text_cached(self.title_font, f"{local_player.client_name}", True, (255, 255, 255))
        #     name_rect = name_text.get_rect(midtop=(self.rect.width // 3, 5))
        #     self.surface.blit(name_text, name_rect)

        # Calculate how many player cards can fit in a row
        cards_per_row = max(1, (self.rect.width - 20) // (self.card_width + self.card_spacing))

        # Draw player cards
        if local_player:
            # Always draw local player first
            self._draw_player_card(0, local_player, self.local_color)

            # Draw remote players
            card_index = 1
            for player in list(self.game_state.playerlist.values()):
                # Skip local player as it's already drawn
                if player.client_id == local_player.client_id:
                    continue

                # Skip if we've run out of space
                if card_index >= cards_per_row:
                    break

                # Draw remote player card with cycling colors
                color_index = (card_index - 1) % len(self.remote_colors)
                self._draw_player_card(card_index, player, self.remote_colors[color_index])
                card_index += 1

        # Blit the panel surface onto the screen
        self.screen.blit(self.surface, self.rect)

    def _draw_player_card(self, index, player, color):
        """Draw a card with player information"""
        # Calculate card position
        x = 10 + index * (self.card_width + self.card_spacing)
        y = self.header_height + 5

        # Create player card background with rounded corners
        card_rect = pygame.Rect(x, y, self.card_width, self.card_height)
        pygame.draw.rect(self.surface, (50, 50, 60), card_rect, border_radius=5)
        pygame.draw.rect(self.surface, color, card_rect, width=2, border_radius=5)

        # player is either the local Bomberplayer sprite or a remote PlayerState
        # entry; both expose these as plain attributes.
        player_id = str(player.client_id)
        client_name = str(player.client_name)
        health = int(player.health or 0)
        score = int(player.score or 0)
        bombs_left = int(player.bombs_left or 0)
        bomb_power = int(player.bomb_power or 0)

        cache_key = (client_name, health, score, bombs_left, bomb_power)
        cached = self._player_text_cache.get(player_id)
        if cached is None or cached[0] != cache_key:
            id_text = _render_text_cached(self.player_font, f"Player: {client_name}", True, (255, 255, 255))
            health_text = _render_text_cached(self.stats_font, f"HP: {health}", True, (255, 255, 255))
            score_text = _render_text_cached(self.stats_font, f"Score: {score}", True, (255, 255, 255))
            bombs_text = _render_text_cached(self.stats_font, f"Bombs: {bombs_left} {bomb_power}", True, (255, 255, 255))
            self._player_text_cache[player_id] = (cache_key, id_text, health_text, score_text, bombs_text)
        else:
            _, id_text, health_text, score_text, bombs_text = cached

        # Draw player ID
        self.surface.blit(id_text, (x + 10, y + 5))

        # Draw health bar
        health_bar_rect = pygame.Rect(x + 10, y + 30, self.card_width - 20, 12)
        pygame.draw.rect(self.surface, self.health_bg, health_bar_rect)

        # Calculate health bar width
        health_pct = max(0, min(100, health)) / 100
        health_width = int(health_pct * (self.card_width - 20))

        if health_width > 0:
            health_fill_rect = pygame.Rect(x + 10, y + 30, health_width, 12)
            pygame.draw.rect(self.surface, self.health_fg, health_fill_rect)

        # Draw health text on top of the bar
        health_text_rect = health_text.get_rect(center=health_bar_rect.center)
        self.surface.blit(health_text, health_text_rect)

        # Draw score and bombs
        # score_text cached above
        # self.surface.blit(score_text, (x + 10, y + 47))

        # bombs_text cached above
        # self.surface.blit(bombs_text, (x + 10, y + 67))
        # Position score on the left and bombs on the right of the same line
        self.surface.blit(score_text, (x + 10, y + 47))
        self.surface.blit(bombs_text, (x + self.card_width - bombs_text.get_width() - 10, y + 47))
