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
		super().__init__((0,0), (0,0))
		self.vel = Vector2(0, 0)
		self.pos = (0,0)
		self.gridpos = [0,0]
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
		return f'player {self.client_id} ready={self.ready} pos={self.pos} gp={self.gridpos} k={self.kill} conn:{self.connected} gotmap:{self.gotmap} gotpos:{self.gotpos}'
	
	def move(self, direction):
		if self.ready:
			gpx = int(self.pos[0] // BLOCK)
			gpy = int(self.pos[1] // BLOCK)
			self.gridpos = (gpx, gpy)
			x = int(self.gridpos[0])
			y = int(self.gridpos[1])
			# logger.debug(f'{self} move {direction} {self.gridpos}')
			if direction == 'up':
				if self.client.gamemap.grid[x][y-1] == 0:
					self.gridpos = (x, y-1)
				else:
					logger.warning(f'{self} cant move g:{self.client.gamemap.grid[x][y-1]}')
			elif direction == 'down':
				if self.client.gamemap.grid[x][y+1] == 0:
					self.gridpos = (x, y+1)
				else:
					logger.warning(f'{self} cant move g:{self.client.gamemap.grid[x][y+1]}')
			elif direction == 'left':
				if self.client.gamemap.grid[x-1][y] == 0:
					self.gridpos = (x-1, y)
				else:
					logger.warning(f'{self} cant move g:{self.client.gamemap.grid[x-1][y]}')
			elif direction == 'right':
				if self.client.gamemap.grid[x+1][y] == 0:
					self.gridpos = (x+1, y)
				else:
					logger.warning(f'{self} cant move g:{self.client.gamemap.grid[x+1][y]}')
			self.pos[0] = self.gridpos[0] * BLOCK
			self.pos[1] = self.gridpos[1] * BLOCK
			self.rect.x = self.pos[0]
			self.rect.y = self.pos[1]
			self.client.pos = self.pos
			self.client.gridpos = self.gridpos
			self.setpos(pos=self.pos, gridpos=self.gridpos)

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

	def update(self, blocks=None):
		self.rect.topleft = (self.pos[0]+5, self.pos[1]+5)
		self.gridpos = (int(self.pos[0] // BLOCK), int(self.pos[1] // BLOCK))
		
		if self.client.gotpos and self.client.gotmap:			
			self.gotmap = self.client.gotmap
			if not self.gotpos: # self.gridpos[0] == 0 or self.gridpos[1] == 0:
				logger.info(f'[ {self} ] resetgridpos  client:{self.client} pos = {self.client.pos} {self.client.gridpos}')
				
				self.pos = self.client.pos
				self.gridpos = self.client.gridpos
				self.gotpos = True
				self.ready = True
		if self.connected:
			self.client.send_pos(pos=self.pos, center=self.pos, gridpos=self.gridpos)

	def take_powerup(self, powerup=None):
		pass

	def add_score(self):
		self.score += 1

	def setpos(self, pos, gridpos):
		#ngx = int(pos[0]*BLOCK)
		#ngy = int(pos[1]*BLOCK)
		#newgridpos = (ngx,ngy)
		logger.info(f'{self} setpos {self.pos} to {pos} gp={gridpos} ogp={self.gridpos} ngp={gridpos} client {self.client.pos} {self.client.gridpos}')
		self.pos = pos
		self.gridpos = gridpos
		self.client.pos = self.pos
		self.client.gridpos = self.gridpos
		self.gotpos = True
		self.client.gotpos = True
		self.ready = True
		self.client.send_pos(pos=self.pos, center=self.pos, gridpos=self.gridpos)
		#logger.info(f'{self} setposdone {self.pos}gp={self.gridpos} client {self.client.pos} {self.client.gridpos}')

