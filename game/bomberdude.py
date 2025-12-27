import time
import asyncio
import requests
import pygame
import socket
import argparse
from pygame.math import Vector2 as Vec2d
import json
from loguru import logger
from utils import gen_randid
from game.gamestate import GameState
from constants import UPDATE_TICK, SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE
from camera import Camera
from objects.player import Bomberplayer, MOVE_MAP
from debug import draw_debug_info
from panels import PlayerInfoPanel

class Bomberdude():
    def __init__(self, args: argparse.Namespace):
        self.title = "Bomberdude"
        self.args = args
        self.draw_debug = False

        # Render to a fixed "virtual" resolution, then scale to the actual resizable window.
        self.base_size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        self.window = pygame.display.set_mode(self.base_size, flags=pygame.RESIZABLE)
        pygame.display.set_caption(SCREEN_TITLE + ' - ' + self.title)

        # All game rendering happens here (virtual canvas)
        self.screen = pygame.Surface(self.base_size)

        # Defer expensive display resize until the user finishes dragging.
        self._pending_resize: tuple[int, int] | None = None
        self._last_resize_event_time: float = 0.0

        self.running = True
        self.selected_bomb = 1
        self.client_id = 'bdudenotset'  # str(gen_randid())
        self.game_state = GameState(args=self.args, client_id=self.client_id)
        self._connected = False
        self.timer = 0
        self.mouse_pos = Vec2d(x=0, y=0)
        self.background_color = (100, 149, 237)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(False)  # Make non-blocking
        # Networking tasks should wait for this before using the socket.
        self.socket_connected = asyncio.Event()
        self.last_position_update = 0
        self.position_update_interval = 0.05  # 50ms = 20 updates/second
        self.last_frame_time = time.time()
        self.delta_time = 0
        self.show_minimap = False
        self.player_info_panel = PlayerInfoPanel(self.screen, self.game_state)

        self.fog_enabled = True  # Toggle for fog of war
        self.fog_radius = 200    # Visible radius around player
        self.fog_color = (0, 0, 0, 180)  # Semi-transparent black
        self.fog_surface = None  # Will be created on first render
        self._fog_size = None
        self._visibility_mask = None
        self.memory_duration = 10.0  # How long to remember (in seconds)
        self.trail_radius = 100      # Radius of trail visibility (smaller than main)
        self.max_trail_points = 100  # Limit trail length for performance

        # Fog-of-war caching: only recompute when inputs change.
        self._fog_last_center: tuple[int, int] | None = None
        self._fog_last_radius: int | None = None
        self.draw_player_info_panel = True

        self.remote_player_sprites: dict[str, Bomberplayer] = {}  # Cache for remote players

    def __repr__(self):
        return f"Bomberdude( {self.title} playerlist: {len(self.game_state.playerlist)} players_sprites: {len(self.game_state.players_sprites)} {self.connected()})"

    def connected(self):
        return self._connected

    async def disconnect(self, *, return_to_menu: bool = True) -> None:
        """Disconnect from server and stop the in-game loop without quitting the app."""
        self._connected = False
        self.running = False
        self.return_to_menu = return_to_menu
        try:
            if hasattr(self, "sock") and self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                except Exception as e:
                    logger.error(f"Error shutting down socket: {e} {type(e)}")
                try:
                    self.sock.close()
                except Exception as e:
                    logger.error(f"Error closing socket: {e} {type(e)}")
        except Exception as e:
            logger.error(f"disconnect error: {e} {type(e)}")

    async def connect(self):
        self.sock.setblocking(False)
        logger.info(f'connecting to server... event_queue: {self.game_state.event_queue.qsize()} ')
        await asyncio.get_event_loop().sock_connect(self.sock, (self.args.server, self.args.server_port))
        self.socket_connected.set()
        try:
            resp = requests.get(f"http://{self.args.server}:{self.args.api_port}/get_tile_map", timeout=10).text
        except Exception as e:
            logger.error(f"Error connecting to server: {e} {type(e)}")
            return 0
        try:
            resp = json.loads(resp)
            mapname = resp.get("mapname")
            self.client_id = resp.get("client_id")
            self.game_state.client_id = resp.get("client_id")
            tile_x = resp.get('position').get('position')[0]
            tile_y = resp.get('position').get('position')[1]
            modified_tiles = resp.get('modified_tiles', {})  # Get map modifications
        except Exception as e:
            logger.error(f"{type(e)} {e=} {resp}")
            raise e
        self.game_state.load_tile_map(mapname)
        # Apply map modifications
        if modified_tiles:
            if self.args.debug:
                logger.debug(f"Applying {len(modified_tiles)} modified_tiles from server.")
            self.game_state._apply_modifications_dict(modified_tiles)
        else:
            if self.args.debug:
                logger.debug("No modified_tiles received from server.")
        pixel_x = tile_x * self.game_state.tile_map.tilewidth
        pixel_y = tile_y * self.game_state.tile_map.tileheight

        pos = Vec2d(x=pixel_x, y=pixel_y)

        map_width = self.game_state.tile_map.width * self.game_state.tile_map.tilewidth
        map_height = self.game_state.tile_map.height * self.game_state.tile_map.tileheight
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, map_width, map_height)
        player_one = Bomberplayer(texture="data/playerone.png", client_id=self.client_id, position=pos)
        await player_one._set_texture(player_one.texture)
        player_one.rect = player_one.image.get_rect()
        player_one.rect.topleft = (int(player_one.position.x), int(player_one.position.y))
        self.game_state.players_sprites.add(player_one)
        connection_event = {
            "event_time": 0,
            'event_type': "connection_event",
            "client_id": str(player_one.client_id),
            "client_name": str(getattr(player_one, "client_name", "client_namenotset")),
            "position": (player_one.position.x, player_one.position.y),
            "bombs_left": player_one.bombs_left,
            "health": player_one.health,
            "score": player_one.score,
            "handled": False,
            "handledby": "connection_event",
            "event_id": gen_randid(),
        }
        connection_attempts = 0
        while not self.game_state._ready:
            await self.game_state.event_queue.put(connection_event)
            self._connected = True
            if self.args.debug:
                logger.debug(f'connecting {connection_attempts}: {self.connected()} game_state.ready {self.game_state.ready()} event_queue: {self.game_state.event_queue.qsize()} self.client_id: {self.client_id}')
            await asyncio.sleep(0.2)
            connection_attempts += 1
        if self.args.debug:
            logger.info(f'connected after {connection_attempts} attempts: {self.connected()} game_state.ready {self.game_state.ready()} event_queue: {self.game_state.event_queue.qsize()} self.client_id: {self.client_id}')
        return True

    async def draw_player(self, player_data):
        """Draw a player sprite based on player data"""
        if not player_data:
            logger.warning("draw_player called with None player_data")
            return
        client_id = player_data.client_id
        try:
            # Determine if player is dead
            health = player_data.health
            killed = player_data.killed
            is_dead = bool(killed) or (isinstance(health, (int, float)) and health <= 0)

            if client_id not in self.remote_player_sprites:
                texture = "data/netplayerdead.png" if is_dead else "data/player2.png"
                player_sprite = Bomberplayer(texture=texture, client_id=client_id)
                await player_sprite._set_texture(texture)
                self.remote_player_sprites[client_id] = player_sprite
                if self.args.debug:
                    logger.debug(f"Created new remote player sprite for {client_id} (dead: {is_dead}) player_sprite: {player_sprite} self.remote_player_sprites: {len(self.remote_player_sprites)}")
            else:
                player_sprite = self.remote_player_sprites[client_id]
                # Always update dead/alive state and texture if needed
                await player_sprite.set_dead(is_dead)

            position = player_data.position
            player_sprite.position = Vec2d(position)
            player_sprite.rect.topleft = (int(player_sprite.position.x), int(player_sprite.position.y))
            if player_sprite.image:
                self.screen.blit(player_sprite.image, self.camera.apply(player_sprite.rect))
            else:
                logger.warning(f"Player sprite image not loaded for {client_id}")

        except Exception as e:
            logger.error(f"Error drawing player: {e} {type(player_data)}")

    async def on_draw(self):
        # Clear virtual screen
        self.screen.fill((0, 0, 0))

        # draw map
        self.screen.blit(self.game_state.static_map_surface, self.camera.apply(pygame.Rect(0, 0, self.game_state.static_map_surface.get_width(), self.game_state.static_map_surface.get_height())))

        # Draw upgrade blocks
        for upgrade_block in self.game_state.upgrade_blocks:
            self.screen.blit(upgrade_block.image, self.camera.apply(upgrade_block.rect))

        # Draw local player
        player_one = self.game_state.get_playerone()
        if player_one.image:
            self.screen.blit(player_one.image, self.camera.apply(player_one.rect))

        # Draw remote players from playerlist
        for client_id, player in self.game_state.playerlist.items():
            if client_id != self.client_id:
                await self.draw_player(player)

        # Draw bullets, bombs, etc.
        for bullet in self.game_state.bullets:
            pos = self.camera.apply(bullet.rect)
            self.screen.blit(bullet.image, pos)

        for bomb in self.game_state.bombs:
            pos = self.camera.apply(bomb.rect)
            self.screen.blit(bomb.image, pos)

        # Draw explosion particles
        self.game_state.explosion_manager.draw(self.screen, self.camera)

        # Draw fog of war
        if self.fog_enabled:
            self.apply_fog_of_war()

        if self.draw_debug:
            draw_debug_info(self.screen, self.game_state, self.camera)
        if self.show_minimap:
            self.draw_minimap()
        if self.draw_player_info_panel:
            self.player_info_panel.draw()

        self.window.blit(self.screen, (0, 0))

    def draw_minimap(self):
        """Draw a minimap in the bottom-right corner showing all players"""
        # Minimap dimensions and position
        minimap_width = 150
        minimap_height = 150
        minimap_x = SCREEN_WIDTH - minimap_width - 10  # 10px padding
        minimap_y = SCREEN_HEIGHT - minimap_height - 10
        minimap_border = 2

        # Calculate scale ratio (map size to minimap size)
        map_width = self.game_state.tile_map.width * self.game_state.tile_map.tilewidth
        map_height = self.game_state.tile_map.height * self.game_state.tile_map.tileheight
        scale_x = minimap_width / map_width
        scale_y = minimap_height / map_height
        scale = min(scale_x, scale_y)  # Use the smaller scale to fit entire map

        # Draw background and border
        pygame.draw.rect(self.screen, (0, 0, 0), (minimap_x - minimap_border, minimap_y - minimap_border, minimap_width + 2*minimap_border, minimap_height + 2*minimap_border))
        pygame.draw.rect(self.screen, (50, 50, 50), (minimap_x, minimap_y, minimap_width, minimap_height))

        # Draw map blocks
        for tile in self.game_state.collidable_tiles:
            if tile.layer in ('Blocks',):
                mini_x = minimap_x + int(tile.rect.x * scale)
                mini_y = minimap_y + int(tile.rect.y * scale)
                mini_w = max(2, int(tile.rect.width * scale))
                mini_h = max(2, int(tile.rect.height * scale))
                pygame.draw.rect(self.screen, (150, 75, 0), (mini_x, mini_y, mini_w, mini_h))

        # Draw player one (as green dot)
        try:
            player_one = self.game_state.get_playerone()
            player_x = minimap_x + int(player_one.position.x * scale)
            player_y = minimap_y + int(player_one.position.y * scale)
            pygame.draw.circle(self.screen, (0, 255, 0), (player_x, player_y), 3)

            # Get camera viewport position
            # Instead of using offset_x and offset_y directly, calculate it from player position and screen center
            # This assumes camera is centered on player (modify if your camera logic is different)
            center_x = player_one.position.x - SCREEN_WIDTH/2
            center_y = player_one.position.y - SCREEN_HEIGHT/2

            # Clamp to map boundaries
            center_x = max(0, min(center_x, map_width - SCREEN_WIDTH))
            center_y = max(0, min(center_y, map_height - SCREEN_HEIGHT))

            # Draw view rectangle on minimap
            view_x = minimap_x + int(center_x * scale)
            view_y = minimap_y + int(center_y * scale)
            view_w = int(SCREEN_WIDTH * scale)
            view_h = int(SCREEN_HEIGHT * scale)
            pygame.draw.rect(self.screen, (200, 200, 200), (view_x, view_y, view_w, view_h), 1)
        except Exception as e:
            logger.error(f"Minimap player error: {e} {type(e)}")

        # Draw other players (as red dots)
        for client_id, player in self.game_state.playerlist.items():
            if client_id != self.client_id:
                try:
                    pos = player.position
                    if hasattr(pos, 'x') and hasattr(pos, 'y'):
                        other_x = minimap_x + int(pos.x * scale)
                        other_y = minimap_y + int(pos.y * scale)
                    else:
                        other_x = minimap_x + int(pos[0] * scale)
                        other_y = minimap_y + int(pos[1] * scale)
                    pygame.draw.circle(self.screen, (255, 0, 0), (other_x, other_y), 3)
                except Exception as e:
                    logger.error(f"Minimap other player error: {e} {type(e)}")

        # Draw bombs as yellow dots
        for bomb in self.game_state.bombs:
            try:
                bomb_x = minimap_x + int(bomb.position.x * scale)
                bomb_y = minimap_y + int(bomb.position.y * scale)
                pygame.draw.circle(self.screen, (255, 55, 0), (bomb_x, bomb_y), 2)
            except Exception as e:
                logger.error(f"Minimap bomb error: {e} {type(e)}")

    async def handle_on_mouse_press(self, x, y, button) -> None:
        if button == 1:
            player_one = self.game_state.get_playerone()
            # Dead players can't shoot.
            if player_one.killed or player_one.health <= 0:
                return
            # Convert screen coordinates to world coordinates
            mouse_world_pos = self.camera.reverse_apply(x, y)
            # player_world_pos = player_one.rect.center
            player_world_pos = (player_one.position.x + player_one.rect.width/2, player_one.position.y + player_one.rect.height/2)

            # Calculate direction in world space
            direction_vector = Vec2d(mouse_world_pos[0] - player_world_pos[0], mouse_world_pos[1] - player_world_pos[1])

            # Normalize direction vector
            if direction_vector.length() > 0:
                direction_vector = direction_vector.normalize()
            else:
                direction_vector = Vec2d(1, 0)  # Default direction if no movement

            # Use player's center as bullet start position
            bullet_pos = Vec2d(player_world_pos)
            # Create the event
            event = {
                "event_time": self.timer,
                'event_type': "on_bullet_fired",
                "client_id": self.client_id,
                "position": (bullet_pos.x, bullet_pos.y),
                "direction": (direction_vector.x, direction_vector.y),
                "timer": self.timer,
                "handled": False,
                "handledby": self.client_id,
                "event_id": gen_randid()
            }

            await self.game_state.event_queue.put(event)

    async def handle_on_key_press(self, key):
        player_one = self.game_state.get_playerone()
        if key == pygame.K_1:
            self.selected_bomb = 1
        elif key == pygame.K_2:
            self.selected_bomb = 2
        elif key == pygame.K_F1:
            self.args.debug = not self.args.debug
            logger.debug(f"debug: {self.args.debug}")
        elif key == pygame.K_F2:
            self.draw_debug = not self.draw_debug
            logger.debug(f"draw_debug: {self.draw_debug} debug: {self.args.debug}")
        elif key == pygame.K_F3:
            pass
        elif key == pygame.K_F4:
            pass
        elif key == pygame.K_F5:
            self.show_minimap = not self.show_minimap
            logger.debug(f"Minimap toggled: {self.show_minimap}")
        elif key == pygame.K_F6:
            self.fog_enabled = not self.fog_enabled
            logger.debug(f"Fog of war toggled: {self.fog_enabled}")
        elif key == pygame.K_F7:
            pygame.display.toggle_fullscreen()
        elif key == pygame.K_TAB:
            self.draw_player_info_panel = not self.draw_player_info_panel
        elif key in (pygame.K_ESCAPE, pygame.K_q, 27):
            await self.disconnect(return_to_menu=True)
            # self._connected = False
            # self.running = False
            logger.info("quit to main menu")
            # pygame.event.post(pygame.event.Event(pygame.QUIT))
            return

        if player_one.killed or player_one.health <= 0:
            if self.args.debug_gamestate:
                logger.debug(f"{player_one} is dead, ignoring key press {key}")
            return

        # Movement (table-driven)
        move = MOVE_MAP.get(key)
        if move is not None:
            dx, dy = move
            player_one.change_x = dx
            player_one.change_y = dy
            self.game_state.keyspressed.keys[key] = True
            return

        # Actions
        if key == pygame.K_SPACE:
            drop_bomb_event = await player_one.drop_bomb()
            if drop_bomb_event.get('event_type') == "player_drop_bomb":
                if drop_bomb_event.get('position') == (16,16):
                    logger.warning(f"Attempted to drop bomb at invalid position (16,16), ignoring. bomb event: {drop_bomb_event}")
                else:
                    await self.game_state.event_queue.put(drop_bomb_event)
            else:
                if self.args.debug_gamestate:
                    logger.debug(f"{player_one.client_name} has {player_one.bombs_left} bombs. drop bomb ignored, event: {drop_bomb_event.get('event_type')}")
            return

    async def handle_on_key_release(self, key):
        player_one = self.game_state.get_playerone()
        if key in (pygame.K_UP, pygame.K_w):
            player_one.change_y = 0
            self.game_state.keyspressed.keys[key] = False
        elif key in (pygame.K_DOWN, pygame.K_s):
            player_one.change_y = 0
            self.game_state.keyspressed.keys[key] = False
        elif key in (pygame.K_LEFT, pygame.K_a):
            player_one.change_x = 0
            self.game_state.keyspressed.keys[key] = False
        elif key in (pygame.K_RIGHT, pygame.K_d):
            player_one.change_x = 0
            self.game_state.keyspressed.keys[key] = False
        if key == pygame.K_SPACE:
            pass
        self.game_state.keyspressed.keys[key] = False

    async def update(self):
        player_one = self.game_state.get_playerone()
        current_time = time.time()
        self.delta_time = current_time - self.last_frame_time
        self.last_frame_time = current_time
        self.timer += self.delta_time
        player_one.update(self.game_state)
        player_one.rect.x = int(player_one.position.x)
        player_one.rect.y = int(player_one.position.y)

        map_width = self.game_state.tile_map.width * self.game_state.tile_map.tilewidth
        map_height = self.game_state.tile_map.height * self.game_state.tile_map.tileheight
        player_one.position.x = max(0, min(player_one.position.x, map_width - player_one.rect.width))
        player_one.position.y = max(0, min(player_one.position.y, map_height - player_one.rect.height))

        player_one.rect.x = int(player_one.position.x)
        player_one.rect.y = int(player_one.position.y)

        self.camera.update(player_one)

        # --- Upgrade block pickup logic ---
        # Use a copy to avoid modifying the set during iteration
        for upgrade_block in list(self.game_state.upgrade_blocks):
            upgrade_block.update()
            if upgrade_block.killed:
                self.game_state.upgrade_blocks.discard(upgrade_block)
                if self.args.debug_gamestate:
                    logger.debug(f'Removed expired upgrade block: {upgrade_block} remaining: {len(self.game_state.upgrade_blocks)}')

        self.game_state.bullets.update(self.game_state)
        for bomb in self.game_state.bombs:
            await bomb.update(self.game_state)
        await self.game_state.check_bullet_collisions()
        await self.game_state.check_upgrade_collisions()
        # await self.game_state.explosion_manager.update(self.game_state.collidable_tiles, self.game_state)

        # Use the already calculated delta time
        await self.game_state.explosion_manager.update(self.game_state.collidable_tiles, self.game_state, self.delta_time)
        self.game_state.check_flame_collisions()

        self.game_state.cleanup_playerlist()
        current_time = time.time()
        if current_time - self.last_position_update > self.position_update_interval:
            playerlist = [player.to_dict() for player in self.game_state.playerlist.values()]
            update_event = {
                "event_time": self.timer,
                'event_type': "player_update",
                "client_id": str(player_one.client_id),
                "client_name": player_one.client_name,
                "position": (player_one.position.x, player_one.position.y),
                "health": player_one.health,
                "score": player_one.score,
                "bombs_left": player_one.bombs_left,
                "handled": False,
                "handledby": "game_update",
                "playerlist": playerlist,
                "event_id": gen_randid(),}
            await self.game_state.event_queue.put(update_event)
            self.last_position_update = current_time
            await asyncio.sleep(1 / UPDATE_TICK)

    def apply_fog_of_war(self):
        """Apply fog of war effect with persistent trail"""
        if not self.fog_enabled:
            return

        # Get screen dimensions (handle resize)
        screen_width, screen_height = self.screen.get_size()
        if self._fog_size != (screen_width, screen_height) or self.fog_surface is None or self._visibility_mask is None:
            self._fog_size = (screen_width, screen_height)
            self.fog_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
            self._visibility_mask = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
            # Force a refresh after resize/recreate.
            self._fog_last_center = None
            self._fog_last_radius = None

        player_one = self.game_state.get_playerone()

        # Convert world to screen without extra allocations/calls
        map_width = self.game_state.tile_map.width * self.game_state.tile_map.tilewidth
        map_height = self.game_state.tile_map.height * self.game_state.tile_map.tileheight
        camera_x = player_one.position.x - SCREEN_WIDTH / 2
        camera_y = player_one.position.y - SCREEN_HEIGHT / 2
        camera_x = max(0, min(camera_x, map_width - SCREEN_WIDTH))
        camera_y = max(0, min(camera_y, map_height - SCREEN_HEIGHT))
        screen_x = int(player_one.position.x - camera_x)
        screen_y = int(player_one.position.y - camera_y)

        # Only recompute the composed fog overlay when the reveal center or radius changed.
        # This avoids two large Surface fills + a circle draw every frame.
        center = (screen_x, screen_y)
        radius = int(self.fog_radius)
        if center != self._fog_last_center or radius != self._fog_last_radius:
            # Fill with semi-transparent black
            self.fog_surface.fill((0, 0, 0, 220))
            # Reset mask to fully opaque black
            self._visibility_mask.fill((0, 0, 0, 255))
            pygame.draw.circle(self._visibility_mask, (0, 0, 0, 0), center, radius)
            self.fog_surface.blit(self._visibility_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self._fog_last_center = center
            self._fog_last_radius = radius

        self.screen.blit(self.fog_surface, (0, 0))

    def camera_apply_pos(self, world_pos):
        """Convert world position to screen position"""
        player_one = self.game_state.get_playerone()
        camera_x = player_one.position.x - SCREEN_WIDTH/2
        camera_y = player_one.position.y - SCREEN_HEIGHT/2

        # Clamp camera to map boundaries
        map_width = self.game_state.tile_map.width * self.game_state.tile_map.tilewidth
        map_height = self.game_state.tile_map.height * self.game_state.tile_map.tileheight
        camera_x = max(0, min(camera_x, map_width - SCREEN_WIDTH))
        camera_y = max(0, min(camera_y, map_height - SCREEN_HEIGHT))

        # Convert world to screen
        screen_x = int(world_pos[0] - camera_x)
        screen_y = int(world_pos[1] - camera_y)
        return (screen_x, screen_y)

    def handle_resize(self, width: int, height: int) -> None:
        """Resize the actual OS window. Game renders at base_size and is scaled up/down."""
        width = max(320, int(width))
        height = max(240, int(height))
        self.window = pygame.display.set_mode((width, height), flags=pygame.RESIZABLE)

    def queue_resize(self, width: int, height: int) -> None:
        """Record the latest requested window size; apply later."""
        self._pending_resize = (max(320, int(width)), max(240, int(height)))
        self._last_resize_event_time = time.time()

    def apply_pending_resize(self) -> None:
        """Apply any buffered resize immediately."""
        if not self._pending_resize:
            return
        w, h = self._pending_resize
        self._pending_resize = None
        self.handle_resize(w, h)

    def maybe_apply_pending_resize(self, debounce_seconds: float = 0.25) -> None:
        """Fallback: apply resize once events stop (e.g., after drag ends)."""
        if not self._pending_resize:
            return
        if (time.time() - self._last_resize_event_time) >= debounce_seconds:
            self.apply_pending_resize()

    def window_to_virtual(self, x: int, y: int) -> tuple[int, int]:
        """Convert window pixel coords -> virtual canvas coords."""
        win_w, win_h = self.window.get_size()
        base_w, base_h = self.base_size
        if win_w <= 0 or win_h <= 0:
            return (x, y)
        vx = int(x * (base_w / win_w))
        vy = int(y * (base_h / win_h))
        # Clamp inside virtual surface
        vx = max(0, min(base_w - 1, vx))
        vy = max(0, min(base_h - 1, vy))
        return (vx, vy)
