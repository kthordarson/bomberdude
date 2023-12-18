import hashlib
import math
import os
import random
import time
from threading import Thread, Timer
import pygame
from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group, Sprite, spritecollide
from pygame.event import Event
from constants import (BLOCK, BLOCKTYPES, BOMBSIZE, DEFAULTFONT, FLAMESIZE, MAXPARTICLES, POWERUPSIZE)
from constants import BOMBXPLODE

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

def random_velocity(direction=None) -> Vector2:
	vel = Vector2((random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0)))
	if direction == "left":
		vel.x = random.uniform(-5.0, -2)
	if direction == "right":
		vel.x = random.uniform(2, 5.0)
	if direction == "down":
		vel.y = random.uniform(2, 5.0)
	if direction == "up":
		vel.y = random.uniform(-5.0, -2)
	return vel

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
		return f'(BB pos={self.pos} {self.gridpos})'

	def draw(self, screen):
		screen.blit(self.image, self.rect)

	def update(self):
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		# logger.debug(f'{self}')


class NewBomb(Sprite):
	def __init__(self, bombimg ,bomberid, gridpos, bombtimer=1000):
		super().__init__()
		self.start_time = pygame.time.get_ticks()
		self.image = bombimg
		self.gridpos = gridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		self.rect = self.image.get_rect(center=self.pos)
		self.bomberid = bomberid
		self.bombtimer = bombtimer
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]

	def __repr__(self):
		return f'(Nb pos={self.pos} {self.gridpos} bt:{self.bombtimer} {pygame.time.get_ticks() - self.start_time})'

	def update(self):
		# logger.info(f'{self}')
		if pygame.time.get_ticks() - self.start_time >= self.bombtimer:
			logger.warning(f'{self}')
			pygame.event.post(Event(BOMBXPLODE, payload={'msgtype': 'bombxplode', 'gridpos': self.gridpos, 'bomberid': self.bomberid}))
			self.kill()

class NewFlame(Sprite): # todo
	def __init__(self, bombpos=None, image=None, bomberid=None, flametimer=4000, vel=(1,1)):
		super().__init__()
		self.start_time = pygame.time.get_ticks()
		self.image = image
		self.gridpos = bombpos
		self.pos = [self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK]
		self.rect = self.image.get_rect(center=self.pos)
		self.bomberid = bomberid
		self.flametimer = flametimer
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.vel = vel

	def __repr__(self):
		return f'(newflame pos={self.pos} {self.gridpos} t:{self.flametimer} {pygame.time.get_ticks() - self.start_time})'

	def update(self):
		# logger.info(f'{self}')
		self.pos[0] += self.vel[0]
		self.pos[1] += self.vel[1]
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		if pygame.time.get_ticks() - self.start_time >= self.flametimer:
			logger.warning(f'{self}')
			self.kill()
