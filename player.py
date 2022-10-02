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
		self.pos = pos
		self.rect = self.image.get_rect(center=self.pos)
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.speed = 3
		self.client = BombClient(client_id=self.client_id, serveraddress='127.0.0.1', serverport=9696, mainqueue=self.mainqueue)
		self.gotmap = False
		self.gotpos = False

	def __str__(self):
		return f'player {self.client_id} pos={self.pos} k={self.kill} ck={self.client.kill}'

	def start_client(self):
		self.client.start()

	def update(self, blocks=None, screen=None):
		if not self.ready:
			return
		#self.rect.center = self.pos
		#self.pos.x += self.vel.x
		#self.pos.y += self.vel.y
		oldrect = self.rect
		oldpos = (self.pos[0], self.pos[1])

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
					#pygame.draw.rect(surface=screen, color=(255, 0, 0), rect=block.rect, border_radius=0 )
					#pygame.draw.circle(screen, center=(block.rect.x, block.rect.y), color=(0,255,0), radius=5)

		# self.client.pos = (self.pos[0], self.pos[1])
		#self.pos += self.vel
		if self.connected:
			try:
				if self.ready:
					self.client.send_pos(pos=(self.pos[0], self.pos[1]), center=self.centerpos)
			except ConnectionResetError as e:
				logger.error(f'[{self}] {e}')
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
		self.pos = pos

