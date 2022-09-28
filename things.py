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
from globals import random_velocity
# from queue import Queue as OldQueue

class BasicThing(Sprite):
	def __init__(self, pos):
		Sprite.__init__(self)
		# self.thingq = OldQueue() # multiprocessing.Manager().Queue()
		self.pos = Vector2(pos)
		self.vel = Vector2()
		self.start_time = pygame.time.get_ticks()

class Block(BasicThing):
	pass

class Powerup(BasicThing):
	pass

class Bomb(BasicThing):
	pass