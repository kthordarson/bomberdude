from dataclasses import dataclass, field
import asyncio
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import json
import math
import pygame
import random
import time
from utils import gen_randid
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY
from .particles import Particle
from .bullets import Bullet

MOVE_MAP = {
	pygame.K_UP: (0, PLAYER_MOVEMENT_SPEED),
	pygame.K_w: (0, PLAYER_MOVEMENT_SPEED),
	119: (0, PLAYER_MOVEMENT_SPEED),

	pygame.K_DOWN: (0, -PLAYER_MOVEMENT_SPEED),
	pygame.K_s: (0, -PLAYER_MOVEMENT_SPEED),
	115: (0, -PLAYER_MOVEMENT_SPEED),

	pygame.K_LEFT: (-PLAYER_MOVEMENT_SPEED, 0),
	pygame.K_a: (-PLAYER_MOVEMENT_SPEED, 0),
	97: (-PLAYER_MOVEMENT_SPEED, 0),

	pygame.K_RIGHT: (PLAYER_MOVEMENT_SPEED, 0),
	pygame.K_d: (PLAYER_MOVEMENT_SPEED, 0),
	100: (PLAYER_MOVEMENT_SPEED, 0),
}

KEY_NAME_MAP = {v: k for k, v in pygame.key.__dict__.items() if isinstance(v, int)}

class KeysPressed:
	def __init__(self, name):
		self.name = name
		self.keys = {k: False for k in MOVE_MAP}

	def __repr__(self):
		return f'KeyPressed ({self.name})'

	def to_json(self):
		return json.dumps({"name": self.name, "keys": {KEY_NAME_MAP.get(k, str(k)): v for k, v in self.keys.items()}})

@dataclass(eq=True)
class Bomberplayer(Sprite):
	texture: str
	scale: float = 0.7
	client_id: str = None
	position: Vec2d = field(default_factory=lambda: Vec2d(99, 99))
	# name: str = 'xnonex'

	def __post_init__(self):
		super().__init__()
		self.image = pygame.image.load(self.texture)
		self.rect = self.image.get_rect()
		self.change_x = 0
		self.change_y = 0
		self.bombsleft = 3
		self.health = 100
		self.killed = False
		self.timeout = False
		self.score = 0
		self.angle = 0
		self.candrop = True
		self.lastdrop = 0
		self.keyspressed = KeysPressed('gamestate')
		# self.bullets = pygame.sprite.Group()

	def __hash__(self):
		return hash((self.client_id))

	def to_dict(self):
		"""Convert player object to dictionary"""
		try:
			return {
				'id': self.client_id,
				'position': [float(self.position.x), float(self.position.y)],
				'score': self.score,
				'health': self.health,
				'timeout': self.timeout,
				'msg_dt': time.time(),
				'killed': self.killed,
				'bombsleft': self.bombsleft,
				'angle': self.angle
			}
		except Exception as e:
			logger.error(f"Error converting player to dict: {e}")
			return {}

	def update(self, collidable_tiles):
		# Store previous position before movement for rollback
		prev_x, prev_y = self.position.x, self.position.y

		# Move the player
		self.position.x += self.change_x
		self.position.y += self.change_y

		# Update the rectangle position
		self.rect.topleft = self.position

		# Check for collisions
		for tile in collidable_tiles:
			if self.rect.colliderect(tile.rect):
				# Rollback to previous position if collision occurs
				self.position.x, self.position.y = prev_x, prev_y
				self.rect.topleft = self.position
				return

	def old__update(self, collidable_tiles):
		# Calculate new position
		new_x = self.position.x + self.change_x
		new_y = self.position.y + self.change_y

		# Check for collisions
		new_rect = self.rect.copy()
		new_rect.topleft = (new_x, new_y)
		collision = any(new_rect.colliderect(tile) for tile in collidable_tiles)
		if not collision:
			self.position.update(new_x, new_y)
			self.rect.topleft = self.position
		# self.bullets.update()

	def shoot(self, direction):
		# Calculate direction from player's position to target
		bullet_pos = Vec2d(self.rect.center)
		bullet = Bullet(position=bullet_pos,direction=direction, screen_rect=self.rect)
		return bullet  # self.bullets.add(bullet)

	def drop_bomb(self):
		event = {"event_time": 0,
				"event_type": "drop_bomb",
				"client_id": self.client_id,
				"position": (self.rect.x, self.rect.y),
				"ba": 1,
				"timer": 1,
				"handled": False,
				"handledby": self.client_id,
				"eventid": gen_randid(),}
		return event

	def draw(self, screen):
		screen.blit(self.image, self.rect.topleft)

	def rotate_around_point(self, point, degrees):
		self.angle += degrees
		self.position = pygame.math.Vector2(self.rect.center).rotate_around(point, degrees)

	def respawn(self):
		self.killed = False
		self.health = 100
		self.position = Vec2d(101, 101)
		self.bombsleft = 3
		self.score = 0
		self.timeout = False
		self.image = pygame.image.load('data/playerone.png')
		logger.info(f'{self} respawned')

	def set_texture(self, texture):
		self.image = pygame.image.load(texture)

	def addscore(self, score):
		self.score += score
		logger.info(f'{self} score:{self.score}')

	def take_damage(self, damage, dmgfrom):
		self.health -= damage
		logger.info(f'{self} health:{self.health} {damage=} {dmgfrom=}')
		if self.health <= 0:
			self.killed = True
			self.kill(dmgfrom)
			return 5
		return 1

	def kill(self, dmgfrom):
		logger.info(f'{self} killed by {dmgfrom}')
		self.killed = True
		self.image = pygame.image.load('data/netplayerdead.png')
		return 11

	def set_pos(self, newpos):
		self.rect.topleft = newpos
		self.update()
