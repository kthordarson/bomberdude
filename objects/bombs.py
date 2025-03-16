from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import math
import pygame
import random
from constants import PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED
from .particles import Particle
from .flames import Flame

class Bomb(Sprite):
	def __init__(self, position, power=3, speed=10, timer=3, bomb_size=(10,10)):
		super().__init__()
		# self.image = pygame.Surface(bomb_size)
		self.image = pygame.image.load('data/bomb5.png')
		self.rect = self.image.get_rect()
		self.position = Vec2d(position)
		self.timer = timer
		self.start_time = pygame.time.get_ticks() / 1000
		self.rect.topleft = self.position
		self.exploded = False
		self.power = power

	def __repr__(self):
		return f'Bomb (pos: {self.position} )'

	def update(self, collidable_tiles=None, explosion_manager=None):
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			# Create explosion particles if manager is provided
			if explosion_manager and not self.exploded:
				explosion_manager.create_explosion(self.rect.center)
				self.create_flames(explosion_manager)
				self.exploded = True
			self.kill()

	def create_flames(self, explosion_manager):
		directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]  # Right, Left, Down, Up
		for direction in directions:
			# for i in range(1, self.power + 1):
			# flame_position = Vec2d(self.position.x + direction[0] * i * self.rect.width, self.position.y + direction[1] * i * self.rect.height)
			flame_position = Vec2d(self.position.x + direction[0] * self.rect.width//2, self.position.y + direction[1] * self.rect.height//2)
			flame = Flame(flame_position, direction)
			explosion_manager.add_flame(flame)
