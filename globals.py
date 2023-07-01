import hashlib
import math
import os
import random
import time

import pygame
from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group, Sprite, spritecollide

from constants import (BLOCK, BLOCKTYPES, BOMBSIZE, DEFAULTFONT, FLAMESIZE,
                       MAXPARTICLES, POWERUPSIZE)

class BlockNotFoundError(Exception):
	pass
def random_velocity(direction=None) -> Vector2:
	vel = Vector2((random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0)))
	if direction == "left":
		vel.x = random.uniform(-5.0, -2)
	if direction == "right":
		vel.x = random.uniform(2, 5.0)
	if direction == "down":
		vel.y = random.uniform(2, 5.0)
	if direction == "up":
		vel.y = random.uniform(-5.0, -2)
	return vel


def load_image(name, colorkey=None) -> tuple:
	fullname = os.path.join("data", name)
	image = pygame.image.load(fullname).convert()
	# image = image.convert()
	return image, image.get_rect()

class ResourceHandler:
	def __init__(self):
		self.name = 'ResourceHandler'
		self.__images = {}

	def get_image(self, filename=None, force=False) -> tuple:
		if force or filename not in list(self.__images.keys()):
			img = pygame.image.load(filename).convert()
			rect = img.get_rect()
			self.__images[filename] = (img, rect)
			# logger.info(f'Image {filename} loaded images={len(self.__images)}')
			return img, rect
		else:
			# logger.info(f'Image {filename} already loaded images={len(self.__images)}')
			return self.__images[filename]

def gen_randid() -> str:
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it

class BasicThing(Sprite):
	def __init__(self, gridpos, image):
		super().__init__()
		self.gridpos = gridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		self.image = image
		self.vel = Vector2()
		self.start_time = pygame.time.get_ticks()
		self.clock = pygame.time.Clock()
		self.accel = Vector2(0, 0)

	def __str__(self):
		return f'[basic] pos={self.pos} gridpos={self.gridpos}'

	def draw(self, screen):
		pass
		# screen.blit(self.image, self.rect)

	def hit_list(self, objlist):
		hlist = []
		for obj in objlist:
			if obj.rect.colliderect(self.rect):
				hlist.append(obj)
		return hlist

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions

class Block(BasicThing):
	def __init__(self, pos, gridpos, block_type, client_id, rm):
		super().__init__(gridpos=gridpos, image=None)
		self.rm = rm
		self.blkid = gen_randid()
		self.client_id = client_id
		self.block_type = block_type
		self.size = BLOCKTYPES.get(self.block_type)["size"]
		self.bitmap = BLOCKTYPES.get(self.block_type)["bitmap"]
		self.powerup = BLOCKTYPES.get(self.block_type)["powerup"]
		self.image, self.rect = self.rm.get_image(filename=self.bitmap, force=False)
		self.explode = False
		self.timer = BLOCKTYPES.get(self.block_type)["timer"]
		self.image = pygame.transform.scale(self.image, self.size).convert()
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.image.set_alpha(255)
		self.image.set_colorkey((0, 0, 0))

	def __str__(self):
		return f'[block] pos={self.pos} gp={self.gridpos} type={self.block_type} blkid={self.blkid} client_id={self.client_id}'

	def debug_draw(self, screen=None, font=None):
		if self.block_type == 11:
			col = (255, 0, 0)
		elif self.block_type == 10:
			col = (55, 10, 10)
		else:
			col = (10,10,10)
		pygame.draw.rect(surface=screen, color=col, rect=self.rect, width=1)
		font.render_to(surf=screen,dest=(self.rect.x+5, self.rect.y+5), text=f'{self.gridpos}', fgcolor=col)
		font.render_to(surf=screen,dest=(self.rect.x+5, self.rect.y+15), text=f'{self.block_type}', fgcolor=col)

	def hit(self, flame):
		particles = Group()
		newblock = None
		pcount = MAXPARTICLES+random.randint(1, 10)
		if self.powerup:
			newblktype = random.choice([20,21,22])
			newblock = Block(self.rect.topleft, self.gridpos, block_type=newblktype, client_id=flame.client_id, rm=self.rm)
			logger.info(f'blockhit by {flame} powerup newblock={newblock} pc={pcount} ')
		else:
			newblktype = 11
			newblock = Block(self.rect.topleft, self.gridpos, block_type=newblktype, client_id=flame.client_id, rm=self.rm)
			#logger.info(f'{self} pc={pcount} hit by {flame} block newblock={newblock}')

		for k in range(1, pcount):
			if flame.vel.x < 0:  # flame come from left
				particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right")))  # make particle go right
			elif flame.vel.x > 0:  # right
				particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left")))  # for k in range(1,2)]
			elif flame.vel.y > 0:  # down
				particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up")))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
			elif flame.vel.y < 0:  # up
				particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down")))  # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
		return particles, newblock

	def gen_particles(self, flame):
		# called when block is hit by a flame
		# generate particles and set initial velocity based on direction of flame impact
		#self.particles = Group()
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		# flame.vel = Vector2(flame.vel[0], flame.vel[1])
		particles = Group()
		for k in range(1, random.randint(4,11)):
			if flame.vel.x < 0: # flame come from left
				particles.add(Particle(pos=flame.rect.midright, vel=random_velocity(direction="right"))) # make particle go right
			elif flame.vel.x > 0: # right
				particles.add(Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left"))) # for k in range(1,2)]
			elif flame.vel.y > 0: # down
				particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(direction="up"))) # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
			elif flame.vel.y < 0: # up
				particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(direction="down"))) # flame.vel.y+random.uniform(-1.31,1.85))))  #for k in range(1,2)]
		return particles


class Bomb(BasicThing):
	def __init__(self, pos, bomber_id, bombpower, gridpos, rm):
		self.rm = rm
		self.pos = pos
		self.gridpos = gridpos
		super().__init__(gridpos=self.gridpos, image=None)
		self.image, self.rect = self.rm.get_image(filename='data/bomb.png', force=False)
		self.image = pygame.transform.scale(self.image, BOMBSIZE).convert()
		self.bomber_id = bomber_id
		self.rect = self.image.get_rect(center=self.pos)
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.timer = 3232
		self.bomb_timer = 1
		self.bomb_fuse = 1
		self.bomb_end = 2
		self.bomb_size = 5
		self.explode = False
		self.exp_radius = 1
		self.done = False
		self.bombpower = bombpower
		self.flame_width = 10
		self.flamesout = False
		self.flames = Group()
		self.block_type = 11

	def __str__(self):
		return f'[bomb] gridpos={self.gridpos} pos={self.pos} bomber={self.bomber_id} timer={self.timer}'

	def exploder(self):
		flames = Group()
		fvel = self.bombpower/100
		flames.add(Flame(pos=self.rect.center, vel=Vector2(1+fvel,0), flame_length=self.bombpower, client_id=self.bomber_id))
		flames.add(Flame(pos=self.rect.center, vel=Vector2(-1-fvel,0), flame_length=self.bombpower, client_id=self.bomber_id))
		flames.add(Flame(pos=self.rect.center, vel=Vector2(0,-1-fvel), flame_length=self.bombpower, client_id=self.bomber_id))
		flames.add(Flame(pos=self.rect.center, vel=Vector2(0,1+fvel), flame_length=self.bombpower, client_id=self.bomber_id))
		# self.bomber_id.bombs_left += 1
		return flames

class Particle(BasicThing):
	def __init__(self, pos, vel):
		self.pos = pos
		self.gridpos = (self.pos[0]//BLOCK, self.pos[1]//BLOCK)
		super().__init__(gridpos=self.gridpos, image=None)
		#super().__init__(pos, None)
		# self.pos = pos
		xsize = random.randint(1,4)
		ysize = random.randint(1,4)
		self.image = pygame.Surface((xsize ,ysize))
		self.image.fill((random.randint(1,255), random.randint(1,255), random.randint(1,255)))
		self.rect = self.image.get_rect(center = pos)
		self.alpha = 255
		self.timer = 7000
		self.hits = 0
		self.maxhits = random.randint(2,5)
		self.mass = 11
		self.vel = Vector2(vel[0], vel[1])

	def __str__(self) -> str:
		return f'[particle] pos={self.pos} vel={self.vel}'

	def update(self, blocks):
		if self.rect.top <= 0 or self.rect.left <= 0:
			logger.info(f'{self} outofbounds')
			self.kill()
		self.image.set_alpha(self.alpha)
		#self.vel -= self.accel
		self.vel.y += abs(self.vel.y * 0.1) + random.triangular(0.01,0.03) # 0.025
		self.pos += self.vel
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		for b in spritecollide(self, blocks, False):
			if b.block_type != 11:
				#logger.info(f'{self} hitblock {b}')
				self.hit()

	def hit(self):
		self.hits += 1
		if self.hits >= self.maxhits:
			#logger.info(f'{self} maxhits')
			self.kill()
			return
		self.vel = -self.vel
		self.vel.y *= 0.5
		#self.vel.x *= 0.5
		self.vel.x -= random.triangular(0.01,0.03)
		self.vel.y -= random.triangular(0.01,0.03)
		self.alpha = round(self.alpha * 0.5)

class Flame(BasicThing):
	def __init__(self, pos, vel, flame_length, client_id):
		gridpos = (pos[0]//BLOCK, pos[1]//BLOCK)
		super().__init__(gridpos=gridpos, image=None)
		self.pos = pos
		self.client_id = client_id
		self.image = pygame.Surface((5,5), pygame.SRCALPHA)
		#self.image.fill((255,0,0))
		self.rect = self.image.get_rect()
		self.size = FLAMESIZE
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.start_pos = self.pos
		self.start_rect = self.rect
		self.start_midtop = self.rect.midtop
		self.start_midbottom = self.rect.midbottom
		self.start_center = Vector2((self.rect.x, self.rect.y))
		self.vel = Vector2(vel)
		self.timer = 4000
		self.flame_length = flame_length

	def __str__(self) -> str:
		return f'[flame] clid={self.client_id} pos={self.pos} vel={self.vel}'

	def update(self, surface):
		if pygame.time.get_ticks() - self.start_time >= self.timer:
			self.kill()
		self.pos += self.vel
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		dist = Vector2(self.start_pos).distance_to(Vector2(self.pos))
		if dist >= self.flame_length:
			self.kill()
		pygame.draw.line(surface, (200, 5, 5), self.start_center, self.rect.center, 1)
		#pygame.draw.line(surface, (255, 255, 255), self.start_midtop, self.pos, 2)
		#pygame.draw.line(surface, (255, 255, 255), self.start_midbottom, self.pos, 2)
		#pygame.draw.line(surface, (255, 5, 5), self.start_rect.midbottom, self.pos, 3)
		pygame.draw.circle(surface, color=(200, 5, 5), center=self.rect.center, radius=7, width=1)
		#pygame.draw.line(surface, (1, 255, 0), self.start_pos, self.rect.center, 2)
		#pygame.draw.line(surface, (255, 0, 1), self.start_center, self.rect.center, 2)
