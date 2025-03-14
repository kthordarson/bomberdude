import time
import asyncio
import requests
import pygame
import socket
from pygame.math import Vector2 as Vec2d
import orjson as json
from loguru import logger
from utils import gen_randid
from gamestate import GameState
from constants import UPDATE_TICK, PLAYER_MOVEMENT_SPEED, SCREEN_WIDTH, SCREEN_HEIGHT
from camera import Camera
from objects.player import Bomberplayer
from debug import draw_debug_info
from gamestate import PlayerState

class Bomberdude():
	def __init__(self, args):
		self.title = "Bomberdude"
		self.args = args
		self.draw_debug = True
		self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
		# self.screen = pygame.display.get_surface()
		self.running = True
		self.selected_bomb = 1
		self.client_id = str(gen_randid())
		self.client_game_state = GameState(args=self.args, client_id=self.client_id)
		self._connected = False
		self.timer = 0
		self.mouse_pos = Vec2d(x=0, y=0)
		self.background_color = (100, 149, 237)
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setblocking(False)  # Make non-blocking
		self.last_position_update = 0
		self.last_frame_time = time.time()
		self.delta_time = 0

	def __repr__(self):
		return f"Bomberdude( {self.title} playerlist: {len(self.client_game_state.playerlist)} players_sprites: {len(self.client_game_state.players_sprites)} {self.connected()})"

	def connected(self):
		return self._connected

	async def connect(self):
		self.sock.setblocking(False)
		logger.info(f'connecting to server... event_queue: {self.client_game_state.event_queue.qsize()} ')
		await asyncio.get_event_loop().sock_connect(self.sock, (self.args.server, 9696))
		if self.args.debug:
			logger.debug(f'conn: {self.connected()}')
		try:
			resp = requests.get(f"http://{self.args.server}:9699/get_tile_map").text
			resp = json.loads(resp)
			mapname = resp.get("mapname")
			tile_x = resp.get('position').get('position')[0]
			tile_y = resp.get('position').get('position')[1]
			# pos = Vec2d(x=resp.get('position').get('position')[0], y=resp.get('position').get('position')[1])
			# logger.debug(f"map {mapname} {pos=} {resp=}")
		except Exception as e:
			logger.error(f"{type(e)} {e=} {resp}")
			raise e
		self.client_game_state.load_tile_map(mapname)
		pixel_x = tile_x * self.client_game_state.tile_map.tilewidth
		pixel_y = tile_y * self.client_game_state.tile_map.tileheight

		pos = Vec2d(x=pixel_x, y=pixel_y)

		map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
		map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
		self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, map_width, map_height)
		if self.args.debug:
			logger.debug(f'conn: {self.connected()} {pos=} event_queue: {self.client_game_state.event_queue.qsize()}')

		connection_event = {
			"event_time": 0,
			"event_type": "connection_event",
			"client_id": str(self.client_id),
			"position": (pos.x, pos.y),
			"handled": False,
			"handledby": "connection_event",
			"eventid": gen_randid(),
		}
		player_one = Bomberplayer(texture="data/playerone.png", client_id=self.client_id)
		player_one.position = pos
		self.client_game_state.players_sprites.add(player_one)
		while not self.client_game_state.ready():
			await self.client_game_state.event_queue.put(connection_event)
			# await self.client_game_state.broadcast_event({"msgtype": "game_event", "event": connection_event})
			self._connected = True
			await asyncio.sleep(0.1)
			logger.debug(f'conn: {self.connected()} event_queue: {self.client_game_state.event_queue.qsize()} waiting for client_game_state.ready {self.client_game_state.ready()}')
			await asyncio.sleep(0.2)
			if self.client_game_state.ready():
				return True

	def draw_player(self, player_data):
		# logger.debug(f'player_data: {player_data} {type(player_data)}')
		try:
			if isinstance(player_data, dict):
				player = Bomberplayer(texture="data/player2.png", client_id=player_data.get('client_id'))
				player.position = Vec2d(player_data.get('position', [0, 0]))
				player.rect.topleft = (player.position.x, player.position.y)
				self.screen.blit(player.image, self.camera.apply(player.rect))
			elif isinstance(player_data, PlayerState):
				player = Bomberplayer(texture="data/player2.png", client_id=player_data.client_id)
				player.position = Vec2d(player_data.position)
				# player.rect.topleft = (player.position[0], player.position[1])
				player.rect.topleft = (player.position.x, player.position.y)
				self.screen.blit(player.image, self.camera.apply(player.rect))
			else:
				logger.warning(f'player_data: {player_data} {type(player_data)}')
		except Exception as e:
			logger.error(f'{e} {type(e)} player_data: {player_data}')

	def on_draw(self):
		# Clear screen
		self.screen.fill((0, 0, 0))

		self.client_game_state.render_map(self.screen, self.camera)
		# Draw local player
		player_one = self.client_game_state.get_playerone()
		self.screen.blit(player_one.image, self.camera.apply(player_one.rect))

		# Draw local player from players_sprites
		# self.client_game_state.get_playerone().draw(self.screen)
		# for player in self.client_game_state.players_sprites:
		# 	if player.client_id == self.client_id:
		# 		player.draw(self.screen)

		# Draw remote players from playerlist
		for client_id, player in self.client_game_state.playerlist.items():
			if client_id != self.client_id:
				self.draw_player(player)

		# Draw bullets, bombs, etc.
		for bullet in self.client_game_state.bullets:
			# Draw bullet
			pos = self.camera.apply(bullet.rect)
			self.screen.blit(bullet.image, pos)

		for bomb in self.client_game_state.bombs:
			# Draw bomb
			pos = self.camera.apply(bomb.rect)
			self.screen.blit(bomb.image, pos)

		self.client_game_state.bombs.update(
			self.client_game_state.collidable_tiles,
			self.client_game_state.explosion_manager
		)

		# Draw explosion particles
		self.client_game_state.explosion_manager.draw(self.screen, self.camera)

		if self.draw_debug:
			draw_debug_info(self.screen, self.client_game_state)
			# Add camera position debug
			font = pygame.font.Font(None, 26)
			player_one = self.client_game_state.get_playerone()
			debug_text = font.render(f"Camera pos: {self.camera.position} Player pos: {player_one.position}", True, (255, 255, 255))
			self.screen.blit(debug_text, (10, 120))

		if self.draw_debug and len(self.client_game_state.bullets) > 0:
			# Draw debug lines for all bullets
			for bullet in self.client_game_state.bullets:
				bullet_screen = self.camera.apply(bullet.rect).center
				line_end = (bullet_screen[0] + bullet.direction.x * 25, bullet_screen[1] + bullet.direction.y * 25)
				pygame.draw.line(self.screen, (255, 0, 0), bullet_screen, line_end, 2)
				# Draw a line showing bullet direction
				start_pos = self.camera.apply(bullet.rect).center
				end_pos = (start_pos[0] + bullet.direction.x * 25, start_pos[1] + bullet.direction.y * 25)
				pygame.draw.line(self.screen, (255, 255, 0), start_pos, end_pos, 2)

	async def handle_on_mouse_press(self, x, y, button):
		if button == 1:
			player_one = self.client_game_state.get_playerone()
			if player_one:
				# Convert screen coordinates to world coordinates
				mouse_world_pos = self.camera.reverse_apply(x, y)
				# player_world_pos = player_one.rect.center
				player_world_pos = (player_one.position.x + player_one.rect.width/2, player_one.position.y + player_one.rect.height/2)

				# Calculate direction in world space
				direction_vector = Vec2d(
					mouse_world_pos[0] - player_world_pos[0],
					mouse_world_pos[1] - player_world_pos[1]
				)

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
					"event_type": "bulletfired",
					"client_id": self.client_id,
					"position": (bullet_pos.x, bullet_pos.y),
					"direction": (direction_vector.x, direction_vector.y),
					"timer": self.timer,
					"handled": False,
					"handledby": self.client_id,
					"eventid": gen_randid()
				}

				if self.args.debug:
					logger.debug(f'bullet_pos: {bullet_pos} direction_vector: {direction_vector}  mouse_world_pos: {mouse_world_pos} player_world_pos: {player_world_pos}  self.camera.position:{self.camera.position}')

				await self.client_game_state.event_queue.put(event)

	def handle_on_key_press(self, key):
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
			pass
		elif key == pygame.K_F6:
			pass
		elif key == pygame.K_F7:
			pygame.display.toggle_fullscreen()
		elif key == pygame.K_ESCAPE or key == pygame.K_q or key == 27:
			self._connected = False
			self.running = False
			logger.info("quit")
			pygame.event.post(pygame.event.Event(pygame.QUIT))
			return
		elif key == pygame.K_UP or key == pygame.K_w or key == 119:
			player_one.change_y = -PLAYER_MOVEMENT_SPEED
			self.client_game_state.keyspressed.keys[key] = True
		elif key == pygame.K_DOWN or key == pygame.K_s or key == 115:
			player_one.change_y = PLAYER_MOVEMENT_SPEED
			self.client_game_state.keyspressed.keys[key] = True
		elif key == pygame.K_LEFT or key == pygame.K_a or key == 97:
			player_one.change_x = -PLAYER_MOVEMENT_SPEED
			self.client_game_state.keyspressed.keys[key] = True
		elif key == pygame.K_RIGHT or key == pygame.K_d or key == 100:
			player_one.change_x = PLAYER_MOVEMENT_SPEED
			self.client_game_state.keyspressed.keys[key] = True

	async def handle_on_key_release(self, key):
		try:
			player_one = self.client_game_state.get_playerone()
		except AttributeError as e:
			logger.error(f"{e} {type(e)}")
			return
		if key == pygame.K_UP or key == pygame.K_w:
			player_one.change_y = 0
			self.client_game_state.keyspressed.keys[key] = False
		elif key == pygame.K_DOWN or key == pygame.K_s:
			player_one.change_y = 0
			self.client_game_state.keyspressed.keys[key] = False
		elif key == pygame.K_LEFT or key == pygame.K_a:
			player_one.change_x = 0
			self.client_game_state.keyspressed.keys[key] = False
		elif key == pygame.K_RIGHT or key == pygame.K_d:
			player_one.change_x = 0
			self.client_game_state.keyspressed.keys[key] = False
		if key == pygame.K_SPACE:
			drop_bomb_event = player_one.drop_bomb()
			await self.client_game_state.event_queue.put(drop_bomb_event)
		self.client_game_state.keyspressed.keys[key] = False

	async def update(self):
		try:
			player_one = self.client_game_state.get_playerone()
		except AttributeError as e:
			logger.error(f"{e} {type(e)}")
			await asyncio.sleep(0.1)
			return
		# self.timer += 1 / 60
		current_time = time.time()
		self.delta_time = current_time - self.last_frame_time
		self.last_frame_time = current_time
		self.timer += self.delta_time

		player_one.update(self.client_game_state.collidable_tiles)

		map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
		map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
		player_one.position.x = max(0, min(player_one.position.x, map_width - player_one.rect.width))
		player_one.position.y = max(0, min(player_one.position.y, map_height - player_one.rect.height))

		player_one.rect.x = int(player_one.position.x)
		player_one.rect.y = int(player_one.position.y)

		self.camera.update(player_one)

		self.client_game_state.bullets.update(self.client_game_state.collidable_tiles)
		self.client_game_state.bombs.update()
		self.client_game_state.explosion_manager.update(self.client_game_state.collidable_tiles)

		playerlist = [player.to_dict() if hasattr(player, 'to_dict') else player for player in self.client_game_state.playerlist.values()]
		update_event = {
			"event_time": self.timer,
			"msgtype": "player_update",
			"event_type": "player_update",
			"client_id": str(player_one.client_id),
			"position": (player_one.position.x, player_one.position.y),
			"angle": player_one.angle,
			"health": player_one.health,
			"score": player_one.score,
			"bombsleft": player_one.bombsleft,
			"handled": False,
			"handledby": "game_update",
			"playerlist": playerlist,
			"eventid": gen_randid(),}
		current_time = time.time()
		if current_time - self.last_position_update > 0.035:
			await self.client_game_state.event_queue.put(update_event)
			await asyncio.sleep(1 / UPDATE_TICK)
			self.last_position_update = current_time
