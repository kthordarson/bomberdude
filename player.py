import pygame, time
from pygame.sprite import Group, Sprite

from pygame.math import Vector2
from globals import BasicThing, load_image, Block, gen_randid, Bomb, Gamemap
from loguru import logger
import socket
from signal import signal, SIGPIPE, SIG_DFL 
from queue import Queue
from netutils import DataReceiver, DataSender, data_identifiers
from globals import StoppableThread
from globals import ResourceHandler
from threading import Thread
from constants import *
class Player(BasicThing, Thread):
	def __init__(self, pos=None, dt=None, image=None):
		Thread.__init__(self, name='player')
		self.name = 'player'
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.client_id = None
		self.dt = dt
		self.rm = ResourceHandler()
		self.image, self.rect = self.rm.get_image(filename=image, force=False) #  load_image(image, -1)
		self.pos = Vector2(pos)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 15
		self.speed = 5
		self.accel = Vector2(0, 0)
		self.health = 100
		self.dead = False
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.kill = False
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')

	def __str__(self):
		return self.client_id

	def __repr__(self):
		return str(self.client_id)

	def run(self):
		self.kill = False
		while True:
			if self.kill:
				logger.debug(f'player kill')
				break

	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.rect.centerx, self.rect.centery))
			bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=self, bomb_power=self.bomb_power)
			# self.bombs.add(bomb)
			self.bombs_left -= 1
			return bomb
		else:
			return 0

	def update(self, blocks):
		# self.vel += self.accel
		oldy = self.rect.y
		oldx = self.rect.x
		self.pos.x += self.vel.x
		self.pos.y += self.vel.y
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			if isinstance(block, Block):
				if self.vel.x != 0 and self.vel.y != 0 and block.solid:
					self.vel.x = 0
					self.vel.y = 0
					self.rect.x = oldx
					self.rect.y = oldy
					break
				if self.vel.x > 0 and block.solid:
					self.rect.right = block.rect.left
					self.vel.x = 0
				if self.vel.x < 0 and block.solid:
					self.rect.left = block.rect.right
					self.vel.x = 0
				if self.vel.y > 0 and block.solid:
					self.rect.bottom = block.rect.top
					self.vel.y = 0
				if self.vel.y < 0 and block.solid:
					self.rect.top = block.rect.bottom
					self.vel.y = 0
				#elif self.vel.x != 0 and self.vel.y != 0:
				#	self.vel.x = 0
				#	self.vel.y = 0
		self.pos.y = self.rect.y
		self.pos.x = self.rect.x

	def _update(self, blocks):
		# self.vel += self.accel
		self.pos.x += self.vel.x
		self.rect.x = int(self.pos.x)
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			if isinstance(block, Block):
				if self.vel.x > 0 and block.solid:
					self.rect.right = block.rect.left
				elif self.vel.x < 0 and block.solid:
					self.rect.left = block.rect.right
				self.pos.x = self.rect.x
		self.pos.y += self.vel.y
		self.rect.y = int(self.pos.y)
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			if self.vel.y > 0 and block.solid:
				self.rect.bottom = block.rect.top
			elif self.vel.y < 0 and block.solid:
				self.rect.top = block.rect.bottom
			self.pos.y = self.rect.y
	# logger.debug(f'[player] move sp:{self.speed} vel:{self.vel} p:{self.pos}')

	def take_powerup(self, powerup=None):
		# pick up powerups...
		if powerup == 1:
			if self.max_bombs < 10:
				self.max_bombs += 1
				self.bombs_left += 1
		if powerup == 2:
			pass
			#self.speed += 1
		if powerup == 3:
			self.bomb_power += 10

	def add_score(self):
		self.score += 1
