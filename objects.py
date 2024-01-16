import arcade
from arcade.gui import UILabel
import random
import math
from loguru import logger
from constants import *
import time
import hashlib

def gen_randid() -> str:
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


class Bomberplayer(arcade.Sprite):
	def __init__(self, image=None, scale=1, client_id=None, visible=False):
		super().__init__(image,scale,visible=visible,center_x=0,center_y=0)
		self.bombsleft = 3
		self.client_id = client_id
		self.visible = visible
		self.center_x = 0
		self.center_y = 0
		self.position = (self.center_x, self.center_y)
		self.text = arcade.Text(f'{self.client_id} {self.position}', 10,10)

	def __repr__(self):
		return f'Bomberplayer(id: {self.client_id} pos={self.center_x},{self.center_y} b:{self.bombsleft})'

	def setpos(self, newpos):
		self.position = newpos
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
