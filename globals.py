import hashlib
import math
import os
import random
import sys
import time
from threading import Thread, Event, Event
from queue import Queue, Empty
import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, GRIDSIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID


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


def inside_circle(radius, pos_x, pos_y):
	x = int(radius)  # radius is the radius
	for x in range(-x, x + 1):
		y = int((radius * radius - x * x) ** 0.5)  # bound for y given x
		for y in range(-y, y + 1):
			yield x + pos_x, y + pos_y


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


class BasicThing(Sprite):
	def __init__(self, pos, image):
		Sprite.__init__(self)
		self.pos = Vector2(pos)
		self.image = image
		self.collisions = []
		self.start_time = pygame.time.get_ticks() / 1000
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
		self.start_time = pygame.time.get_ticks() / 1000
		self.start_time = pygame.time.get_ticks() / 1000
		self.explode = False
		self.bomb_timer = 1
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
		self.timer = 5
		self.time_left = self.timer
		self.start_time = pygame.time.get_ticks() / 1000

	# self.dt = pygame.time.get_ticks() / 1000

	def update(self, items=None):
		dt = pygame.time.get_ticks() / 1000
		# logger.debug(f'[pu] {dt - self.start_time} {self.timer}')
		self.time_left = dt - self.start_time
		if dt - self.start_time >= self.timer:
			self.kill()

	def hit(self):
		pass
	# self.bitmap = BLOCKTYPES.get(11)["bitmap"]
	# self.solid = False
	# self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)


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
		self.start_time = 1  # pygame.time.get_ticks() // 1000
		self.timer = 20
		self.hits = 0
		self.maxhits = 4
		self.start_time = pygame.time.get_ticks() / 1000
		self.angle = math.degrees(0)
		self.mass = 11
		self.vel = vel  # Vector2(random.uniform(-2, 2), random.uniform(-2, 2)) # Vector2(0, 0)

	def update(self, items=None):
		self.dt = pygame.time.get_ticks() / 1000
		if self.dt - self.start_time >= self.timer:
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
		self.timer = 10
		self.start_time = pygame.time.get_ticks() / 1000
		self.flame_length = flame_length

	def update(self):
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
		if distance >= self.flame_length:  # or (self.dt - self.start_time >= self.timer):
			self.kill()
		if self.dt - self.start_time >= self.timer:
			pass


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
			flex = [Flame(pos=Vector2(self.pos), vel=k, flame_length=self.flame_len, reshandler=self.rm) for k in dirs]
			for f in flex:
				self.flames.add(f)
			self.flamesout = True
		return self.flames


class Gamemap:
	def __init__(self, genmap=True):
		if genmap:
			self.grid = self.generate()
		else:
			self.grid = DEFAULTGRID

	def generate(self):
		grid = [[random.randint(0, 5) for k in range(GRIDSIZE[1])] for j in range(GRIDSIZE[0])]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(GRIDSIZE[0]):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
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
		if len(grid) == 0:
			logger.error(f'[place_player] grid is empty')
			return None
		if location == 0:  # center pos
			x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
			y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
			# x = int(x)
			try:
				grid[x][y] = 0
			except IndexError as e:
				logger.error(f'IndexError {e} x:{x} y:{y} gz:{GRIDSIZE} g:{type(grid)} {len(grid)}')
				return None
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.error(f"[e] place_player {block} {e}")
					return None
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
					logger.error(f"[e] place_player {block} {e}")
					return None
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
		t.join(0)
	sys.exit()


def start_all_threads(threads):
	logger.debug(f'starting {threads}')
	for t in threads:
		logger.debug(f'start {t}')
		t.run()


def empty_queue(queue_to_empty: Queue):
	logger.debug(f'[queue_to_empty] start q:{queue_to_empty.name} qs:{queue_to_empty.qsize()}')
	while queue_to_empty.qsize() != 0:
		try:
			with queue_to_empty.mutex:
				queue_to_empty.queue.clear()
			# queue_to_empty.all_tasks_done()
			# queue_to_empty.get_nowait()
			# queue_to_empty.task_done()
			logger.debug(f'[queue_to_empty] q:{queue_to_empty.name} qs:{queue_to_empty.qsize()}')
		except Empty as e:
			logger.error(f'[queue_to_empty] empty:{e} q:{queue_to_empty} qs:{queue_to_empty.qsize()}')
		except ValueError as e:
			logger.error(f'[queue_to_empty] error:{e} q:{queue_to_empty} qs:{queue_to_empty.qsize()}')
