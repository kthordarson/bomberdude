import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, POWERUPS, PLAYERSIZE
from globals import limit as limit

class Block(pg.sprite.Sprite):
	def __init__(self, x, y, screen, block_type):
		super().__init__()
		self.screen = screen
		self.block_type = block_type
		self.pos = pg.math.Vector2(x * BLOCKSIZE, y * BLOCKSIZE)
		self.x = self.pos.x
		self.y = self.pos.y
		self.gridpos = (x,y)
		# self.pos = [self.x, self.y]
		# self.block_color = (255,255,0)
		if self.block_type == 0:
			self.solid = False
			self.permanent = False
			self.block_color = pg.Color('black')
			self.bordercolor = (255,255,255)
		elif self.block_type == 1:
			self.solid = True
			self.permanent = True
			self.block_color = pg.Color('orangered1')
			self.bordercolor = (0,255,0)
		elif self.block_type == 2:
			self.solid = True
			self.permanent = True
			self.block_color = pg.Color('orangered2')
			self.bordercolor = (244,20,44)
		elif self.block_type == 3:
			self.solid = True
			self.permanent = True
			self.block_color = pg.Color('orangered3')
			self.bordercolor = (144,10,144)
		elif 4 < self.block_type <= 9:
			self.solid = True
			self.permanent = False
			self.block_color = pg.Color('gray31')
			self.bordercolor = (44,0,44)
		elif self.block_type == 99:
			self.solid = False
			self.permanent = False
			self.block_color = pg.Color('black')
			self.bordercolor = (4,123,44)
		else:
			self.solid = False
			self.permanent = False
			self.block_color = pg.Color('white')
			self.bordercolor = (55,55,244)

		self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE), pg.SRCALPHA)
		# pg.draw.rect(self.image, self.block_color, (self.pos.x, self.pos.y, BLOCKSIZE, BLOCKSIZE))
		self.rect = self.image.get_rect()
		# self.image.fill(self.block_color, self.rect)
		# self.rect.center = (50,50)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# self.solid = solid
		self.font = pg.font.SysFont('calibri', 10, True)
		# self.pos = pg.math.Vector2(self.rect.x,self.rect.y)

#	def update(self):
#		self.pos = pg.math.Vector2(self.rect.x,self.rect.y)
		
	def draw(self):
		pg.draw.rect(self.screen, self.block_color, (self.pos.x, self.pos.y, BLOCKSIZE, BLOCKSIZE))
		# pg.draw.rect(self.screen, (255,0,0), (self.pos.x, self.pos.y, BLOCKSIZE, BLOCKSIZE), 1)

	def set_zero(self):
		self.solid = False
		self.permanent = False
		self.block_type = 0
		self.block_color = pg.Color('black')
		self.bordercolor = (255,255,255)
		
class Powerup_Block(pg.sprite.Sprite):
	def __init__(self, x, y, screen):
		super().__init__()
		self.screen = screen
		self.x = x * BLOCKSIZE
		self.y = y * BLOCKSIZE
		self.pos = (x * BLOCKSIZE, y * BLOCKSIZE)
		self.gridpos = (x, y)
		self.pos = (self.x, self.y)
		self.block_color = random.choice(list(colordict.items()))[1]   #block_color
		self.image = pg.Surface((BLOCKSIZE // 2,BLOCKSIZE // 2), pg.SRCALPHA)
		self.radius = BLOCKSIZE // 2
		pg.draw.rect(self.image, (0,0,0), (self.x, self.y, BLOCKSIZE // 2 , BLOCKSIZE // 2))
		self.rect = self.image.get_rect()
		self.image.fill(self.block_color, self.rect)
		self.rect.centerx = self.x + BLOCKSIZE // 2
		self.rect.centery = self.y + BLOCKSIZE // 2
		self.solid = False
		self.powerup_type = random.choice(list(POWERUPS.items()))
		self.timer = 400
		self.time_left = self.timer
		self.ending_soon = False
		self.taken = False
		self.start_time = pg.time.get_ticks() / FPS

	def flash(self):
		self.block_color = random.choice(list(colordict.items()))[1]   #block_color
		self.image = pg.Surface((BLOCKSIZE // 2,BLOCKSIZE // 2), pg.SRCALPHA)
		pg.draw.rect(self.image, (0,0,0), (self.x, self.y, BLOCKSIZE // 2 , BLOCKSIZE // 2))
		self.rect = self.image.get_rect()
		self.image.fill(self.block_color, self.rect)
		self.rect.centerx = self.x + BLOCKSIZE // 2
		self.rect.centery = self.y + BLOCKSIZE // 2

	def update(self):
		self.dt = pg.time.get_ticks() / FPS
		if self.dt - self.start_time >= self.timer:
			self.time_left = 0
			# self.kill()
		if self.dt - self.start_time >= self.timer // 3:
			self.ending_soon = True

	def draw_outlines(self):
		pass

