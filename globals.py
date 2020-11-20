import random
import math
import pygame
import os
from pygame.colordict import THECOLORS as colordict


DEBUG = True

# global constants
#GRIDSIZE[0] = 15
#GRIDSIZE[1] = 15
GRIDSIZE = (20, 20)
BLOCKSIZE = (32, 32)
POWERUPSIZE = (12, 12)
BOMBSIZE = (16, 16)
PLAYERSIZE = (16,16)
FLAMESIZE = (8,8)
FLAMELENGTH = 20
PARTICLESIZE = (2,2)
SCREENSIZE = (BLOCKSIZE[0] * (GRIDSIZE[0] + 1), BLOCKSIZE[1] * GRIDSIZE[1] + 100)
#SCREENSIZE = (700, 700)
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
		"bitmap": 'black.png',
		"powerup": False,
	},
	"1": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'darkSkyBlock1.png',
		"powerup": False,
	},
	"11": {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'black.png',
		"powerup": False,
	},
	"2": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'darkSkyBlock2.png',
		"powerup": False,
	},
	"3": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'darkSkyBlock1.png',
		"powerup": False,
	},
	"4": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'darkSkyBlock2.png',
		"powerup": False,
	},
	"10": {
		"solid": True,
		"permanent": True,
		"size": BLOCKSIZE,
		"bitmap": 'blocksprite2.png',
		"powerup": False,
	},
	"20": {
		"solid": False,
		"permanent": False,
		"size": POWERUPSIZE,
		"bitmap": 'heart.png',
		"powerup": True,
	},
}

def random_velocity():
	vel = pygame.math.Vector2((random.uniform(-2,2),random.uniform(-2,2)))
	return vel
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


def inside_circle(R, pos_x, pos_y):
	X = int(R)  # R is the radius
	for x in range(-X, X + 1):
		Y = int((R * R - x * x)**0.5)  # bound for y given x
		for y in range(-Y, Y + 1):
			yield (x + pos_x, y + pos_y)

def load_image(name, colorkey=None):
	fullname = os.path.join('data', name)
	try:
		image = pygame.image.load(fullname)
		image = image.convert()
		if colorkey is not None:
			if colorkey == -1:
				colorkey = image.get_at((0, 0))
			image.set_colorkey(colorkey)
		return image, image.get_rect()
	except FileNotFoundError as e:
		print(f'[load_image] {name} {e}')

class BasicThing(pygame.sprite.Sprite):
	def __init__(self, screen=None, gridpos=None, color=None):
		pygame.sprite.Sprite.__init__(self)
		self.screen = screen
		self.vel = pygame.math.Vector2((0,0))
		self.accel = pygame.math.Vector2((0,0))
		self.gridpos = gridpos
		# self.size = BLOCKSIZE
		self.font = pygame.freetype.Font("DejaVuSans.ttf", 12)
		self.font_color = (255, 255, 255)
		self.collisions = []
		self.collision_types = {'top':False,'bottom':False,'right':False,'left':False,'slant_bottom':False,'data':[]}
		self.start_time = pygame.time.get_ticks() / 1000

	def collide(self, items):
		self.collisions = pygame.sprite.spritecollide(self, items, False)
		return self.collisions

	def set_screen(self,screen):
		self.screen = screen
class Block(BasicThing):
	def __init__(self, gridpos=None, block_type=None, blockid=None, pos=None):
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.gridpos = gridpos
		self.block_type = block_type
		self.blockid = blockid
		self.set_type(block_type)
		self.particles = pygame.sprite.Group()
		self.start_time = pygame.time.get_ticks() / 1000

	def get_type(self):
		return self.block_type

	def set_type(self, block_type='0'):
		self.start_time = pygame.time.get_ticks() / 1000
		self.explode = False
		self.hit = False
		self.timer = 10
		self.bomb_timer = 1
		self.poweruptime = 10
		# self.particles = pygame.sprite.Group()
		self.pos = pygame.math.Vector2((BLOCKSIZE[0]*self.gridpos[0], BLOCKSIZE[1]*self.gridpos[1]))
		self.gridpos = pygame.math.Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
		self.solid = BLOCKTYPES.get(block_type)["solid"]
		self.permanent = BLOCKTYPES.get(block_type)["permanent"]
		self.size = BLOCKTYPES.get(block_type)["size"]
		self.bitmap = BLOCKTYPES.get(block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(block_type)["powerup"]
		self.image, self.rect = load_image(self.bitmap, -1)
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# self.gridpos = pygame.math.Vector2((self.rect.x // BLOCKSIZE[0], self.rect.y // BLOCKSIZE[1]))
		#self.rect.x = self.gridpos.x
		#self.rect.y = self.gridpos.y
		self.image.set_alpha(100)
		self.image.set_colorkey((0,0,0))
		# print(f'[set_type] t:{block_type} ')

	def update(self):
		#if self.hit:
		#	[particle.update() for particle in self.particles]
		# self.pos = pygame.math.Vector2(self.rect.x, self.rect.y)
		if self.powerup:
			self.dt = pygame.time.get_ticks() / 1000
			if self.dt - self.start_time >= self.poweruptime:
				# print(f'pt:{self.dt} t:{self.poweruptime} t:{self.start_time-self.dt} ')
				self.set_type('0')
				self.powerup = False

#		self.gridpos = pygame.math.Vector2((self.rect.x // BLOCKSIZE[0], self.rect.y // BLOCKSIZE[1]))
	def get_particles(self):
		return self.particles

	def take_damage(self, item):
		self.hit = True
		item.vel = pygame.math.Vector2(item.vel[0], item.vel[1])
		if item.direction == 'left':
			pos = (self.rect.midright)
			[self.particles.add(Particle(pos=pos, direction=item.direction)) for k in range(5,10)]
		if item.direction == 'right':
			pos = self.rect.midleft
			[self.particles.add(Particle(pos=pos, direction=item.direction)) for k in range(5,10)]
		if item.direction == 'up':
			pos = self.rect.midbottom
			[self.particles.add(Particle(pos=pos, direction=item.direction)) for k in range(5,10)]
		if item.direction == 'down':
			pos = self.rect.midtop
			[self.particles.add(Particle(pos=pos, direction=item.direction)) for k in range(5,10)]


class Particle(BasicThing):
	def __init__(self, pos=None, vel=None, direction=None):
		# super().__init__()
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.direction = direction
		self.pos = pygame.math.Vector2(pos)
		self.image, self.rect = load_image('greenorb.png', -1)
		self.size = PARTICLESIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.start_time = 1  # pygame.time.get_ticks() // 1000
		self.timer = 10
		self.start_time = pygame.time.get_ticks() / 1000
		# self.direction = direction
		if vel is not None:
			self.vel = vel  # pygame.math.Vector2(random.uniform(-2, 2), random.uniform(-2, 2))  # pygame.math.Vector2(0, 0)
			print(f'[p] vel {self.vel}')
		else:
			self.vel = random_velocity()
			# print(f'[p] randvel {self.vel} {self.direction}')
		if direction == 'up' and self.vel.y <= 0:
			self.vel.y = -1 * self.vel.y
		if direction == 'down' and self.vel.y >= 0:
			self.vel.y = -1 * self.vel.y
		if direction == 'left' and self.vel.x >= 0:
			self.vel.x = -1 * self.vel.x
			self.vel.y = random.uniform(-2,2)
		if direction == 'right' and self.vel.x <= 0:
			self.vel.x = -1 * self.vel.x
			self.vel.y = random.uniform(-2,2)

	def update(self, items=None):
		self.dt = pygame.time.get_ticks() / 1000
		if self.dt  - self.start_time >= self.timer:
			self.kill()
			# print(f'[p] time {self.dt - self.start_time} >= {self.timer}')
		# if self.direction == 'up':  #self.vel.y <= 0:  # direction up
		# 	self.pos.y += abs(self.vel.y)
		# 	self.pos.x += self.vel.x * 1.3
		# if self.direction == 'down':  # self.vel.y >= 0 :  # direction down
		# 	self.pos.y -= abs(self.vel.y)
		# 	self.pos.x += self.vel.x  * 1.3
		# if self.direction == 'right':  # self.vel.y >= 0 :  # direction down
		# 	self.pos.x -= abs(self.vel.x)
		# 	self.pos.y += self.vel.y  * 1.3
		# if self.direction == 'left':  # self.vel.y >= 0 :  # direction down
		# 	self.pos.x += abs(self.vel.x)
		# 	self.pos.y += self.vel.y  * 1.3
		# self.rect.x = self.pos.x
		# self.rect.y = self.pos.y
		self.pos += self.vel
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		if isinstance(items, pygame.sprite.Group):
			block_hit_list = self.collide(items)
			for block in block_hit_list:
				if block.block_type == '1' or block.block_type == '2' or block.block_type == '3' or block.block_type == '4':
					# print(f'[parthits] {len(block_hit_list)} {block}')
					self.vel = (random.uniform(-1,-0.1)) * self.vel
					#self.pos += self.vel
					#self.rect.x = self.pos.x
					#self.rect.y = self.pos.y
#				if not hit.solid:
#					pass
					#print(f'[parthits] kill {len(block_hit_list)} {hit}')
					#self.kill()
		# print(f'[P] {self.pos} {self.rect}')

class Flame(BasicThing):
	def __init__(self, pos=None, vel=None, direction=None):
		# super().__init__()
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.image, self.rect = load_image('flame2.png', -1)
		self.image = pygame.transform.scale(self.image, FLAMESIZE)
		if direction == 'left':
			self.image, self.rect = rot_center(self.image, self.rect, 90)
		if direction == 'right':
			self.image, self.rect = rot_center(self.image, self.rect, -90)
		if direction == 'down':
			self.image, self.rect = rot_center(self.image, self.rect, 180)
		self.direction = direction
		self.size = FLAMESIZE
		self.pos = pygame.math.Vector2(pos)
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.start_pos = pygame.math.Vector2(pos)
		self.vel = vel  # pygame.math.Vector2(vel[0], vel[1])  # flame direction
		self.timer = 10
		self.start_time = pygame.time.get_ticks() / 1000

	def check_time(self):
		pass

	def draw(self, screen):
		screen.blit(self.image, self.pos)

	def update(self):
		self.dt = pygame.time.get_ticks() / 1000
		self.pos += self.vel
		distance = abs(int(self.pos.distance_to(self.start_pos)))
		self.rect = self.image.get_rect()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# print(f'{self.pos.x} {self.start_pos.x} {self.pos.distance_to(self.start_pos)}')
		if distance >= FLAMELENGTH: # or (self.dt - self.start_time >= self.timer):
			# print(f'[flame] dist {distance} max {self.FLAMELENGTH}')
			self.kill()
		if self.dt - self.start_time >= self.timer:
			# print(f'[flame] time {self.dt - self.start_time} >= {self.timer}')
			self.kill()

	def flamecollide(self, block):
		#block_hit_list = self.collide(blocks)
		#for block in block_hit_list:
			# print(f'{block.get_type}')
		if block.get_type() == '1':
			block.take_damage(self)
			#block.set_type('20')
			self.kill()
		if block.get_type() == '2':
			block.take_damage(self)
			#block.set_type('20')
			self.kill()
		if block.get_type() == '3':
			block.take_damage(self)
			#block.set_type('20')
			self.kill()
		if block.get_type() == '4':
			block.take_damage(self)
			#block.set_type('20')
			self.kill()
		if block.get_type() == '11':
			block.take_damage(self)
			#block.set_type('0')
			self.kill()
		else:
			pass
				# print(f'[fl] p:{self.pos} b:{block.block_type}')

class Bomb(BasicThing):
	def __init__(self, pos=None, bomber_id=None, bomb_power=None):
		#super().__init__()
		pygame.sprite.Sprite.__init__(self)
		# self.flames = pygame.sprite.Group()
		# 		self.screen = screen
		self.pos = pos
		self.image, self.rect = load_image('bomb.png', -1)
		self.image = pygame.transform.scale(self.image, BOMBSIZE)
		# self.gridpos = gridpos
		self.bomber_id = bomber_id
		self.start_time = pygame.time.get_ticks() / 1000
		self.rect = self.image.get_rect()
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.bomb_timer = 1
		self.bomb_fuse = 1
		self.bomb_end = 5
		self.bomb_size = 5
		self.explode = False
		self.exp_radius = 1
		self.done = False
		self.flame_len = 50
		self.flame_power = bomb_power
		self.flame_width = 10
		self.flamesout = False
		self.flames = pygame.sprite.Group()

	def get_flames(self):
		if not self.flamesout:
			flame1 = Flame(pos=pygame.math.Vector2(self.pos), vel=(-1, 0),direction="left")
			flame2 = Flame(pos=pygame.math.Vector2(self.pos), vel=(1, 0), direction="right")
			flame3 = Flame(pos=pygame.math.Vector2(self.pos), vel=(0, 1), direction="down")
			flame4 = Flame(pos=pygame.math.Vector2(self.pos), vel=(0, -1), direction="up")
			flames = pygame.sprite.Group()
			flames.add(flame1)
			flames.add(flame2)
			flames.add(flame3)
			flames.add(flame4)
			self.flamesout = True
			return flames
		else:
			return pygame.sprite.Group()

	def update(self):
		self.dt = pygame.time.get_ticks() / 1000
		#print(f'{self.start_time} {self.dt} {self.dt - self.start_time} {self.bomb_timer}')
		# I will start exploding after xxx seconds....
		if self.dt - self.start_time >= self.bomb_fuse:
			self.explode = True
		if self.dt - self.start_time >= self.bomb_end:
			self.kill()

class Player(BasicThing):
	def __init__(self, pos=None, player_id=None):
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.image, self.rect = load_image('player1.png', -1)
		self.pos = pygame.math.Vector2(pos)
		self.vel = pygame.math.Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 1
		self.speed = 3
		self.player_id = player_id
		self.health = 100
		self.dead = False
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)

	def update(self, blocks):
			self.vel += self.accel
			self.pos.x += self.vel.x
			self.rect.x = int(self.pos.x)
			block_hit_list = self.collide(blocks)
			for block in block_hit_list:
				if isinstance(block, Block):
					markers = [False,False,False,False]
					if self.vel.x > 0 and block.solid:
							self.rect.right = block.rect.left
							self.collision_types['right'] = True
							markers[0] = True
					elif self.vel.x < 0 and block.solid:
							self.rect.left = block.rect.right
							self.collision_types['left'] = True
							markers[1] = True
					self.collision_types['data'].append([block,markers])
					self.pos.x = self.rect.x
					#self.vel.x = 0
			self.pos.y += self.vel.y
			self.rect.y = int(self.pos.y)
			block_hit_list = self.collide(blocks)
			for block in block_hit_list:
					markers = [False,False,False,False]
					if self.vel.y > 0 and block.solid:
							self.rect.bottom = block.rect.top
							self.collision_types['bottom'] = True
							markers[2] = True
					elif self.vel.y < 0 and block.solid:
							self.rect.top = block.rect.bottom
							self.collision_types['top'] = True
							markers[3] = True
					self.collision_types['data'].append([block,markers])
					# self.change_y = 0
					self.pos.y = self.rect.y
					#self.vel.y = 0
			return self.collision_types

	def take_powerup(self, powerup):
		# pick up powerups...
		if powerup.powerup_type[0] == "addbomb":
			if self.max_bombs < 10:
				self.max_bombs += 1
				self.bombs_left += 1
		if powerup.powerup_type[0] == "bombpower":
			if self.bomb_power < 10:
				self.bomb_power += 1
		if powerup.powerup_type[0] == "speedup":
			if self.speed < 10:
				self.speed += 1
		if powerup.powerup_type[0] == "healthup":
			self.health += 10

	def add_score(self):
		self.score += 1


class Gamemap:
	def __init__(self):
		self.grid = (self.generate())  # None # [[random.randint(0, 9) for k in range(GRIDSIZE[1] + 1)] for j in range(GRIDSIZE[0] + 1)]

	def generate(self):
		grid = [[random.randint(0, 4) for k in range(GRIDSIZE[1] + 1)]
				for j in range(GRIDSIZE[0] + 1)]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(GRIDSIZE[0] + 1):
			grid[x][0] = 10
			grid[x][GRIDSIZE[1]] = 10
		for y in range(GRIDSIZE[1] + 1):
			grid[0][y] = 10
			grid[GRIDSIZE[0]][y] = 10
		return grid

	def place_player(self):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridgamemap
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
				print(f"exception in place_player {block} {e}")
		return pygame.math.Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))

	def get_block(self, x, y):
		# get block inf from grid
		try:
			value = self.grid[x][y]
		except IndexError as e:
			print(f'[get_block] {e} x:{x} y:{y}')
			return -1
		return value

	def get_block_real(self, x, y):
		x = x // BLOCKSIZE[0]
		y = y // BLOCKSIZE[1]
		try:
			value = self.grid[x][y]
		except IndexError as e:
			print(f'[get_block] {e} x:{x} y:{y}')
			return -1
		return value

	def set_block(self, x, y, value):
		self.grid[x][y] = value
