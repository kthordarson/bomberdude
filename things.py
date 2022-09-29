import math
import random
from threading import Thread, Event, Event
import multiprocessing
import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import MAXPARTICLES,BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, GRIDSIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID
from globals import ResourceHandler, random_velocity
# from queue import Queue as OldQueue

class BasicThing(Sprite):
	def __init__(self, pos, image):
		Sprite.__init__(self)
		# self.thingq = OldQueue() # multiprocessing.Manager().Queue()
		self.pos = Vector2(pos)
		self.vel = Vector2()
		self.start_time = pygame.time.get_ticks()
		self.image = image

class Block(BasicThing):
	def __init__(self, pos, gridpos, block_type):
		
		self.block_type = block_type
		self.solid = BLOCKTYPES.get(self.block_type)["solid"]
		self.permanent = BLOCKTYPES.get(self.block_type)["permanent"]
		self.size = BLOCKTYPES.get(self.block_type)["size"]
		self.bitmap = BLOCKTYPES.get(self.block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(self.block_type)["powerup"]
		self.rm = ResourceHandler()
		self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)
		BasicThing.__init__(self, pos, self.image)
		self.explode = False
		self.poweruptime = 10
		self.gridpos = gridpos  # Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.image.set_alpha(255)
		self.image.set_colorkey((0, 0, 0))

class Powerup(BasicThing):
	pass

class Bomb(BasicThing):
	pass