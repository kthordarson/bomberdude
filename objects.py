from typing import Dict
from pymunk import Vec2d
import arcade
from arcade.gui import UIFlatButton
from arcade.gui import UILabel
from arcade.math import (rotate_point,)
from arcade.sprite_list import SpatialHash
import random
import math
from loguru import logger
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_COLORS, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY
import time
import json
from dataclasses import dataclass, asdict, field
from arcade.types import Point

from utils import gen_randid

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
		super().__init__()  # width=120,text=client_id,text_color=text_color, multiline=False, *args, **kwargs)
		self.client_id = client_id
		self.name = str(client_id)
		self.button = UIFlatButton(text=f'{self.client_id}', height=20, width=120)
		self.textlabel = UIFlatButton(text=' ', height=20, width=400)

	@property
	def value(self):
		return f'{self._value}'

	@value.setter
	def value(self, value):
		self._value = f'{value}'
		self.text = f'{self._value}'  # self._value # f'{self.client_id}\\n{value}'
		self.textlabel.text = self._value
		self.fit_content()

	def set_value(self, value):
		# logger.debug(f'old={self._value} new={value}')
		self._value = f'{value}'
		self.text = f'{self._value}'  # self._value # f'{self.client_id}\\n{value}'
		self.textlabel.text = self._value
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
	position = [1,12]

	def __repr__(self):
		return f'Playerstate_repr ({self.client_id} pos={self.position} h={self.health} u={self.updated})'

	def __str__(self):
		return f'Playerstate_str ({self.client_id} pos={self.position} h={self.health} u={self.updated})'

	def __init__(self, client_id, *args, **kwars):
		self.client_id = client_id
		# self.position = [101,101]

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
	# def __init__(self, texture, scale=0.7, client_id=None, position=Vec2d(x=99,y=99)):
	def __init__(self, texture, scale=0.7, client_id=None, position=Vec2d(x=99,y=99), name='xnonex'):
		super().__init__(texture,scale)
		self.name = name
		self.client_id = client_id
		# self.ps = PlayerState(self.client_id, position)
		# self.ps.set_pos(position)
		self.position = position
		self.bombsleft = 3
		self.health = 100
		self.killed = False
		self.timeout = False
		self.score = 0
		self.angle = 0
		self.spatial_hash = SpatialHash(cell_size=32)
		self.candrop = True
		self.lastdrop = 0  # last bomb dropped
		self.all_bomb_drops = {}  # keep track of bombs
		# self.text = arcade.Text(f'{self.client_id} h:{self.health} pos:{self.position}', 10,10)

	def __repr__(self):
		return f'Bomberplayer ({self.client_id} s:{self.score} h:{self.health} pos:{self.position} )'

	def __hash__(self):
		return self.client_id

	def dropbomb(self, bombtype, eventq) -> None:
		if not self.candrop:  # dunno about this logic....
			logger.warning(f'{self} cannot drop bomb ! candrop: {self.candrop} last: {self.lastdrop} drops: {len(self.all_bomb_drops)}')
			return
		if self.bombsleft <= 0:
			logger.warning(f'p1: {self} has no bombs left {self.lastdrop}...')
			return
		if self.candrop:
			bombpos = Vec2d(x=self.center_x,y=self.center_y)
			bombevent = {'event_time':0, 'event_type':'bombdrop', 'bombtype':bombtype, 'bomber': self.client_id, 'pos': bombpos, 'timer': 1, 'handled': False, 'handledby': self.client_id, 'ld':self.lastdrop, 'eventid': gen_randid()}
			self.all_bomb_drops[bombevent['eventid']] = bombevent
			eventq.put(bombevent)
			self.candrop = False
			self.lastdrop = bombevent['eventid']
			logger.debug(f'{self} dropped bomb {bombevent["eventid"]}')
			return

	def update_netdata(self, playeronedata):
		self.score = playeronedata['score']
		self.health = playeronedata['health']
		self.bombsleft = playeronedata['bombsleft']
		# self.score = playeronedata['score']

	def rotate_around_point(self, point: Point, degrees: float):
		"""
		Rotate the sprite around a point by the set amount of degrees

		:param point: The point that the sprite will rotate about
		:param degrees: How many degrees to rotate the sprite
		"""

		# Make the sprite turn as its position is moved
		self.angle += degrees

		# Move the sprite along a circle centered around the passed point
		self.position = rotate_point(self.center_x, self.center_y, point[0], point[1], degrees)

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

	def take_damage(self, damage, dmgfrom):
		self.health -= damage
		logger.info(f'{self} health:{self.health} {damage=} {dmgfrom=}')
		if self.health <= 0:
			self.killed = True
			self.kill(dmgfrom)
			return 5
		return 1

	def kill(self, dmgfrom):
		logger.info(f'{self} killed by {dmgfrom}')
		self.killed = True
		self.texture = arcade.load_texture('data/netplayerdead.png')
		return 11

	def set_data(self, data):
		pass
		# self.client_id = data['client_id']
		# self.position = data['position']
		# self.angle = data['angle']
		# self.health = data['health']
		# self.timeout = data['timeout']
		# self.killed = data['killed']
		# self.score = data['score']
		# self.bombsleft = data['bombsleft']

	def set_pos(self, newpos):
		# logger.debug(f'setpos {newpos=} oldc={self.center_x},{self.center_y} selfposition={self.position}')
		self.center_x = newpos.x
		self.center_y = newpos.y
		self.update()

class Bomb(arcade.Sprite):
	def __init__(self, image=None, scale=1.0, bomber=None, timer=1000):
		super().__init__(image,scale)
		self.bomber = bomber
		self.timer = timer
		self.spatial_hash = SpatialHash(cell_size=32)

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
	def __init__(self, image=None, scale=1.0, bomber=None, timer=1000):
		super().__init__(image,scale)
		self.bomber = bomber
		self.timer = timer
		self.spatial_hash = SpatialHash(cell_size=32)

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
	def __init__(self, texture, scale=1, shooter=None, timer=1000):
		super().__init__(texture)
		self.shooter = shooter
		self.timer = timer
		self.angle = 90
		self.do_rotate = False
		self.do_shrink = False
		self.can_kill = True
		self.bullet_id = gen_randid()
		self.spatial_hash = SpatialHash(cell_size=32)
		self.hitcount = 0
		self.damage = 1
		# self.spatial_hash: self.bullet_id
		# self.velocity = Vec2d(x=0, y=0)

	def __hash__(self):
		return self.bullet_id

	def __repr__(self):
		return f'Bullet( id: {self.bullet_id} pos={self.center_x:.2f},{self.center_y:.2f} shooter={self.shooter} t:{self.timer} angle={self.angle:.2f} cx:{self.change_x:.2f} cy:{self.change_y:.2f} )'

	def rotate_around_point(self, point: Point, degrees: float):
		self.angle += degrees
		self.position = rotate_point(self.center_x, self.center_y, point[0], point[1], degrees)

	def hit(self, oldpos,other):
		if self.hitcount <= 1:
			if self.left <= other.left+self.change_x or self.right <= other.right+self.change_x:
				self.change_x *= -1
			if self.top <= other.top+self.change_y or self.bottom <= other.bottom+self.change_y:
				self.change_y *= -1
			if self.hitcount > 1:
				logger.warning(f'{self} hit {other} {self.hitcount=}')
			self.hitcount += 1
			self.can_kill = False
			self.do_shrink = True
		else:
			self.remove_from_sprite_lists()

	def update(self):
		# self.velocity = Vec2d(x=self.velocity[0], y=self.velocity[1])
		self.timer -= BULLET_TIMER
		if self.do_shrink:
			# self.draw_hit_box()
			# self.angle += 10
			# self.angle_change = 10
			self.scale -= 0.02
			if self.scale <= 0.1:
				# logger.debug(f'{self} scaleout ')
				self.remove_from_sprite_lists()
		self.center_x += self.change_x
		self.center_y += self.change_y
		if self.timer <= 0:
			# logger.debug(f'{self} timeout ')
			self.remove_from_sprite_lists()


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

class Upgrade(arcade.Sprite):
	def __init__(self, upgradetype, image, position, scale, timer=1000):
		super().__init__(scale=scale)
		self.image = image
		self.upgradetype = upgradetype
		self.position = position
		self.center_x = self.position.x
		self.center_y = self.position.y
		self.texture = arcade.load_texture(self.image)
		self.timer = timer
		self.spatial_hash = SpatialHash(cell_size=32)

	def __repr__(self):
		return f'upgrade( {self.upgradetype} pos={self.center_x},{self.center_y}  t:{self.timer})'

	def update(self):
		if self.timer <= 0:
			self.remove_from_sprite_lists()
		else:
			self.timer -= 1
