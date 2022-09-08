import math
import random
from threading import Thread, Event, Event
from queue import Queue, Empty
import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, GRIDSIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID
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
		particles = Group()
		for k in range(1, 10):
			if flame.vel.x < 0:  # flame come from left
				particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right"), reshandler=self.rm))  # make particle go right
			elif flame.vel.x > 0:  # right
				particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left"), reshandler=self.rm))  # for k in range(1,2)]
			elif flame.vel.y > 0:  # down
				particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up"), reshandler=self.rm))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
			elif flame.vel.y < 0:  # up
				particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down"), reshandler=self.rm))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
		return self.pos, self.gridpos, particles


class Powerup(BasicThing):
	def __init__(self, pos, reshandler):
		# super().__init__()
		self.rm = reshandler
		self.powertype = random.choice([0, 1, 2, 3])
		if self.powertype == 0:
			self.image, self.rect = self.rm.get_image(filename='data/black.png', force=False)
		if self.powertype == 1:
			self.image, self.rect = self.rm.get_image(filename='data/heart.png', force=False)
		if self.powertype == 2:
			self.image, self.rect = self.rm.get_image(filename='data/newbomb.png', force=False)
		if self.powertype == 3:
			self.image, self.rect = self.rm.get_image(filename='data/bombpwr.png', force=False)
		self.size = POWERUPSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.rect = self.image.get_rect()
		self.rect.center = pos
		self.alpha = 255
		self.image.set_alpha(self.alpha)
		self.timer = 10000
		self.timeleft = self.timer

	def update(self, items=None):
		
		# logger.debug(f'[pu] {dt - self.start_time} {self.timer}')
		self.timeleft = self.timer - (pygame.time.get_ticks() - self.start_time)
		if pygame.time.get_ticks() - self.start_time >= self.timer:
			self.kill()

	def hit(self):
		pass

class Particle(BasicThing):
	def __init__(self, pos, vel, reshandler=None):
		# super().__init__()
		self.rm = reshandler
		self.image, self.rect = self.rm.get_image(filename='data/greenorb.png', force=False)
		self.size = PARTICLESIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.alpha = 255
		self.image.set_alpha(self.alpha)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.timer = 20000
		self.hits = 0
		self.maxhits = 4
		self.angle = math.degrees(0)
		self.mass = 11
		self.vel = vel  # Vector2(random.uniform(-2, 2), random.uniform(-2, 2)) # Vector2(0, 0)

	def update(self, items=None):
		if pygame.time.get_ticks() - self.start_time >= self.timer:
			# logger.debug(f'[px] timer p:{self.pos} v:{self.vel} al:{self.alpha} dt:{self.dt} st:{self.start_time} t:{self.timer} dt-st:{self.dt - self.start_time} timechk:{self.dt - self.start_time >= self.timer} hits:{self.hits}' )
			self.kill()
			return
		if self.rect.top <= 0 or self.rect.left <= 0:
			logger.warning(f'[px] bounds p:{self.pos} v:{self.vel} al:{self.alpha} dt:{self.dt} st:{self.start_time} t:{self.timer} dt-st:{self.dt - self.start_time} timechk:{self.dt - self.start_time >= self.timer} hits:{self.hits}')
			self.kill()
			return
		# self.alpha -= random.randrange(1, 5)
		# elif self.alpha <= 0:
		# 	logger.debug(f'[px] amax p:{self.pos} v:{self.vel} al:{self.alpha} dt:{self.dt} st:{self.start_time} t:{self.timer} dt-st:{self.dt - self.start_time} timechk:{self.dt - self.start_time >= self.timer} hits:{self.hits}' )
		# 	self.kill()
		if self.hits >= self.maxhits:
			# logger.debug(f'[px] maxhits p:{self.pos} v:{self.vel} al:{self.alpha} dt:{self.dt} st:{self.start_time} t:{self.timer} dt-st:{self.dt - self.start_time} timechk:{self.dt - self.start_time >= self.timer} hits:{self.hits}' )
			self.kill()
			return
		else:
			self.image.set_alpha(self.alpha)
			self.vel -= self.accel
			# if self.vel.y>=0:
			# 	self.vel.y += self.vel.y * 0.1
			# if self.vel.y<=0:
			# 	self.vel.y -= self.vel.y * 0.1
			self.vel.y += abs(self.vel.y * 0.1) + 0.045
			self.pos += self.vel
			self.rect.x = self.pos.x
			self.rect.y = self.pos.y
		# self.vel.rotate_ip(self.hits)
		# self.alpha = int(self.alpha * 0.9)

	def hit(self):
		self.hits += 1
		self.vel = -self.vel.rotate(random.choice([45, 90, 180]))
		# self.vel.x = (self.vel.x * random.choice([-1,1])) # (self.vel.x * -1)
		# self.vel.y = (self.vel.x * random.choice([-1,1])) #(self.vel.y * -1)
		self.alpha = int(self.alpha * 0.6)


class Flame(BasicThing):
	def __init__(self, pos, vel, flame_length, reshandler):
		# super().__init__()
		self.rm = reshandler
		if vel[0] == -1 or vel[0] == 1:
			self.image, self.rect = self.rm.get_image(filename='data/flame4.png', force=False)
		elif vel[1] == -1 or vel[1] == 1:
			self.image, self.rect = self.rm.get_image(filename='data/flame3.png', force=False)
		self.image = pygame.transform.scale(self.image, FLAMESIZE)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		# dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
		self.size = FLAMESIZE
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.start_pos = Vector2(pos)
		self.vel = Vector2(vel[0], vel[1])  # flame direction
		self.timer = 20000
		self.flame_length = flame_length

	def update(self):
		self.pos += self.vel
		distance = abs(int(self.pos.distance_to(self.start_pos)))
		center = self.rect.center
		if self.vel[0] == -1 or self.vel[0] == 1:
			self.image = pygame.transform.scale(self.image, (self.size[0] + distance, self.size[1]))
		if self.vel[1] == -1 or self.vel[1] == 1:
			self.image = pygame.transform.scale(self.image, (self.size[0], self.size[1] + distance))
		self.rect = self.image.get_rect()
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.center = center
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		if distance >= self.flame_length:  # or (self.dt - self.start_time >= self.timer):
			self.kill()


class Bomb(BasicThing):
	def __init__(self, pos, bomber_id, bomb_power, reshandler=None):
		self.rm = reshandler
		self.image, self.rect = self.rm.get_image(filename='data/bomb.png', force=False)
		self.image = pygame.transform.scale(self.image, BOMBSIZE)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.bomber_id = bomber_id
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.timer = 3000
		self.bomb_size = 5
		self.explode = False
		self.exp_radius = 1
		self.done = False
		self.flame_power = bomb_power
		self.flame_len = bomb_power
		self.flame_width = 10
		self.flamesout = False
		self.flames = Group()


	def update(self):
		dt = pygame.time.get_ticks()
		if dt - self.start_time >= self.timer:
			flames = self.gen_flames()
			self.thingq.put_nowait({'flames':flames})
			self.bomber_id.bombs_left += 1
			# logger.debug(f'[bomb] flames:{len(flames)} tq:{self.thingq.qsize()}')
			# self.kill()
		# for bomb in self.bombs:
		# 	bomb.dt = pygame.time.get_ticks()
		# 	if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
		# 		self.flames.add(bomb.gen_flames())
		# 		bomb.bomber_id.bombs_left += 1
		# 		bomb.kill()

	def gen_flames(self):
		if not self.flamesout:
			self.flames = Group()
			dirs = [Vector2(-1, 0), Vector2(1, 0), Vector2(0, 1), Vector2(0, -1)]
			flex = [Flame(pos=Vector2(self.pos), vel=k, flame_length=self.flame_len, reshandler=self.rm) for k in dirs]
			for f in flex:
				self.flames.add(f)
			self.flamesout = True
		return self.flames
