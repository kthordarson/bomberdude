import os, sys
import random
import math
import hashlib
import time
import pygame
import pygame.locals as pl
from pygame.math import Vector2
from loguru import logger
# from net.bombclient import gen_randid
# from net.bombclient import UDPClient

# from pygame.colordict import THECOLORS as colordict

data_identifiers = {'info': 0, 'data': 1, 'image': 2}

DEBUG = True
DEFAULTFONT = "data/DejaVuSans.ttf"

# global constants
# GRIDSIZE[0] = 15
# GRIDSIZE[1] = 15
GRIDSIZE = (20, 20)
BLOCK = 30
BLOCKSIZE = (BLOCK, BLOCK)
PLAYERSIZE = [int(x // 1.5) for x in BLOCKSIZE]
POWERUPSIZE = [int(x // 2) for x in BLOCKSIZE]
BOMBSIZE = [int(x // 2.5) for x in BLOCKSIZE]
PARTICLESIZE = [int(x // 6) for x in BLOCKSIZE]
FLAMESIZE = [10, 5]
# FLAMESIZE = [int(x // 6) for x in BLOCKSIZE]

# POWERUPSIZE = (12, 12)
# BOMBSIZE = (16, 16)
# FLAMESIZE = (8,8)
# FLAMELENGTH = 20
# PARTICLESIZE = (3,3)
SCREENSIZE = (BLOCKSIZE[0] * (GRIDSIZE[0] + 1), BLOCKSIZE[1] * GRIDSIZE[1] + 100)
# SCREENSIZE = (700, 700)
FPS = 30
POWERUPS = {
	"bombpower": 11,
	"speedup": 12,
	"addbomb": 13,
	"healthup": 14,
}

BLOCKTYPES = {
	"0": {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "blackfloor.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"1": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "blocksprite5a.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"11": {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "black.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"2": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "blocksprite3b.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"3": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "blocksprite6.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"4": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "blocksprite3.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"5": {
		"solid": True,
		"permanent": True,
		"size": BLOCKSIZE,
		"bitmap": "blocksprite1b.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"10": {
		"solid": True,
		"permanent": True,
		"size": BLOCKSIZE,
		"bitmap": "blocksprite1.png",
		"bgbitmap": "black.png",
		"powerup": False,
	},
	"20": {
		"solid": False,
		"permanent": False,
		"size": POWERUPSIZE,
		"bitmap": "heart.png",
		"bgbitmap": "blackfloor.png",
		"powerup": True,
	},
}


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


def limit(num, minimum=1, maximum=255):
	return max(min(num, maximum), minimum)


def inside_circle(radius, pos_x, pos_y):
	x = int(radius)  # radius is the radius
	for x in range(-x, x + 1):
		y = int((radius * radius - x * x) ** 0.5)  # bound for y given x
		for y in range(-y, y + 1):
			yield x + pos_x, y + pos_y


def load_image(name, colorkey=None):
	fullname = os.path.join("data", name)
	try:
		image = pygame.image.load(fullname)
		image = image.convert()
		if colorkey is not None:
			if colorkey == -1:
				colorkey = image.get_at((0, 0))
			image.set_colorkey(colorkey)
		return image, image.get_rect()
	except FileNotFoundError as e:
		logger.debug(f"[load_image] {name} {e}")
	except pygame.error as e:
		logger.debug(f"[load_image] {name} {e}")

def dot_product(v1, v2):
	r = 0.0
	for a, b in zip(v1, v2):
		r += a * b
	return r


def scalar_product(v, n):
	return [i * n for i in v]


def normalize(v):
	m = 0.0
	for spam in v:
		m += spam ** 2.0
	m = m ** 0.5
	return [spam / m for spam in v]


class BasicThing(pygame.sprite.Sprite):
	def __init__(self, screen=None, gridpos=None, color=None, vel=Vector2(), accel=Vector2(), dt=None):
		pygame.sprite.Sprite.__init__(self)
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

	def collide(self, items=None, dt=None):
		self.collisions = pygame.sprite.spritecollide(self, items, False)
		return self.collisions

	def set_vel(self, vel):
		self.vel = vel

	def set_screen(self, screen):
		self.screen = screen


class Block(BasicThing):
	def __init__(self, gridpos=None, block_type=None, blockid=None, pos=None):
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.gridpos = gridpos
		self.block_type = block_type
		self.blockid = blockid
		self.start_time = pygame.time.get_ticks() / 1000
		self.particles = pygame.sprite.Group()
		self.start_time = pygame.time.get_ticks() / 1000
		self.explode = False
		# self.hit = False
		self.timer = 10
		self.bomb_timer = 1
		self.poweruptime = 10
		self.pos = Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
		self.gridpos = Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
		self.solid = BLOCKTYPES.get(self.block_type)["solid"]
		self.permanent = BLOCKTYPES.get(self.block_type)["permanent"]
		self.size = BLOCKTYPES.get(self.block_type)["size"]

	def init_image(self):
		self.bitmap = BLOCKTYPES.get(self.block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(self.block_type)["powerup"]
		self.image, self.rect = load_image(self.bitmap, -1)
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.image.set_alpha(255)
		self.image.set_colorkey((0, 0, 0))

	def hit(self):
		if not self.permanent:
			self.block_type = '0'
			self.solid = False
			self.image, self.rect = load_image('blackfloor.png', -1)
			self.image = pygame.transform.scale(self.image, self.size)
			self.image.set_alpha(255)
			self.image.set_colorkey((0, 0, 0))
			self.rect = self.image.get_rect(topleft=self.pos)
			self.rect.x = self.pos.x
			self.rect.y = self.pos.y
		# self.rect = self.image.get_rect()

	def get_type(self):
		return self.block_type

	def set_type(self, block_type="0"):
		pass

	def update(self, items=None):
		pass

	# if len(self.particles) <= 0:
	#   self.hit = False

	def get_particles(self):
		return self.particles

	def gen_particles(self, flame):
		# called when block is hit by a flame
		# generate particles and set initial velocity based on direction of flame impact
		self.particles = pygame.sprite.Group()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# flame.vel = Vector2(flame.vel[0], flame.vel[1])
		for k in range(1, 10):
			if flame.vel.x < 0:  # flame come from left
				self.particles.add(
					Particle(pos=flame.rect.midright, vel=random_velocity(direction="right")))  # make particle go right
			elif flame.vel.x > 0:  # right
				self.particles.add(
					Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left")))  # for k in range(1,2)]
			elif flame.vel.y > 0:  # down
				self.particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(
					direction="up")))  # flame.vel.y+random.uniform(-1.31,1.85))))   #for k in range(1,2)]
			elif flame.vel.y < 0:  # up
				self.particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(
					direction="down")))  # flame.vel.y+random.uniform(-1.31,1.85))))   #for k in range(1,2)]
		return self.particles


class Powerup(BasicThing):
	def __init__(self, pos=None, vel=None, dt=None):
		# super().__init__()
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.dt = dt
		self.image, self.rect = load_image("heart.png", -1)
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
	def __init__(self, pos=None, vel=None, dt=None):
		# super().__init__()
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.dt = dt
		self.pos = Vector2(pos)
		self.image, self.rect = load_image("greenorb.png", -1)
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

	def collide_blocks(self, blocks, dt):
		pass
# for block in blocks:
#     if self.surface_distance(block, dt) <= 0:
#         collision_vector = self.pos - block.pos
#         collision_vector.normalize()
#         logger.debug(f'{self.surface_distance(block, dt)}')
#         self.vel = self.vel.reflect(collision_vector)
#         block.vel = block.vel.reflect(collision_vector)


class Flame(BasicThing):
	def __init__(self, pos=None, vel=None, direction=None, dt=None, flame_length=None):
		# super().__init__()
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.dt = dt
		if vel[0] == -1 or vel[0] == 1:
			self.image, self.rect = load_image("flame4.png", -1)
		elif vel[1] == -1 or vel[1] == 1:
			self.image, self.rect = load_image("flame3.png", -1)
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
	def __init__(self, pos=None, bomber_id=None, bomb_power=None, dt=None):
		pygame.sprite.Sprite.__init__(self)
		BasicThing.__init__(self)
		self.dt = dt
		self.pos = pos
		self.image, self.rect = load_image("bomb.png", -1)
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
		self.flames = pygame.sprite.Group()

	def gen_flames(self):
		if not self.flamesout:
			self.flames = pygame.sprite.Group()
			dirs = [Vector2(-1, 0), Vector2(1, 0), Vector2(0, 1), Vector2(0, -1)]
			flex = [Flame(pos=Vector2(self.pos), vel=k, dt=self.dt, flame_length=self.flame_len) for k in dirs]
			for f in flex:
				self.flames.add(f)
			self.flamesout = True
		return self.flames


class Gamemap:
	def __init__(self):
		self.grid = self.generate()

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

	def place_player(self, location=0):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridgamemap
		if location == 0:  # center pos
			x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
			y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
			# x = int(x)
			self.grid[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					self.grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.debug(f"exception in place_player {block} {e}")
			return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))
		if location == 1:  # top left
			x = 5
			y = 5
			# x = int(x)
			self.grid[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					self.grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.debug(f"exception in place_player {block} {e}")
			return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))

	def get_block(self, x, y):
		# get block inf from grid
		try:
			value = self.grid[x][y]
		except IndexError as e:
			logger.debug(f"[get_block] {e} x:{x} y:{y}")
			return -1
		return value

	def get_block_real(self, x, y):
		x = x // BLOCKSIZE[0]
		y = y // BLOCKSIZE[1]
		try:
			value = self.grid[x][y]
		except IndexError as e:
			logger.debug(f"[get_block] {e} x:{x} y:{y}")
			return -1
		return value

	def set_block(self, x, y, value):
		self.grid[x][y] = value


def xxgen_randid(seed=None):
	randid = []
	for k in range(0, 7):
		n = random.randint(1, 99)
		randid.append(n)
	return randid


def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it

# class NetworkEntity():
# 	def __init__(self, identifier):
# 		super(NetworkEntity, self).__init__()
# 		self.identifier = identifier
# 		self.x = 0
# 		self.y = 0

# 	def update(self):
# 		pass

# 	def move(self, x, y):
# 		self.x += x
# 		self.y += y
class TextInputManager:
	'''
	Keeps track of text inputted, cursor position, etc.
	Pass a validator function returning if a string is valid,
	and the string will only be updated if the validator function
	returns true. 

	For example, limit input to 5 characters:
	```
	limit_5 = lambda x: len(x) <= 5
	manager = TextInputManager(validator=limit_5)
	```
	
	:param initial: The initial string
	:param validator: A function string -> bool defining valid input
	'''

	def __init__(self,
				initial = "",
				validator = lambda x: True):
		
		self.left = initial # string to the left of the cursor
		self.right = "" # string to the right of the cursor
		self.validator = validator
		

	@property
	def value(self):
		""" Get / set the value currently inputted. Doesn't change cursor position if possible."""
		return self.left + self.right
	
	@value.setter
	def value(self, value):
		cursor_pos = self.cursor_pos
		self.left = value[:cursor_pos]
		self.right = value[cursor_pos:]
	
	@property
	def cursor_pos(self):
		""" Get / set the position of the cursor. Will clamp to [0, length of input]. """
		return len(self.left)

	@cursor_pos.setter
	def cursor_pos(self, value):
		complete = self.value
		self.left = complete[:value]
		self.right = complete[value:]
	
	def update(self, events):
		"""
		Update the interal state with fresh pygame events.
		Call this every frame with all events returned by `pygame.event.get()`.
		"""
		for event in events:
			if event.type == pl.KEYDOWN:
				v_before = self.value
				c_before = self.cursor_pos
				self._process_keydown(event)
				if not self.validator(self.value):
					self.value = v_before
					self.cursor_pos = c_before

	def _process_keydown(self, ev):
		attrname = f"_process_{pygame.key.name(ev.key)}"
		if hasattr(self, attrname):
			getattr(self, attrname)()
		else:
			self._process_other(ev)

	def _process_delete(self):
		self.right = self.right[1:]
	
	def _process_backspace(self):
		self.left = self.left[:-1]
	
	def _process_right(self):
		self.cursor_pos += 1
	
	def _process_left(self):
		self.cursor_pos -= 1

	def _process_end(self):
		self.cursor_pos = len(self.value)
	
	def _process_home(self):
		self.cursor_pos = 0
	
	def _process_return(self):
		pass

	def _process_other(self, event):
		self.left += event.unicode

class TextInputVisualizer:
	"""
	Utility class to quickly visualize textual input, like a message or username.
	Pass events every frame to the `.update` method, then get the surface
	of the rendered font using the `.surface` attribute.

	All arguments of constructor can also be set via attributes, so e.g.
	to change `font_color` do
	```
	inputVisualizer.font_color = (255, 100, 0)
	```
	The surface itself is lazily re-rendered only when the `.surface` field is 
	accessed, and if any parameters changed since the last `.surface` access, so
	values can freely be changed between renders without performance overhead.

	:param manager: The TextInputManager used to manage the user input
	:param font_object: a pygame.font.Font object used for rendering
	:param antialias: whether to render the font antialiased or not
	:param font_color: color of font rendered
	:param cursor_blink_interal: the interval of the cursor blinking, in ms
	:param cursor_width: The width of the cursor, in pixels
	:param cursor_color: The color of the cursor
	"""
	def __init__(self,
			screen = None,
			manager = None,
			font_object = None,
			antialias = True,
			font_color = (0, 0, 0),
			cursor_blink_interval = 300,
			cursor_width = 3,
			cursor_color = (0, 0, 0)
			):
		self.screen = screen
		self._manager = TextInputManager() if manager is None else manager
		self._font_object = pygame.font.Font(pygame.font.get_default_font(), 25) if font_object is None else font_object
		self._antialias = antialias
		self._font_color = font_color
		
		self._clock = pygame.time.Clock()
		self._cursor_blink_interval = cursor_blink_interval
		self._cursor_visible = False
		self._last_blink_toggle = 0

		self._cursor_width = cursor_width
		self._cursor_color = cursor_color

		self._surface = pygame.Surface((self._cursor_width, self._font_object.get_height()))
		self._rerender_required = True
	
	@property
	def value(self):
		""" Get / set the value of text alreay inputted. Doesn't change cursor position if possible."""
		return self.manager.value
	
	@value.setter
	def value(self, v):
		self.manager.value = v
	
	@property
	def manager(self):
		""" Get / set the underlying `TextInputManager` for this instance"""
		return self._manager
	
	@manager.setter
	def manager(self, v):
		self._manager = v
	
	@property
	def surface(self):
		""" Get the surface with the rendered user input """
		if self._rerender_required:
			self._rerender()
			self._rerender_required = False
		return self._surface
	
	@property
	def antialias(self):
		""" Get / set antialias of the render """
		return self._antialias

	@antialias.setter
	def antialias(self, v):
		self._antialias = v
		self._require_rerender()

	@property
	def font_color(self):
		""" Get / set color of rendered font """
		return self._font_color

	@font_color.setter
	def font_color(self, v):
		self._font_color = v
		self._require_rerender()

	@property
	def font_object(self):
		""" Get / set the font object used to render the text """
		return self._font_object

	@font_object.setter
	def font_object(self, v):
		self._font_object = v
		self._require_rerender()

	@property
	def cursor_visible(self):
		""" Get / set cursor visibility (flips again after `.cursor_interval` if continuously update)"""
		return self._cursor_visible
	
	@cursor_visible.setter
	def cursor_visible(self, v):
		self._cursor_visible = v
		self._last_blink_toggle = 0
		self._require_rerender()
	
	@property
	def cursor_width(self):
		""" Get / set width in pixels of the cursor """
		return self._cursor_width
	
	@cursor_width.setter
	def cursor_width(self, v):
		self._cursor_width = v
		self._require_rerender()
	
	@property
	def cursor_color(self):
		""" Get / set the color of the cursor """
		return self._cursor_color
	
	@cursor_color.setter
	def cursor_color(self, v):
		self._cursor_color = v
		self._require_rerender()

	@property
	def cursor_blink_interval(self):
		""" Get / set the interval of time with which the cursor blinks (toggles), in ms"""
		return self._cursor_blink_interval
	
	@cursor_blink_interval.setter
	def cursor_blink_interval(self, v):
		self._cursor_blink_interval = v

	def draw(self, screen):
		screen.blit(self.surface, (100, 300))

	def update(self, events: pygame.event.Event):
		"""
		Update internal state.
		
		Call this once every frame with all events returned by `pygame.event.get()`
		"""

		# Update self.manager internal state, rerender if value changes
		value_before = self.manager.value
		self.manager.update(events)
		if self.manager.value != value_before:
			self._require_rerender()

		# Update cursor visibility after self._blink_interval milliseconds
		self._clock.tick()
		self._last_blink_toggle += self._clock.get_time()
		if self._last_blink_toggle > self._cursor_blink_interval:
			self._last_blink_toggle %= self._cursor_blink_interval
			self._cursor_visible = not self._cursor_visible

			self._require_rerender()

		# Make cursor visible when something is pressed
		if [event for event in events if event.type == pl.KEYDOWN]:
			self._last_blink_toggle = 0
			self._cursor_visible = True
			self._require_rerender()


	def _require_rerender(self):
		"""
		Trigger a re-render of the surface the next time the surface is accessed.
		"""
		self._rerender_required = True

	def _rerender(self):
		""" Rerender self._surface."""
		# Final surface is slightly larger than font_render itself, to accomodate for cursor
		rendered_surface = self.font_object.render(self.manager.value + " ",
												self.antialias,
												self.font_color)
		w, h = rendered_surface.get_size()
		self._surface = pygame.Surface((w + self._cursor_width, h))
		self._surface = self._surface.convert_alpha(rendered_surface)
		self._surface.fill((0, 0, 0, 0))
		self._surface.blit(rendered_surface, (0, 0))
		
		if self._cursor_visible:
			str_left_of_cursor = self.manager.value[:self.manager.cursor_pos]
			cursor_y = self.font_object.size(str_left_of_cursor)[0]
			cursor_rect = pygame.Rect(cursor_y, 0, self._cursor_width, self.font_object.get_height())
			self._surface.fill(self._cursor_color, cursor_rect)


def check_threads(threads):
	return True in [t.is_alive() for t in threads]


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
