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
import pytmx
from pytmx import load_pygame
import json

@dataclass
class PlayerState:
	client_id: str
	name: str
	position: tuple
	health: int
	bombsleft: int
	angle: float
	score: int
	msg_dt: float
	timeout: bool
	killed: bool
	msgtype: str

@dataclass
class GameState:

	def __init__(self, args, mapname=None, name='undefined'):
		self.args = args
		self.name = name
		self.players_sprites = Group()
		self.bullets = Group()
		self.bombs = Group()
		self.flames = Group()
		self.particles = Group()
		self.event_queue = []
		self.mapname = mapname
		self.game_events = []
		self.event_queue = asyncio.Queue()
		self.raw_event_queue = asyncio.Queue()
		self.keyspressed = KeysPressed('gamestate')
		# self.tile_map = load_pygame('data/map3.tmx')
		self.tile_map = pytmx.TiledMap('data/map3.tmx')
		self.collidable_tiles = []
		self.connections = set()
		self.client_queue = asyncio.Queue()
		self.playerlist = {}  # dict = field(default_factory=dict)

	def __repr__(self):
		return f'Gamestate ( events:{len(self.game_events)} players:{len(self.playerlist)} )'

	async def debug_dump(self):
		"""Debug dump of game state"""
		try:
			state = self.to_json()
			await self.broadcast_state({'msgtype': 'debug_dump','payload': state})
			return
		except Exception as e:
			logger.error(f"Error in debug_dump: {e}")
			return f"Error: {e}"

	def add_connection(self, connection):
		"""Add a new client connection"""
		self.connections.add(connection)
		logger.info(f"New connection added. Total connections: {len(self.connections)}")

	def remove_connection(self, connection):
		"""Remove a client connection"""
		if connection in self.connections:
			self.connections.remove(connection)
			logger.info(f"Connection removed. Total connections: {len(self.connections)}")

	async def broadcast_state(self, game_state):
		"""Broadcast game state to all connected clients"""
		if not self.connections:
			# logger.warning(f'{self} got no connections....')
			return
		try:
			data = json.dumps(game_state).encode('utf-8') + b'\n'
			loop = asyncio.get_event_loop()

			# logger.debug(f'broadcast_state to {len(self.connections)} clients')
			dead_connections = set()

			for conn in self.connections:
				try:
					# data = json.dumps(game_state)
					# Get the current event loop
					# loop = asyncio.get_event_loop()
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
		await asyncio.sleep(0.1)

	def get_playerone(self):
		for player in self.players_sprites:
			if isinstance(player, Bomberplayer):
				return player

	def load_tile_map(self, mapname):
		self.mapname = mapname
		# self.tile_map = pytmx.TiledMap('data/map3.tmx')
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

	def get_players(self, skip=None):
		for p in self.playerlist:
			if p == skip:
				pass
			else:
				playerdata = self.playerlist[p]
				yield {'client_id': p, 'playerdata': playerdata}

	def check_players(self):
		dt = time.time()
		playerscopy = copy.copy(self.playerlist)
		for p in playerscopy:
			dt_diff = dt - self.playerlist[p]['msg_dt']
			if dt_diff > 10:  # player timeout
				self.playerlist[p]['timeout'] = True
				self.event_queue.put_nowait({'event_time': 0, 'event_type': 'playerquit', 'client_id': p, 'reason': 'timeout', 'eventid': gen_randid()})
				if not self.playerlist[p]['timeout']:
					logger.info(f'player timeout {p} dt_diff={dt_diff} selfplayers={self.playerlist}')

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
		msghealth = msg.get('health')
		msgtimeout = msg.get('timeout')
		msgkilled = msg.get('killed')

		# if self.args.debug:
		# 	logger.debug(f'update_game_state {clid=} {msg=}')

		playerdict = {
			'client_id': clid,
			'name': msg.get('name', 'ugsmissing'),
			'position': msg.get('position'),
			# 'position': tuple(msg.get('position', (42, 42))),  # Ensure position is a tuple
			'angle': msg.get('angle'),
			'score': msg.get('score'),
			'health': msghealth,
			'msg_dt': msg.get('msg_dt'),
			'timeout': msgtimeout,
			'killed': msgkilled,
			'msgtype': 'update_game_state',
			'bombsleft': msg.get('bombsleft'),
		}
		self.playerlist[clid] = playerdict

	async def update_game_events(self, msg):
		# logger.info(f'update_game_events {msg=}')
		game_event = msg.get('game_events')
		event_type = game_event.get('event_type')
		eventid = game_event.get('eventid')
		msg_client_id = game_event.get("client_id", "8888888888")
		match event_type:
			case 'player_update':
				if msg_client_id not in self.playerlist:
					# Initialize player state if it does not exist
					self.playerlist[msg_client_id] = {
						'client_id': msg_client_id,
						'name': msg.get('name', 'ugsmissing'),
						'position': tuple(game_event.get('position', (0, 0))),
						'angle': game_event.get('angle'),
						'score': game_event.get('score'),
						'health': game_event.get('health'),
						'msg_dt': game_event.get('msg_dt'),
						'timeout': game_event.get('timeout'),
						'killed': game_event.get('killed'),
						'msgtype': 'update_game_events',
						'bombsleft': game_event.get('bombsleft'),
					}
				else:
					# Update existing player state
					self.playerlist[msg_client_id]['position'] = tuple(game_event.get('position', (0, 0)))
					self.playerlist[msg_client_id]['angle'] = game_event.get('angle')
					self.playerlist[msg_client_id]['score'] = game_event.get('score')
					self.playerlist[msg_client_id]['health'] = game_event.get('health')
					self.playerlist[msg_client_id]['msg_dt'] = game_event.get('msg_dt')
					self.playerlist[msg_client_id]['timeout'] = game_event.get('timeout')
					self.playerlist[msg_client_id]['killed'] = game_event.get('killed')
					self.playerlist[msg_client_id]['bombsleft'] = game_event.get('bombsleft')

			case 'debug_dump':
				logger.debug(f'{msg}')
				await asyncio.sleep(0.5)
			case 'playerquit':
				self.playerlist[msg_client_id]['playerquit'] = True
				await self.event_queue.put(game_event)
			case 'newconnection':
				name = game_event['name']
				if self.args.debug:
					logger.info(f'{event_type} from {msg_client_id} {name}')
				game_event['handled'] = True
				game_event['handledby'] = 'ugsnc'
				game_event['event_type'] = 'acknewconn'
				await self.event_queue.put(game_event)
			case 'blkxplode':
				uptype = random.choice([1, 2, 3])
				newevent = {'event_time': 0, 'event_type': 'upgradeblock', 'client_id': msg_client_id, 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
				await self.event_queue.put(newevent)
				if self.args.debug:
					logger.info(f'{event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
			case 'takeupgrade':
				game_event['handledby'] = 'ugstakeupgrade'
				upgradetype = game_event.get("upgradetype")
				msg_client_id = game_event['client_id']
				match upgradetype:
					case 1:
						self.playerlist[msg_client_id]['health'] += EXTRA_HEALTH
						logger.debug(f'{msg_client_id} got extrahealth -> {self.playerlist[msg_client_id].get("health")}')
						event = {'event_time': 0, 'event_type': 'extrahealth', 'amount': EXTRA_HEALTH, 'client_id': msg_client_id, 'eventid': gen_randid()}
						await self.event_queue.put(event)
					case 2:
						self.playerlist[msg_client_id]['bombsleft'] += 1
						logger.debug(f'{msg_client_id} got extrabomb -> {self.playerlist[msg_client_id].get("bombsleft")}')
						event = {'event_time': 0, 'event_type': 'extrabomb', 'client_id': msg_client_id, 'eventid': gen_randid()}
						await self.event_queue.put(event)
					case 3:
						pass
					case _:
						logger.warning(f'unknown upgradetype {upgradetype=} {msg=}')
			case 'bombdrop':
				game_event['handledby'] = 'ugsbomb'
				bomber = game_event.get("bomber")
				eventid = game_event.get('eventid')
				name = self.playerlist[bomber]['name']
				if self.playerlist[bomber].get("bombsleft") > 0:
					game_event['event_type'] = 'ackbombdrop'
					self.playerlist[bomber]['bombsleft'] -= 1
					await self.event_queue.put(game_event)
					if self.args.debug:
						logger.debug(f'{event_type} from {name=} {bomber} {eventid=} pos:{game_event.get("pos")} bl={self.playerlist[bomber].get("bombsleft")}')
				else:
					if self.args.debug:
						logger.debug(f'nobombsleft ! {event_type} {name=}  from {bomber} pos:{game_event.get("pos")} bl={self.playerlist[bomber].get("bombsleft")}')
			case 'bulletfired':
				game_event['handledby'] = 'ugsbomb'
				game_event['event_type'] = 'ackbullet'
				if self.args.debug:
					logger.debug(f'type: {event_type} msg: {msg}')
				await self.event_queue.put(game_event)
			case 'bombxplode':
				game_event['handledby'] = 'ugsbomb'
				game_event['event_type'] = 'ackbombxplode'
				eventid = game_event.get('eventid')
				bomber = game_event.get("bomber")
				self.playerlist[bomber]['bombsleft'] += 1
				await self.event_queue.put(game_event)
				if self.args.debug:
					logger.debug(f'{event_type} from {bomber}  bl={self.playerlist[bomber].get("bombsleft")} {eventid=}')
			case 'playerkilled':
				dmgfrom = game_event.get("dmgfrom")
				dmgto = game_event.get("dmgto")
				self.playerlist[dmgfrom]['score'] += 1
				game_event['handled'] = True
				game_event['handledby'] = 'ugskill'
				await self.event_queue.put(game_event)
				if self.args.debug:
					logger.debug(f'{event_type} {dmgfrom=} {dmgto=} {self.playerlist[dmgfrom]}')
			case 'takedamage':
				dmgfrom = game_event.get("dmgfrom")
				dmgto = game_event.get("dmgto")
				damage = game_event.get("damage")
				self.playerlist[dmgto]['health'] -= damage
				game_event['handled'] = True
				game_event['handledby'] = 'ugskill'
				self.playerlist[dmgfrom]['score'] += 1
				if self.playerlist[dmgto]['health'] > 0:
					game_event['event_type'] = 'acktakedamage'
					self.playerlist[dmgfrom]['score'] += 1
					logger.info(f'{event_type} {dmgfrom=} {dmgto=} killerscore={self.playerlist[dmgfrom]["score"]}')
				else:
					self.playerlist[dmgfrom]['score'] += 10
					game_event['event_type'] = 'dmgkill'
					game_event['killtimer'] = 5
					game_event['killstart'] = game_event.get("msg_dt")
					logger.debug(f'{event_type} {dmgfrom=} {dmgto=} ')
				await self.event_queue.put(game_event)
			case 'respawn':
				self.playerlist[msg_client_id]['health'] = 100
				self.playerlist[msg_client_id]['killed'] = False
				game_event['handled'] = True
				game_event['handledby'] = 'ugsrspwn'
				game_event['event_type'] = 'ackrespawn'
				await self.event_queue.put(game_event)
				logger.debug(f'{event_type} {msg_client_id=} {self.playerlist[msg_client_id]}')
			case 'getmap':
				payload = {'msgtype': 'scenedata', 'payload': self.scene}
				logger.info(f'{event_type} from {msg_client_id} {len(payload)} {game_event=}')
				await self.event_queue.put(payload)
			case _:
				payload = {'msgtype': 'error99', 'payload': ''}
				logger.warning(f'unknown game_event:{event_type} from msg={msg}')
				await self.event_queue.put(payload)

	def to_json(self):
		"""Convert game state to JSON-serializable format"""
		return {'msgtype': 'playerlist', 'playerlist': [player for player in self.playerlist.values()], 'events': len(self.game_events), 'connections': len(self.connections), 'name': self.name}

	def from_json(self, data):
		if data.get('msgtype') == 'debug_dump':
			logger.debug(f'fromjson: {data=}')
		else:
			try:
				playerlist = data.get('playerlist', [])
				self.playerlist = {player['client_id']: PlayerState(**player) for player in playerlist}
				# self.playerlist = {player['client_id']: PlayerState(**player) for player in data['players']}
			except KeyError as e:
				logger.warning(f'fromjson: {e} {data=}')
			for ge in data.get('game_events', []):
				if ge == []:
					break
				if self.args.debug and self.name != 'b':
					logger.info(f'ge={ge.get("event_type")} dgamest={data=}')
				self.event_queue.put_nowait(ge)
			if self.args.debug:
				pass
