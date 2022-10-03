import pygame
from pygame.math import Vector2
from globals import BasicThing, Block, Bomb
from loguru import logger
from globals import gen_randid
from threading import Thread
from constants import *
from network import dataid
from bclient import BombClient

class Player(BasicThing, Thread):
	def __init__(self, pos=None, mainqueue=None):
		Thread.__init__(self, daemon=True)
		super().__init__(pos, None)
		self.image = pygame.image.load('data/playerone.png')
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		# BasicThing.__init__(self, pos, self.image)
		self.mainqueue = mainqueue
		self.ready = False
		self.client_id = gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		self.pos = (100,100)
		self.rect = self.image.get_rect(center=self.pos)
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.speed = 3
		self.client = BombClient(client_id=self.client_id, serveraddress='192.168.1.122', serverport=9696, mainqueue=self.mainqueue, pos=self.pos)
		self.gotmap = False
		self.gotpos = False

	def __str__(self):
		return f'{self.client_id} ready={self.ready} pos={self.pos} k={self.kill} ck={self.client.kill} conn:{self.connected}/{self.client.connected} gotmap:{self.gotmap} gotpos:{self.gotpos}'

	def start_client(self):
		self.client.start()
		self.ready = True

	def update(self, blocks=None, screen=None):
		if not self.ready and self.connected:
			logger.warning(f'{self} not ready but connected r:{self.ready} c:{self.connected} cc:{self.client.connected}')
			#return
		elif not self.connected and not self.ready:
			pass
			#logger.warning(f'{self} not connected not ready r:{self.ready} c:{self.connected} cc:{self.client.connected}')
			#return
		elif not self.client.connected and self.ready:
			logger.warning(f'{self} ready but client not connected r:{self.ready} c:{self.connected} cc:{self.client.connected}')
			#return

		#self.rect.center = self.pos
		#self.pos.x += self.vel.x
		#self.pos.y += self.vel.y
		oldrect = self.rect
		try:
			oldpos = (self.pos[0], self.pos[1])
		except TypeError as e:
			logger.error(f'{self} {e} pos {self.pos}')
			oldpos = (100,100)

		self.pos += self.vel
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		#self.pos.y = self.rect.y
		#self.pos.x = self.rect.x
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			if isinstance(block, Block):				
				if pygame.Rect.colliderect(block.rect, self.rect) and block.solid:
					self.vel = Vector2(0,0)
					self.rect = oldrect
					self.pos = oldpos
		if self.connected:
			try:
				# self.client.pos = (self.pos[0], self.pos[1])
				self.client.send_pos(pos=(self.pos[0], self.pos[1]), center=self.centerpos)
			except ConnectionResetError as e:
				logger.error(f'[ {self} ] {e}')
				self.connected = False
				self.client.kill = True
				self.client.socket.close()
				self.kill = True
				return

	def take_powerup(self, powerup=None):
		pass

	def add_score(self):
		self.score += 1
	
	def setpos(self, pos):
		if pos:
			logger.info(f'{self} setpos {self.pos} to {pos}')
			self.pos = pos
			self.client.pos = self.pos
		else:
			logger.warning(f'{self} ignoring setpos {self.pos} to {pos}')

