from pygame.math import Vector2 as Vec2d
import math
import pygame
import random
from constants import PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, SHOCKWAVE_EXPANSION_RATE, SHOCKWAVE_MAX_RADIUS_PRIMARY, SHOCKWAVE_MAX_RADIUS_SECONDARY
from .particles import Particle
from .flames import Flame
from .shockwave import Shockwave

class ExplosionManager:
	def __init__(self):
		self.particles = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()
		self.shockwaves = []

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
			lifetime = 2.0  # random.uniform(1.0, 2.0)

			# Create particle
			particle = Particle(
				position=position,
				velocity=velocity,
				radius=random.randint(2, PARTICLE_RADIUS),
				color=color,
				life=lifetime
			)
			self.particles.add(particle)
		self.create_shockwave(position)

	def create_shockwave(self, position):
		# self.shockwaves = []
		# Primary shockwave - faster and more transparent
		primary = Shockwave(
			position=position,
			max_radius=SHOCKWAVE_MAX_RADIUS_PRIMARY,
			duration=0.8,  # Fixed duration
			expansion_rate=SHOCKWAVE_EXPANSION_RATE,
			color=(255, 255, 255, 100)
		)
		self.shockwaves.append(primary)

		# Secondary shockwave - slower and more visible
		secondary = Shockwave(
			position=position,
			max_radius=SHOCKWAVE_MAX_RADIUS_SECONDARY,
			duration=1.0,  # Fixed duration (slightly longer)
			expansion_rate=SHOCKWAVE_EXPANSION_RATE * 0.8,  # 80% of primary speed
			color=(255, 220, 150, 130)
		)
		self.shockwaves.append(secondary)

	def add_flame(self, flame):
		self.flames.add(flame)

	async def update(self, collidable_tiles, game_state, delta_time=1/10):
		self.particles.update(collidable_tiles)
		for flame in self.flames:
			await flame.flame_update(collidable_tiles, game_state)
		# Update shockwaves and remove dead ones
		for shockwave in self.shockwaves:
			shockwave.update(delta_time)
			if not shockwave.alive:
				self.shockwaves.remove(shockwave)

	def draw(self, screen, camera):
		for particle in self.particles:
			screen_pos = camera.apply(particle.rect)
			screen.blit(particle.image, screen_pos)
		for flame in self.flames:
			screen_pos = camera.apply(flame.rect)
			screen.blit(flame.image, screen_pos)
		# Draw shockwaves
		for shockwave in self.shockwaves:
			shockwave.draw(screen, camera)

	def create_flames(self, owner):
		directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]  # Right, Left, Down, Up
		for direction in directions:
			# Start from exact bomb center
			flame_position = Vec2d(owner.rect.center)
			flame = Flame(flame_position, direction, owner.client_id, power=owner.power)
			self.add_flame(flame)
