import hashlib
import math
import os
import random
import sys
import time
from threading import Thread, Event

import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import *

def random_velocity(direction=None):
	while True:
		vel = Vector2(
			(random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0))
		)
		if direction == "left":
			vel.x = random.uniform(-3.0, 0.3)
		if direction == "right":
			vel.x = random.uniform(0.3, 3.0)
		if direction == "down":
			vel.y = random.uniform(0.3, 3.0)
		if direction == "up":
			vel.y = random.uniform(-3.0, 0.3)
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


def inside_circle(radius, pos_x, pos_y):
	x = int(radius)  # radius is the radius
	for x in range(-x, x + 1):
		y = int((radius * radius - x * x) ** 0.5)  # bound for y given x
		for y in range(-y, y + 1):
			yield x + pos_x, y + pos_y


def load_image(name, colorkey=None):
	fullname = os.path.join("data", name)
	image = pygame.image.load(fullname)
	#image = image.convert()
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
	
	def has_image(self, filename=None):
		return filename in self.__images

	def set_image_path(self, imgpath=None):
		self.__imgpath = imgpath

	def get_image_path(self):
		return self.__imgpath

class BasicThing(Sprite):
	def __init__(self, screen=None, gridpos=None, color=None, vel=Vector2(), accel=Vector2(), dt=None, pos=Vector2()):
		Sprite.__init__(self)
		self.pos = pos
		self.color = color
		self.screen = screen
		self.vel = vel
		self.dt = dt
		self.accel = accel
		self.mass = 3
		self.radius = 3
		self.gridpos = gridpos
		# self.size = BLOCKSIZE
		# self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.collisions = []
		self.start_time = pygame.time.get_ticks() / 1000
		# self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.thing_id = ''.join([''.join(str(random.randint(0, 99))) for k in range(10)])

	# def __str__(self):
	# 	return self.thing_id

	# def __repr__(self):
	# 	return self.thing_id

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions

	def set_vel(self, vel):
		self.vel = vel

	def set_screen(self, screen):
		self.screen = screen


class Block(BasicThing):
	def __init__(self, gridpos=None, block_type=None, blockid=None, pos=None, reshandler=None):
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.pos = pos
		self.gridpos = gridpos
		self.block_type = block_type
		self.blockid = blockid
		self.start_time = pygame.time.get_ticks() / 1000
		self.particles = Group()
		self.start_time = pygame.time.get_ticks() / 1000
		self.explode = False
		# self.hit = False
		self.timer = 10
		self.bomb_timer = 1
		self.poweruptime = 10
		self.gridpos = Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
		# self.pos = Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
		self.solid = BLOCKTYPES.get(self.block_type)["solid"]
		self.permanent = BLOCKTYPES.get(self.block_type)["permanent"]
		self.size = BLOCKTYPES.get(self.block_type)["size"]
		self.bitmap = BLOCKTYPES.get(self.block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(self.block_type)["powerup"]
		self.rm = reshandler
		self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.image.set_alpha(255)
		self.image.set_colorkey((0, 0, 0))

	def init_image(self):
		pass

	def hit(self):
		if not self.permanent:
			self.block_type = 0
			self.solid = False
			self.image.set_alpha(255)
			self.image.set_colorkey((0, 0, 0))
			self.rect = self.image.get_rect(topleft=self.pos)
			self.rect.x = self.pos.x
			self.rect.y = self.pos.y


	def get_particles(self):
		return self.particles

	def gen_particles(self, flame):
		# called when block is hit by a flame
		# generate particles and set initial velocity based on direction of flame impact
		self.particles = Group()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# flame.vel = Vector2(flame.vel[0], flame.vel[1])
		for k in range(1, 10):
			if flame.vel.x < 0:  # flame come from left
				self.particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right"), reshandler=self.rm))  # make particle go right
			elif flame.vel.x > 0:  # right
				self.particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left"), reshandler=self.rm))  # for k in range(1,2)]
			elif flame.vel.y > 0:  # down
				self.particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up"), reshandler=self.rm))  # flame.vel.y+random.uniform(-1.31,1.85))))   #for k in range(1,2)]
			elif flame.vel.y < 0:  # up
				self.particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down"), reshandler=self.rm))  # flame.vel.y+random.uniform(-1.31,1.85))))   #for k in range(1,2)]
		return self.particles


class Powerup(BasicThing):
	def __init__(self, pos=None, vel=None, dt=None, reshandler=None):
		# super().__init__()
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.rm = reshandler
		self.dt = dt
		self.image, self.rect = self.rm.get_image(filename='data/heart.png', force=False)
		self.size = POWERUPSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.rect.center = pos
		self.pos = Vector2(pos)
		self.alpha = 255
		self.image.set_alpha(self.alpha)
		self.timer = 5
		self.start_time = pygame.time.get_ticks() / 1000

	def update(self, items=None):
		self.dt = pygame.time.get_ticks() / 1000
		# logger.debug(f'[pu] {dt  - self.start_time} {self.timer}')
		if self.dt - self.start_time >= self.timer:
			self.kill()


class Particle(BasicThing):
	def __init__(self, pos=None, vel=None, dt=None, reshandler=None):
		# super().__init__()
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.rm = reshandler
		self.dt = dt
		self.pos = Vector2(pos)
		self.image, self.rect = self.rm.get_image(filename='data/greenorb.png', force=False)
		self.size = PARTICLESIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.alpha = 255
		self.image.set_alpha(self.alpha)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.start_time = 1  # pygame.time.get_ticks() // 1000
		self.timer = 10
		self.hits = 0
		self.maxhits = 10
		self.start_time = pygame.time.get_ticks() / 1000
		self.angle = math.degrees(0)
		self.mass = 11
		self.vel = vel  # Vector2(random.uniform(-2, 2), random.uniform(-2, 2))  # Vector2(0, 0)

	# self.accel = Vector2(0.05,0.05)

	def stop(self):
		logger.debug(f"[stop] {self.vel}")
		self.vel = Vector2(0, 0)
		logger.debug(f"[stop] {self.vel}")

	def move(self):
		logger.debug(f"[move] {self.vel}")

	def update(self, items=None):
		self.dt = pygame.time.get_ticks() / 1000
		if self.dt - self.start_time >= self.timer:
			self.kill()
		if self.rect.top <= 0 or self.rect.left <= 0:
			self.kill()
		self.alpha -= random.randrange(1, 5)
		if self.alpha <= 0:
			self.kill()
		else:
			self.image.set_alpha(self.alpha)
		self.vel -= self.accel
		self.pos += self.vel
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y


# for block in blocks:
#     if self.surface_distance(block, dt) <= 0:
#         collision_vector = self.pos - block.pos
#         collision_vector.normalize()
#         logger.debug(f'{self.surface_distance(block, dt)}')
#         self.vel = self.vel.reflect(collision_vector)
#         block.vel = block.vel.reflect(collision_vector)


class Flame(BasicThing):
	def __init__(self, pos=None, vel=None, direction=None, dt=None, flame_length=None, reshandler=None):
		# super().__init__()
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.rm = reshandler
		self.dt = dt
		if vel[0] == -1 or vel[0] == 1:
			self.image, self.rect = self.rm.get_image(filename='data/flame4.png', force=False)
		elif vel[1] == -1 or vel[1] == 1:
			self.image, self.rect = self.rm.get_image(filename='data/flame3.png', force=False)
		self.image = pygame.transform.scale(self.image, FLAMESIZE)
		# dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
		self.size = FLAMESIZE
		self.pos = Vector2(pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.start_pos = Vector2(pos)
		self.vel = Vector2(vel[0], vel[1])  # flame direction
		self.timer = 10
		self.start_time = pygame.time.get_ticks() / 1000
		self.flame_length = flame_length
		self.stopped = False

	def check_time(self):
		pass

	def stop(self):
		self.vel = Vector2((0, 0))
		self.stopped = True
		self.kill()

	def draw(self, screen):
		screen.blit(self.image, self.pos)

	def update(self):
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
			# logger.debug(f'{self.pos.x} {self.start_pos.x} {self.pos.distance_to(self.start_pos)}')
			if distance >= self.flame_length:  # or (self.dt - self.start_time >= self.timer):
				# logger.debug(f'[flame] dist {distance} max {self.flame_length}')
				self.kill()
			if self.dt - self.start_time >= self.timer:
				pass
	# logger.debug(f'[flame] time {self.dt - self.start_time} >= {self.timer}')
	# self.kill()


class Bomb(BasicThing):
	def __init__(self, pos=None, bomber_id=None, bomb_power=None, dt=None, reshandler=None):
		Sprite.__init__(self)
		BasicThing.__init__(self)
		self.rm = reshandler
		self.dt = dt
		self.pos = pos
		self.image, self.rect = self.rm.get_image(filename='data/bomb.png', force=False)
		self.image = pygame.transform.scale(self.image, BOMBSIZE)
		# self.gridpos = gridpos
		self.bomber_id = bomber_id
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.start_time = pygame.time.get_ticks() / 1000
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

	def gen_flames(self):
		if not self.flamesout:
			self.flames = Group()
			dirs = [Vector2(-1, 0), Vector2(1, 0), Vector2(0, 1), Vector2(0, -1)]
			flex = [Flame(pos=Vector2(self.pos), vel=k, dt=self.dt, flame_length=self.flame_len, reshandler=self.rm) for k in dirs]
			for f in flex:
				self.flames.add(f)
			self.flamesout = True
		return self.flames


class Gamemap:
	def __init__(self, genmap=True):
		self.grid = self.generate()
		#self.clear_center()

	# @staticmethod
	def generate(self):
		grid = [[random.randint(0, 5) for k in range(GRIDSIZE[1] + 1)] for j in range(GRIDSIZE[0] + 1)]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(GRIDSIZE[0] + 1):
			grid[x][0] = 10
			grid[x][GRIDSIZE[1]] = 10
		for y in range(GRIDSIZE[1] + 1):
			grid[0][y] = 10
			grid[GRIDSIZE[0]][y] = 10
		return grid

	def clear_center(self):
		x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
		y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
		# x = int(x)
		self.grid[x][y] = 0
		# make a clear radius around spawn point
		for block in list(inside_circle(3, x, y)):
			self.grid[block[0]][block[1]] = 0
		# return grid

	def place_player(self, grid, location=0):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridgamemap
		if location == 0:  # center pos
			x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
			y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
			# x = int(x)
			grid[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.error(f"exception in place_player {block} {e}")
			return grid
		# return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))
		if location == 1:  # top left
			x = 5
			y = 5
			# x = int(x)
			grid[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.error(f"exception in place_player {block} {e}")
			return grid

	# return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))

	def get_block(self, x, y):
		# get block inf from grid
		try:
			value = self.grid[x][y]
		except IndexError as e:
			logger.error(f"[get_block] {e} x:{x} y:{y}")
			return -1
		return value

	def get_block_real(self, x, y):
		x = x // BLOCKSIZE[0]
		y = y // BLOCKSIZE[1]
		try:
			value = self.grid[x][y]
		except IndexError as e:
			logger.error(f"[get_block] {e} x:{x} y:{y}")
			return -1
		return value

	def set_block(self, x, y, value):
		self.grid[x][y] = value
	
	def set_grid(self, newgrid):
		logger.debug(f'[map] setting newgrid')
		self.grid = newgrid


def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


def stop_all_threads(threads):
	logger.debug(f'stopping {threads}')
	for t in threads:
		logger.debug(f'waiting for {t}')
		t.kill = True
		t.join(1)
	sys.exit()


def start_all_threads(threads):
	logger.debug(f'starting {threads}')
	for t in threads:
		logger.debug(f'start {t}')
		t.run()


class StoppableThread(Thread):
	"""Thread class with a stop() method. The thread itself has to check
	regularly for the stopped() condition."""

	def __init__(self, name=None, *args, **kwargs):
		super(StoppableThread, self).__init__(*args, **kwargs)
		self._stop_event = Event()
		self.name = name
		logger.debug(f'{self.name} init ')

	def stop(self):
		logger.debug(f'{self.name} stop event')
		self._stop_event.set()

	def stopped(self):
		# logger.debug(f'{self.name} stopped check')
		return self._stop_event.is_set()

	def join(self, timeout=None):
		logger.debug(f'{self.name} join')
		self._stop_event.set()
		Thread.join(self, timeout=timeout)
