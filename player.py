import pygame
from pygame.math import Vector2
from pygame.sprite import Group, spritecollide, Sprite
from globals import BasicThing, Block, Bomb
from loguru import logger
from globals import gen_randid
from threading import Thread
from constants import *
from network import dataid
from bclient import BombClient

class Player(BasicThing, Thread):
	def __init__(self, mainqueue=None):
		Thread.__init__(self, daemon=True)
		super().__init__()
		self.vel = Vector2(0, 0)
		self.pos = (100,100)
		#self.image = pygame.image.load('data/playerone.png')
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(pygame.image.load('data/playerone.png'), self.size)
		self.rect = pygame.Surface.get_rect(self.image, center=self.pos)
		self.surface = pygame.display.get_surface() # pygame.Surface(PLAYERSIZE)
		#self.rect = self.surface.fill(color=(90,90,90))
		# BasicThing.__init__(self, pos, self.image)
		self.mainqueue = mainqueue
		self.ready = False
		self.client_id = gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		#self.rect = self.surface.get_rect() #pygame.Rect((self.pos[0], self.pos[1], PLAYERSIZE[0], PLAYERSIZE[1])) #self.image.get_rect()
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.speed = 3
		self.client = BombClient(client_id=self.client_id, serveraddress='192.168.1.168', serverport=9696, mainqueue=self.mainqueue, pos=self.pos)
		self.gotmap = False
		self.gotpos = False

	def __str__(self):
		return f'{self.client_id} ready={self.ready} pos={self.pos} k={self.kill} ck={self.client.kill} conn:{self.connected}/{self.client.connected} gotmap:{self.gotmap} gotpos:{self.gotpos}'
	

	def hit_list(self, objlist):
		hlist = []
		for obj in objlist:
			if obj.rect.colliderect(self.rect):
				hlist.append(obj)
		return hlist

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions

	def start_client(self):
		self.client.start()
		self.ready = True

	def update(self, blocks=None):
		if not self.ready and self.connected:
			logger.warning(f'{self} not ready but connected r:{self.ready} c:{self.connected} cc:{self.client.connected}')
			return
		elif not self.connected and not self.ready:
			#pass
			#logger.warning(f'{self} not connected not ready r:{self.ready} c:{self.connected} cc:{self.client.connected}')
			return
		elif not self.client.connected and self.ready:
			logger.warning(f'{self} ready but client not connected r:{self.ready} c:{self.connected} cc:{self.client.connected}')
			return
		hitlist = self.hit_list(blocks)
		oldy = self.rect.y
		oldx = self.rect.x
		oldpos = self.pos
		oldrect = self.rect
		self.pos += self.vel
		#self.pos.x += self.vel.x
		#self.pos.y += self.vel.y
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		pygame.draw.rect(surface=self.surface, color=(23,23,223), rect=self.rect, width=1)
		for hit in hitlist:
			if hit.block_type != 0:
				logger.debug(f'{self} hitlist {len(hitlist)} hit={hit}')
				pygame.draw.rect(surface=self.surface, color=(123,123,123), rect=hit.rect, width=1)
				pygame.draw.rect(surface=self.surface, color=(223,123,223), rect=self.rect, width=1)
				if self.vel.x > 0:
					# moving right
					self.rect.right = hit.rect.left
					self.vel[0] = 0
				if self.vel.x < 0:
					# moving left
					self.rect.left = hit.rect.right
					self.vel[0] = 0
				if self.vel.y > 0:
					# moving down
					self.rect.bottom = hit.rect.top
					self.vel[1] = 0
				if self.vel.y < 0:
					# moving up
					self.rect.top = hit.rect.bottom
					self.vel[1] = 0				
				
		self.pos.y = self.rect.y
		self.pos.x = self.rect.x
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
			self.client.send_pos(pos=self.pos, center=self.pos)
		else:
			logger.warning(f'{self} ignoring setpos {self.pos} to {pos}')

