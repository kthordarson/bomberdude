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

class Bullet(pygame.sprite.Sprite):
	def __init__(self, position, direction, screen_rect, speed=10, bounce_count=3):
		super().__init__()
		self.image = pygame.Surface((10, 10))
		self.image.fill((255, 0, 0))
		self.position = Vec2d(position)
		self.rect = self.image.get_rect(center=self.position)
		# Normalize direction and multiply by speed to get velocity
		# self.velocity = direction.normalize() * speed
		self.velocity = direction * speed  # direction is already normalized
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count

	def __repr__(self):
		return f'Bullet (pos: {self.position} vel: {self.velocity} )'

	def update(self, collidable_tiles):
		# Update position using velocity
		self.position += self.velocity
		self.rect.center = self.position
		# Check for collisions with collidable tiles
		for tile in collidable_tiles:
			if self.rect.colliderect(tile):
				# Calculate the new direction based on the collision
				if abs(self.rect.right - tile.rect.left) < self.velocity.length() or abs(self.rect.left - tile.rect.right) < self.velocity.length():
					self.velocity.x *= -1  # Reverse the x-direction
				if abs(self.rect.bottom - tile.rect.top) < self.velocity.length() or abs(self.rect.top - tile.rect.bottom) < self.velocity.length():
					self.velocity.y *= -1  # Reverse the y-direction

				# Decrease the bounce count
				self.bounce_count -= 1
				if self.bounce_count <= 0:
					self.kill()  # Remove the bullet if bounce count is zero
				break  # Only handle one collision per update
