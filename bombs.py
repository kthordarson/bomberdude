import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, POWERUPS, PLAYERSIZE
from globals import limit as limit

BOMBSIZE = 5

class Bomb_Flame(pg.sprite.Sprite):
	def __init__(self, screen, name, pos, vel, flame_length):
		super().__init__()
		self.screen = screen
		self.name = name
		self.flame_length = flame_length
		self.color = pg.Color('red')
		self.pos = pg.math.Vector2(pos)
		self.endpos = pg.math.Vector2(self.pos.x, self.pos.y)
		self.vel = pg.math.Vector2(vel[0], vel[1])  # flame direction
		self.image = pg.Surface([1,1])
		pg.draw.line(self.image, self.color, self.pos, self.endpos, 1)
		#pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, self.endpos.x, self.endpos.y))
		self.rect = self.image.get_rect()
		self.image.fill(self.color, self.rect)
		self.max_length = 13
		self.length = 1
		self.flame_adder = 1
		self.expand = True

	def update(self):
		self.endpos += self.vel
		self.rect.x = self.endpos.x
		self.rect.y = self.endpos.y
		#self.image = pg.Surface((1,1), pg.SRCALPHA)
		#pg.draw.line(self.image, self.color, self.pos, self.endpos, 1)
		#pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, self.endpos.x, self.endpos.y))
		#self.rect = self.image.get_rect()

	def draw(self):
		pg.draw.line(self.screen, self.color, self.pos, self.endpos, 1)

class BlockBomb(pg.sprite.Sprite):
	def __init__(self, pos, bomber_id, block_color, screen, bomb_power, gridpos):
		super().__init__()
		self.screen = screen
		self.pos = pg.math.Vector2(pos[0], pos[1])
		# self.pos = pg.math.Vector2(pos)
		# self.pos = (self.pos.x * BLOCKSIZE, self.pos.y * BLOCKSIZE)
		self.gridpos = gridpos
		# self.x = x * BLOCKSIZE
		# self.y = y * BLOCKSIZE
		self.bomber_id = bomber_id
		self.block_color = block_color
		self.start_time = pg.time.get_ticks() / FPS
		# self.pos = (self.x, self.y)
		self.image = pg.Surface((BOMBSIZE,BOMBSIZE ), pg.SRCALPHA)
		# todo fix exact placement on grid
		# pg.draw.rect(self.image, self.block_color, [pos[0], pos[1], BOMBSIZE,BOMBSIZE])
		pg.draw.circle(self.image, self.block_color, (self.pos.x,self.pos.y), BOMBSIZE)
		# pg.draw.circle(self.image, (255,0,0), [self.x,self.y], BOMBSIZE+30, 15)
		self.rect = self.image.get_rect()
		# self.image.fill(self.block_color, self.rect)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		#self.rect.x = self.pos.x # + BLOCKSIZE // 2
		#self.rect.y = self.pos.y # + BLOCKSIZE // 2
		self.font = pg.font.SysFont('calibri', 10, True)
		self.bomb_timer = 100
		self.exploding = False
		self.exp_steps = 50
		self.exp_radius = 1
		self.done = False
		self.flame_len = 1
		self.flame_power = bomb_power
		self.flame_width = 10
		self.expand_up = True
		self.expand_down = True
		self.expand_right = True
		self.expand_left = True
		# each bomb has four flames for each side
		# self.flames = [Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, flame_length=self.flame_len) for k in range(4)]
		self.flames = pg.sprite.Group()
		# screen, name, pos, vel, flame_length
		flame = Bomb_Flame(screen=self.screen, pos=(self.rect.centerx, self.rect.centery), flame_length=self.flame_len, vel=(-1,0), name='left')
		self.flames.add(flame)
		flame = Bomb_Flame(screen=self.screen, pos=(self.rect.centerx, self.rect.centery), flame_length=self.flame_len, vel=(1,0), name='right')
		self.flames.add(flame)
		flame = Bomb_Flame(screen=self.screen, pos=(self.rect.centerx, self.rect.centery), flame_length=self.flame_len, vel=(0,1), name='down')
		self.flames.add(flame)
		flame = Bomb_Flame(screen=self.screen, pos=(self.rect.centerx, self.rect.centery), flame_length=self.flame_len, vel=(0,-1), name='up')
		self.flames.add(flame)
		#flameright = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, flame_length=self.flame_len, vel=(1,0), name='right')  # right
		#flamedown = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, flame_length=self.flame_len, vel=(0,1), name='down')  # down
		#flameup = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, flame_length=self.flame_len, vel=(0,-1), name='up') # up
		#self.flames.add(flameleft)
		#self.flames.add(flameright)
		#self.flames.add(flamedown)
		#self.flames.add(flameup)

	def update(self):
		self.dt = pg.time.get_ticks() / FPS
		if self.dt - self.start_time >= self.bomb_timer: # I will start exploding after xxx seconds....
			self.exploding = True
		if self.exploding:
			self.exp_radius += 1     # make it bigger
			if self.exp_radius >= BLOCKSIZE:
				self.exp_radius = BLOCKSIZE # not too big
			[flame.update() for flame in self.flames] # update flame animation, flames do player damage and destroy most blocks
			self.exp_steps -= 1 # animation steps ?
			if self.exp_steps <= 0: # stop animation and kill bomb
				self.done = True
				# self.kill()
				# self.exploding = False
				# self.done = True
				# self.kill() # destroy flame
	def update_map(self, game_map):
		# do stuff with map after explosion...
		return game_map

	def draw(self):
		# pg.draw.rect(self.screen, self.block_color, [self.pos.x,self.pos.y, BOMBSIZE,BOMBSIZE])
		pg.draw.circle(self.screen, self.block_color, (self.pos.x,self.pos.y), BOMBSIZE)
		if self.exploding:
			pg.draw.circle(self.screen, (255,255,255), (self.rect.centerx, self.rect.centery), self.exp_radius,1)
			[flame.draw() for flame in self.flames]
