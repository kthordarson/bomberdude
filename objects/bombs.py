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

	def update(self, explosion_manager):
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			# Create explosion particles if manager is provided
			if not self.exploded:
				explosion_manager.create_explosion(self.rect.center)
				explosion_manager.create_flames(self.rect)
				self.exploded = True
			self.kill()
