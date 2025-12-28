# panels.py
import asyncio
import argparse
import socket
import json
import pygame
from collections import OrderedDict
from loguru import logger


# Global text render cache to avoid repeated Font.render() work every frame.
# Keyed by (font_id, text, antialias, color, background).
_TEXT_CACHE_MAX = 512
_TEXT_CACHE: "OrderedDict[tuple[int, str, bool, tuple[int, int, int, int] | tuple[int, int, int], tuple[int, int, int, int] | tuple[int, int, int] | None], pygame.Surface]" = OrderedDict()


def _render_text_cached(font: pygame.font.Font, text: str, antialias: bool, color, background=None) -> pygame.Surface:
    key = (id(font), text, bool(antialias), tuple(color), tuple(background) if background is not None else None)
    surf = _TEXT_CACHE.get(key)
    if surf is not None:
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

class MainMenu:
    def __init__(self, screen, args: argparse.Namespace):
        self.screen = screen
        self.args = args
        # Add server management options
        self.options = ["Start", "Start Server", "Stop Server", "Find server", "Setup", "Quit"]
        self.selected_option = 0
        self.font = pygame.font.Font(None, 36)
        self.running = True
        self.option_rects = []
        self.setup_panel = SetupMenu(screen, args)
        self.discovery_panel = ServerDiscoveryPanel(self.screen, args)
        self.server_running = False

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.option_rects = []

        # Filter options based on server state
        display_options = [opt for opt in self.options]

        for i, option in enumerate(display_options):
            color = (255, 0, 0) if i == self.selected_option else (255, 255, 255)

            # Add status indicator for server
            if option == "Start" and self.server_running:
                option = "Start (Server Running)"

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
                    action = 'Quit'
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
        elif current_option == "Start Server":
            action = "Start Server"
        elif current_option == "Stop Server":
            action = "Stop Server"
        elif current_option == "Find server":
            action = "Find server"
        elif current_option == "Setup":
            action = self.setup_panel.run()
        elif current_option == "Quit":
            self.running = False
            action = 'Quit'
        return action

    def run(self):
        while self.running:
            self.draw()
            action = self.handle_input()
            if action:
                return action
        return None

class SetupMenu:
    def __init__(self, screen, args: argparse.Namespace):
        self.screen = screen
        self.args = args
        self.options = ["option1", "option2", "option3", "Back"]
        self.selected_option = 0
        self.font = pygame.font.Font(None, 26)
        self.running = True
        self.option_rects = []

    def draw(self):
        self.screen.fill((0, 0, 0))
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
        while self.running:
            self.draw()
            action = self.handle_input()
            if action:
                return action
        return action

class Panel:
    def __init__(self, screen, position, size, color):
        self.screen = screen
        self.position = position
        self.size = size
        self.color = color

    def draw(self):
        pygame.draw.rect(self.screen, self.color, (*self.position, *self.size))

class ServerDiscoveryPanel():
    def __init__(self, screen, args: argparse.Namespace):
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
        # loop = asyncio.get_event_loop()
        loop = asyncio.get_running_loop()

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
        # Store selection for the caller and set args.server for convenience.
        # IMPORTANT: use the sender IP (addr) rather than the server-reported "listen",
        # which is often 127.0.0.1 and not reachable from other machines.
        try:
            self.args.server = addr
            if isinstance(info, dict):
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
        while self.discovery_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.hide()
                    return None
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.hide()
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
            await asyncio.sleep(0)
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
    def __init__(self, screen, game_state, height=110, bg_color=(30, 30, 40, 180)):
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
        self._player_text_cache: dict[str, tuple[tuple[str, int, int, int], pygame.Surface, pygame.Surface, pygame.Surface, pygame.Surface]] = {}

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

        # Get player attributes (safely)
        if isinstance(player, dict):
            player_id = str(player.get('client_id', 'unknown'))
            client_name = str(player.get('client_name', 'unknown'))
            health = int(player.get('health', 0) or 0)
            score = int(player.get('score', 0) or 0)
            bombs_left = int(player.get('bombs_left', 0) or 0)
        else:
            player_id = str(getattr(player, 'client_id', 'unknown'))
            client_name = str(getattr(player, 'client_name', 'unknown'))
            health = int(getattr(player, 'health', 0) or 0)
            score = int(getattr(player, 'score', 0) or 0)
            bombs_left = int(getattr(player, 'bombs_left', 0) or 0)

        cache_key = (client_name, health, score, bombs_left)
        cached = self._player_text_cache.get(player_id)
        if cached is None or cached[0] != cache_key:
            id_text = _render_text_cached(self.player_font, f"Player: {client_name}", True, (255, 255, 255))
            health_text = _render_text_cached(self.stats_font, f"HP: {health}", True, (255, 255, 255))
            score_text = _render_text_cached(self.stats_font, f"Score: {score}", True, (255, 255, 255))
            bombs_text = _render_text_cached(self.stats_font, f"Bombs: {bombs_left}", True, (255, 255, 255))
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
