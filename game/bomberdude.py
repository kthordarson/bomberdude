import time
import ast
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
from constants import UPDATE_TICK, PLAYER_MOVEMENT_SPEED, SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE
from camera import Camera
from objects.player import Bomberplayer, MOVE_MAP
from game.playerstate import PlayerState  # Import PlayerState
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
        self.client_game_state = GameState(args=self.args, client_id=self.client_id)
        self._connected = False
        self.timer = 0
        self.mouse_pos = Vec2d(x=0, y=0)
        self.background_color = (100, 149, 237)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(False)  # Make non-blocking
        self.last_position_update = 0
        self.position_update_interval = 0.05  # 50ms = 20 updates/second
        self.last_frame_time = time.time()
        self.delta_time = 0
        self.show_minimap = False
        self.player_info_panel = PlayerInfoPanel(self.screen, self.client_game_state)

        self.fog_enabled = True  # Toggle for fog of war
        self.fog_radius = 200    # Visible radius around player
        self.fog_color = (0, 0, 0, 180)  # Semi-transparent black
        self.fog_surface = None  # Will be created on first render
        self._fog_size = None
        self._visibility_mask = None
        self.memory_duration = 10.0  # How long to remember (in seconds)
        self.trail_radius = 100      # Radius of trail visibility (smaller than main)
        self.max_trail_points = 100  # Limit trail length for performance

    def __repr__(self):
        return f"Bomberdude( {self.title} playerlist: {len(self.client_game_state.playerlist)} players_sprites: {len(self.client_game_state.players_sprites)} {self.connected()})"

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
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"disconnect error: {e} {type(e)}")

    async def connect(self):
        self.sock.setblocking(False)
        logger.info(f'connecting to server... event_queue: {self.client_game_state.event_queue.qsize()} ')
        await asyncio.get_event_loop().sock_connect(self.sock, (self.args.server, 9696))
        try:
            resp = requests.get(f"http://{self.args.server}:9699/get_tile_map", timeout=10).text
        except Exception as e:
            logger.error(f"Error connecting to server: {e} {type(e)}")
            return 0
        try:
            resp = json.loads(resp)
            mapname = resp.get("mapname")
            self.client_id = resp.get("client_id")
            self.client_game_state.client_id = resp.get("client_id")
            tile_x = resp.get('position').get('position')[0]
            tile_y = resp.get('position').get('position')[1]
            modified_tiles = resp.get('modified_tiles', {})  # Get map modifications
        except Exception as e:
            logger.error(f"{type(e)} {e=} {resp}")
            raise e
        self.client_game_state.load_tile_map(mapname)
        # Apply map modifications
        if modified_tiles:
            self.apply_map_modifications(modified_tiles)
        else:
            if self.args.debug:
                logger.debug(f'no modified_tiles {len(modified_tiles)}')
        pixel_x = tile_x * self.client_game_state.tile_map.tilewidth
        pixel_y = tile_y * self.client_game_state.tile_map.tileheight

        pos = Vec2d(x=pixel_x, y=pixel_y)

        map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
        map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, map_width, map_height)
        player_one = Bomberplayer(texture="data/playerone.png", client_id=self.client_id, position=pos)
        self.client_game_state.players_sprites.add(player_one)
        connection_event = {
            "event_time": 0,
            "event_type": "connection_event",
            "client_id": str(player_one.client_id),
            "client_name": str(getattr(player_one, "client_name", "client_namenotset")),
            "position": (player_one.position[0], player_one.position[1]),
            "bombs_left": player_one.bombs_left,
            "health": player_one.health,
            "score": player_one.score,
            "handled": False,
            "handledby": "connection_event",
            "eventid": gen_randid(),
        }
        connection_attempts = 0
        while not self.client_game_state._ready:
            await self.client_game_state.event_queue.put(connection_event)
            self._connected = True
            if self.args.debug:
                logger.debug(f'connecting {connection_attempts}: {self.connected()} client_game_state.ready {self.client_game_state.ready()} event_queue: {self.client_game_state.event_queue.qsize()} self.client_id: {self.client_id}')
            await asyncio.sleep(0.2)
            connection_attempts += 1
        if self.args.debug:
            logger.info(f'connected after {connection_attempts} attempts: {self.connected()} client_game_state.ready {self.client_game_state.ready()} event_queue: {self.client_game_state.event_queue.qsize()} self.client_id: {self.client_id}')
        return True

    def apply_map_modifications(self, modified_tiles):
        """Apply map modifications received from the server"""
        if not modified_tiles:
            return
        if self.args.debug:
            logger.info(f"Applying {len(modified_tiles)} map modifications from server")
        try:
            # Reuse the GameState batch applier (parses "(x,y)" keys and updates visuals/collisions)
            self.client_game_state._apply_modifications_dict(modified_tiles)
        except Exception as e:
            logger.error(f"Error applying map modifications: {e}")

    def draw_player(self, player_data):
        """Draw a player sprite based on player data"""
        if not player_data:
            if self.args.debug:
                logger.warning("draw_player called with None player_data")
            return
        try:
            client_id = getattr(player_data, 'client_id', 'unknown')
            position = getattr(player_data, 'position', [0, 0])
            health = getattr(player_data, 'health', 0)
            killed = getattr(player_data, 'killed', False)
            is_dead = bool(killed) or (isinstance(health, (int, float)) and health <= 0)
            texture = "data/netplayerdead.png" if is_dead else "data/player2.png"

            # Create temporary sprite for drawing
            player_sprite = Bomberplayer(texture=texture, client_id=client_id)
            player_sprite.position = Vec2d(position) if position else Vec2d(0, 0)
            # player_sprite.rect.topleft = (player_sprite.position.x, player_sprite.position.y)
            player_sprite.rect.topleft = (int(player_sprite.position.x), int(player_sprite.position.y))

            # Now we can safely draw the sprite
            self.screen.blit(player_sprite.image, self.camera.apply(player_sprite.rect))  # type: ignore

        except Exception as e:
            logger.error(f"Error drawing player: {e} {type(player_data)}")

    def on_draw(self):
        # Clear virtual screen
        self.screen.fill((0, 0, 0))

        self.client_game_state.render_map(self.screen, self.camera)
        # Draw local player
        player_one = self.client_game_state.get_playerone()
        if player_one.client_id != 'theserver':
            if player_one.image is not None:  # type: ignore
                self.screen.blit(player_one.image, self.camera.apply(player_one.rect))  # type: ignore

                # Draw remote players from playerlist
                for client_id, player in self.client_game_state.playerlist.items():
                    if client_id != self.client_id:
                        try:
                            self.draw_player(player)
                        except Exception as e:
                            logger.error(f'draw_player {e} {type(e)} player: {player} {type(player)}')
            else:
                logger.warning(f"Player one not found {player_one=} {self.client_game_state=}")
        else:
            if self.args.debug:
                logger.warning(f"Skipping drawing server player {player_one.client_id}")

        # Draw bullets, bombs, etc.
        for bullet in self.client_game_state.bullets:
            pos = self.camera.apply(bullet.rect)
            self.screen.blit(bullet.image, pos)

        for bomb in self.client_game_state.bombs:
            pos = self.camera.apply(bomb.rect)
            self.screen.blit(bomb.image, pos)

        self.client_game_state.bombs.update(self.client_game_state)

        # Draw explosion particles
        self.client_game_state.explosion_manager.draw(self.screen, self.camera)

        # Draw fog of war
        self.apply_fog_of_war()

        if self.draw_debug:
            draw_debug_info(self.screen, self.client_game_state, self.camera)
        if self.show_minimap:
            self.draw_minimap()
        self.player_info_panel.draw()

        # Scale virtual frame to the actual window and present it
        try:
            scaled = pygame.transform.smoothscale(self.screen, self.window.get_size())
        except Exception:
            # Fallback if smoothscale fails for some reason
            scaled = pygame.transform.scale(self.screen, self.window.get_size())
        self.window.blit(scaled, (0, 0))

    def draw_minimap(self):
        """Draw a minimap in the bottom-right corner showing all players"""
        # Minimap dimensions and position
        minimap_width = 150
        minimap_height = 150
        minimap_x = SCREEN_WIDTH - minimap_width - 10  # 10px padding
        minimap_y = SCREEN_HEIGHT - minimap_height - 10
        minimap_border = 2

        # Calculate scale ratio (map size to minimap size)
        map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
        map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
        scale_x = minimap_width / map_width
        scale_y = minimap_height / map_height
        scale = min(scale_x, scale_y)  # Use the smaller scale to fit entire map

        # Draw background and border
        pygame.draw.rect(self.screen, (0, 0, 0), (minimap_x - minimap_border, minimap_y - minimap_border, minimap_width + 2*minimap_border, minimap_height + 2*minimap_border))
        pygame.draw.rect(self.screen, (50, 50, 50), (minimap_x, minimap_y, minimap_width, minimap_height))

        # Draw map blocks
        for tile in self.client_game_state.collidable_tiles:
            if tile.layer == 'Blocks':
                mini_x = minimap_x + int(tile.rect.x * scale)
                mini_y = minimap_y + int(tile.rect.y * scale)
                mini_w = max(2, int(tile.rect.width * scale))
                mini_h = max(2, int(tile.rect.height * scale))
                pygame.draw.rect(self.screen, (150, 75, 0), (mini_x, mini_y, mini_w, mini_h))

        # Draw player one (as green dot)
        try:
            player_one = self.client_game_state.get_playerone()
            if player_one.client_id != 'theserver':
                player_x = minimap_x + int(player_one.position[0] * scale)
                player_y = minimap_y + int(player_one.position[1] * scale)
                pygame.draw.circle(self.screen, (0, 255, 0), (player_x, player_y), 3)

            # Get camera viewport position
            # Instead of using offset_x and offset_y directly, calculate it from player position and screen center
            # This assumes camera is centered on player (modify if your camera logic is different)
            center_x = player_one.position[0] - SCREEN_WIDTH/2
            center_y = player_one.position[1] - SCREEN_HEIGHT/2

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
        for client_id, player in self.client_game_state.playerlist.items():
            if client_id != self.client_id:
                try:
                    pos = player.position
                    other_x = minimap_x + int(pos[0] * scale)
                    other_y = minimap_y + int(pos[1] * scale)
                    pygame.draw.circle(self.screen, (255, 0, 0), (other_x, other_y), 3)
                except Exception as e:
                    logger.error(f"Minimap other player error: {e} {type(e)}")

        # Draw bombs as yellow dots
        for bomb in self.client_game_state.bombs:
            try:
                bomb_x = minimap_x + int(bomb.position.x * scale)
                bomb_y = minimap_y + int(bomb.position.y * scale)
                pygame.draw.circle(self.screen, (255, 55, 0), (bomb_x, bomb_y), 2)
            except Exception as e:
                logger.error(f"Minimap bomb error: {e} {type(e)}")

    async def handle_on_mouse_press(self, x, y, button) -> None:
        if button == 1:
            player_one = self.client_game_state.get_playerone()
            if player_one and player_one.client_id != 'theserver':
                # Dead players can't shoot.
                if getattr(player_one, 'killed', False) or getattr(player_one, 'health', 0) <= 0:
                    if self.args.debug_gamestate:
                        logger.debug(f"{player_one} is dead, ignoring mouse press")
                    return
                # Convert screen coordinates to world coordinates
                mouse_world_pos = self.camera.reverse_apply(x, y)
                # player_world_pos = player_one.rect.center
                player_world_pos = (player_one.position[0] + player_one.rect.width/2, player_one.position[1] + player_one.rect.height/2)

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
                    "event_type": "on_bullet_fired",
                    "client_id": self.client_id,
                    "position": (bullet_pos.x, bullet_pos.y),
                    "direction": (direction_vector.x, direction_vector.y),
                    "timer": self.timer,
                    "handled": False,
                    "handledby": self.client_id,
                    "eventid": gen_randid()
                }

                await self.client_game_state.event_queue.put(event)

    async def handle_on_key_press(self, key):
        try:
            player_one = self.client_game_state.get_playerone()
        except AttributeError as e:
            logger.error(f"{e} {type(e)}")
            return
        if not player_one:
            return
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
            self.client_game_state.keyspressed.keys[key] = True
            return

        # Actions
        if key == pygame.K_SPACE:
            drop_bomb_event = player_one.drop_bomb()
            if drop_bomb_event and drop_bomb_event.get("event_type") == "player_drop_bomb":
                await self.client_game_state.event_queue.put(drop_bomb_event)
            return

    async def handle_on_key_release(self, key):
        try:
            player_one = self.client_game_state.get_playerone()
        except AttributeError as e:
            logger.error(f"{e} {type(e)}")
            return
        if key in (pygame.K_UP, pygame.K_w):
            player_one.change_y = 0
            self.client_game_state.keyspressed.keys[key] = False
        elif key in (pygame.K_DOWN, pygame.K_s):
            player_one.change_y = 0
            self.client_game_state.keyspressed.keys[key] = False
        elif key in (pygame.K_LEFT, pygame.K_a):
            player_one.change_x = 0
            self.client_game_state.keyspressed.keys[key] = False
        elif key in (pygame.K_RIGHT, pygame.K_d):
            player_one.change_x = 0
            self.client_game_state.keyspressed.keys[key] = False
        if key == pygame.K_SPACE:
            pass
            # drop_bomb_event = player_one.drop_bomb()
            # await self.client_game_state.event_queue.put(drop_bomb_event)
        self.client_game_state.keyspressed.keys[key] = False

    async def update(self):
        try:
            player_one = self.client_game_state.get_playerone()
        except AttributeError as e:
            logger.error(f"{e} {type(e)}")
            await asyncio.sleep(1)
            return
        current_time = time.time()
        self.delta_time = current_time - self.last_frame_time
        self.last_frame_time = current_time
        self.timer += self.delta_time
        if player_one.client_id != 'theserver':
            player_one.update(self.client_game_state.collidable_tiles)

            map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
            map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
            player_one.position.x = max(0, min(player_one.position.x, map_width - player_one.rect.width))
            player_one.position.y = max(0, min(player_one.position.y, map_height - player_one.rect.height))

            player_one.rect.x = int(player_one.position.x)
            player_one.rect.y = int(player_one.position.y)

            self.camera.update(player_one)

            self.client_game_state.bullets.update(self.client_game_state.collidable_tiles)
            self.client_game_state.check_bullet_collisions()
            # await self.client_game_state.explosion_manager.update(self.client_game_state.collidable_tiles, self.client_game_state)

            # Use the already calculated delta time
            await self.client_game_state.explosion_manager.update(self.client_game_state.collidable_tiles, self.client_game_state, self.delta_time)
            self.client_game_state.check_flame_collisions()

            self.client_game_state.cleanup_playerlist()
            playerlist = [player.to_dict() if hasattr(player, 'to_dict') else player for player in self.client_game_state.playerlist.values()]
            update_event = {
                "event_time": self.timer,
                "event_type": "player_update",
                "client_id": str(player_one.client_id),
                "client_name": str(getattr(player_one, "client_name", "client_namenotset")),
                "position": (player_one.position.x, player_one.position.y),
                "health": player_one.health,
                "score": player_one.score,
                "bombs_left": player_one.bombs_left,
                "handled": False,
                "handledby": "game_update",
                "playerlist": playerlist,
                "eventid": gen_randid(),}
            current_time = time.time()
            if current_time - self.last_position_update > self.position_update_interval:
                await self.client_game_state.event_queue.put(update_event)
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

        # Fill with semi-transparent black
        self.fog_surface.fill((0, 0, 0, 250))
        # Reset mask to fully opaque black
        self._visibility_mask.fill((0, 0, 0, 255))

        player_one = self.client_game_state.get_playerone()
        # Convert world to screen without extra allocations/calls
        map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
        map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
        camera_x = player_one.position.x - SCREEN_WIDTH / 2
        camera_y = player_one.position.y - SCREEN_HEIGHT / 2
        camera_x = max(0, min(camera_x, map_width - SCREEN_WIDTH))
        camera_y = max(0, min(camera_y, map_height - SCREEN_HEIGHT))
        screen_x = int(player_one.position.x - camera_x)
        screen_y = int(player_one.position.y - camera_y)

        pygame.draw.circle(self._visibility_mask, (0, 0, 0, 0), (screen_x, screen_y), self.fog_radius)
        self.fog_surface.blit(self._visibility_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.screen.blit(self.fog_surface, (0, 0))

    def camera_apply_pos(self, world_pos):
        """Convert world position to screen position"""
        player_one = self.client_game_state.get_playerone()
        camera_x = player_one.position.x - SCREEN_WIDTH/2
        camera_y = player_one.position.y - SCREEN_HEIGHT/2

        # Clamp camera to map boundaries
        map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
        map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
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
