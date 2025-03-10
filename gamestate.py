import asyncio
import copy
import pygame
from pygame.sprite import Group
import random
from loguru import logger
from constants import EXTRA_HEALTH, TILE_SCALING
import time
from queue import Empty  # Queue,
from dataclasses import dataclass, field
from utils import gen_randid
from objects.player import Bomberplayer, KeysPressed
from objects.blocks import Upgrade
from objects.bullets import Bullet
from objects.bombs import Bomb
from constants import UPDATE_TICK
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

	def __repr__(self):
		return f'Gamestate ( event_queue:{self.event_queue.qsize()} client_queue:{self.client_queue.qsize()}  players:{len(self.playerlist)} players_sprites:{len(self.players_sprites)})'

	async def debug_dump(self):
		"""Debug dump of game state"""
		try:
			state = self.to_json()
			await self.broadcast_state({'msgtype': 'debug_dump','payload': state})
		except Exception as e:
			logger.error(f"Error in debug_dump: {e}")

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
			if time.time() - self.last_pos_broadcast < 0.1:  # Only broadcast 10 times/sec
				return
			self.last_pos_broadcast = time.time()

		try:
			await self.broadcast_state({"msgtype": "game_event", "event": event})
		except Exception as e:
			logger.error(f"Error in broadcast_event: {e} {type(e)}")

	async def broadcast_state(self, game_state):
		"""Broadcast game state to all connected clients"""
		if not self.connections:
			pass  # logger.warning(f'{self} got no connections....')
			# return
		try:
			data = json.dumps(game_state).encode('utf-8') + b'\n'
			loop = asyncio.get_event_loop()
			# logger.debug(f'broadcast_state to {len(self.connections)} clients')
			dead_connections = set()
			for conn in self.connections:
				try:
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
		self.scene = pygame.sprite.Group()  # add_sprite_list
		for layer in self.tile_map.visible_layers:
			if isinstance(layer, pytmx.TiledTileLayer):
				for x, y, gid in layer:
					tile = self.tile_map.get_tile_image_by_gid(gid)
					if tile:
						sprite = pygame.sprite.Sprite()
						sprite.image = tile
						# sprite.rect = pygame.Rect(x * TILE_SCALING, y * TILE_SCALING, TILE_SCALING, TILE_SCALING)
						sprite.rect = pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)
						self.scene.add(sprite)
						if layer.properties.get('collidable'):
							self.collidable_tiles.append(sprite)
		logger.debug(f'loading {self.mapname} done. Sprites = {len(self.scene)} collidable_tiles: {len(self.collidable_tiles)}')

	def render_map(self, screen, camera):
		# self.scene.draw(screen)
		for layer in self.tile_map.visible_layers:
			if isinstance(layer, pytmx.TiledTileLayer):
				for x, y, gid in layer:
					tile = self.tile_map.get_tile_image_by_gid(gid)
					if tile:
						# screen.blit(tile, (x * self.tile_map.tilewidth, y * self.tile_map.tileheight))
						# screen.blit(tile, camera.apply(pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)))
						screen.blit(tile, camera.apply(pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)))

	def create_upgrade_block(self, upgradetype, blkpos):
		match upgradetype:
			case 1:
				upgrade = Upgrade(upgradetype, 'data/heart.png', blkpos, scale=0.8, timer=2000)
			case 2:
				upgrade = Upgrade(upgradetype, 'data/bombpwr.png', blkpos, scale=0.8, timer=1500)
			case 3:
				upgrade = Upgrade(upgradetype, 'data/bomb2.png', blkpos, scale=0.8, timer=3000)
			case _:
				upgrade = Upgrade(upgradetype, 'data/skull.png', blkpos, scale=0.8, timer=5000)
				logger.warning(f'unknown upgradetype {upgradetype=} {blkpos=}')
		return upgrade

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
						if hasattr(player, 'position'):
							# If PlayerState object
							if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
								player.position.x, player.position.y = position[0], position[1]
							else:
								player.position = position
						else:
							# If dictionary
							player['position'] = position

					if msg_client_id not in self.playerlist:
						# Initialize player state if it does not exist
						self.playerlist[msg_client_id] = PlayerState(
							client_id=msg_client_id,
							position=position,
							angle=game_event.get('angle', 0),
							health=game_event.get('health', 100),
							score=game_event.get('score', 0),
							bombsleft=game_event.get('bombsleft', 3)
						)

						logger.debug(f'new player_update {msg_client_id=} event_type: {game_event.get('event_type')}')
				await self.broadcast_event(game_event)

			case 'debug_dump':
				logger.debug(f'debug_dump game_event={game_event}')
			case 'playerquit':
				self.playerlist[msg_client_id]['playerquit'] = True
				await self.event_queue.put(game_event)
			case 'newconnection':
				if self.args.debug:
					logger.info(f'{event_type} from {msg_client_id} event_queue: {self.event_queue.qsize()}')
				game_event['handled'] = True
				game_event['handledby'] = 'ugsnc'
				game_event['event_type'] = 'acknewconn'

				# await self.event_queue.put(game_event)
			case 'drop_bomb':
				if self.args.debug:
					logger.debug(f'{event_type} from {msg_client_id} position: {game_event.get('position')}')
				game_event['handledby'] = 'ugsbomb'
				# if self.playerlist[bomber].get("bombsleft",0) > 0:
				# self.playerlist[bomber]['bombsleft'] -= 1
				# await self.event_queue.put(game_event)
				try:
					# player_one = self.get_playerone()
					if msg_client_id == self.client_id:
						bomb = Bomb(position=game_event.get('position'))
						logger.info(f'{event_type} from self {msg_client_id}')
					else:
						bomb = Bomb(position=game_event.get('position'), bomb_size=(5,5))
						logger.info(f'{event_type} from other {msg_client_id}')
					self.bombs.add(bomb)
				except AttributeError as e:
					logger.error(f'{e} unable to add bomb {game_event=} players_sprites: {self.players_sprites}')
				game_event['event_type'] = 'ackbombdrop'
				# await self.event_queue.put(game_event)
				# await self.client_queue.put(game_event)
				await self.broadcast_event(game_event)

			case 'ackbombdrop':
				if msg_client_id != self.client_id:
					bomb = Bomb(position=game_event.get('position'), bomb_size=(5,5))
					# logger.debug(f'{event_type} from other {msg_client_id}')
				elif msg_client_id == self.client_id:
					bomb = Bomb(position=game_event.get('position'), bomb_size=(10,10))
					# logger.debug(f'{event_type} from self {msg_client_id}')
				self.bombs.add(bomb)

			case 'bulletfired':
				game_event['handledby'] = 'update_game_event'
				game_event['event_type'] = 'ackbullet'
				game_event['handled'] = True
				if self.args.debug:
					logger.debug(f'type: {event_type} from {msg_client_id} event_queue: {self.event_queue.qsize()} ')
				# await self.client_queue.put(game_event)
				await self.broadcast_event(game_event)

			case 'ackbullet':
				# bullet = Bullet()
				if msg_client_id == self.get_playerone().client_id:
					bullet = Bullet(position=game_event.get('position'),direction=game_event.get('direction'), screen_rect=self.get_playerone().rect)
					# logger.info(f'{event_type} from self {msg_client_id}')
				else:
					bullet = Bullet(position=game_event.get('position'),direction=game_event.get('direction'), screen_rect=self.get_playerone().rect, bullet_size=(5,5))
					# logger.debug(f'{event_type} from other {msg_client_id}')
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
				playerlist.append(player)  # Assuming this is already a dict

		return {
			'event_type': 'playerlistupdate',
			'msgtype': 'playerlist',
			'playerlist': playerlist,
			'connections': len(self.connections),
		}

	def from_json(self, data):
		if data.get('msgtype') == 'pushermsgdict':
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
						else:
							# Create new player
							self.playerlist[client_id] = PlayerState(**player_data)
			except Exception as e:
				logger.error(f"Error updating player from json: {e}")
		else:
			logger.warning(f"Unknown msgtype: {data.get('msgtype')} data: {data}")
