import hashlib
import math
import os
import random
import time
import copy
from threading import Thread, Timer
import pygame
from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group, Sprite, spritecollide
from pygame.event import Event
from constants import (BLOCK, BLOCKTYPES, BOMBSIZE, DEFAULTFONT, FLAMESIZE, MAXPARTICLES, POWERUPSIZE)
from constants import USEREVENT, USEREVENT

class RepeatedTimer():
	def __init__(self, interval, function, *args, **kwargs):
		self._timer     = None
		self.interval   = interval
		self.function   = function
		self.args       = args
		self.kwargs     = kwargs
		self.is_running = False
		self.start()

	def _run(self):
		self.is_running = False
		self.start()
		self.function(*self.args, **self.kwargs)

	def start(self):
		if not self.is_running:
			self._timer = Timer(self.interval, self._run)
			self._timer.start()
			self.is_running = True

	def stop(self):
		self._timer.cancel()
		self.is_running = False


class BlockNotFoundError(Exception):
	pass


def load_image(name, colorkey=None) -> tuple:
	fullname = os.path.join("data", name)
	image = pygame.image.load(fullname).convert()
	# image = image.convert()
	return image, image.get_rect()

def get_bomb_flames(bombpos, bomberid, image):
	flamegroup = Group()
	vel = (-1,0)
	flamegroup.add(NewFlame(vel=vel, bomberid=bomberid, bombpos=bombpos, image=image))
	vel = (1,0)
	flamegroup.add(NewFlame(vel=vel, bomberid=bomberid, bombpos=bombpos, image=image))
	vel = (0,1)
	flamegroup.add(NewFlame(vel=vel, bomberid=bomberid, bombpos=bombpos, image=image))
	vel = (0,-1)
	flamegroup.add(NewFlame(vel=vel, bomberid=bomberid, bombpos=bombpos, image=image))
	return flamegroup

class ResourceHandler:
	def __init__(self):
		self.name = 'ResourceHandler'
		self.__images = {}

	def get_image(self, filename:str, force=False) -> tuple:
		if force or filename not in list(self.__images.keys()):
			img = pygame.image.load(filename).convert()
			# img = pygame.transform.scale(img, (BLOCK, BLOCK))
			rect = img.get_rect()
			self.__images[filename] = (img, rect)
			# logger.info(f'Image {filename} loaded images={len(self.__images)}')
			return img
		else:
			# logger.info(f'Image {filename} already loaded images={len(self.__images)}')
			return self.__images[filename][0]

def gen_randid() -> str:
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


class NewBlock(Sprite):
	def __init__(self, gridpos, image, blocktype):
		super().__init__()
		self.blocktype = blocktype
		if self.blocktype == 40:
			self.blocktimer = 4000
		elif self.blocktype == 44:
			self.blocktimer = 4000
		else:
			self.blocktimer = 0
		self.gridpos = gridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		self.image = image
		self.rect = self.image.get_rect()
		self.vel = Vector2()
		self.start_time = pygame.time.get_ticks()
		self.clock = pygame.time.Clock()
		self.accel = Vector2(0, 0)
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]

	def __repr__(self):
		return f'NewBlock (t:{self.blocktype} pos={self.pos} {self.gridpos} bt:{self.blocktimer} {pygame.time.get_ticks() - self.start_time} )'

	def draw(self, screen):
		screen.blit(self.image, self.rect)

	def update(self):
		pass

class UpgradeBlock(Sprite):
	def __init__(self, gridpos, image, blocktype):
		super().__init__()
		self.blocktype = blocktype
		if self.blocktype == 40:
			self.blocktimer = 4000
		elif self.blocktype == 44:
			self.blocktimer = 4000
		else:
			self.blocktimer = 0
		self.gridpos = gridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		self.image = image
		self.rect = self.image.get_rect()
		self.vel = Vector2()
		self.start_time = pygame.time.get_ticks()
		self.clock = pygame.time.Clock()
		self.accel = Vector2(0, 0)
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]

	def __repr__(self):
		return f'Upgradeblock (t:{self.blocktype} pos={self.pos} {self.gridpos} bt:{self.blocktimer} {pygame.time.get_ticks() - self.start_time} )'

	def draw(self, screen):
		screen.blit(self.image, self.rect)

	def update(self):
		if pygame.time.get_ticks() - self.start_time >= self.blocktimer:
			# logger.debug(f'timeoutkill tchk:{pygame.time.get_ticks() - self.start_time >= self.blocktimer} start {self.start_time} {self.blocktimer} ticks: {pygame.time.get_ticks()}')
			self.kill()


class NewBomb(Sprite):
	def __init__(self, bombimg ,bomberid, gridpos, bombtimer=1000):
		super().__init__()
		self.start_time = pygame.time.get_ticks()
		self.image = bombimg
		self.gridpos = gridpos
		self.pos = (self.gridpos[0] * BLOCK+4, self.gridpos[1] * BLOCK+4)
		self.rect = self.image.get_rect(center=self.pos)
		self.bomberid = bomberid
		self.bombtimer = bombtimer
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]

	def __repr__(self):
		return f'NewBomb (pos={self.pos} {self.gridpos} bt:{self.bombtimer} {pygame.time.get_ticks() - self.start_time})'

	def update(self):
		# logger.info(f'{self}')
		if pygame.time.get_ticks() - self.start_time >= self.bombtimer:
			# logger.debug(f'{self} xplode')
			pygame.event.post(Event(USEREVENT, payload={'msgtype': 'bombxplode', 'gridpos': self.gridpos, 'bomberid': self.bomberid}))
			self.kill()

class NewFlame(Sprite):
	def __init__(self, bombpos=None, image=None, bomberid=None, flametimer=2000, vel=(1,1)):
		super().__init__()
		self.start_time = pygame.time.get_ticks()
		self.image = image
		self.gridpos = bombpos
		self.pos = [self.gridpos[0] * BLOCK+8, self.gridpos[1] * BLOCK+8]
		self.bomberid = bomberid
		self.flametimer = flametimer
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.vel = vel
		self.damage = 40

	def __repr__(self):
		return f'Newflame ( b:{self.bomberid} d:{self.damage} pos={self.pos} {self.gridpos} t:{self.flametimer} tt: {pygame.time.get_ticks() - self.start_time})'

	def update(self):
		# logger.info(f'{self}')
		self.pos[0] += self.vel[0]
		self.pos[1] += self.vel[1]
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		if pygame.time.get_ticks() - self.start_time >= self.flametimer:
			# logger.warning(f'{self}')
			self.kill()


class Particle(Sprite): # todo fix initial position
	def __init__(self, gridpos=None, ptimer=2000, vel=(1,1)):
		super().__init__()
		self.start_time = pygame.time.get_ticks()
		self.gridpos = gridpos
		self.pos = [self.gridpos[0] * BLOCK+8, self.gridpos[1] * BLOCK+8]
		self.ptimer = ptimer
		self.vel = vel # random.choice(([1+random.random(),1-random.random()], [1-random.random(),1+random.random()], [random.random(),1+random.random()], [random.random(),1-random.random()], [random.random()-1,random.random()-1], [1-random.random(),1-random.random()], [1+random.random(),1+random.random()], [1+random.random(),random.random()-1]))
		self.image = pygame.surface.Surface( random.choice([ (8,8), (6,6), (4,4), (2,2) ]))
		self.rect = self.image.get_rect()
		self.fill_col = [255,0,255]
		self.image.fill(self.fill_col)
		self.uc = 0

	def __repr__(self):
		return f'Particle ( uc:{self.uc} pos={self.pos} {self.gridpos} )'

	def bounce(self, block): # change velocity to bounce off block
		if block.blocktype == 2:
			return
		else:
			self.vel = [-1,-1]

	def update(self):
		# noise = 1 * random.random() - 4.5
		# self.pos[0] += math.cos(self.theta + noise)
		# self.pos[1] += math.sin(self.theta + noise)
		self.pos[0]  += self.vel[0]
		self.pos[1]  += self.vel[1]
		#self.vel[0]  -= random.random()
		self.vel[1]  += random.random() / 10
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.uc += 1
		self.fill_col[0] -= 1
		self.fill_col[2] -= 1
		self.image.fill(self.fill_col)
		if pygame.time.get_ticks() - self.start_time >= self.ptimer:
			# logger.info(f'{self} timeoutkill')
			self.kill()

