from pyvex.utils import stable_hash
from pymunk import Vec2d
import copy
import arcade
from arcade.gui.style import UIStyleBase, UIStyledWidget
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
from arcade.types import Point

def gen_randid() -> int:
	return int(''.join([str(random.randint(0,9)) for k in range(10)]))
	#hashid = hashlib.sha1()
	#hashid.update(str(time.time()).encode("utf-8"))
	#return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


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
		super().__init__(width=120,text=client_id,text_color=text_color, multiline=False,  *args, **kwargs)
		self.client_id = client_id
		self.name = str(client_id)
		self.button = UIFlatButton(text=f'{self.client_id}', height=20, width=120)
		self.textlabel = UIFlatButton(text=f' ', height=20, width=400)
		self.textlabel.text_color=arcade.color.GREEN
		# self.textlabel._apply_style(NP_LABEL_STYLE)

	@property
	def value(self):
		return f'{self._value}'

	@value.setter
	def value(self, value):
		self._value = f'{value}'
		self.text = f'{self._value}' # self._value # f'{self.client_id}\\n{value}'
		self.textlabel.text = self._value
		#self.textlabel._apply_style(NP_LABEL_STYLE)
		self.fit_content()

	def set_value(self, value):
		# logger.debug(f'old={self._value} new={value}')
		self._value = f'{value}'
		self.text = f'{self._value}' # self._value # f'{self.client_id}\\n{value}'
		self.textlabel.text = self._value
		#self.textlabel._apply_style(NP_LABEL_STYLE)
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
class Networkthing(arcade.Sprite):
	client_id: str = 'none'
	def __init__(self, client_id, position, *args, **kwars):
		self.client_id = client_id
		super().__init__(*args, **kwars)

@dataclass
class Bomberplayer(arcade.Sprite):
	def __init__(self, image=None, scale=1.0, client_id=None, position=Vec2d(x=99,y=99)):
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

	def x__eq__(self, other):
		if not isinstance(other, type(self)):
			return False
		# compare values in slots
		for slot in self.__slots__:
			if getattr(self, slot) != getattr(other, slot):
				return False
		return True

	def __hash__(self):
		return self.client_id

	def x__hash__(self):
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
		self.position = Vec2d(x=101,y=101)
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

	def set_pos(self, newpos):
		# logger.debug(f'setpos {newpos=} oldc={self.center_x},{self.center_y} selfposition={self.position}')
		self.center_x = newpos.x
		self.center_y = newpos.y
		self.update()

class Bomb(arcade.Sprite):
	def __init__(self, image=None, scale=1, bomber=None, timer=1000):
		super().__init__(image,scale)
		self.bomber = bomber
		self.timer = timer

	def __repr__(self):
		return f'Bomb(pos={self.center_x},{self.center_y} bomber={self.bomber} t:{self.timer})'

	def update(self, scene, eventq):
		if self.timer <= 0:
			for k in range(PARTICLE_COUNT):
				p = Particle()
				p.center_x = self.center_x
				p.center_y = self.center_y
				scene.add_sprite('Particles', p)
			for k in ['left','right','up','down']:
				f = Flame(flamespeed=FLAME_SPEED, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.center_x = self.center_x
				f.center_y = self.center_y
				scene.add_sprite('Flames', f)
			event = {'event_time':0, 'event_type':'bombxplode', 'bomber':self.bomber, 'eventid': gen_randid()}
			eventq.put(event)
			self.remove_from_sprite_lists()
		else:
			self.timer -= BOMBTICKER

class BiggerBomb(arcade.Sprite):
	def __init__(self, image=None, scale=1, bomber=None, timer=1000):
		super().__init__(image,scale)
		self.bomber = bomber
		self.timer = timer

	def __repr__(self):
		return f'BiggerBomb(pos={self.center_x},{self.center_y} bomber={self.bomber} t:{self.timer})'

	def update(self, scene, eventq):
		if self.timer <= 0:
			for k in range(PARTICLE_COUNT*2):
				p = Particle(xtra=3)
				p.center_x = self.center_x
				p.center_y = self.center_y
				scene.add_sprite('Particles', p)
			for k in ['left','right','up','down']:
				f = Flame(flamespeed=FLAME_SPEED*2, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.center_x = self.center_x
				f.center_y = self.center_y
				scene.add_sprite('Flames', f)
			event = {'event_time':0, 'event_type':'bombxplode', 'bomber':self.bomber, 'eventid': gen_randid()}
			eventq.put(event)
			self.remove_from_sprite_lists()
		else:
			self.timer -= BOMBTICKER

class Bullet(arcade.Sprite):
	def __init__(self, image=None, scale=1, shooter=None, timer=1000, cx=1,cy=1):
		super().__init__(image,scale)
		self.shooter = shooter
		self.timer = timer
		self.cx = cx
		self.cy = cy

	def __repr__(self):
		return f'Bullet(pos={self.center_x:.2f},{self.center_y:.2f} shooter={self.shooter} t:{self.timer})'

	def rotate_around_point(self, point: Point, degrees: float):
		self.angle += degrees
		self.position = rotate_point( self.center_x, self.center_y, point[0], point[1], degrees)

	def update(self):
		self.center_x += self.change_x
		self.center_y += self.change_y
		if self.timer <= 0:
			# logger.debug(f'{self} timeout ')
			self.remove_from_sprite_lists()
		else:
			self.timer -= BULLET_TIMER

class Particle(arcade.SpriteCircle):
	def __init__(self, my_list=None, xtra=0):
		color = random.choice(PARTICLE_COLORS)
		super().__init__(PARTICLE_RADIUS, color)
		self.normal_texture = self.texture
		speed = random.random() * PARTICLE_SPEED_RANGE + PARTICLE_MIN_SPEED
		direction = random.randrange(360)
		self.change_x = math.sin(math.radians(direction)) * speed+xtra
		self.change_y = math.cos(math.radians(direction)) * speed+xtra
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


