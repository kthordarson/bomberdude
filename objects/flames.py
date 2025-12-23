from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from constants import FLAME_SPEED, BLOCK
import math
from utils import load_image_cached

class Flame(Sprite):
	def __init__(self, position, direction, client_id, size=1, power=3):
		super().__init__()
		self.client_id = client_id
		self.original_image = load_image_cached('data/flameball.png')
		self.size = size
		self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.size), int(self.original_image.get_height() * self.size)))
		self.rect = self.image.get_rect()

		# Give flame an initial offset in its direction to prevent immediate collision
		self.position = Vec2d(position[0] + direction[0] * 10, position[1] + direction[1] * 10)
		self.rect.center = (int(self.position.x), int(self.position.y))

		self.direction = direction
		self.shrink_rate = 0.002
		self.speed = 2
		self.min_size = 0.2

		# New properties for distance tracking
		self.starting_position = Vec2d(position)  # Store initial position
		self.max_distance = power * BLOCK  # Max distance based on power (assuming 32px tiles)
		self.distance_traveled = 0
		# Small grace period before checking collisions
		self.collision_grace = 8  # pixels

	async def flame_update(self, collidable_tiles, game_state) -> None:
		# Move in smaller steps to avoid missing collisions
		steps = 3  # Check position 3 times during movement
		dx = self.direction[0] * FLAME_SPEED / steps
		dy = self.direction[1] * FLAME_SPEED / steps
		step_len = math.hypot(dx, dy)

		for _ in range(steps):
			self.position.x += dx
			self.position.y += dy
			self.rect.center = (int(self.position.x), int(self.position.y))

			# Accumulate distance with constant step length
			self.distance_traveled += step_len

			# Check if max distance reached
			if self.distance_traveled >= self.max_distance:
				self.kill()
				return

			# Skip collision checks during grace period
			if self.distance_traveled < self.collision_grace:
				continue

			# Check nearby tiles for collisions without allocating lists
			flame_area = pygame.Rect(
				self.rect.x - BLOCK//2,
				self.rect.y - BLOCK//2,
				self.rect.width + BLOCK,
				self.rect.height + BLOCK
			)

			# Killable tiles
			try:
				if hasattr(game_state, "iter_killable_in_rect"):
					killables = game_state.iter_killable_in_rect(flame_area, pad_pixels=0)
				else:
					killables = game_state.killable_tiles
				for tile in killables:
					if self.rect.colliderect(tile.rect):
						await game_state.destroy_block(tile)
						self.kill()
						return
			except Exception as e:
				logger.error(f"flame killable collision error: {e} {type(e)}")

			# Solid walls / collidables
			try:
				if hasattr(game_state, "iter_collidable_in_rect"):
					colliders = game_state.iter_collidable_in_rect(flame_area, pad_pixels=0)
				else:
					colliders = game_state.collidable_tiles
				for tile in colliders:
					if self.rect.colliderect(tile.rect):
						self.kill()
						return
			except Exception as e:
				logger.error(f"flame collidable collision error: {e} {type(e)}")

		# Update size/appearance for animation
		self.size -= self.shrink_rate
		if self.size <= self.min_size:
			self.kill()
		else:
			self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.size), int(self.original_image.get_height() * self.size)))
			self.rect = self.image.get_rect()
			self.rect.center = (int(self.position.x), int(self.position.y))

