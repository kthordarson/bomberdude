from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import math
import pygame
import random
from constants import PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED
from .particles import Particle
from .flames import Flame

class ExplosionManager:
	def __init__(self):
		self.particles = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()

	def create_explosion(self, position, count=PARTICLE_COUNT, colors=None):
		if colors is None:
			colors = [(255, 165, 0), (255, 69, 0), (255, 215, 0)]

		for _ in range(count):
			# Random angle and speed
			angle = random.uniform(0, 2 * math.pi)
			speed = random.uniform(PARTICLE_MIN_SPEED, PARTICLE_MIN_SPEED + PARTICLE_SPEED_RANGE)
			velocity = Vec2d(math.cos(angle) * speed, math.sin(angle) * speed)

			# Random color from palette
			color = random.choice(colors)

			# Random lifetime between 1-2 seconds
			lifetime = random.uniform(1.0, 2.0)

			# Create particle
			particle = Particle(
				position=position,
				velocity=velocity,
				radius=random.randint(2, PARTICLE_RADIUS),
				color=color,
				life=lifetime
			)
			self.particles.add(particle)

	def add_flame(self, flame):
		self.flames.add(flame)

	def update(self, collidable_tiles, game_state):
		self.particles.update(collidable_tiles)
		for flame in self.flames:
			flame.update(collidable_tiles, game_state)

	def draw(self, screen, camera):
		for particle in self.particles:
			screen_pos = camera.apply(particle.rect)
			screen.blit(particle.image, screen_pos)
		for flame in self.flames:
			screen_pos = camera.apply(flame.rect)
			screen.blit(flame.image, screen_pos)

