from pyvex.utils import stable_hash
import arcade
from arcade.gui import UILabel
import random
import math
from loguru import logger
from constants import *
import time
import hashlib

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

#	def __init__(self, client_id='missing', *args, **kwars):
#		self.client_id = client_id
		#self.keys: Dict = field(default_factory=lambda: {k: False for k in MOVE_MAP})

	def __post_init__(self):
		self.keys = {int(k): v for k, v in self.keys.items()}

	def __repr__(self):
		return f'PlayerEvent ({self.client_id})'

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
	health: float = 0.0
	ammo: float = 0.0
	score: int = 0
	client_id: str = 'none'
	position  = [101,101]

	def __repr__(self):
		return f'Playerstate ({self.client_id} pos={self.position} u={self.updated})'

	def __str__(self):
		return f'Playerstate ({self.client_id} pos={self.position} u={self.updated})'

	def __init__(self, client_id, *args, **kwars):
		self.client_id = client_id
		#self.position = [101,101]

	def asdict(self):
		ps_dict = asdict(self)
		ps_dict['position'] = self.position
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
	player_states: List[PlayerState]
	game_seconds: int = 0
	cjsonupdate: int = 0


	def __repr__(self):
		return f'Gamestate (gs:{self.game_seconds} cj:{self.cjsonupdate} ps:{len(self.player_states)})'

	def __init__(self, player_states=None, game_seconds=None):
		self.players = {}
		self.player_states = player_states
		self.game_seconds = game_seconds

	def to_json(self, players):
		for p in players:
			self.players[p] = {'position': players[p]["position"]}
		d = dict(player_states=[asdict(p) for p in self.player_states], game_seconds=self.game_seconds)
		d['players'] = self.players
		d['gsplayers'] = players
		logger.info(f'd={d}')
		# logger.debug(f'players={self.players}')
		# logger.info(f'tojsonplayers={players}')
		return json.dumps(d)

	def from_json(self, dgamest, players):
		# d = json.loads(data)
		for p in players:
			self.players[p] = {'position': players[p]["position"]}
		self.game_seconds += dgamest['game_seconds']
		plist = dgamest.get('players', [])
		for p in plist:
			pos = plist.get(p).get('position')
			self.players[p] = {'position': pos}
		# for i, p in enumerate(dgamest['player_states']):
		# 	ps =  PlayerState(**p)
		# 	ps.position = player.position
		# 	self.players[ps.client_id] = ps
		# 	self.players[player.client_id] = player
		# 	# self.players[ps.client_id] = {'position': ps.position}
		# 	if len(self.players) >= 2:
		# 		# logger.info(f'{i} p={p} ps={ps} updatefrom {player} self.game_seconds={self.game_seconds} d={d}')
		# 		logger.debug(f'players: {len(self.players)} {self.players}')

@dataclass
class Networkthing(arcade.Sprite):
	client_id: str = 'none'
	def __init__(self, client_id, position, *args, **kwars):
		self.client_id = client_id
		super().__init__(*args, **kwars)

@dataclass
class Bomberplayer(arcade.Sprite):
	def __init__(self, image=None, scale=1, client_id=None,position=[123.3,123.5]):
		super().__init__(image,scale)
		self.client_id = client_id
		self.ps = PlayerState(self.client_id, position)
		self.position = self.ps.position
		self.bombsleft = 3
		self.text = arcade.Text(f'{self.client_id} {self.position}', 10,10)

	def __repr__(self):
		return f'Bomberplayer ({self.client_id} pos:{self.position} pspos={self.ps.position})'

	def get_ps(self):
		return PlayerState(self.client_id, self.position)

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

	def setpos(self, newpos):
		self.ps.position = newpos
		self.position = self.ps.position
		self.ps = PlayerState(self.client_id, newpos)
		return self.ps
		# self.center_x = newpos[0]
		# self.center_x = newpos[1]

	def moveup(self):
		pass
	def movedown(self):
		pass
	def moveleft(self):
		pass
	def moveright(self):
		pass

class Bomb(arcade.Sprite):
	def __init__(self, image=None, scale=1, bomber=None, timer=1000):
		super().__init__(image,scale)
		self.bomber = bomber
		self.timer = timer

	def __repr__(self):
		return f'Bomb(pos={self.center_x},{self.center_y} bomber={self.bomber} t:{self.timer})'

	def update(self):
		if self.timer <= 0:
			logger.debug(f'{self} timeout ')
			self.remove_from_sprite_lists()
			plist = []
			flames = []
			for k in range(PARTICLE_COUNT):
				p = Particle()
				p.center_x = self.center_x
				p.center_y = self.center_y
				plist.append(p)
			for k in ['left','right','up','down']:
				f = Flame(flamespeed=FLAME_SPEED, timer=FLAME_TIME, direction=k)
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
	def __init__(self, flamespeed=10, timer=3000, direction=''):
		color = arcade.color.ORANGE
		super().__init__(FLAMEX,FLAMEY, color)
		self.normal_texture = self.texture
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
		return f'Flame(pos={self.center_x},{self.center_y})'

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
	def __init__(self):
		color = arcade.color.BLACK
		width = 12
		height = 12
		super().__init__(width,height, color)
		self.center_x = 111
		self.center_y = 111
		self.normal_texture = self.texture
		# super().__init__(image,scale)
		# Size and rotation
