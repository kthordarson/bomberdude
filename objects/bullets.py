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
	def __init__(self, position, velocity, screen_rect, bounce_count=3):
		super().__init__()
		self.image = pygame.Surface((10, 10))
		self.image.fill((255, 0, 0))
		self.position = Vec2d(position)
		self.rect = self.image.get_rect(center=self.position)
		self.velocity = Vec2d(velocity)
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count

	def update(self, collidable_tiles):
		self.rect.x += self.velocity[0]  # No flips!
		self.rect.y += self.velocity[1]

	def xczvxupdate(self, collidable_tiles):
		if self.bounce_count <= 0:
			self.kill()
			return

		# Update position based on velocity
		new_x = self.position.x + self.velocity.x
		new_y = self.position.y + self.velocity.y

		# Store original position for collision resolution
		original_x = self.position.x
		original_y = self.position.y

		# Move and check collisions
		self.position.x = new_x
		self.position.y = new_y
		self.rect.center = (int(self.position.x), int(self.position.y))

		# Check collisions only with collidable tiles
		hit_tile = None
		for tile in collidable_tiles:
			if hasattr(tile, 'collidable') and tile.collidable and self.rect.colliderect(tile):
				hit_tile = tile
				break

		if hit_tile:
			# Determine which side was hit by checking the previous position
			left_collision = original_x < hit_tile.left and self.rect.right > hit_tile.left
			right_collision = original_x > hit_tile.right and self.rect.left < hit_tile.right
			top_collision = original_y < hit_tile.top and self.rect.bottom > hit_tile.top
			bottom_collision = original_y > hit_tile.bottom and self.rect.top < hit_tile.bottom

			if left_collision or right_collision:
				self.velocity.x *= -1
			if top_collision or bottom_collision:
				self.velocity.y *= -1

			# Reset position and update with new velocity
			self.position.x = original_x
			self.position.y = original_y
			self.rect.center = (int(self.position.x), int(self.position.y))
			self.bounce_count -= 1

		# Handle screen boundaries
		if self.rect.left <= self.screen_rect.left:
			self.velocity.x = abs(self.velocity.x)
			self.bounce_count -= 1
		elif self.rect.right >= self.screen_rect.right:
			self.velocity.x = -abs(self.velocity.x)
			self.bounce_count -= 1
		if self.rect.top <= self.screen_rect.top:
			self.velocity.y = abs(self.velocity.y)
			self.bounce_count -= 1
		elif self.rect.bottom >= self.screen_rect.bottom:
			self.velocity.y = -abs(self.velocity.y)
			self.bounce_count -= 1
