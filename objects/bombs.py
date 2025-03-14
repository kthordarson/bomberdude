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

class Flame(Sprite):
	def __init__(self, position, direction):
		super().__init__()
		self.image = pygame.image.load('data/flame.png')
		self.rect = self.image.get_rect()
		self.position = Vec2d(position)
		self.rect.topleft = self.position
		self.direction = direction

	def update(self, collidable_tiles, game_state):
		self.position.x += self.direction[0] * FLAME_SPEED
		self.position.y += self.direction[1] * FLAME_SPEED
		self.rect.topleft = self.position

		for tile in collidable_tiles:
			try:
				if self.rect.colliderect(tile.rect):
					# logger.info(f"Flame collision with: {tile} {type(tile)}")
					if hasattr(tile, 'layer') and tile.layer == 'Blocks':
						try:
							if tile.layer == 'Blocks':
								game_state.destroy_block(tile)
						except AttributeError as e:
							logger.warning(f"Error destroying block: {e} tile: {tile} {type(tile)} {dir(tile)}")
			except Exception as e:
				logger.warning(f"{e} {type(e)} tile: {tile} {type(tile)}\n{dir(tile)}")
			finally:
				self.kill()


class Bomb(Sprite):
	def __init__(self, position, power=3, speed=10, timer=3, bomb_size=(10,10)):
		super().__init__()
		# self.image = pygame.Surface(bomb_size)
		self.image = pygame.image.load('data/bomb4.png')
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
			flame_position = Vec2d(self.position.x + direction[0] * self.rect.width, self.position.y + direction[1] * self.rect.height)
			flame = Flame(flame_position, direction)
			explosion_manager.add_flame(flame)
