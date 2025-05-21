from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from constants import FLAME_SPEED, BLOCK

class Flame(Sprite):
	def __init__(self, position, direction, client_id, size=1, power=3):
		super().__init__()
		self.client_id = client_id
		self.original_image = pygame.image.load('data/flameball.png')
		self.size = size
		self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.size), int(self.original_image.get_height() * self.size)))
		self.rect = self.image.get_rect()
		self.position = Vec2d(position)
		self.rect.topleft = (int(self.position[0]), int(self.position[1]))
		self.direction = direction
		self.shrink_rate = 0.02
		self.speed = 2
		self.min_size = 0.2

		# New properties for distance tracking
		self.starting_position = Vec2d(position)  # Store initial position
		self.max_distance = power * BLOCK  # Max distance based on power (assuming 32px tiles)
		self.distance_traveled = 0

	async def flame_update(self, collidable_tiles, game_state) -> None:
		old_position = Vec2d(self.position)
		self.position.x += self.direction[0] * FLAME_SPEED
		self.position.y += self.direction[1] * FLAME_SPEED
		self.rect.topleft = (int(self.position[0]), int(self.position[1]))

		# Calculate distance traveled this frame
		movement = Vec2d(self.position) - old_position
		self.distance_traveled += movement.length()

		# Check if max distance reached
		if self.distance_traveled >= self.max_distance:
			self.kill()
			return

		self.size -= self.shrink_rate
		if self.size <= self.min_size:
			self.kill()
			return
		else:
			# Update image size
			self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.size), int(self.original_image.get_height() * self.size)))
			self.rect = self.image.get_rect()
			self.rect.center = (int(self.position[0]), int(self.position[1]))

			# Use spatial partitioning - define a small area around the flame
			flame_area = pygame.Rect(
				self.rect.x - BLOCK,  # Expand 32px left
				self.rect.y - BLOCK,  # Expand 32px up
				self.rect.width + BLOCK*2,  # Add 32px to both sides
				self.rect.height + BLOCK*2   # Add 32px to top and bottom
			)

			# Get nearby tiles using rect intersection instead of direct coordinate access
			nearby_killable = [tile for tile in game_state.killable_tiles if flame_area.colliderect(tile.rect)]
			nearby_collidable = [tile for tile in game_state.collidable_tiles if flame_area.colliderect(tile.rect)]

			# Check collision with nearby killable tiles first
			for tile in nearby_killable:
				if self.rect.colliderect(tile.rect):
					await game_state.destroy_block(tile)
					self.kill()

			# Then check collision with nearby collidable tiles
			for tile in nearby_collidable:
				if self.rect.colliderect(tile.rect):
					self.kill()

