import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, POWERUPS, PLAYERSIZE, BOMBSIZE
from globals import limit as limit

class Block(pg.sprite.Sprite):
	def __init__(self, x, y, screen, block_type):
		super().__init__()
		self.screen = screen
		self.block_type = block_type
		self.x = x * BLOCKSIZE
		self.y = y * BLOCKSIZE
		self.screen_pos = [x * BLOCKSIZE, y * BLOCKSIZE]
		self.gridpos = [x,y]
		self.pos = [self.x, self.y]
		# self.block_color = (255,255,0)
		if self.block_type == 0:
			self.solid = False
			self.permanent = False
			self.block_color = pg.Color('black')
			self.bordercolor = (255,255,255)
		elif self.block_type == 1:
			self.solid = True
			self.permanent = True
			self.block_color = pg.Color('orangered4')
			self.bordercolor = (0,255,0)
		elif self.block_type == 2:
			self.solid = True
			self.permanent = True
			self.block_color = pg.Color('orangered4')
			self.bordercolor = (244,20,44)
		elif 2 < self.block_type <= 9:
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
		pg.draw.rect(self.image, (0,0,0), (self.screen_pos[0], self.screen_pos[1], BLOCKSIZE, BLOCKSIZE))
		self.rect = self.image.get_rect()
		self.image.fill(self.block_color, self.rect)
		# self.rect.center = (50,50)
		self.rect.x = self.screen_pos[0]
		self.rect.y = self.screen_pos[1]
		# self.solid = solid
		self.font = pg.font.SysFont('calibri', 10, True)
		self.pos = pg.math.Vector2(self.rect.x,self.rect.y)

	def update(self):
		self.pos = pg.math.Vector2(self.rect.x,self.rect.y)

	def draw(self):
		pass
		# pg.draw.rect(self.screen, (0,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
		#pg.draw.line(self.screen, self.bordercolor, (self.x, self.y), (self.x + BLOCKSIZE, self.y))
		#pg.draw.line(self.screen, self.bordercolor, (self.x, self.y), (self.x, self.y + BLOCKSIZE))
		#pg.draw.line(self.screen, self.bordercolor, (self.x + BLOCKSIZE, self.y), (self.x + BLOCKSIZE, self.y + BLOCKSIZE))
		#pg.draw.line(self.screen, self.bordercolor, (self.x + BLOCKSIZE, self.y + BLOCKSIZE), (self.x, self.y + BLOCKSIZE))
		# pg.draw.circle(self.screen, (255,255,255), (self.x, self.y), 300)

class Powerup_Block(pg.sprite.Sprite):
	def __init__(self, x, y, screen):
		super().__init__()
		self.screen = screen
		self.x = x * BLOCKSIZE
		self.y = y * BLOCKSIZE
		self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
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

