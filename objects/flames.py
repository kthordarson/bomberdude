from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from constants import FLAME_SPEED

class Flame(Sprite):
	def __init__(self, position, direction, size=1):
		super().__init__()
		self.original_image = pygame.image.load('data/flameball.png')
		self.size = size
		self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.size), int(self.original_image.get_height() * self.size)))
		self.rect = self.image.get_rect()
		self.position = Vec2d(position)
		self.rect.topleft = self.position
		self.direction = direction
		self.shrink_rate = 0.02
		self.speed = 2
		self.min_size = 0.2

	def update(self, collidable_tiles, game_state):
		self.position.x += self.direction[0] * FLAME_SPEED
		self.position.y += self.direction[1] * FLAME_SPEED
		self.rect.topleft = self.position
		self.size -= self.shrink_rate
		if self.size <= self.min_size:
			self.kill()
			return
		else:
			# Update image size
			self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.size), int(self.original_image.get_height() * self.size)))
			self.rect = self.image.get_rect()
			self.rect.center = self.position
			for tile in collidable_tiles:
				try:
					if self.rect.colliderect(tile.rect):
						# logger.info(f"Flame collision with: {tile} {type(tile)}")
						if tile.layer == 'Blocks':
							game_state.destroy_block(tile)
						self.kill()
				except Exception as e:
					logger.warning(f"{e} {type(e)} tile: {tile} {type(tile)}\n{dir(tile)}")
