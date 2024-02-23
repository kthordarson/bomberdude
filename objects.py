from pyvex.utils import stable_hash
import copy
import arcade
from arcade.tilemap import TileMap
from arcade.gui import UIManager, UIBoxLayout, UITextArea, UIFlatButton, UIGridLayout
from arcade.gui import UILabel
from arcade.math import (get_angle_radians, rotate_point, get_angle_degrees,)
import random
import math
from loguru import logger
from constants import *
import time
import hashlib
from queue import Queue, Empty
from typing import List, Dict
import json
from dataclasses import dataclass, asdict, field
import zlib
import pickle
from arcade.types import Point
def gen_randid() -> str:
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


MOVE_MAP = {
	arcade.key.UP: (0, PLAYER_MOVEMENT_SPEED),
	arcade.key.W: (0, PLAYER_MOVEMENT_SPEED),
	119: (0, PLAYER_MOVEMENT_SPEED),

	arcade.key.DOWN: (0, -PLAYER_MOVEMENT_SPEED),
	arcade.key.S: (0, -PLAYER_MOVEMENT_SPEED),
	115: (0, -PLAYER_MOVEMENT_SPEED),

	arcade.key.LEFT: (-PLAYER_MOVEMENT_SPEED, 0),
	arcade.key.A: (-PLAYER_MOVEMENT_SPEED, 0),
	97: (-PLAYER_MOVEMENT_SPEED, 0),

	arcade.key.RIGHT: (PLAYER_MOVEMENT_SPEED, 0),
	arcade.key.D: (PLAYER_MOVEMENT_SPEED, 0),
	100: (PLAYER_MOVEMENT_SPEED, 0),
}



class UIPlayerLabel(UILabel):
	_value: str = ''
	def __init__(self, client_id, value='', l_text='', text_color=arcade.color.HAN_BLUE, *args, **kwargs):
		super().__init__(width=120,text=client_id,text_color=text_color, multiline=False, name=client_id, *args, **kwargs)
		self.client_id = client_id
		self.name = client_id
		self.button = UIFlatButton(text=f'{self.client_id}', height=20, width=120,name=self.name)

	@property
	def value(self):
		return f'{self._value}'

	@value.setter
	def value(self, value):
		self._value = f'{value}'
		self.text = f'{self._value}' # self._value # f'{self.client_id}\\n{value}'
		self.fit_content()


class KeysPressed:
	def __init__(self, client_id):
		self.client_id = client_id
		self.keys = {k: False for k in MOVE_MAP}

	def __repr__(self):
		return f'KeyPressed ({self.client_id})'

@dataclass
class PlayerEvent:
	keys: Dict = field(default_factory=lambda: {k: False for k in MOVE_MAP})
	client_id: str = 'pemissing'
	ufcl_cnt: int = 0
	pe_counter: int = 0
	# game_events: None
	# events: None

	def __post_init__(self):
		self.keys = {int(k): v for k, v in self.keys.items()}

	def __repr__(self):
		return f'PlayerEvent ({self.client_id} )'

	def asdict(self):
		return asdict(self)

	def set_client_id(self,clid):
		self.client_id = clid


@dataclass
class PlayerState:
	updated: float = 0.0
	# x: float = 123.1
	# y: float = 123.1
	speed: float = 0.0
	health: float = 100.1
	ammo: float = 0.0
	# score: int = 0
	client_id: str = 'none'
	position  = [222,222]

	def __repr__(self):
		return f'Playerstate_repr ({self.client_id} pos={self.position} h={self.health} u={self.updated})'

	def __str__(self):
		return f'Playerstate_str ({self.client_id} pos={self.position} h={self.health} u={self.updated})'

	def __init__(self, client_id, *args, **kwars):
		self.client_id = client_id
		#self.position = [101,101]

	def asdict(self):
		ps_dict = asdict(self)
		ps_dict['client_id'] = self.client_id
		ps_dict['position'] = self.position
		ps_dict['health'] = self.health
		ps_dict['msgsource'] = 'asdict'
		return ps_dict

	def _asdict(self):
		return asdict(self)

	def set_client_id(self,clid):
		self.client_id = clid

	def set_pos(self, newpos):
		self.position = newpos

	def get_pos(self):
		return self.position


@dataclass
class GameState:
	# player_states: List[PlayerState]
	game_seconds: int = 0
	cjsonupdate: int = 0

	def __repr__(self):
		return f'Gamestate (gs:{self.game_seconds} events:{len(self.game_events)} counters = chkpc: {self.chkp_counter} ugsc: {self.ugs_counter} tojc: {self.toj_counter} fjc: {self.fj_counter} players:{len(self.players)})'

	def __init__(self,  game_seconds=0, debugmode=False):
		self.players = {}
		# self.player_states = player_states
		self.game_seconds = game_seconds
		self.debugmode = debugmode
		self.debugmode_trace = False
		self.game_events = []
		self.event_queue = Queue()
		self.raw_event_queue = Queue()
		# debugstuff
		self.chkp_counter = 0
		self.ugs_counter = 0
		self.toj_counter = 0
		self.fj_counter = 0
		self.tile_map:TileMap = arcade.load_tilemap('data/map3.json', layer_options={"Blocks": {"use_spatial_hash": True},}, scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)

	def load_tile_map(self, mapname):
		logger.debug(f'loading {mapname}')
		self.tile_map = arcade.load_tilemap(mapname, layer_options={"Blocks": {"use_spatial_hash": True},}, scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)


	def check_players(self):
		self.chkp_counter += 1
		dt = time.time()
		playerscopy = copy.copy(self.players)
		old_len = len(self.players)
		pops = []
		for p in playerscopy:
			dt_diff = dt - self.players[p].get('msg_dt')
			playerhealth = self.players[p].get('health')
			if dt_diff > 10: # player timeout
				self.players[p]['timeout'] = True
				if not self.players[p]['timeout']:
					logger.info(f'player timeout {p} dt_diff={dt_diff} selfplayers={self.players}')

	def update_game_state(self, clid, msg):
		self.ugs_counter += 1
		self.game_seconds += 1
		if self.debugmode_trace:
			logger.debug(f'gsge={len(self.game_events)}  from: {clid} msg={msg}')
		msghealth = msg.get('health')
		msgtimeout = msg.get('timeout')
		msgkilled = msg.get('killed')
		playerdict = {
			'client_id':clid,
			'position': msg.get('position'),
			'score': msg.get('score'),
			'health': msghealth,
			'msg_dt': msg.get('msg_dt'),
			'timeout': msgtimeout,
			'killed': msgkilled,
			'msgsource': 'update_game_state',
			'bombsleft': msg.get('bombsleft'),

		}
		self.players[clid] = playerdict
		# game_events = msg.get('game_events', None)
		# if game_events:
		# self.game_events = []
	def update_game_events(self, msg):
		for game_event in msg.get('game_events'):
			if game_event == []:
				break
			if self.debugmode:
				logger.info(f'{game_event=}')
			game_event['event_time'] += 1
			event_type = game_event.get('event_type')
			eventid = game_event.get('eventid')
			evntchk =  [k for k in self.game_events if k.get('eventid') == eventid]
			if len(evntchk) > 0:
				continue # logger.warning(f'dupeevntchk {len(evntchk)} eventid {eventid} {game_event} already in game_events')# :  msg={msg} selfgameevents:{self.game_events}')
				# r = [self.game_events.remove(k) for k in evntchk]
			else:
				match event_type:
					# logger.debug(f'self.game_events={self.game_events}')
					case 'newconn':
						game_event['handled'] = True
						game_event['handledby'] = f'ugsnc'
						game_event['event_type'] = 'acknewconn'
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.info(f'{event_type} ')
					case 'blkxplode': # todo make upgradeblock here....
						# game_event['handled'] = True
						uptype = random.choice([1,2,3])
						newevent = {'event_time':0, 'event_type': 'upgradeblock', 'client_id': game_event.get("client_id"), 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
						self.event_queue.put_nowait(newevent)
						if self.debugmode:
							logger.info(f'gsge={len(self.game_events)} {event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
					case 'bombdrop': # decide on somethingsomething..
						game_event['handledby'] = f'ugsbomb'
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'gsge={len(self.game_events)} {event_type} from {game_event.get("bomber")} pos:{game_event.get("pos")}')
					case 'upgradeblock': # decide on somethingsomething..
						game_event['handled'] = True
						game_event['handledby'] = f'ugsupgr'
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'gsge={len(self.game_events)} {event_type} {game_event.get("upgradetype")} pos:{game_event.get("fpos")} from {game_event.get("client_id")}')
					case 'playerkilled': # increase score for killer
						killer = game_event.get("killer")
						killed = game_event.get("killed")
						self.players[killer]['score'] += 1
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {killer=} {killed=} {self.players[killer]}')
					case 'takedamage': # increase score for killer
						killer = game_event.get("killer")
						killed = game_event.get("killed")
						damage = game_event.get("damage")
						self.players[killed]['health'] -= damage
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
						if self.players[killed]['health'] > 0:
							game_event['event_type'] = 'acktakedamage'
						else:
							self.players[killer]['score'] += 1
							game_event['event_type'] = 'dmgkill'
							game_event['killtimer'] = 5
							game_event['killstart'] = game_event.get("msg_dt")
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {killer=} {killed=} {self.players[killer]}')
					case 'respawn': # increase score for killer
						clid = game_event.get("client_id")
						self.players[clid]['health'] = 100
						self.players[clid]['killed'] = False
						game_event['handled'] = True
						game_event['handledby'] = f'ugsrspwn'
						game_event['event_type'] = 'ackrespawn'
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {clid=} {self.players[clid]}')
					case 'getmap': # send map to client
						clid = game_event.get("client_id")
						payload = {'msgtype': 'scenedata', 'payload':self.scene}
						logger.info(f'{event_type} from {clid} {len(payload)} {game_event=}')
						#await sockpush.send(payload)
						# game_event['event_type'] = 'ackgetmap'
						# game_event['payload'] = pickle.dumps(self.scene)
						# self.raw_event_queue.put_nowait(pickle.dumps(self.tile_map))
					case _: #
						logger.warning(f'gsge={len(self.game_events)} unknown game_event:{event_type} from msg={msg}')
				#elif game_event.get('handled') == True:
				#	logger.warning(f'game_event already handled: {game_event} msg={msg}')


	def to_json(self):
		self.toj_counter += 1
		dout = {'players':{}, 'game_events': []}
		try:
			pending_event = self.event_queue.get_nowait()
			self.event_queue.task_done()
			dout['game_events'].append(pending_event)
		except Empty:
			pending_events = []
		for player in self.players:
			playerdict = {
			'client_id':player,
			'position': self.players[player].get('position'),
			'health': self.players[player].get('health'),
			'msg_dt': self.players[player].get('msg_dt'),
			'timeout': self.players[player].get('timeout'),
			'killed': self.players[player].get('killed'),
			'score': self.players[player].get('score'),
			'bombsleft': self.players[player].get('bombsleft'),
			'msgsource': 'to_json',
			}
			dout['players'][player] = playerdict #Q = playerdict
		return dout

	def from_json(self, dgamest):
		self.fj_counter += 1
		for ge in dgamest.get('game_events', []):
			if ge == []:
				break
			if self.debugmode:
				logger.info(f'ge={ge.get("event_type")} dgamest={dgamest=}')
			self.event_queue.put_nowait(ge)
		plist = dgamest.get('players',[])
		for player in plist:
			if plist.get(player).get('timeout'):
				pass # logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			elif plist.get(player).get('killed'):
				pass # logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			else:
				self.players[plist.get(player).get('client_id')] = plist.get(player)
				# logger.info(f'player={player} dgamest={dgamest} selfplayers={self.players}')
		if self.debugmode:
			pass # logger.debug(f'dgamest={dgamest}')# gs={self.game_seconds} selfplayers={self.players}')

@dataclass
class Networkthing(arcade.Sprite):
	client_id: str = 'none'
	def __init__(self, client_id, position, *args, **kwars):
		self.client_id = client_id
		super().__init__(*args, **kwars)

@dataclass
class Bomberplayer(arcade.Sprite):
	def __init__(self, image=None, scale=1.0, client_id=None, position=[123.3,123.5]):
		super().__init__(image,scale)
		self.client_id = client_id
		# self.ps = PlayerState(self.client_id, position)
		# self.ps.set_pos(position)
		self.position = position
		self.bombsleft = 3
		self.health = 100
		self.killed = False
		self.timeout = False
		self.score = 0
		# self.text = arcade.Text(f'{self.client_id} h:{self.health} pos:{self.position}', 10,10)

	def __repr__(self):
		return f'Bomberplayer ({self.client_id} s:{self.score} h:{self.health} pos:{self.position} )'

	def __eq__(self, other):
		if not isinstance(other, type(self)):
			return False
		# compare values in slots
		for slot in self.__slots__:
			if getattr(self, slot) != getattr(other, slot):
				return False
		return True

	def __hash__(self):
		values = [getattr(self, slot) for slot in self.__slots__]
		for i in range(len(values)):
			if isinstance(values[i], list):
				values[i] = tuple(values[i])
		return stable_hash(tuple([type(self)] + values))

	def rotate_around_point(self, point: Point, degrees: float):
		"""
		Rotate the sprite around a point by the set amount of degrees

		:param point: The point that the sprite will rotate about
		:param degrees: How many degrees to rotate the sprite
		"""

		# Make the sprite turn as its position is moved
		self.angle += degrees

		# Move the sprite along a circle centered around the passed point
		self.position = rotate_point( self.center_x, self.center_y, point[0], point[1], degrees)



	def respawn(self):
		self.killed = False
		self.health = 100
		self.position = [123.3,123.5]
		self.bombsleft = 3
		self.score = 0
		self.timeout = False
		self.set_texture(arcade.load_texture('data/playerone.png'))
		logger.info(f'{self} respawned')

	def set_texture(self, texture):
		self.texture = texture

	def addscore(self, score):
		self.score += score
		logger.info(f'{self} score:{self.score}')

	def get_playerstate(self):
		playerstate = {
			'client_id': self.client_id,
			'position': self.position,
			'health': self.health,
			'msgsource': 'get_playerstate',
			'msg_dt': time.time(),
			'timeout': self.timeout,
			'killed': self.killed,
			'score': self.score,
			'bombsleft': self.bombsleft,
		}
		return json.dumps({self.client_id: playerstate})

	def take_damage(self, damage, killer):
		self.health -= damage
		# logger.info(f'{self} health:{self.health} {damage=} {killer=}')
		if self.health <= 0:
			self.killed = True
			self.kill(killer)
			return 1
		return 0

	def kill(self, killer):
		logger.info(f'{self} killed by {killer}')
		self.killed = True
		self.texture = arcade.load_texture('data/netplayerdead.png')
		return 1

class Bomb(arcade.Sprite):
	def __init__(self, image=None, scale=1, bomber=None, timer=1000):
		super().__init__(image,scale)
		self.bomber = bomber
		self.timer = timer

	def __repr__(self):
		return f'Bomb(pos={self.center_x},{self.center_y} bomber={self.bomber} t:{self.timer})'

	def update(self):
		if self.timer <= 0:
			# logger.debug(f'{self} timeout ')
			self.remove_from_sprite_lists()
			plist = []
			flames = []
			for k in range(PARTICLE_COUNT):
				p = Particle()
				p.center_x = self.center_x
				p.center_y = self.center_y
				plist.append(p)
			for k in ['left','right','up','down']:
				f = Flame(flamespeed=FLAME_SPEED, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.center_x = self.center_x
				f.center_y = self.center_y
				flames.append(f)
			return {'bomb': self, 'plist':plist, 'flames':flames}
		else:
			# Update
			self.timer -= BOMBTICKER
			return []

class Bullet(arcade.Sprite):
	def __init__(self, image=None, scale=1, shooter=None, timer=1000, cx=1,cy=1):
		super().__init__(image,scale)
		self.shooter = shooter
		self.timer = timer
		self.cx = cx
		self.cy = cy

	def __repr__(self):
		return f'Bullet(pos={self.center_x},{self.center_y} shooter={self.shooter} t:{self.timer})'

	def update(self):
		self.center_x += self.change_x
		self.center_y += self.change_y
		if self.timer <= 0:
			# logger.debug(f'{self} timeout ')
			self.remove_from_sprite_lists()
		else:
			self.timer -= BULLET_TIMER

class Particle(arcade.SpriteCircle):
	def __init__(self, my_list=None):
		color = random.choice(PARTICLE_COLORS)
		super().__init__(PARTICLE_RADIUS, color)
		self.normal_texture = self.texture
		speed = random.random() * PARTICLE_SPEED_RANGE + PARTICLE_MIN_SPEED
		direction = random.randrange(360)
		self.change_x = math.sin(math.radians(direction)) * speed
		self.change_y = math.cos(math.radians(direction)) * speed
		self.my_alpha = 255
		self.my_list = my_list

	def __repr__(self) -> str:
		return f'Particle({self.my_alpha} pos={self.center_x},{self.center_y})'

	def update(self):
		if self.my_alpha <= 0:
			self.remove_from_sprite_lists()
			# logger.debug(f'{self} timeout')
		else:
			# Update
			self.my_alpha -= PARTICLE_FADE_RATE
			self.alpha = self.my_alpha
			self.center_x += self.change_x
			self.center_y += self.change_y
			self.change_y -= PARTICLE_GRAVITY

class Flame(arcade.SpriteSolidColor):
	def __init__(self, flamespeed=10, timer=3000, direction='', bomber=None):
		color = arcade.color.ORANGE
		super().__init__(FLAMEX,FLAMEY, color=color)
		self.normal_texture = self.texture
		self.bomber = bomber
		self.speed = flamespeed
		self.timer = timer
		self.direction = direction
		if self.direction == 'left':
			self.change_y = 0
			self.change_x = -self.speed
		if self.direction == 'right':
			self.change_y = 0
			self.change_x = self.speed
		if self.direction == 'up':
			self.change_y = -self.speed
			self.change_x = 0
		if self.direction == 'down':
			self.change_y = self.speed
			self.change_x = 0

	def __repr__(self) -> str:
		return f'Flame(bomber={self.bomber} pos={self.center_x},{self.center_y})'

	def update(self):
		if self.timer <= 0:
			self.remove_from_sprite_lists()
			# logger.debug(f'{self} timeout')
		else:
			# Update
			self.timer -= FLAME_RATE
			self.center_x += self.change_x
			self.center_y += self.change_y


def pack(data):
	dtypes, shapes, buffers = [], [], []
	items = sorted(data.items(), key=lambda x: x[0])
	keys, vals = zip(*items)
	dtypes = [v.dtype.name for v in vals]
	shapes = [v.shape for v in vals]
	buffers = [v.tobytes() for v in vals]
	meta = (keys, dtypes, shapes)
	parts = [pickle.dumps(meta), *buffers]
	return parts


def unpack(parts):
	meta, *buffers = parts
	keys, dtypes, shapes = pickle.loads(meta)
	vals = [
		np.frombuffer(b, d).reshape(s)
		for i, (d, s, b) in enumerate(zip(dtypes, shapes, buffers))]
	data = dict(zip(keys, vals))
	return data


async def send_zipped_pickle(socket, obj, flags=0, protocol=-1):
	"""pickle an object, and zip the pickle before sending it"""
	p = pickle.dumps(obj, protocol)
	z = zlib.compress(p)
	return await socket.send(z, flags=flags)

async def recv_zipped_pickle(socket, flags=0, protocol=-1):
	"""inverse of send_zipped_pickle"""
	z = await socket.recv(flags)
	# print(f'{z=}')
	p = zlib.decompress(z)
	return pickle.loads(p)

