import pygame
from globals import BasicThing, Block, Bomb
from loguru import logger
from globals import gen_randid
from threading import Thread
from constants import *
from network import dataid
from bclient import BombClient

class Player(BasicThing, Thread):
	def __init__(self, pos=None, visible=False, mainqueue=None):
		Thread.__init__(self, daemon=True)
		super().__init__(pos, None)
		self.image = pygame.image.load('data/playerone.png')
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		# BasicThing.__init__(self, pos, self.image)
		self.mainqueue = mainqueue
		self.visible = visible
		self.client_id = gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.pos = pos
		self.rect = self.image.get_rect(center=self.pos)
		self.speed = 3
		self.client = BombClient(client_id=self.client_id, serveraddress='127.0.0.1', serverport=9696, mainqueue=self.mainqueue)
		self.gotmap = False

	def start_client(self):
		self.client.start()

	def bombdrop(self):
		pass

	def update(self, blocks):
		oldy = self.rect.y
		oldx = self.rect.x
		self.pos += self.vel
		#self.pos.x += self.vel.x
		#self.pos.y += self.vel.y
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

		# self.client.pos = (self.pos[0], self.pos[1])
		#self.pos += self.vel
		#self.rect.center = self.pos
		if self.connected:
			self.client.send_pos((self.pos[0], self.pos[1]))
			if not self.gotmap:
				if self.client.gotmap:
					#self.mainqueue.put_nowait({'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':self.client.gamemapgrid})
					self.gotmap = True
					logger.debug(f'[{self}] gotmap:{self.gotmap} grid:{len(self.client.gamemapgrid)}')


	def take_powerup(self, powerup=None):
		pass

	def add_score(self):
		self.score += 1
