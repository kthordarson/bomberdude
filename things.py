import math
import random
from threading import Thread, Event, Event
from queue import Queue, Empty
import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import MAXPARTICLES,BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, GRIDSIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID
from globals import random_velocity

class BasicThing(Sprite):
	def __init__(self, pos, image):
		Sprite.__init__(self)
		self.thingq = Queue()
		self.pos = Vector2(pos)
		self.image = image
		self.collisions = []
		self.start_time = pygame.time.get_ticks()
		self.accel = Vector2(0, 0)

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions



class Block(BasicThing):
	def __init__(self, pos, gridpos, block_type, reshandler):
		
		self.block_type = block_type
		self.solid = BLOCKTYPES.get(self.block_type)["solid"]
		self.permanent = BLOCKTYPES.get(self.block_type)["permanent"]
		self.size = BLOCKTYPES.get(self.block_type)["size"]
		self.bitmap = BLOCKTYPES.get(self.block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(self.block_type)["powerup"]
		self.rm = reshandler
		self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)
		BasicThing.__init__(self, pos, self.image)
		self.explode = False
		self.poweruptime = 10
		self.gridpos = gridpos  # Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.image.set_alpha(255)
		self.image.set_colorkey((0, 0, 0))

	def hit(self, flame):
		# self.bitmap = BLOCKTYPES.get(11)["bitmap"]
		# self.solid = False
		# self.permanent = True
		# self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)
		particles = None
		newblock = None
		powerblock = None
		if self.block_type != 0:
			particles = Group()
			for k in range(1, MAXPARTICLES+random.randint(1, 10)):
				if flame.vel.x < 0:  # flame come from left
					particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right"), reshandler=self.rm))  # make particle go right
				elif flame.vel.x > 0:  # right
					particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left"), reshandler=self.rm))  # for k in range(1,2)]
				elif flame.vel.y > 0:  # down
					particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up"), reshandler=self.rm))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
				elif flame.vel.y < 0:  # up
					particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down"), reshandler=self.rm))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
			if self.powerup:
				powerblock = Powerup(pos=self.rect.center, reshandler=self.rm)
			newblock = Block(self.pos, self.gridpos, block_type=0, reshandler=self.rm)
			flame.kill()
			self.kill()
		return self.pos, self.gridpos, particles, newblock, powerblock


class Powerup(BasicThing):
	def __init__(self, pos, reshandler):
		# super().__init__()
		self.rm = reshandler
		self.powertype = random.choice([1, 2, 3])
#		if self.powertype == 0:
#			self.image_org, self.rect = self.rm.get_image(filename='data/black.png', force=False)
		if self.powertype == 1:
			self.image_org, self.rect = self.rm.get_image(filename='data/heart.png', force=False)
		if self.powertype == 2:
			self.image_org, self.rect = self.rm.get_image(filename='data/newbomb.png', force=False)
		if self.powertype == 3:
			self.image_org, self.rect = self.rm.get_image(filename='data/bombpwr.png', force=False)
		self.size = [15,15]
		self.image = pygame.transform.scale(self.image_org, self.size)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image_org)
		self.rect = self.image.get_rect()
		self.rect.center = pos
		self.alpha = 255
		self.image.set_alpha(self.alpha)
		self.timer = 10000
		self.timeleft = self.timer
		self.sizemod = -0.25

	def update(self, items=None, surface=None):		
		self.timeleft = self.timer - (pygame.time.get_ticks() - self.start_time)
		self.size[0] += self.sizemod
		self.size[1] += self.sizemod
		if self.size[0] <= 10 or self.size[0] >= 15:
			self.sizemod *= -1
			#self.size = [15,15]
		self.image = pygame.transform.scale(self.image_org, self.size)
		self.rect = self.image.get_rect()
		self.rect.center = self.pos
		if pygame.time.get_ticks() - self.start_time >= self.timer:
			self.kill()

	def hit(self):
		pass

class Particle(BasicThing):
	def __init__(self, pos, vel, reshandler=None):
		# super().__init__()
		self.rm = reshandler
		#self.image, self.rect = self.rm.get_image(filename='data/greenorb.png', force=False)
		xsize = random.randint(1,3)
		ysize = random.randint(1,3)
		self.image = pygame.Surface((xsize ,ysize))
		self.image.fill((95, 95, 95))
		#self.image.fill((random.randint(0,255),random.randint(0,255),random.randint(0,255)))
		self.rect = self.image.get_rect(center = pos)
		self.size = PARTICLESIZE
		#self.image = pygame.transform.scale(self.image, self.size)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.alpha = 255
		self.image.set_alpha(self.alpha)
		#self.rect = self.image.get_rect(topleft=self.pos)
		#self.rect.x = self.pos.x
		#self.rect.y = self.pos.y
		self.timer = 20000
		self.hits = 0
		self.maxhits = 1
		self.angle = math.degrees(0)
		self.mass = 11
		self.vel = vel

	def __str__(self) -> str:
		return f'Particle: {self.pos} {self.vel}'

	def update(self, items=None, surface=None):
		if pygame.time.get_ticks() - self.start_time >= self.timer:
			self.kill()
			return
		if self.rect.top <= 0 or self.rect.left <= 0:
			self.kill()
			return
		if self.hits >= self.maxhits:
			self.kill()
			return
		else:
			self.image.set_alpha(self.alpha)
			self.vel -= self.accel
			self.vel.y += abs(self.vel.y * 0.1) + 0.025
			self.pos += self.vel
			self.rect.x = self.pos.x
			self.rect.y = self.pos.y

	def hit(self, other):
		self.hits += 1
		self.vel = -self.vel
		self.alpha = int(self.alpha * 0.6)


class Flame(BasicThing):
	def __init__(self, pos, vel, flame_length, reshandler, rect):
		self.rm = reshandler
		self.image = pygame.Surface((5,5), pygame.SRCALPHA)
		self.image.fill((255,0,0))
		self.rect = self.image.get_rect()
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.size = FLAMESIZE
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.start_pos = Vector2((rect.centerx, rect.centery))
		self.vel = Vector2(vel)
		self.timer = 2000
		self.flame_length = flame_length
		self.timeleft = self.timer


	def update(self, surface=None):
		self.timeleft = self.timer - (pygame.time.get_ticks() - self.start_time)
		if pygame.time.get_ticks() - self.start_time >= self.timer:
			self.kill()
		self.pos += self.vel
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		pygame.draw.line(surface, (155, 0, 0), self.start_pos, self.rect.center, 2)


class Bomb(BasicThing):
	def __init__(self, pos, bomber_id, bomb_power, reshandler=None):
		self.rm = reshandler
		self.image, self.rect = self.rm.get_image(filename='data/bomb.png', force=False)
		self.size = BOMBSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.bomber_id = bomber_id
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.timer = 3000
		self.bomb_size = 5
		self.exp_radius = 1
		self.done = False
		self.flame_power = bomb_power
		self.flame_len = bomb_power
		self.flame_width = 10
		self.flamesout = False
		self.flames = Group()
		self.bsize = self.size


	def update(self):
		dt = pygame.time.get_ticks()
		if dt - self.start_time >= self.timer:
			pass

	def exploder(self):
		flames = Group()
		flames.add(Flame(pos=self.pos, vel=Vector2(1,0), flame_length=self.flame_len, reshandler=self.rm, rect=self.rect))
		flames.add(Flame(pos=self.pos, vel=Vector2(-1,0), flame_length=self.flame_len, reshandler=self.rm, rect=self.rect))
		flames.add(Flame(pos=self.pos, vel=Vector2(0,-1), flame_length=self.flame_len, reshandler=self.rm, rect=self.rect))
		flames.add(Flame(pos=self.pos, vel=Vector2(0,1), flame_length=self.flame_len, reshandler=self.rm, rect=self.rect))
		self.bomber_id.bombs_left += 1
		return flames
