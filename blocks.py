import random
import pygame as pg
import pygame.freetype
from pygame.colordict import THECOLORS as colordict
from globals import BLOCKSIZE, FPS, POWERUPS

class Particle(pg.sprite.Sprite):
	def __init__(self, pos, direction=None, blockrect=None):
		super().__init__()
		# self.screen = screen
		self.blockrect = blockrect
		self.color = random.choice(list(colordict.items()))[1]  # (255, 155, 55)
		self.image = pg.Surface((3, 3), pg.SRCALPHA)
		self.direction = direction
		self.alpha = 255
		self.alpha_mod = -3
		self.image.set_alpha(self.alpha)
		self.rect = self.image.get_rect()  # pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, 1, 1))
		self.image.set_alpha(self.alpha)
		self.image.fill(self.color, self.rect)
		self.pos = pg.math.Vector2(pos.x, pos.y)
		self.vel = pg.math.Vector2(random.uniform(-2,2), random.uniform(-2,2))  # pg.math.Vector2(0, 0)
		if self.direction == 'up' and self.vel.y <= 0:
			self.vel.y = -self.vel.y
			self.pos = self.blockrect.midbottom
		if self.direction == 'down' and self.vel.y >= 0:
			self.vel.y = -self.vel.y
			self.pos = self.blockrect.midtop
		if self.direction == 'right' and self.vel.x >= 0:
			self.vel.x = -self.vel.x
			self.pos = self.blockrect.midleft
		if self.direction == 'left' and self.vel.x <= 0:
			self.vel.x = -self.vel.x
			self.pos = self.blockrect.midright
		# self.vel = pg.math.Vector2(0,0)
		#self.rect.centerx = self.pos.x
		#self.rect.centery = self.pos.y
		self.move = False
		self.radius = 2

		self.timer = 100
		self.time_left = self.timer
		self.start_time = pg.time.get_ticks() / FPS

	def update(self):
		pass

	def draw(self, screen):
		pass

	def bounce(self, screen):
		self.dt = pg.time.get_ticks() / FPS
		if self.dt - self.start_time >= self.timer:
			self.time_left = 0
			# print(f'[particle] timekill {self.pos} v {self.vel} c {self.color} a {self.alpha}')
			self.kill()
		self.pos += self.vel
		self.alpha += self.alpha_mod
		if self.alpha <= 0:
			self.alpha = 0
			# print(f'[particle] alphakill {self.pos} v {self.vel} c {self.color} a {self.alpha}')
			self.kill()
		# col = [self.color[0], self.color[1], self.color[2]] # color fading foobar
		# if col[0] > 0:
		# 	col_r = col[0]  - 13
		# 	if col_r <= 0:
		# 		col_r = 0
		# else:
		# 	col_r = col[0]
		# if col[1] > 0:
		# 	col_g = col[1]  - 13
		# 	if col_g <= 0:
		# 		col_g = 0
		# else:
		# 	col_g = col[1]
		# if col[2] > 0:
		# 	col_b = col[2]  - 13
		# 	if col_b <= 0:
		# 		col_b = 0
		# else:
		# 	col_b = col[2]
		# self.color = [col_r, col_g, col_b]
		# print(f'[bounce] pos {self.pos} vel {self.vel} color {col}')
		# pg.draw.rect(screen, self.color, (self.pos.x, self.pos.y, 3, 3))
		self.image.set_alpha(self.alpha)
		pg.draw.circle(self.image, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)
		screen.blit(self.image, self.pos)

class Block(pg.sprite.Sprite):
	def __init__(self, gridpos, block_type, solid=True, permanent=False, block_color=(40,30,60), border_color=(255,255,255)):
		super().__init__()
		self.block_type = block_type
		self.block_color = block_color
		self.solid = solid
		self.permanent = permanent
		self.bordercolor = border_color
		self.size = BLOCKSIZE
		self.gridpos = gridpos
		self.pos = pg.math.Vector2(self.gridpos[0] * BLOCKSIZE, self.gridpos[1] * BLOCKSIZE)
#		self.x = self.pos.x
#		self.y = self.pos.y
#		self.gridpos = (x, y)
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
		# [self.particles.add(Particle(self.pos)) for k in range(2, random.randint(4,10))]
		self.ending_soon = False
		self.timer = 100
		self.time_left = self.timer
		self.start_time = -1  #  will be set when block converts to powerup
		self.dt = pg.time.get_ticks() / FPS
		self.powerblock = False
		self.hit = False
		self.font = pg.freetype.Font("DejaVuSans.ttf", 10)
		self.font.fgcolor = pg.Color('white')

	def update(self):
		# [particle.bounce(screen) for particle in self.particles]
		if self.powerblock:
			self.dt = pg.time.get_ticks() / FPS
			# print(f'[block] poweruptimer {self.timer} {self.time_left} {self.start_time} {self.dt - self.start_time}')
			if self.dt - self.start_time >= self.timer:
				self.time_left = 0
				self.block_color = pg.Color('black')
				self.block_type = 0
				self.powerblock = False
				self.size = BLOCKSIZE
				self.pos.x -= 5
				self.pos.y -= 5
				# self.kill()
			if self.dt - self.start_time >= self.timer // 3:
				self.ending_soon = True

	def draw(self, screen):
		#if self.block_type > 0:
		[particle.bounce(screen) for particle in self.particles]
		pg.draw.rect(screen, self.block_color, (self.pos.x, self.pos.y, self.size, self.size))
			# self.font.render_to(screen, (self.pos.x+2, self.pos.y), f'{self.block_type}', self.font.fgcolor)
		# self.font.render_to(screen, (self.pos.x+2, self.pos.y), f'{self.gridpos[0]}', self.font.fgcolor)
		# self.font.render_to(screen, (self.pos.x+2, self.pos.y+10), f'{self.gridpos[1]}', self.font.fgcolor)

	def set_zero(self):
		pass

	def drop_powerblock(self):
		if not self.powerblock:
			self.start_time = pg.time.get_ticks() / FPS
			self.block_color = pg.Color('firebrick4')
			# self.dt = pg.time.get_ticks() / FPS
			self.size = BLOCKSIZE // 2
			self.solid = False
			self.permanent = False
			self.pos.x += 5
			self.pos.y += 5
			self.powerblock = True
			print(f'[powerblock] {self.pos} {self.gridpos} {self.powerblock} ')
			self.hit = False

	def take_damage(self, screen, flame):
		if not self.hit:
			[self.particles.add(Particle(self.pos, flame.direction, self.rect)) for k in range(2, random.randint(4,10))]
			self.hit = True
		# self.particles.add(Particle(flame.pos))

		# print(f'[part] {len(self.particles)}')

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
