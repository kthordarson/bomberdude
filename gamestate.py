import asyncio
import copy
import pygame
from pygame.sprite import Group
import random
from loguru import logger
from constants import EXTRA_HEALTH, TILE_SCALING
import time
from queue import Empty  # Queue,
from dataclasses import dataclass
from utils import gen_randid
from objects.player import Bomberplayer, KeysPressed
from objects.blocks import Upgrade
import pytmx
from pytmx import load_pygame
import json

@dataclass
class GameState:

	def __init__(self, args, mapname=None, name='undefined'):
		self.args = args
		self.name = name
		self.players = Group()
		self.bullets = Group()
		self.bombs = Group()
		self.flames = Group()
		self.particles = Group()
		self.event_queue = []
		self.mapname = mapname
		self.game_events = []
		self.event_queue = asyncio.Queue()
		self.raw_event_queue = asyncio.Queue()
		self.keys_pressed = KeysPressed('gamestate')
		# self.tile_map = load_pygame('data/map3.tmx')
		self.tile_map = pytmx.TiledMap('data/map3.tmx')
		self.collidable_tiles = []
		self.connections = set()
		self.client_queue = asyncio.Queue()

	def __repr__(self):
		return f'Gamestate ( events:{len(self.game_events)} players:{len(self.players)} )'

	async def debug_dump(self):
		"""Debug dump of game state"""
		try:
			state = self.to_json()
			await self.broadcast_state({
				'msgtype': 'debugdump',
				'payload': state
			})
			return (f'{self.name} players: {len(self.players)} '
					f'events: {len(self.game_events)} '
					f'conns: {len(self.connections)}')
		except Exception as e:
			logger.error(f"Error in debug_dump: {e}")
			return f"Error: {e}"

	async def old_debug_dump(self):
		await self.broadcast_state({'msgtype': 'debugdump', 'payload': self.players})
		return f'{self.name} {self} players: {self.players} events: {self.game_events} conns: {len(self.connections)}'

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
			logger.warning(f'{self} got no connections....')
			return
		try:
			data = json.dumps(game_state).encode('utf-8')
			loop = asyncio.get_event_loop()

			logger.debug(f'broadcast_state to {len(self.connections)} clients')
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

	def get_playerone(self):
		for player in self.players:
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
		for p in self.players:
			if p == skip:
				pass
			else:
				playerdata = self.players[p]
				yield {'client_id': p, 'playerdata': playerdata}

	def check_players(self):
		dt = time.time()
		playerscopy = copy.copy(self.players)
		for p in playerscopy:
			dt_diff = dt - self.players[p]['msg_dt']
			if dt_diff > 10:  # player timeout
				self.players[p]['timeout'] = True
				self.event_queue.put_nowait({'event_time': 0, 'event_type': 'playerquit', 'client_id': p, 'reason': 'timeout', 'eventid': gen_randid()})
				if not self.players[p]['timeout']:
					logger.info(f'player timeout {p} dt_diff={dt_diff} selfplayers={self.players}')

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

	def debug_keypress_status(self, keypress_status):
		pass

	def update_game_state(self, clid, msg):
		msghealth = msg.get('health')
		msgtimeout = msg.get('timeout')
		msgkilled = msg.get('killed')

		keypress_status = msg.get('keyspressed')
		if self.args.debug:
			self.debug_keypress_status(keypress_status)

		playerdict = {
			'client_id': clid,
			'name': msg.get('name', 'ugsmissing'),
			'position': msg.get('position'),
			'angle': msg.get('angle'),
			'score': msg.get('score'),
			'health': msghealth,
			'msg_dt': msg.get('msg_dt'),
			'timeout': msgtimeout,
			'killed': msgkilled,
			'msgsource': 'update_game_state',
			'bombsleft': msg.get('bombsleft'),
		}
		self.players[clid] = playerdict

	def update_game_events(self, msg):
		game_event = msg.get('game_events')
		event_type = game_event.get('event_type')
		game_event['event_time'] += 1
		eventid = game_event.get('eventid')
		evntchk = [k for k in self.game_events if k.get('eventid') == eventid]
		msg_client_id = str(game_event.get("client_id"))
		if len(evntchk) > 0:
			logger.warning(f'dupeevntchk {len(evntchk)} eventid {eventid} {game_event} already in game_events')
		match event_type:
			case 'playerquit':
				self.players[msg_client_id]['playerquit'] = True
				self.event_queue.put_nowait(game_event)
			case 'newconnection':
				name = game_event['name']
				if self.args.debug:
					logger.info(f'{event_type} from {msg_client_id} {name}')
				if msg.get('connection'):
					self.add_connection(msg.get('connection'))
				else:
					logger.warning(f'newconnection missing conn {msg=}')
				game_event['handled'] = True
				game_event['handledby'] = 'ugsnc'
				game_event['event_type'] = 'acknewconn'
				self.players[msg_client_id] = {'client_id': msg_client_id, 'name': name, 'timeout': False, 'msg_dt': time.time()}
				self.event_queue.put_nowait(game_event)
			case 'blkxplode':
				uptype = random.choice([1, 2, 3])
				newevent = {'event_time': 0, 'event_type': 'upgradeblock', 'client_id': msg_client_id, 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
				self.event_queue.put_nowait(newevent)
				if self.args.debug:
					logger.info(f'{event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
			case 'takeupgrade':
				game_event['handledby'] = 'ugstakeupgrade'
				upgradetype = game_event.get("upgradetype")
				msg_client_id = game_event['client_id']
				match upgradetype:
					case 1:
						self.players[msg_client_id]['health'] += EXTRA_HEALTH
						logger.debug(f'{msg_client_id} got extrahealth -> {self.players[msg_client_id].get("health")}')
						event = {'event_time': 0, 'event_type': 'extrahealth', 'amount': EXTRA_HEALTH, 'client_id': msg_client_id, 'eventid': gen_randid()}
						self.event_queue.put_nowait(event)
					case 2:
						self.players[msg_client_id]['bombsleft'] += 1
						logger.debug(f'{msg_client_id} got extrabomb -> {self.players[msg_client_id].get("bombsleft")}')
						event = {'event_time': 0, 'event_type': 'extrabomb', 'client_id': msg_client_id, 'eventid': gen_randid()}
						self.event_queue.put_nowait(event)
					case 3:
						pass
					case _:
						logger.warning(f'unknown upgradetype {upgradetype=} {msg=}')
			case 'bombdrop':
				game_event['handledby'] = 'ugsbomb'
				bomber = game_event.get("bomber")
				eventid = game_event.get('eventid')
				name = self.players[bomber]['name']
				if self.players[bomber].get("bombsleft") > 0:
					game_event['event_type'] = 'ackbombdrop'
					self.players[bomber]['bombsleft'] -= 1
					self.event_queue.put_nowait(game_event)
					if self.args.debug:
						logger.debug(f'{event_type} from {name=} {bomber} {eventid=} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')
				else:
					if self.args.debug:
						logger.debug(f'nobombsleft ! {event_type} {name=}  from {bomber} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')
			case 'bulletfired':
				game_event['handledby'] = 'ugsbomb'
				game_event['event_type'] = 'ackbullet'
				self.event_queue.put_nowait(game_event)
				if self.args.debug:
					pass
			case 'bombxplode':
				game_event['handledby'] = 'ugsbomb'
				game_event['event_type'] = 'ackbombxplode'
				eventid = game_event.get('eventid')
				bomber = game_event.get("bomber")
				self.players[bomber]['bombsleft'] += 1
				self.event_queue.put_nowait(game_event)
				if self.args.debug:
					logger.debug(f'{event_type} from {bomber}  bl={self.players[bomber].get("bombsleft")} {eventid=}')
			case 'playerkilled':
				dmgfrom = game_event.get("dmgfrom")
				dmgto = game_event.get("dmgto")
				self.players[dmgfrom]['score'] += 1
				game_event['handled'] = True
				game_event['handledby'] = 'ugskill'
				self.event_queue.put_nowait(game_event)
				if self.args.debug:
					logger.debug(f'{event_type} {dmgfrom=} {dmgto=} {self.players[dmgfrom]}')
			case 'takedamage':
				dmgfrom = game_event.get("dmgfrom")
				dmgto = game_event.get("dmgto")
				damage = game_event.get("damage")
				self.players[dmgto]['health'] -= damage
				game_event['handled'] = True
				game_event['handledby'] = 'ugskill'
				self.players[dmgfrom]['score'] += 1
				if self.players[dmgto]['health'] > 0:
					game_event['event_type'] = 'acktakedamage'
					self.players[dmgfrom]['score'] += 1
					logger.info(f'{event_type} {dmgfrom=} {dmgto=} killerscore={self.players[dmgfrom]["score"]}')
				else:
					self.players[dmgfrom]['score'] += 10
					game_event['event_type'] = 'dmgkill'
					game_event['killtimer'] = 5
					game_event['killstart'] = game_event.get("msg_dt")
					logger.debug(f'{event_type} {dmgfrom=} {dmgto=} ')
				self.event_queue.put_nowait(game_event)
			case 'respawn':
				self.players[msg_client_id]['health'] = 100
				self.players[msg_client_id]['killed'] = False
				game_event['handled'] = True
				game_event['handledby'] = 'ugsrspwn'
				game_event['event_type'] = 'ackrespawn'
				self.event_queue.put_nowait(game_event)
				logger.debug(f'{event_type} {msg_client_id=} {self.players[msg_client_id]}')
			case 'getmap':
				payload = {'msgtype': 'scenedata', 'payload': self.scene}
				logger.info(f'{event_type} from {msg_client_id} {len(payload)} {game_event=}')
			case _:
				logger.warning(f'unknown game_event:{event_type} from msg={msg}')

	def to_json(self):
		"""Convert game state to JSON-serializable format"""
		return {
			'players': [p.to_dict() for p in self.players],
			'events': len(self.game_events),
			'connections': len(self.connections),
			'name': self.name
		}

	async def old_to_json(self):
		dout = {'players': {}, 'game_events': []}
		dout['keys_pressed'] = self.keys_pressed.to_json()
		if self.args.debug and self.name != 'server':
			pass
		try:
			pending_event = await self.event_queue.get()
			self.event_queue.task_done()
			dout['game_events'].append(pending_event)
		except Empty:
			pass
		for player in self.players:
			playerdict = {
				'client_id': player,
				'name': self.players[player].get('name', 'fjmissing'),
				'position': self.players[player].get('position', (123, 123)),
				'angle': self.players[player].get('angle', 0),
				'health': self.players[player].get('health', 1110),
				'msg_dt': self.players[player].get('msg_dt', time.time()),
				'timeout': self.players[player].get('timeout', False),
				'killed': self.players[player].get('killed', False),
				'score': self.players[player].get('score', 0),
				'bombsleft': self.players[player].get('bombsleft', 110),
				'msgsource': 'to_json',
			}
			dout['players'][player] = playerdict
		return dout

	def from_json(self, dgamest):
		for ge in dgamest.get('game_events', []):
			if ge == []:
				break
			if self.args.debug and self.name != 'b':
				logger.info(f'ge={ge.get("event_type")} dgamest={dgamest=}')
			self.event_queue.put_nowait(ge)
		plist = dgamest.get('players', [])
		for player in plist:
			if plist.get(player).get('timeout'):
				logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			elif plist.get(player).get('killed'):
				logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			else:
				logger.debug(f'player={player} dgamest={dgamest} selfplayers={self.players}')
				localid = plist.get(player).get('client_id')
				self.players[localid] = plist.get(player)
		if self.args.debug:
			pass
