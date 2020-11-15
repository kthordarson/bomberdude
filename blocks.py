import random
import pygame as pg
import pygame.freetype
from pygame.colordict import THECOLORS as colordict
from globals import BLOCKSIZE, FPS, POWERUPS

class Particle(pg.sprite.Sprite):
	def __init__(self, block, direction=None):
		super().__init__()
		# self.screen = screen
		# block.rect = block.rect
		self.color = random.choice(list(colordict.items()))[1]  # (255, 155, 55)
		self.image = pg.Surface((1, 1), pg.SRCALPHA)
		self.direction = direction
		self.alpha = 0
		self.alpha_mod = 13
		self.image.set_alpha(self.alpha)
		self.rect = self.image.get_rect()  # pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, 1, 1))
		self.image.set_alpha(self.alpha)
		self.image.fill(self.color, self.rect)
		# self.pos = pg.math.Vector2(block.pos)
		self.vel = pg.math.Vector2(random.uniform(-2,2), random.uniform(-2,2))  # pg.math.Vector2(0, 0)
		if self.direction == 'up':
			# self.vel.y = -self.vel.y
			self.rect.midtop = block.rect.midbottom
			#self.rect.x += 2
			#self.pos = pg.math.Vector2(block.rect.midbottom[0],  block.rect.midbottom[1] )
			#self.rect.y += 12
		if self.direction == 'down': # and self.vel.y >= 0:
			#self.vel.y = -self.vel.y
			self.rect.midbottom = block.rect.midtop
			#self.pos = self.pos = pg.math.Vector2(block.rect.midtop[0],  block.rect.midtop[1] - 2)
			#self.pos.y -= 2
		if self.direction == 'right': # and self.vel.x >= 0:
			#self.vel.x = -self.vel.x
			self.rect.x = block.rect.midright[1]
			#self.pos = pg.math.Vector2(block.rect.midleft[0] - 2 , block.rect.midleft[1])
			#self.pos.x -= 2
		if self.direction == 'left': # and self.vel.x <= 0:
			#self.vel.x = -self.vel.x
			self.rect.midright = block.rect.midleft
			#self.pos = pg.math.Vector2(block.rect.midright[0] + 2, block.rect.midright[1])
			#self.pos.x += 4
		# self.vel = pg.math.Vector2(0,0)
		#self.rect.centerx = self.pos.x
		#self.rect.centery = self.pos.y
		self.pos = self.rect.center
		self.move = False
		self.radius = 1
		self.dt = pg.time.get_ticks() / FPS
		self.timer = 100
		self.time_left = self.timer
		self.start_time = pg.time.get_ticks() / FPS
		#self.pos.x = self.rect.x
		#self.pos.y = self.rect.y
	
	def collide(self, blocks):
		return pg.sprite.spritecollide(self, blocks, False)

	def update(self, screen):
		self.dt = pg.time.get_ticks() / FPS
		w, h = pg.display.get_surface().get_size()
		if self.dt - self.start_time >= self.timer:
			#self.time_left = 0
			#print(f'[particle] timekill {self.pos} v {self.vel} c {self.color} a {self.alpha}')
			self.kill()
		self.pos += self.vel
		self.alpha += self.alpha_mod
		if self.alpha <= 0:
			self.alpha = 0
			# print(f'[particle] alphakill {self.pos} v {self.vel} c {self.color} a {self.alpha}')
			# self.kill()
		self.image.set_alpha(self.alpha)
		if self.pos.x >= w or self.pos.x <= 0 or self.pos.y >= h or self.pos.y <= 0:
			self.kill()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
#		if self.pos.y >= h or self.pos.y <= 0:
#			self.kill()
		#surfacecolor = screen.get_at((int(self.pos.x), int(self.pos.y))) # get color behind particle
		#if surfacecolor != (0,0,0):										# only draw particle if background is balck
		#	self.kill()

	def draw(self, screen):
		pg.draw.circle(self.image, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)
		screen.blit(self.image, self.pos)

#	def bounce(self, screen):

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
		# self.particles = pg.sprite.Group()
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

	def collide(self, items):
		return pg.sprite.spritecollide(self, items, False)

	def update(self):
		# [particle.bounce(screen) for particle in self.particles]
		if self.powerblock:
			self.dt = pg.time.get_ticks() / FPS
			# print(f'[block] poweruptimer {self.timer} {self.time_left} {self.start_time} {self.dt - self.start_time}')
			if self.dt - self.start_time >= self.timer:
				self.time_left = 0
				self.block_color = pg.Color('black')
				self.block_type = 0
				self.solid = False
				self.powerblock = False
				self.size = BLOCKSIZE
				self.pos.x -= 5
				self.pos.y -= 5
				# self.kill()
			if self.dt - self.start_time >= self.timer // 3:
				self.ending_soon = True

	def draw(self, screen):
		#if self.block_type > 0:
		# [particle.bounce(screen) for particle in self.particles]
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

#	def take_damage(self, screen, flame):
#		if not self.hit:
#			[self.particles.add(Particle(self.pos, flame.direction, self.rect)) for k in range(12, random.randint(14,30))]
#			self.hit = True
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
