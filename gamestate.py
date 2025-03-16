import asyncio
import pygame
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Group
from loguru import logger
import time
from dataclasses import dataclass, field
from utils import gen_randid
from objects.player import KeysPressed
from objects.bullets import Bullet
from objects.bombs import Bomb
from objects.explosionmanager import ExplosionManager
import pytmx
from pytmx import load_pygame
import json

@dataclass
class PlayerState:
	client_id: str
	position: tuple
	health: int
	bombsleft: int
	angle: float
	score: int
	prev_position: tuple | None = None
	target_position: tuple | None = None
	interp_time: float | None = None
	position_updated: bool = False
	msg_dt: float | None = None
	timeout: bool | None = None
	killed: bool | None = None
	msgtype: str | None = None
	event_time: int | None = None
	event_type: str | None = None
	handled: bool = False
	handledby: str = 'PlayerState'
	playerlist: list = field(default_factory=list)
	eventid: str = field(default_factory=gen_randid)

	def to_dict(self):
		return {
			'client_id': self.client_id,
			'position': self.position,
			'health': self.health,
			'bombsleft': self.bombsleft,
			'angle': self.angle,
			'score': self.score,
			'msg_dt': self.msg_dt,
			'timeout': self.timeout,
			'killed': self.killed,
			'msgtype': self.msgtype}

@dataclass
class GameState:

	def __init__(self, args, mapname=None, client_id=None):
		self.client_id = client_id
		self.args = args
		self.players_sprites = Group()
		self.bullets = Group()
		self.bombs = Group()
		self.flames = Group()
		self.particles = Group()
		self.mapname = mapname
		self.event_queue = asyncio.Queue()
		self.keyspressed = KeysPressed('gamestate')
		self.tile_map = pytmx.TiledMap(mapname)
		self.collidable_tiles = []
		self.connections = set()
		self.client_queue = asyncio.Queue()
		self.playerlist = {}  # dict = field(default_factory=dict)
		self.last_pos_broadcast = 0
		self.explosion_manager = ExplosionManager()
		self._ready = False

	def __repr__(self):
		return f'Gamestate ( event_queue:{self.event_queue.qsize()} client_queue:{self.client_queue.qsize()}  players:{len(self.playerlist)} players_sprites:{len(self.players_sprites)})'

	def destroy_block(self, block):
		"""
		Simplest possible version - just remove the block from collision group
		"""
		x, y = block.rect.topleft
		tile_x = x // self.tile_map.tilewidth
		tile_y = y // self.tile_map.tileheight
		layer = self.tile_map.get_layer_by_name('Blocks')
		# background_layer = self.tile_map.get_layer_by_name('Background')

		if block in self.collidable_tiles:
			self.collidable_tiles.remove(block)
			logger.info(f"Block {block} removed at {block.rect.topleft}")
			layer.data[tile_y][tile_x] = 0  # Set to empty tile
			# background_layer.data[tile_y][tile_x] = 1  # Set to empty tile
			# block.kill()

	def ready(self):
		return self._ready

	def add_connection(self, connection):
		"""Add a new client connection"""
		self.connections.add(connection)
		logger.info(f"New connection added. Total connections: {len(self.connections)}")

	def remove_connection(self, connection):
		"""Remove a client connection"""
		if connection in self.connections:
			self.connections.remove(connection)
			logger.info(f"Connection removed. Total connections: {len(self.connections)}")

	async def broadcast_event(self, event):
		# Only broadcast player_update events at a reduced rate
		if event.get('event_type') == 'player_update':
			if time.time() - self.last_pos_broadcast < 0.03:  # Only broadcast 10 times/sec
				return
			self.last_pos_broadcast = time.time()
		try:
			await self.broadcast_state({"msgtype": "game_event", "event": event})
		except Exception as e:
			logger.error(f"Error in broadcast_event: {e} {type(e)}")

	async def broadcast_state(self, game_state):
		"""Broadcast game state to all connected clients"""
		dead_connections = set()
		loop = asyncio.get_event_loop()
		try:
			# Fix the data encoding
			if isinstance(game_state, bytes):
				data = game_state + b'\n'  # Add newline for message boundary
			else:
				data = json.dumps(game_state).encode('utf-8') + b'\n'
		except TypeError as e:
			logger.error(f"Error encoding game_state: {e} game_state: {game_state}")
			return

		try:
			for conn in self.connections:
				try:
					# Check if it's a StreamWriter (from NewBombServer) or a socket
					if hasattr(conn, 'write'):  # StreamWriter
						if conn.is_closing():
							dead_connections.add(conn)
							continue
						conn.write(data)
						await conn.drain()
					else:  # Socket
						await loop.sock_sendall(conn, data)
				except Exception as e:
					logger.error(f"Error broadcasting to client: {e}")
					dead_connections.add(conn)
			# Clean up dead connections
			for dead_conn in dead_connections:
				logger.warning(f"Removing {dead_conn} from connections")
				self.remove_connection(dead_conn)
		except Exception as e:
			logger.error(f"Error in broadcast_state: {e} {type(e)}")

	def get_playerone(self):
		for player in self.players_sprites:
			if player.client_id == self.client_id:
				return player
		raise AttributeError(f'player one NOT found in self.players_sprites: {self.players_sprites}')

	def load_tile_map(self, mapname):
		self.mapname = mapname
		self.tile_map = load_pygame(self.mapname)
		for layer in self.tile_map.visible_layers:
			if isinstance(layer, pytmx.TiledTileLayer):
				for x, y, gid in layer:
					tile = self.tile_map.get_tile_image_by_gid(gid)
					if tile:
						sprite = pygame.sprite.Sprite()
						sprite.image = tile
						# sprite.rect = pygame.Rect(x * TILE_SCALING, y * TILE_SCALING, TILE_SCALING, TILE_SCALING)
						sprite.rect = pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)
						sprite.layer = layer.name  # Set the layer attribute
						if layer.properties.get('collidable'):
							self.collidable_tiles.append(sprite)
			else:
				logger.warning(f'unknown layer {layer}')
		logger.debug(f'loading {self.mapname} done. ')

	def render_map(self, screen, camera):
		self.explosion_manager.draw(screen, camera)
		for layer in self.tile_map.visible_layers:
			if isinstance(layer, pytmx.TiledTileLayer):
				for x, y, gid in layer:
					tile = self.tile_map.get_tile_image_by_gid(gid)
					if tile:
						screen.blit(tile, camera.apply(pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)))

	def update_game_state(self, clid, msg):
		playerdict = {
			'client_id': clid,
			'position': msg.get('position'),
			'angle': msg.get('angle'),
			'score': msg.get('score'),
			'health': msg.get('health'),
			'msg_dt': msg.get('msg_dt'),
			'timeout': msg.get('timeout'),
			'killed': msg.get('killed'),
			'msgtype': 'update_game_state',
			'bombsleft': msg.get('bombsleft'),
		}
		self.playerlist[clid] = playerdict

	async def update_game_event(self, game_event):
		if self.args.debug:
			if game_event.get('event_type') != 'player_update':
				pass  # logger.info(f'update_game_event {game_event.get('event_type')} event_queue: {self.event_queue.qsize()} client_queue: {self.client_queue.qsize()}')
		event_type = game_event.get('event_type')
		msg_client_id = game_event.get("client_id")
		match event_type:
			case 'player_update':
				# Update other player's position in playerlist
				if msg_client_id != self.client_id:
					position = game_event.get('position')
					if msg_client_id in self.playerlist:
						player = self.playerlist[msg_client_id]
						if isinstance(player, dict):
							# Direct update without complex interpolation
							player['position'] = position
							player['client_id'] = msg_client_id
						else:
							# Handle PlayerState objects
							player.position = position
					else:
						# Add new player with minimal required fields
						self.playerlist[msg_client_id] = {
							'client_id': msg_client_id,
							'position': position,
							'angle': game_event.get('angle', 0)
						}
				await self.broadcast_event(game_event)
			case 'playerquit':
				client_id = game_event.get('client_id')
				if client_id in self.playerlist:
					logger.info(f"Player {client_id} has disconnected")
					del self.playerlist[client_id]

				# self.playerlist[msg_client_id]['playerquit'] = True
				await self.event_queue.put(game_event)
			case 'acknewplayer':
				self._ready = True
				game_event['handled'] = True

			case 'connection_event':
				game_event['handled'] = True
				game_event['handledby'] = 'ugsnc'
				game_event['event_type'] = 'acknewplayer'
				# await self.broadcast_event(game_event)
				await self.broadcast_state({"msgtype": "game_event", "event": game_event})
				# await self.event_queue.put(game_event)
			case 'drop_bomb':
				game_event['handledby'] = 'ugsbomb'
				try:
					if msg_client_id == self.client_id:
						bomb = Bomb(position=game_event.get('position'))
					else:
						bomb = Bomb(position=game_event.get('position'), bomb_size=(5,5))
					self.bombs.add(bomb)
				except AttributeError as e:
					logger.error(f'{e} unable to add bomb {game_event=} players_sprites: {self.players_sprites}')
				game_event['event_type'] = 'ackbombdrop'
				await self.broadcast_event(game_event)

			case 'ackbombdrop':
				if msg_client_id != self.client_id:
					bomb = Bomb(position=game_event.get('position'), bomb_size=(5,5))
				elif msg_client_id == self.client_id:
					bomb = Bomb(position=game_event.get('position'), bomb_size=(10,10))
				self.bombs.add(bomb)

			case 'bulletfired':
				game_event['handledby'] = 'update_game_event'
				game_event['event_type'] = 'ackbullet'
				game_event['handled'] = True
				await self.broadcast_event(game_event)

			case 'ackbullet':
				# bullet = Bullet()
				bullet_position = Vec2d(game_event.get('position')[0], game_event.get('position')[1])
				bullet_direction = Vec2d(game_event.get('direction')[0], game_event.get('direction')[1])
				if msg_client_id == self.get_playerone().client_id:
					bullet_size = (10,10)
				else:
					bullet_size = (5,5)
				bullet = Bullet(position=bullet_position, direction=bullet_direction, screen_rect=self.get_playerone().rect, bullet_size=bullet_size)
				self.bullets.add(bullet)
			case _:
				# payload = {'msgtype': 'error99', 'payload': ''}
				logger.warning(f'unknown game_event:{event_type} from game_event={game_event}')
				# await self.event_queue.put(payload)

	def to_json(self):
		"""Convert game state to JSON-serializable format"""
		playerlist = []
		for player in self.playerlist.values():
			if hasattr(player, 'to_dict'):
				playerlist.append(player.to_dict())
			else:
				playerlist.append(player)

		return {
			'event_type': 'playerlistupdate',
			'msgtype': 'playerlist',
			'playerlist': playerlist,
			'connections': len(self.connections),
		}

	def from_json(self, data):
		if data.get('msgtype') == 'send_game_state':
			for player_data in data.get('playerlist', []):
				client_id = player_data.get('client_id')
				if client_id != self.client_id:  # Don't update our own player
					if client_id in self.playerlist:
						# Update existing player
						player = self.playerlist[client_id]
						position = player_data.get('position')
						player.position = position
					else:
						# Create new player
						self.playerlist[client_id] = PlayerState(**player_data)
		elif data.get('msgtype') == 'playerlist':
			try:
				for player_data in data.get('playerlist', []):
					client_id = player_data.get('client_id')
					if client_id != self.client_id:  # Don't update our own player
						if client_id in self.playerlist:
							# Update existing player
							player = self.playerlist[client_id]
							position = player_data.get('position')
							if position:
								if hasattr(player, 'position'):
									if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
										player.position.x, player.position.y = position[0], position[1]
									else:
										player.position = position
								else:
									player['position'] = position

								# Set up interpolation data
								if hasattr(player, 'target_position'):
									player.target_position = position
									player.position_updated = True
						else:
							# Create new player
							try:
								self.playerlist[client_id] = PlayerState(
									client_id=client_id,
									position=player_data.get('position', (0, 0)),
									health=player_data.get('health', 100),
									bombsleft=player_data.get('bombsleft', 3),
									angle=player_data.get('angle', 0),
									score=player_data.get('score', 0)
								)
							except Exception as e:
								logger.error(f"Could not create PlayerState: {e}")
			except Exception as e:
				logger.error(f"Error updating player from json: {e}")
		else:
			logger.warning(f"Unknown msgtype: {data.get('msgtype')} data: {data}")

	def update_remote_players(self, delta_time):
		"""Update remote player interpolation"""
		for client_id, player in self.playerlist.items():
			if client_id != self.client_id:  # Only update remote players
				try:
					# Check if player is dictionary or PlayerState object
					if isinstance(player, dict):
						# Dictionary players (server-originated)
						if 'position' not in player:
							continue

						# Initialize interpolation properties if needed
						if 'prev_position' not in player:
							player['prev_position'] = player['position']
							player['target_position'] = player['position']
							player['interp_time'] = 0
							player['position_updated'] = False

						# Handle interpolation
						if player.get('position_updated', False):
							if isinstance(player['position'], list):
								player['prev_position'] = player['position'].copy()
							else:
								player['prev_position'] = player['position']
							player['interp_time'] = 0
							player['position_updated'] = False

					else:
						# PlayerState objects (client-originated)
						if not hasattr(player, 'position'):
							continue

						# Initialize interpolation attributes if needed
						if not hasattr(player, 'prev_position') or player.prev_position is None:
							player.prev_position = player.position
							player.target_position = player.position
							player.interp_time = 0
							player.position_updated = False

						# Update interpolation
						if getattr(player, 'position_updated', False):
							player.prev_position = player.position
							player.interp_time = 0
							player.position_updated = False
				except Exception as e:
					logger.warning(f"Error in update_remote_players for {client_id}: {e}")
