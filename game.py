import asyncio
import requests
import pygame
import socket
from pygame.math import Vector2 as Vec2d
import math
import json
from queue import Empty

from loguru import logger
from utils import get_map_coordinates_rev, gen_randid
from gamestate import GameState
from constants import UPDATE_TICK, PLAYER_MOVEMENT_SPEED, BULLET_SPEED, BULLETDEBUG,GRAPH_HEIGHT, GRAPH_WIDTH, GRAPH_MARGIN, SCREEN_WIDTH, SCREEN_HEIGHT
from camera import Camera
from objects.player import Bomberplayer
from objects.bullets import Bullet
from debug import draw_debug_info

class Bomberdude():
	def __init__(self, args):
		self.title = "Bomberdude"
		self.args = args
		self.draw_debug = True
		self.left_pressed = False
		self.right_pressed = False
		self.up_pressed = False
		self.down_pressed = False
		self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
		# self.screen = pygame.display.get_surface()
		self.manager = None  # Replace with pygame UI manager if needed
		self.running = True
		self.selected_bomb = 1
		self.client_id = str(gen_randid())
		self.client_game_state = GameState(args=self.args, client_id=self.client_id)
		self._connected = False
		self._show_kill_screen = False
		self.show_kill_timer = 1
		self.show_kill_timer_start = 1
		self.timer = 0
		self.mouse_pos = Vec2d(x=0, y=0)
		self.background_color = (100, 149, 237)
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setblocking(False)  # Make non-blocking

	def __repr__(self):
		return f"Bomberdude( {self.title} playerlist: {len(self.client_game_state.playerlist)} players_sprites: {len(self.client_game_state.players_sprites)} c:{self._connected} {self.connected()})"

	def connected(self):
		return self._connected

	async def oldconnect(self):
		"""Connect to server and set up sockets"""
		try:
			self.sock.setblocking(False)  # Make non-blocking
			await self.do_connect()
			if self.args.debug:
				logger.info(f'{self} connected successfully')
			return True
		except Exception as e:
			logger.error(f"Connection failed: {e}")
			self._connected = False
			return False

	async def connect(self):
		self.sock.setblocking(False)
		logger.info(f'connecting to server... event_queue: {self.client_game_state.event_queue.qsize()} ')
		await asyncio.get_event_loop().sock_connect(self.sock, (self.args.server, 9696))
		if self.args.debug:
			logger.debug(f'conn: {self.connected()}/{self._connected}')
		try:
			resp = requests.get(f"http://{self.args.server}:9699/get_tile_map").text
			resp = json.loads(resp)
			mapname = resp.get("mapname")
			pos = Vec2d(x=resp.get('position').get('position')[0], y=resp.get('position').get('position')[1])
			logger.debug(f"map {mapname} {pos=} {resp=}")
		except Exception as e:
			logger.error(f"{type(e)} {e=} {resp}")
			raise e
		self.client_game_state.load_tile_map(mapname)
		map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
		map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
		self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, map_width, map_height)
		if self.args.debug:
			logger.debug(f'conn: {self.connected()} - {self._connected} {pos=} event_queue: {self.client_game_state.event_queue.qsize()}')

		self.setup_panels()
		self.setup_labels()
		connection_event = {
			"event_time": 0,
			"event_type": "newconnection",
			"client_id": str(self.client_id),
			"position": (pos.x, pos.y),
			"handled": False,
			"handledby": "do_connect",
			"eventid": gen_randid(),
		}
		await self.client_game_state.event_queue.put(connection_event)
		await asyncio.sleep(0.1)
		self._connected = True
		player_one = Bomberplayer(texture="data/playerone.png", client_id=self.client_id)
		player_one.position = pos
		self.client_game_state.players_sprites.add(player_one)
		if self.args.debug:
			logger.debug(f'conn: {self.connected()} - {self._connected} setup done event_queue: {self.client_game_state.event_queue.qsize()}')

		return True

	def setup_labels(self):
		self.netplayer_labels = {}

	def setup_panels(self):
		pass  # Implement if needed

	def center_camera_on_player(self, speed=0.2):
		player = self.client_game_state.get_playerone()
		screen_center_x = player.center_x - (SCREEN_WIDTH / 2)
		screen_center_y = player.center_y - (SCREEN_HEIGHT / 2)
		if screen_center_x < 0:
			screen_center_x = 0
		if screen_center_y < 0:
			screen_center_y = 0
		self.camera.position = (screen_center_x, screen_center_y)

	def draw_player(self, player):
		try:
			if player.position is None:
				logger.error(f'Player position is None: {player}')
				return

			# Get position coordinates safely
			if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
				# Vec2d object
				pos_x, pos_y = player.position.x, player.position.y
			elif isinstance(player.position, (tuple, list)) and len(player.position) >= 2:
				# Tuple or list
				pos_x, pos_y = player.position[0], player.position[1]
			else:
				logger.error(f'Unknown position format: {type(player.position)}')
				return

			color = (0, 255, 0) if player.client_id == self.client_game_state.get_playerone().client_id else (255, 0, 0)
			rect = pygame.Rect(pos_x, pos_y, 32, 32)
			position = self.camera.apply(rect).topleft
			pygame.draw.circle(self.screen, color, position, 10)

			# Draw player image if available
			if hasattr(player, 'image'):
				rect = player.rect if hasattr(player, 'rect') else rect
				self.screen.blit(player.image, self.camera.apply(rect))
		except Exception as e:
			logger.error(f'{e} {type(e)} player: {player}')

	def old2draw_player(self, player):
		try:
			if player.position is None:
				logger.error(f'Player position is None: {player}')
				return

			# Check if position is already a tuple/list or if it's a Vec2d
			if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
				# It's a Vec2d
				pos_x, pos_y = player.position.x, player.position.y
			else:
				# It's a tuple/list
				pos_x, pos_y = player.position[0], player.position[1]

			color = (0, 255, 0) if player.client_id == self.client_game_state.get_playerone().client_id else (255, 0, 0)
			position = self.camera.apply(pygame.Rect(pos_x, pos_y, 0, 0)).topleft
			pygame.draw.circle(self.screen, color, position, 10)

			# Draw player image if available
			if hasattr(player, 'image'):
				rect = player.rect if hasattr(player, 'rect') else pygame.Rect(pos_x, pos_y, 32, 32)
				self.screen.blit(player.image, self.camera.apply(rect))
		except Exception as e:
			logger.error(f'{e} {type(e)} player: {player}')

	def olddraw_player(self, player):
		try:
			if player.position is None:
				logger.error(f'Player position is None: {player}')
				return
			color = (0, 255, 0) if player.client_id == self.client_game_state.get_playerone().client_id else (255, 0, 0)
			# position = (int(player.position[0]), int(player.position[1]))  # Ensure position is a tuple of integers
			position = self.camera.apply(pygame.Rect(player.position[0], player.position[1], 0, 0)).topleft
			pygame.draw.circle(self.screen, color, position, 10)
			# logger.info(f'drawing player: {player}')
		except Exception as e:
			logger.error(f'{e} {type(e)} player: {player}')

	def on_draw(self):
		# self.screen.fill(self.background_color)
		# Draw game elements here
		self.screen.fill((200, 249, 237))
		try:
			self.client_game_state.render_map(self.screen, self.camera)
		except Exception as e:
			logger.error(f'{e} {type(e)}')
		for bullet in self.client_game_state.bullets:
			self.screen.blit(bullet.image, self.camera.apply(bullet))
		for bomb in self.client_game_state.bombs:
			self.screen.blit(bomb.image, self.camera.apply(bomb))
		for player in self.client_game_state.playerlist.values():
			if player.client_id != self.client_id:
				self.draw_player(player)
				# logger.info(f'drawing player: {player}')
			# self.draw_player(player)
		try:
			player_one = self.client_game_state.get_playerone()
		except AttributeError as e:
			logger.error(f'{e} {type(e)}')
			return
		self.screen.blit(player_one.image, self.camera.apply(player_one))
		if self.draw_debug:
			draw_debug_info(self.screen, self.client_game_state)
		pygame.display.flip()

	def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
		self.mouse_pos = Vec2d(x=x, y=y)

	async def handle_on_mouse_press(self, x, y, button):
		if button == 1:
			player_one = self.client_game_state.get_playerone()
			if player_one:
				# Convert to world coordinates by subtracting camera offset
				# Camera position is already negative of the world offset
				mouse_world = Vec2d(
					x - self.camera.position.x,
					y - self.camera.position.y
				)
				player_world = Vec2d(player_one.rect.center)

				# Calculate direction in world space
				direction = (mouse_world - player_world).normalize()
				bullet = player_one.shoot(direction)
				# self.client_game_state.bullets.add(bullet)
				event = {
					"event_time": 0,
					"event_type": "bulletfired",
					"client_id": self.client_id,
					"position": (bullet.rect.x, bullet.rect.y),
					"direction": (direction.x, direction.y),
					"ba": 1,
					"timer": 1,
					"handled": False,
					"handledby": self.client_id,
					"eventid": gen_randid(),
				}
				if self.args.debug:
					# logger.debug(f'{bullet} {self.client_game_state.event_queue.qsize()}')
					pass  # logger.debug(f'bullet: {bullet} {direction=} {mouse_world=} {player_world=} {self.camera.position=} ')
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
			logger.warning("quit")
			pygame.event.post(pygame.event.Event(pygame.QUIT))
			# pygame.display.quit()
			# pygame.quit()
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
		# key = pygame.key.get_pressed()
		# logger.info(f'{key=}')
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
		self.timer += 1 / 60
		self.client_game_state.bullets.update(self.client_game_state.collidable_tiles)
		self.client_game_state.bombs.update()
		map_width = self.client_game_state.tile_map.width * self.client_game_state.tile_map.tilewidth
		map_height = self.client_game_state.tile_map.height * self.client_game_state.tile_map.tileheight
		player_one.update(self.client_game_state.collidable_tiles)
		player_one.position.x = max(0, min(player_one.position.x, map_width - player_one.rect.width))
		player_one.position.y = max(0, min(player_one.position.y, map_height - player_one.rect.height))
		player_one.rect.topleft = player_one.position
		self.camera.update2(player_one)
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
			"eventid": gen_randid(),}
		await self.client_game_state.event_queue.put(update_event)
		await asyncio.sleep(1 / UPDATE_TICK)
