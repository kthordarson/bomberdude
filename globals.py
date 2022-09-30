import hashlib
import math
import os
import random
import sys
import time
from threading import Thread, Event, Event
# from multiprocessing import Queue
import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, GRIDSIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID, MAXPARTICLES


def random_velocity(direction=None):
	while True:
		vel = Vector2((random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0)))
		if direction == "left":
			vel.x = random.uniform(-3.0, -1)
		if direction == "right":
			vel.x = random.uniform(1, 3.0)
		if direction == "down":
			vel.y = random.uniform(1, 3.0)
		if direction == "up":
			vel.y = random.uniform(-3.0, -1)
		if vel.y != 0 and vel.x != 0:
			return vel
		else:
			logger.debug(f"[vel] {vel}")


def rot_center(image, rect, angle):
	"""rotate an image while keeping its center"""
	rot_image = pygame.transform.rotate(image, angle)
	rot_rect = rot_image.get_rect(center=rect.center)
	return rot_image, rot_rect


def get_entity_angle(e_1, e_2):
	dif_x = e_2.x - e_1.x
	dif_y = e_2.y - e_1.y
	return math.atan2(dif_y, dif_x)


def get_angle(pos_1, pos_2):
	dif_x = pos_2[0] - pos_1[0]
	dif_y = pos_2[1] - pos_1[1]
	return math.atan2(dif_y, dif_x)




def load_image(name, colorkey=None):
	fullname = os.path.join("data", name)
	image = pygame.image.load(fullname)
	# image = image.convert()
	return image, image.get_rect()


class ResourceHandler:
	def __init__(self):
		self.name = 'ResourceHandler'
		self.__images = {}

	def get_image(self, filename=None, force=False):
		if force or filename not in list(self.__images.keys()):
			img = pygame.image.load(filename)
			rect = img.get_rect()
			self.__images[filename] = (img, rect)
			return img, rect
		else:
			return self.__images[filename]


def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


def stop_all_threads(threads):
	logger.debug(f'stopping {threads}')
	for t in threads:
		logger.debug(f'waiting for {t}')
		t.kill = True
		t.join(0)
	sys.exit()


def start_all_threads(threads):
	logger.debug(f'starting {threads}')
	for t in threads:
		logger.debug(f'start {t}')
		t.run()

class BasicThing(Sprite):
	rm = ResourceHandler()
	def __init__(self, pos, image=None):
		Sprite.__init__(self)
		# self.thingq = OldQueue() # multiprocessing.Manager().Queue()		
		self.pos = Vector2(pos)
		self.vel = Vector2()
		self.start_time = pygame.time.get_ticks()
		self.image = image
		self.accel = Vector2(0, 0)

	def __str__(self):
		return f'[basic] {self.pos}'

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions

class Block(BasicThing):
	def __init__(self, pos, gridpos, block_type):		
		BasicThing.__init__(self, pos, None)
		self.block_type = block_type
		self.solid = BLOCKTYPES.get(self.block_type)["solid"]
		self.permanent = BLOCKTYPES.get(self.block_type)["permanent"]
		self.size = BLOCKTYPES.get(self.block_type)["size"]
		self.bitmap = BLOCKTYPES.get(self.block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(self.block_type)["powerup"]
		
		self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)
		self.explode = False
		self.poweruptime = 10
		self.gridpos = gridpos  # Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.image.set_alpha(255)
		self.image.set_colorkey((0, 0, 0))

	def __str__(self):
		return f'[block] {self.pos}'

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
					particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right")))  # make particle go right
				elif flame.vel.x > 0:  # right
					particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left")))  # for k in range(1,2)]
				elif flame.vel.y > 0:  # down
					particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up")))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
				elif flame.vel.y < 0:  # up
					particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down")))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
			if self.powerup:
				powerblock = Powerup(pos=self.rect.center)
			newblock = Block(self.pos, self.gridpos, block_type=0)
			flame.kill()
			self.kill()
		return self.pos, self.gridpos, particles, newblock, powerblock

	def gen_particles(self, flame):
		# called when block is hit by a flame
		# generate particles and set initial velocity based on direction of flame impact
		#self.particles = Group()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# flame.vel = Vector2(flame.vel[0], flame.vel[1])
		particles = Group()
		for k in range(1, 10):
			if flame.vel.x < 0: # flame come from left
				particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right"))) # make particle go right
			elif flame.vel.x > 0: # right
				particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left"))) # for k in range(1,2)]
			elif flame.vel.y > 0: # down
				particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up"))) # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
			elif flame.vel.y < 0: # up
				particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down"))) # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
		return particles

class Powerup(BasicThing):
	def __init__(self, pos):
		# super().__init__()
		self.powertype = random.choice([1,2,3])
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
		self.timer = 5
		self.start_time = pygame.time.get_ticks() / 1000

	def update(self, items=None):
		self.dt = pygame.time.get_ticks() / 1000
		# logger.debug(f'[pu] {dt - self.start_time} {self.timer}')
		if self.dt - self.start_time >= self.timer:
			self.kill()

class Bomb(BasicThing):
	def __init__(self, pos, bomber_id, bomb_power=20):
		self.image, self.rect = self.rm.get_image(filename='data/bomb.png', force=False)
		self.image = pygame.transform.scale(self.image, BOMBSIZE)
		self.pos = pos
		BasicThing.__init__(self, self.pos, self.image)
		self.bomber_id = bomber_id
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.start_time = pygame.time.get_ticks() / 1000
		self.timer = 3000
		self.bomb_timer = 1
		self.bomb_fuse = 1
		self.bomb_end = 2
		self.bomb_size = 5
		self.explode = False
		self.exp_radius = 1
		self.done = False
		self.flame_power = bomb_power
		self.flame_len = bomb_power
		self.flame_width = 10
		self.flamesout = False
		self.flames = Group()

	def __str__(self):
		return f'[bomb] {self.pos}'

	def gen_flames(self):
		if not self.flamesout:
			self.flames = Group()
			dirs = [Vector2(-1, 0), Vector2(1, 0), Vector2(0, 1), Vector2(0, -1)]
			flex = [Flame(pos=Vector2(self.pos), vel=k, flame_length=self.flame_len) for k in dirs]
			for f in flex:
				self.flames.add(f)
			self.flamesout = True
		return self.flames

	def exploder(self):
		flames = Group()
		flames.add(Flame(pos=self.pos, vel=Vector2(1,0), flame_length=self.flame_len, rect=self.rect))
		flames.add(Flame(pos=self.pos, vel=Vector2(-1,0), flame_length=self.flame_len, rect=self.rect))
		flames.add(Flame(pos=self.pos, vel=Vector2(0,-1), flame_length=self.flame_len, rect=self.rect))
		flames.add(Flame(pos=self.pos, vel=Vector2(0,1), flame_length=self.flame_len, rect=self.rect))
		# self.bomber_id.bombs_left += 1
		return flames

class Particle(BasicThing):
	def __init__(self, pos, vel):
		# super().__init__()
		#self.image, self.rect = self.rm.get_image(filename='data/greenorb.png', force=False)
		self.pos = pos
		xsize = random.randint(1,3)
		ysize = random.randint(1,3)
		self.image = pygame.Surface((xsize ,ysize))
		BasicThing.__init__(self, self.pos, self.image)
		self.image.fill((95, 95, 95))
		#self.image.fill((random.randint(0,255),random.randint(0,255),random.randint(0,255)))
		self.rect = self.image.get_rect(center = pos)
		self.size = PARTICLESIZE
		#self.image = pygame.transform.scale(self.image, self.size)
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
	def __init__(self, pos, vel, flame_length, rect):
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

	def xxupdate(self):
		if not self.stopped:
			self.dt = pygame.time.get_ticks() / 1000
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
			if distance >= self.flame_length: # or (self.dt - self.start_time >= self.timer):
				self.kill()
			if self.dt - self.start_time >= self.timer:
				pass
