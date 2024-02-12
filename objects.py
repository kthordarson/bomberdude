from pyvex.utils import stable_hash
import copy
import arcade
from arcade.gui import UILabel

import random
import math
from loguru import logger
from constants import *
import time
import hashlib
from queue import Queue
from typing import List, Dict
import json
from dataclasses import dataclass, asdict, field


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

#class Rectangle:
#	def __init__(self, x, y, width, height, angle, color):



class UINumberLabel(UILabel):
	_value: float = 0
	def __init__(self, value=0, format="Timer: {value:.0f}", text_color=arcade.color.BLACK, *args, **kwargs):
		super().__init__(text_color=text_color, *args, **kwargs)
		self.format = format
		self.value = value
		self.text_color = text_color

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, value):
		self._value = value
		self.text = self.format.format(value=value)
		self.fit_content()

class UITextLabel(UILabel):
	_value: str = ''
	def __init__(self, value='', l_text='', text_color=arcade.color.BLACK, *args, **kwargs):
		super().__init__(text_color=text_color, *args, **kwargs)
		self.value = value
		self.l_text = l_text
		self.text_color = text_color
		# self.align = 'right'

	@property
	def value(self):
		return f'{self.l_text} {self._value}'

	@value.setter
	def value(self, value):
		self._value = value
		self.text = value
		self.fit_content()

class UIPlayerLabel(UILabel):
	_value: str = ''
	def __init__(self, client_id, value='', l_text='', text_color=arcade.color.HAN_BLUE, *args, **kwargs):
		super().__init__(text_color=text_color, *args, **kwargs)
		self.client_id = client_id
		self.value = f'{self.client_id} '
		self.l_text = l_text
		# self.align = 'right'

	@property
	def value(self):
		return f'{self.client_id} {self._value}'

	@value.setter
	def value(self, value):
		self._value = f'{self.client_id} {value}'
		self.text = f'{self.client_id} {value}'
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

	def __init__(self,  game_seconds=None, debugmode=False):
		self.players = {}
		# self.player_states = player_states
		self.game_seconds = game_seconds
		self.debugmode = debugmode
		self.game_events = []
		# self.event_queue = Queue()
		# debugstuff
		self.chkp_counter = 0
		self.ugs_counter = 0
		self.toj_counter = 0
		self.fj_counter = 0

	def check_events(self):
		#eventcopy = copy.copy(self.game_events)
		for event in self.game_events:
			event['event_time'] += 1
			if event.get('handled') == True:
				logger.info(f'removing event {event} {self} sge={self.game_events}')
				self.game_events.remove(event)
			elif event.get('event_time') > 10:
				logger.warning(f'eventtimeout={event} {self} sge={self.game_events}')
				self.game_events.remove(event)
		if len(self.game_events) > 2:
			logger.warning(f'unhandledevents {self} sge={self.game_events}' )

	def check_players(self):
		self.chkp_counter += 1
		dt = time.time()
		playerscopy = copy.copy(self.players)
		old_len = len(self.players)
		pops = []
		for p in playerscopy:
			try:
				dt_diff = dt - self.players[p].get('msg_dt')
				playerhealth = self.players[p].get('health')
				if dt_diff > 10: # player timeout
					self.players[p]['timeout'] = True
			except Exception as e:
				logger.error(f'{self} {type(e)} {e} {p} selfplayers={self.players}')

	def update_game_state(self, clid, msg):
		self.ugs_counter += 1
		self.game_seconds += 1
		if self.debugmode:
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

		}
		self.players[clid] = playerdict
		# game_events = msg.get('game_events', None)
		# if game_events:
		# self.game_events = []
	def update_game_events(self, msg):
		for game_event in msg.get('game_events'):
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
					case 'blkxplode': # todo make upgradeblock here....
						# game_event['handled'] = True
						uptype = random.choice([1,2,3])
						newevent = {'event_time':0, 'event_type': 'upgradeblock', 'client_id': game_event.get("client_id"), 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
						self.game_events.append(newevent)
						if self.debugmode:
							logger.info(f'gsge={len(self.game_events)} {event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
					case 'bombdrop': # decide on somethingsomething..
						game_event['handledby'] = f'ugsbomb'
						self.game_events.append(game_event)
						if self.debugmode:
							logger.debug(f'gsge={len(self.game_events)} {event_type} from {game_event.get("bomber")} pos:{game_event.get("pos")}')
					case 'upgradeblock': # decide on somethingsomething..
						game_event['handled'] = True
						game_event['handledby'] = f'ugsupgr'
						self.game_events.append(game_event)
						if self.debugmode:
							logger.debug(f'gsge={len(self.game_events)} {event_type} {game_event.get("upgradetype")} pos:{game_event.get("fpos")} from {game_event.get("client_id")}')
					case 'playerkilled': # increase score for killer
						self.players[game_event.get("killer")]['score'] += 1
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
						self.game_events.append(game_event)
						if self.debugmode:
							logger.debug(f'gsge={len(self.game_events)} {event_type}  killer:{game_event.get("killer")} gamevent={game_event}')
					case _: #
						logger.warning(f'gsge={len(self.game_events)} unknown game_event:{event_type} from msg={msg}')
				#elif game_event.get('handled') == True:
				#	logger.warning(f'game_event already handled: {game_event} msg={msg}')


	def to_json(self):
		self.toj_counter += 1
		dout = {'players':{}, 'game_events': []}
		for ge in self.game_events:
			ge['event_time'] += 1
			if ge['handled'] == False:
				dout['game_events'].append(ge)
			else:
				logger.warning(f'unhandled {ge} sge={self.game_events}')

		for player in self.players:
			playerdict = {
			'client_id':player,
			'position': self.players[player].get('position'),
			'health': self.players[player].get('health'),
			'msg_dt': self.players[player].get('msg_dt'),
			'timeout': self.players[player].get('timeout'),
			'killed': self.players[player].get('killed'),
			'score': self.players[player].get('score'),
			'msgsource': 'to_json',
			}
			dout['players'][player] = playerdict #Q = playerdict
		if self.debugmode:
			logger.info(f'gsge={len(self.game_events)} tojson dout={dout}')
		# self.game_events = [] # clear events
		return dout

	def from_json(self, dgamest):
		self.fj_counter += 1
		for ge in dgamest.get('game_events', []):
			# logger.info(f'dgamest={dgamest}')
			# self.game_events = []
			#for ge in game_events:
			if len(self.game_events) > 1:
				logger.warning(f'self.game_events: {len(self.game_events)} dgamest={dgamest}  game_events={self.game_events}')
			if ge.get('handled') == False:
				self.game_events.append(ge)
			else:
				logger.warning(f'game_event already handled: {ge}')
			if self.debugmode:
				logger.info(f"ge={ge} sge:{len(self.game_events)} game_events={dgamest.get('game_events')}")
			ge['handledby'] = 'fromjson'
			ge['event_time'] += 1

				##self.game_events = game_events
				# self.event_queue.put_nowait(game_events)

		plist = dgamest.get('players',[])
		for player in plist:
			if plist.get(player).get('timeout'):
				logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
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
	def __init__(self, image=None, scale=1, client_id=None, position=[123.3,123.5]):
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
		}
		return json.dumps({self.client_id: playerstate})

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

	def kill(self, killer):
		logger.info(f'{self} killed by {killer}')
		self.killed = True

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
		super().__init__(FLAMEX,FLAMEY, color)
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

class Rectangle(arcade.SpriteSolidColor):
	def __init__(self, client_id, color,center_x, center_y, width=12, height=12):
		#color = arcade.color.BLACK
		super().__init__(width,height, color)
		# width = 12
		# height = 12
		self.center_x = center_x
		self.center_y = center_y
		self.normal_texture = self.texture
		self.client_id = client_id
		self.angle = 0
		self.color = color
		# super().__init__(image,scale)
		# Size and rotation,
	def __repr__(self):
		return f'GhostRect({self.client_id})'
	def draw(self):
		if self.filled:
			arcade.draw_rectangle_filled( self.position.x, self.position.y, self.width, self.height, self.color, self.angle )
		else:
			arcade.draw_rectangle_outline( self.position.x, self.position.y, self.width, self.height, self.color, border_width=4, tilt_angle=self.angle )
