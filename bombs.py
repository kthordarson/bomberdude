import random
import pygame as pg
# from pygame.locals import *
from globals import BLOCKSIZE, FPS

BOMBSIZE = 5


class Bomb_Flame(pg.sprite.Sprite):
	def __init__(self, name, rect, vel, flame_length):
		super().__init__()
		self.name = name
		self.flame_length = flame_length
		self.color = pg.Color('red')
		self.pos = pg.math.Vector2(rect.centerx, rect.centery)
		self.endpos = pg.math.Vector2(self.pos.x, self.pos.y)
		self.vel = pg.math.Vector2(vel[0], vel[1])  # flame direction
		self.image = pg.Surface([1, 1])
		self.rect = self.image.get_rect() # self.rect = pg.draw.line(self.image, self.color, self.pos, self.endpos, 1)
		self.startrect = rect
		self.max_length = 13
		self.length = 1
		self.flame_adder = 1
		self.expand = True
	def stop(self):
		self.vel = pg.math.Vector2(0, 0) 
	def update(self):
		self.endpos += self.vel
		self.rect.x = self.endpos.x
		self.rect.y = self.endpos.y

	def draw(self, screen):
		pg.draw.line(screen, self.color, self.pos, self.endpos, 1)
		if self.vel[0] > 0: # flame direction = right
			pg.draw.line(screen, (255, 255, 55), self.startrect.topright, self.endpos, 1)
			pg.draw.line(screen, (255, 255, 55), self.startrect.bottomright, self.endpos, 1)
		if self.vel[0] < 0: # flame direction = left
			pg.draw.line(screen, (255, 255, 55), self.startrect.topleft, self.endpos, 1)
			pg.draw.line(screen, (255, 255, 55), self.startrect.bottomleft, self.endpos, 1)
		if self.vel[1] < 0: # flame direction = up
			pg.draw.line(screen, (255, 255, 55), self.startrect.topleft, self.endpos, 1)
			pg.draw.line(screen, (255, 255, 55), self.startrect.topright, self.endpos, 1)
		if self.vel[1] > 0: # flame direction = down
			pg.draw.line(screen, (255, 255, 55), self.startrect.bottomleft, self.endpos, 1)
			pg.draw.line(screen, (255, 255, 55), self.startrect.bottomright, self.endpos, 1)


class BlockBomb(pg.sprite.Sprite):
	def __init__(self, pos, bomber_id, block_color, bomb_power, gridpos):
		super().__init__()
		self.flames = pg.sprite.Group()
# 		self.screen = screen
		self.pos = pg.math.Vector2(pos[0], pos[1])
		self.gridpos = gridpos
		self.bomber_id = bomber_id
		self.block_color = block_color
		self.start_time = pg.time.get_ticks() / FPS
		self.image = pg.Surface((BOMBSIZE, BOMBSIZE), pg.SRCALPHA)
		# todo fix exact placement on grid
		self.rect = self.image.get_rect()  # pg.draw.circle(self.screen, self.block_color, (int(self.pos.x), int(self.pos.y)), BOMBSIZE) # self.image.get_rect()
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pg.font.SysFont('calibri', 10, True)
		self.bomb_timer = 100
		self.exploding = False
		self.exp_steps = 50
		self.exp_radius = 1
		self.done = False
		self.flame_len = 1
		self.flame_power = bomb_power
		self.flame_width = 10
		self.dt = pg.time.get_ticks() / FPS
		# each bomb has four flames for each side
		self.flames = pg.sprite.Group()
		# screen, name, pos, vel, flame_length
		flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(-1, 0), name='left')
		self.flames.add(flame)
		flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(1, 0), name='right')
		self.flames.add(flame)
		flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(0, 1), name='down')
		self.flames.add(flame)
		flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(0, -1), name='up')
		self.flames.add(flame)

	def update(self):
		self.dt = pg.time.get_ticks() / FPS
		# I will start exploding after xxx seconds....
		if self.dt - self.start_time >= self.bomb_timer:
			self.exploding = True
		if self.exploding:
			self.exp_radius += 1     # make it bigger
			if self.exp_radius >= BLOCKSIZE:
				self.exp_radius = BLOCKSIZE  # not too big
			# update flame animation, flames do player damage and destroy most blocks
			[flame.update() for flame in self.flames]
			self.exp_steps -= 1  # animation steps ?
			if self.exp_steps <= 0:  # stop animation and kill bomb
				self.done = True

	def update_map(self, game_map):
		# do stuff with map after explosion...
		return game_map

	def draw(self, screen):
		pg.draw.rect(screen, self.block_color, [self.pos.x,self.pos.y, BOMBSIZE, BOMBSIZE])
		pg.draw.circle(screen, self.block_color, (int(self.pos.x), int(self.pos.y)), BOMBSIZE)
		if self.exploding:
			pg.draw.circle(screen, (255, 255, 255), (self.rect.centerx, self.rect.centery), self.exp_radius, 1)
			[flame.draw(screen) for flame in self.flames]
