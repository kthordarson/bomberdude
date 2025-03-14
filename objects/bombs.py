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
			flame_position = Vec2d(self.position.x + direction[0] * self.rect.width, self.position.y + direction[1] * self.rect.height)
			flame = Flame(flame_position, direction)
			explosion_manager.add_flame(flame)
