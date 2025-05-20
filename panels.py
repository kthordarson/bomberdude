# panels.py
import asyncio
import argparse
import socket
import json
import pygame
from loguru import logger

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
        self.discovery_panel = ServerDiscoveryPanel(self.screen)
        self.server_running = False

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.option_rects = []

        # Filter options based on server state
        display_options = [opt for opt in self.options if not (opt == "Stop Server" and not self.server_running) and not (opt == "Start Server" and self.server_running)]

        for i, option in enumerate(display_options):
            color = (255, 0, 0) if i == self.selected_option else (255, 255, 255)

            # Add status indicator for server
            if option == "Start" and self.server_running:
                option = "Start (Server Running)"

            text = self.font.render(option, True, color)
            rect = text.get_rect(center=(self.screen.get_width() // 2, 150 + i * 50))
            self.screen.blit(text, rect)
            self.option_rects.append(rect)
        pygame.display.flip()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w, 119):
                    self.selected_option = (self.selected_option - 1) % len(self.options)
                elif event.key in (pygame.K_DOWN, pygame.K_s, 115):
                    self.selected_option = (self.selected_option + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return self.select_option()
                elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return 'Quit'
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    return self.handle_mouse_click(event.pos)
        return None

    def handle_mouse_click(self, mouse_pos):
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected_option = i
                return self.select_option()
        return None

    def select_option(self):
        current_option = self.options[self.selected_option]

        if current_option == "Start":
            return "Start"
        elif current_option == "Start Server":
            return "Start Server"
        elif current_option == "Stop Server":
            return "Stop Server"
        elif current_option == "Find server":
            return "Find server"
        elif current_option == "Setup":
            action = self.setup_panel.run()
            return action
        elif current_option == "Quit":
            self.running = False
            return 'Quit'
        return None

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
            text = self.font.render(option, True, color)
            rect = text.get_rect(center=(self.screen.get_width() // 2, 150 + i * 50))
            self.screen.blit(text, rect)
            self.option_rects.append(rect)
        pygame.display.flip()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w, 119):
                    self.selected_option = (self.selected_option - 1) % len(self.options)
                elif event.key in (pygame.K_DOWN, pygame.K_s, 115):
                    self.selected_option = (self.selected_option + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return self.select_option()
                elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return 'Back'
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    return self.handle_mouse_click(event.pos)
        return None

    def handle_mouse_click(self, mouse_pos):
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected_option = i
                return self.select_option()
        return None

    def select_option(self):
        return self.options[self.selected_option]

    def run(self):
        while self.running:
            self.draw()
            action = self.handle_input()
            if action:
                return action
        return None

class Panel:
    def __init__(self, screen, position, size, color):
        self.screen = screen
        self.position = position
        self.size = size
        self.color = color

    def draw(self):
        pygame.draw.rect(self.screen, self.color, (*self.position, *self.size))

class ServerDiscoveryPanel():
    def __init__(self, screen):
        self.screen = screen
        self.rect = pygame.Rect(0, 0, screen.get_width(), screen.get_height())
        self.discovery_port = 12345
        self.servers = {}  # {addr: server_info}
        self.buttons = []
        self.discovery_running = False
        self.last_discovery = 0
        self.discovery_interval = 2.0  # seconds between broadcasts
        self.font = pygame.font.Font(None, 26)

    async def discover_servers(self):
        """Broadcast discovery packets and collect responses"""
        self.discovery_running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1)

        while self.discovery_running:
            try:
                # Broadcast discovery packet
                sock.sendto(b'BOMBERDUDE_DISCOVERY', ('<broadcast>', self.discovery_port))

                # Wait for responses
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 1.0:
                    try:
                        data, addr = sock.recvfrom(1024)
                        server_info = json.loads(data.decode('utf-8'))
                        if server_info.get('type') == 'server_info':
                            self.servers[addr[0]] = server_info
                    except socket.timeout:
                        pass
                    await asyncio.sleep(0.1)

                # Update server buttons
                self.update_server_buttons()
                await asyncio.sleep(self.discovery_interval)

            except Exception as e:
                logger.error(f"Error in server discovery: {e} {type(e)}")
                await asyncio.sleep(1)

    def update_server_buttons(self):
        """Update buttons based on discovered servers"""
        # Remove old server buttons
        self.buttons = [b for b in self.buttons if not hasattr(b, 'server_addr')]

        # Add button for each server
        y = 100
        for addr, info in self.servers.items():
            info_string = f"{info['name']} ({addr}) - {info['players']} players - {info['map']}"
            text = self.font.render(info_string, True, (255, 255, 255))
            rect = text.get_rect(center=(self.screen.get_width() // 2, 150 + y))
            self.screen.blit(text, rect)
            y += 50

    def connect_to_server(self, addr, info):
        """Connect to selected server"""
        self.discovery_running = False
        logger.info(f"Connecting to server {info} at {addr}")

    def show(self):
        # super().show()
        self.servers.clear()
        self.discovery_running = True
        asyncio.create_task(self.discover_servers())

    def hide(self):
        # super().hide()
        self.discovery_running = False

    def draw(self, surface):
        try:
            surface.fill((30, 30, 30), self.rect)
            # Draw title
            font = pygame.font.Font(None, 48)
            title = font.render("Find Local Servers", True, (255, 255, 255))
            surface.blit(title, (self.rect.centerx - title.get_width()//2, 20))

            # Draw buttons
            for button in self.buttons:
                button.draw(surface)
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

    def draw(self):
        """Draw the player info panel"""
        # Clear the surface with semi-transparent background
        self.surface.fill(self.bg_color)

        # Draw panel title
        title = self.title_font.render("PLAYERS", True, (255, 255, 255))
        title_rect = title.get_rect(midtop=(self.rect.width // 2, 5))
        self.surface.blit(title, title_rect)

        # Draw horizontal separator
        pygame.draw.line(self.surface, (200, 200, 200), (10, self.header_height), (self.rect.width - 10, self.header_height), 1)

        # Get all players to display
        players = list(self.game_state.playerlist.values())
        local_player = self.game_state.get_playerone()

        # Calculate how many player cards can fit in a row
        cards_per_row = max(1, (self.rect.width - 20) // (self.card_width + self.card_spacing))

        # Draw player cards
        if local_player:
            # Always draw local player first
            self._draw_player_card(0, local_player, self.local_color)

            # Draw remote players
            card_index = 1
            for player in players:
                # Skip local player as it's already drawn
                if hasattr(player, 'client_id') and player.client_id == local_player.client_id:
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
        client_id = getattr(player, 'client_id', 'unknown')
        # if isinstance(client_id, str) and len(client_id) > 8:
        #     client_id = client_id[:8] + "..."

        health = getattr(player, 'health', 0)
        if isinstance(player, dict):
            health = player.get('health', 0)
            score = player.get('score', 0)
            bombsleft = player.get('bombsleft', 0)
        else:
            health = getattr(player, 'health', 0)
            score = getattr(player, 'score', 0)
            bombsleft = getattr(player, 'bombsleft', 0)

        # Draw player ID
        id_text = self.player_font.render(f"Player: {client_id}", True, (255, 255, 255))
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
        health_text = self.stats_font.render(f"HP: {health}", True, (255, 255, 255))
        health_text_rect = health_text.get_rect(center=health_bar_rect.center)
        self.surface.blit(health_text, health_text_rect)

        # Draw score and bombs
        score_text = self.stats_font.render(f"Score: {score}", True, (255, 255, 255))
        # self.surface.blit(score_text, (x + 10, y + 47))

        bombs_text = self.stats_font.render(f"Bombs: {bombsleft}", True, (255, 255, 255))
        # self.surface.blit(bombs_text, (x + 10, y + 67))
        # Position score on the left and bombs on the right of the same line
        self.surface.blit(score_text, (x + 10, y + 47))
        self.surface.blit(bombs_text, (x + self.card_width - bombs_text.get_width() - 10, y + 47))
