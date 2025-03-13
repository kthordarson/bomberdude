from dataclasses import dataclass, field
import asyncio
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import orjson as json
import math
import pygame
import random
import time
from utils import gen_randid, load_image
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY

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

class ExplosionManager:
	def __init__(self):
		self.particles = pygame.sprite.Group()

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

	def update(self, collidable_tiles):
		self.particles.update(collidable_tiles)

	def draw(self, screen, camera):
		for particle in self.particles:
			screen_pos = camera.apply(particle.rect)
			screen.blit(particle.image, screen_pos)

class Bomb(Sprite):
	def __init__(self, position, speed=10, timer=3, bomb_size=(10,10)):
		super().__init__()
		# self.image = pygame.Surface(bomb_size)
		self.image = pygame.image.load('data/bomb.png')
		self.rect = self.image.get_rect()
		self.position = Vec2d(position)
		self.timer = timer
		self.start_time = pygame.time.get_ticks() / 1000
		self.rect.topleft = self.position
		self.exploded = False

	def __repr__(self):
		return f'Bomb (pos: {self.position} )'

	def update(self, collidable_tiles=None, explosion_manager=None):
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			logger.info(f'{self} BOOM!')
			# Create explosion particles if manager is provided
			if explosion_manager and not self.exploded:
				explosion_manager.create_explosion(self.rect.center)
				self.exploded = True
			self.kill()
