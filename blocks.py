import random
import pygame as pg
from pygame.colordict import THECOLORS as colordict
from globals import BLOCKSIZE, FPS, POWERUPS

class Particle(pg.sprite.Sprite):
	def __init__(self, pos):
		super().__init__()
		# self.screen = screen
		self.pos = pg.math.Vector2(pos.x, pos.y)
		self.vel = pg.math.Vector2(random.uniform(-2,2), random.uniform(-2,2))  # pg.math.Vector2(0, 0)
		# self.vel = pg.math.Vector2(0,0)
		self.color = random.choice(list(colordict.items()))[1]  # (255, 155, 55)
		self.image = pg.Surface((13, 13), pg.SRCALPHA)
		self.image.set_alpha(155)
		self.rect = self.image.get_rect()  # pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, 1, 1))
		self.image.set_alpha(28)
		self.image.fill(self.color, self.rect)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.move = False

	def update(self):
		pass

	def draw(self, screen):
		pass
		# self.update()
		# if self.move:
		# pg.draw.circle(screen, self.color, (int(self.pos.x), int(self.pos.y)), 5)
		# pg.draw.rect(screen, self.color, (self.pos.x, self.pos.y, 3, 3))
	def bounce(self, screen):
		self.pos += self.vel
		col = [self.color[0], self.color[1], self.color[2]] # color fading foobar
		if col[0] > 0:
			col_r = col[0]  - 1
		else:
			col_r = col[0]
		if col[1] > 0:
			col_g = col[1]  - 1
		else:
			col_g = col[1]
		if col[2] > 0:
			col_b = col[2]  - 1
		else:
			col_b = col[2]
		self.color = [col_r, col_g, col_b]
		# print(f'[bounce] pos {self.pos} vel {self.vel}')
		pg.draw.rect(screen, self.color, (self.pos.x, self.pos.y, 3, 3))

class Block(pg.sprite.Sprite):
	def __init__(self, x, y, block_type, solid=True, permanent=False, block_color=(40,30,60), border_color=(255,255,255)):
		super().__init__()
		self.block_type = block_type
		self.block_color = block_color
		self.solid = solid
		self.permanent = permanent
		self.bordercolor = border_color
		self.size = BLOCKSIZE
		self.pos = pg.math.Vector2(x * BLOCKSIZE, y * BLOCKSIZE)
		self.x = self.pos.x
		self.y = self.pos.y
		self.gridpos = (x, y)
		self.image = pg.Surface((BLOCKSIZE, BLOCKSIZE), pg.SRCALPHA)
		pg.draw.rect(self.image, self.block_color, (self.pos.x, self.pos.y, self.size, self.size)) # self.image.get_rect()
		self.image.set_alpha(27)
		self.rect = self.image.get_rect()
		self.image.fill(self.block_color, self.rect)
		self.image.set_colorkey((0, 0, 0))
		self.image.set_alpha(128)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.explode = False
		self.particles = pg.sprite.Group()
		[self.particles.add(Particle(self.pos)) for k in range(2, random.randint(4,10))]
		self.ending_soon = False
		self.timer = 400
		self.time_left = self.timer
		self.start_time = -1
		self.dt = pg.time.get_ticks() / FPS

	def update(self):
		pass
	def draw(self, screen):
		#if self.block_type > 0:
		pg.draw.rect(screen, self.block_color, (self.pos.x, self.pos.y, self.size, self.size))

	def set_zero(self):
		pass
		# self.block_type = 0
		# self.block_color = pg.Color('black')
		# self.bordercolor = (255, 255, 255)

	def drop_powerblock(self):
		self.start_time = pg.time.get_ticks() / FPS
		self.block_color = pg.Color('green')
		self.dt = pg.time.get_ticks() / FPS
		self.size = BLOCKSIZE // 2
		# self.pos.x += self.size
		# self.pos.y += self.size
		self.solid = False
		self.permanent = False
	def take_damage(self, screen):
		# [particle.draw(screen) for particle in self.particles]
		# [particle.update() for particle in self.particles]
		[particle.bounce(screen) for particle in self.particles]

class Powerup_Block(pg.sprite.Sprite):
	def __init__(self, x, y):
		super().__init__()
#		self.screen = screen
		PBLOCKSIZE = BLOCKSIZE
		self.x = x * BLOCKSIZE
		self.y = y * BLOCKSIZE
		self.pos = pg.math.Vector2(x * PBLOCKSIZE, y * PBLOCKSIZE)
		self.gridpos = (x, y)
		self.block_color = pg.Color('red')  # random.choice(list(colordict.items()))[1]   #block_color
		self.image = pg.Surface((PBLOCKSIZE // 2, PBLOCKSIZE // 2), pg.SRCALPHA)
		self.radius = PBLOCKSIZE // 2
		pg.draw.rect(self.image, (0, 220, 0), (self.x, self.y, PBLOCKSIZE // 2 , PBLOCKSIZE // 2))
		self.image.set_alpha(227)
		self.rect = self.image.get_rect()
		self.image.fill(self.block_color, self.rect)
		self.solid = False
		self.powerup_type = random.choice(list(POWERUPS.items()))
		self.timer = 400
		self.time_left = self.timer
		self.ending_soon = False
		self.taken = False
		self.start_time = pg.time.get_ticks() / FPS

	def draw(self, screen):
		#PBLOCKSIZE = BLOCKSIZE // 2
		pg.draw.rect(screen, self.block_color, (self.pos.x, self.pos.y, BLOCKSIZE // 2, BLOCKSIZE // 2))

	def flash(self):
		pass

	def update(self):
		self.dt = pg.time.get_ticks() / FPS
		if self.dt - self.start_time >= self.timer:
			self.time_left = 0
			# self.kill()
		if self.dt - self.start_time >= self.timer // 3:
			self.ending_soon = True

	def draw_outlines(self):
		pass
