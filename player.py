import pygame
from pygame.sprite import Sprite

from pygame.math import Vector2
from globals import BasicThing, Block, gen_randid, Bomb
from loguru import logger
from signal import SIGPIPE, SIG_DFL 
from queue import Empty
from netutils import data_identifiers
from globals import ResourceHandler
from threading import Thread
from constants import *

class Player(BasicThing, Thread):
	def __init__(self, pos, image):
		Thread.__init__(self, name='player')
		self.name = 'player'
		BasicThing.__init__(self, pos, image)
		# Sprite.__init__(self)
		self.client_id = gen_randid()
		self.rm = ResourceHandler()
		image, rect = self.rm.get_image(filename=image, force=False)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 15
		self.speed = 5
		self.health = 100
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.send_pos_count = 0
		self.kill = False
		self.dead = False
		self.gotmap = False
		self.connected = False
		self.net_players = {}
		self.cnt_sq_request = 0
		self.cnt_sq_sendyourpos = 0
		logger.debug(f'[p] init pos:{pos} i:{image} client_id:{self.client_id}')

	def __str__(self):
		return f'[player] {self.client_id}' #self.client_id

	def __repr__(self):
		return f'[player] id:{self.client_id} pos:{self.pos}' #str(self.client_id)

	def run(self):
		self.kill = False
		logger.debug(f'[p]{self.client_id} start ')
		while True:
			if self.kill:
				logger.debug(f'[pk] self.kill:{self.kill}')
				break

	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.rect.centerx, self.rect.centery))
			bomb = Bomb(pos=bombpos, bomber_id=self, bomb_power=self.bomb_power, reshandler=self.rm)
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
