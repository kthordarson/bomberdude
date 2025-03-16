from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import math
import pygame
import random
from constants import PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_RATE, FLAMEX, FLAMEY

class Particle(Sprite):
	def __init__(self, position, velocity, radius=3, color=(255, 165, 0), life=2.0):
		super().__init__()
		self.position = Vec2d(position)
		self.velocity = Vec2d(velocity)
		self.radius = radius
		self.color = color
		self.life = life
		self.original_life = life
		self.born_time = pygame.time.get_ticks() / 1000

		# Create the particle surface
		self.image = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
		pygame.draw.circle(self.image, color, (radius, radius), radius)
		self.rect = self.image.get_rect(center=position)

	def update(self, collidable_tiles):
		# Update position
		self.position.x += self.velocity.x
		self.position.y += self.velocity.y

		# Apply gravity
		self.velocity.y += PARTICLE_GRAVITY

		# Handle wall collisions
		for tile in collidable_tiles:
			if self.rect.colliderect(tile.rect):
				# Simple bounce physics
				if abs(self.rect.right - tile.rect.left) < 5 or abs(self.rect.left - tile.rect.right) < 5:
					self.velocity.x *= -0.8  # Bounce with dampening
				if abs(self.rect.bottom - tile.rect.top) < 5 or abs(self.rect.top - tile.rect.bottom) < 5:
					self.velocity.y *= -0.8  # Bounce with dampening

		# Update rect position
		self.rect.center = (int(self.position.x), int(self.position.y))

		# Fade out over time
		elapsed = pygame.time.get_ticks() / 1000 - self.born_time
		alpha = int(max(0, 255 * (1 - elapsed / self.life)))

		# Recreate the surface with new alpha
		self.image = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
		color_with_alpha = (*self.color, alpha)
		pygame.draw.circle(self.image, color_with_alpha, (self.radius, self.radius), self.radius)

		# Kill if lifetime is over
		if elapsed > self.life:
			self.kill()
