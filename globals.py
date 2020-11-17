import random
import math
import pygame
import os
from pygame.colordict import THECOLORS as colordict

# global constants
BLOCKSIZE = (30, 30)
POWERUPSIZE = (12, 12)
BOMBSIZE = (BLOCKSIZE[0] // 4, BLOCKSIZE[0] // 4)
# PLAYERSIZE = (BLOCKSIZE[0] // 2, BLOCKSIZE[0] // 2)
PLAYERSIZE = (15,15)
GRID_X = 20
GRID_Y = 20
SCREENSIZE = (BLOCKSIZE[0] * (GRID_X + 1), BLOCKSIZE[1] * GRID_Y + 100)
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
		"bitmap": 'blocks/darkDirtBlock.png',
	},
	"1": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'blocks/darkStoneBlock.png',
	},
	"2": {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'blocks/darkStoneBlock.png',
	},
	"3": {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'blocks/darkStoneBlock.png',
	},
	"4": {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": 'blocks/darkStoneBlock.png',
	},
	"10": {
		"solid": True,
		"permanent": True,
		"size": BLOCKSIZE,
		"bitmap": 'blocksprite3.png',
	},
	"20": {
		"solid": False,
		"permanent": False,
		"size": POWERUPSIZE,
		"bitmap": 'blocks/heart.png',
	},
}


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
	def __init__(self, screen=None, gridpos=(0, 0), color=(33, 44, 55, 255)):
		# super().__init__()
		pygame.sprite.Sprite.__init__(self)
		self.screen = screen
		self.pos = pygame.math.Vector2(gridpos[0] * BLOCKSIZE[0], gridpos[1] * BLOCKSIZE[1])
		self.gridpos = gridpos
		self.size = BLOCKSIZE
		self.font = pygame.freetype.Font("DejaVuSans.ttf", 12)
		self.font_color = (255, 255, 255)
#		self.collisions = None

class Block(BasicThing):
	def __init__(self, gridpos=(0, 0), block_type=0):
		# super().__init__(screen, gridpos)
		pygame.sprite.Sprite.__init__(self)
		self.block_type = block_type
		self.solid = BLOCKTYPES.get(block_type)["solid"]
		self.permanent = BLOCKTYPES.get(block_type)["permanent"]
		self.size = BLOCKTYPES.get(block_type)["size"]
		self.bitmap = BLOCKTYPES.get(block_type)["bitmap"]
		self.image, self.rect = load_image(self.bitmap, -1)
		self.image = pygame.transform.scale(self.image, BLOCKSIZE)
		self.rect = self.image.get_rect()
		self.pos = pygame.math.Vector2((gridpos[0] * BLOCKSIZE[0], gridpos[1] * BLOCKSIZE[1]))
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		self.block_type = block_type
		self.explode = False
		self.ending_soon = False
		self.powerblock = False
		# self.solid = False
		self.hit = False
		self.dt = pygame.time.get_ticks() / 1000
		self.timer = 1000
		self.time_left = self.timer
		self.start_time = pygame.time.get_ticks()
		#self.image.set_alpha(100)
		#self.image.set_colorkey((0,0,0))

	def set_bitmap(self, bitmap):
		self.size = BLOCKTYPES.get(block_type)["size"]
		self.image, self.rect = load_image(bitmap, -1)
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()

	def collide(self, items):
		return pygame.sprite.spritecollide(self, items, False)

	def set_type(self, block_type):
		self.solid = BLOCKTYPES.get(block_type)["solid"]
		self.permanent = BLOCKTYPES.get(block_type)["permanent"]
		self.size = BLOCKTYPES.get(block_type)["size"]
		self.bitmap = BLOCKTYPES.get(block_type)["bitmap"]
		self.image, self.rect = load_image(self.bitmap, -1)
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# pygame.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, self.size, self.size))
		# self.rect = self.image.get_rect()

	def update(self):
		if self.powerblock:
			self.dt = pygame.time.get_ticks()
			if self.dt - self.start_time >= self.timer:
				self.set_type("0")
			if self.dt - self.start_time >= self.timer // 3:
				self.ending_soon = True

	#    def draw(self, screen):
	#        pygame.draw.rect(self.image, self.color, (self.pos, self.size))
	#        screen.blit(self.image, self.rect)

	def set_zero(self):
		pass

	def drop_powerblock(self):
		if not self.powerblock:
			self.set_type("20")
			self.start_time = pygame.time.get_ticks()
			self.dt = pygame.time.get_ticks() / 1000
			# self.pos.x += 5
			# self.pos.y += 5
			self.powerblock = True
			# print(f'[powerblock] {self.pos} {self.gridpos} {self.powerblock} ')
			self.hit = False
			self.image = pygame.transform.scale(self.image, POWERUPSIZE)


class Particle(BasicThing):
	def __init__(self, block, direction=None):
		# super().__init__()
		pygame.sprite.Sprite.__init__(self)
		self.image, self.rect = load_image('blocks/blueorb.png', -1)
		self.size = (3, 3)
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.direction = direction
		self.alpha = 255
		self.alpha_mod = -5
		self.image.set_alpha(self.alpha)
		self.vel = pygame.math.Vector2(random.uniform(-2, 2), random.uniform(-2, 2))  # pygame.math.Vector2(0, 0)
		if self.direction == "up":
			self.rect.midtop = block.rect.midbottom
			self.vel.y = -self.vel.y
		if self.direction == "down":  # and self.vel.y >= 0:
			self.rect.midbottom = block.rect.midtop
			self.vel.y = -self.vel.y
		if self.direction == "right":  # and self.vel.x >= 0:
			self.rect.x = block.rect.midright[1]
			self.vel.x = -self.vel.x
		if self.direction == "left":  # and self.vel.x <= 0:
			self.rect.midright = block.rect.midleft
			self.vel.x = -self.vel.x
		self.pos = pygame.math.Vector2((self.rect.centerx, self.rect.centery))
		self.move = False
		self.radius = 1
		self.dt = pygame.time.get_ticks() / 1000
		self.timer = 1000
		self.time_left = self.timer
		self.start_time = pygame.time.get_ticks()

	def update(self):
		self.dt = pygame.time.get_ticks() / 1000
		w, h = pygame.display.get_surface().get_size()
		if self.dt - self.start_time >= self.timer:
			self.kill()
		self.pos += self.vel
		self.alpha += self.alpha_mod
		if self.alpha <= 0:
			self.alpha = 0
		self.image.set_alpha(self.alpha)
		if self.pos.x >= w or self.pos.x <= 0 or self.pos.y >= h or self.pos.y <= 0:
			self.kill()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y

class Bomb_Flame(BasicThing):
	def __init__(self, direction, rect, vel, flame_length):
		# super().__init__()
		pygame.sprite.Sprite.__init__(self)
		self.image, self.rect = load_image('blocks/flame.png', -1)
		self.image = pygame.transform.scale(self.image, (3,3))
		self.direction = direction
		self.flame_length = flame_length
		self.pos = pygame.math.Vector2(rect.centerx, rect.centery)
		self.endpos = pygame.math.Vector2(self.pos.x, self.pos.y)
		self.vel = pygame.math.Vector2(vel[0], vel[1])  # flame direction

	def stop(self):
		self.vel = pygame.math.Vector2(0, 0)

	def update(self):
		self.pos += self.vel
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
class BlockBomb(BasicThing):
	def __init__(self, pos, bomber_id, bomb_power):
		#super().__init__()
		pygame.sprite.Sprite.__init__(self)
		# self.flames = pygame.sprite.Group()
		# 		self.screen = screen
		self.pos = pygame.math.Vector2(pos[0], pos[1])
		self.image, self.rect = load_image('bomb.png', -1)
		self.image = pygame.transform.scale(self.image, BOMBSIZE)
		# self.gridpos = gridpos
		self.bomber_id = bomber_id
		self.start_time = pygame.time.get_ticks()
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.bomb_timer = 1000
		self.bomb_size = 5
		self.exploding = False
		self.exp_steps = 50
		self.exp_radius = 1
		self.done = False
		self.flame_len = 1
		self.flame_power = bomb_power
		self.flame_width = 10
		self.dt = pygame.time.get_ticks()

	def update(self):
		self.dt = pygame.time.get_ticks() / 1000
		# I will start exploding after xxx seconds....
		if self.dt - self.start_time >= self.bomb_timer:
			self.exploding = True
		if self.exploding:
			self.exp_steps -= 1  # animation steps ?
			if self.exp_steps <= 0:  # stop animation and kill bomb
				self.done = True

class Player(BasicThing):
	def __init__(self, pos, player_id):
		#super().__init__()
		pygame.sprite.Sprite.__init__(self)
		# self.screen = screen
		self.image, self.rect = load_image('player1.png', -1)
		self.pos = pygame.math.Vector2(pos)
		self.vel = pygame.math.Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect()
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		# self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 1
		self.speed = 3
		self.player_id = player_id
		self.health = 100
		self.dead = False
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.collisions = []
		self.collide_type = {'top':False, 'bottom':False, 'right':False, 'left':False}
		# self.gridpos = (self.rect.centerx // BLOCKSIZE[0], self.rect.centery // BLOCKSIZE[1])

	def collide(self, items):
		self.collisions = pygame.sprite.spritecollide(self, items, False)
		return self.collisions

	def drop_bomb(self, game_data):
		# get grid pos of player
		#x = self.gridpos[0]
		#y = self.gridpos[1]
		#game_data.grid[x][y] = self.player_id
		# create bomb at gridpos xy, multiply by BLOCKSIZE for screen coordinates
		bomb = BlockBomb(pos=(self.rect.centerx, self.rect.centery), bomber_id=self.player_id, bomb_power=self.bomb_power)
		game_data.bombs.add(bomb)
		self.bombs_left -= 1
		return game_data

	def take_damage(self, amount=25):
		self.health -= amount
		if self.health <= 0:
			self.dead = True

	def update(self, blocks):		
		self.rect.x += self.vel.x
		hit_list = self.collide(blocks)
		for block in hit_list:
			if self.vel.x > 0:
				self.rect.right = self.rect.left
				self.collide_type['right'] = True
			elif self.vel.x < 0:
				self.rect.left = self.rect.right
				self.collide_type['right'] = True

	def update2(self, blocks):
		# Move left/right
		# self.pos += self.vel
		self.pos += self.vel  #* dt
		for item in self.collisions:
			if isinstance(item, Block) and item.solid:
				print(f'{item}')
				if self.vel.x < 0:
					self.rect.right = self.rect.left
					#self.vel.x = 0
				if self.vel.x > 0:
					self.rect.left = self.rect.right
					#self.vel.x = 0
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		# self.rect.x = self.pos.x
		# collisions = pygame.sprite.spritecollide(self, blocks, False)
		# for block in collisions:  # Horizontal collision occurred.
		# 	if self.vel.x < 0 and block.solid:  # Moving right.
		# 		self.rect.right = block.rect.left  # Reset the rect pos.
		# 		self.vel = pygame.math.Vector2((0,0))
		# 	elif self.vel.x > 0 and block.solid:  # Moving left.
		# 		self.rect.left = block.rect.right  # Reset the rect pos.
		# 		self.vel = pygame.math.Vector2((0,0))
		# 	self.pos.x = self.rect.x  # Update the actual x-position.

		# self.pos.y += self.vel.y
		# self.rect.y = self.pos.y
		# collisions = pygame.sprite.spritecollide(self, blocks, False)
		# for block in collisions:  # Vertical collision occurred.
		# 	if self.vel.y < 0 and block.solid:  # Moving down.
		# 		self.rect.bottom = block.rect.top  # Reset the rect pos.
		# 		self.vel = pygame.math.Vector2((0,0))
		# 	elif self.vel.y > 0 and block.solid:  # Moving up.
		# 		self.rect.top = block.rect.bottom  # Reset the rect pos.
		# 		self.vel = pygame.math.Vector2((0,0))
		# 	self.pos.y = self.rect.y  # Update the actual y-position.
		# self.gridpos = (self.rect.centerx // BLOCKSIZE[0], self.rect.centery // BLOCKSIZE[1])
		# #self.rect.centerx = self.pos.x
		# #self.rect.centery = self.pos.y
		
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
		self.grid = (
			self.generate()
		)  # None # [[random.randint(0, 9) for k in range(GRID_Y + 1)] for j in range(GRID_X + 1)]

	def generate(self):
		grid = [[random.randint(0, 4) for k in range(GRID_Y + 1)]
				for j in range(GRID_X + 1)]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(GRID_X + 1):
			grid[x][0] = 10
			grid[x][GRID_Y] = 10
		for y in range(GRID_Y + 1):
			grid[0][y] = 10
			grid[GRID_X][y] = 10
		return grid

	def place_player(self):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridgamemap
		x = int(GRID_X // 2)  # random.randint(2, GRID_X - 2)
		y = int(GRID_Y // 2)  # random.randint(2, GRID_Y - 2)
		self.grid[x][y] = 0
		# make a clear radius around spawn point
		for block in list(inside_circle(3, x, y)):
			try:
				# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
				self.grid[block[0]][block[1]] = 0
			except Exception as e:
				print(f"exception in place_player {block} {e}")
		return (x * BLOCKSIZE[0], y * BLOCKSIZE[1])

	def get_block(self, x, y):
		# get block inf from grid
		return self.grid[x][y]

	def get_block_real(self, x, y):
		return (x, y)
		# get block inf from grid
		# gamemapx = x // BLOCKSIZE
		# gamemapy = y // BLOCKSIZE
		# return self.grid[gamemapx][gamemapy]

	def set_block(self, x, y, value):
		self.grid[x][y] = value
