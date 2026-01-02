from loguru import logger
from pygame.math import Vector2 as Vec2d
import pygame

class Bullet(pygame.sprite.Sprite):
	def __init__(self, position, direction, screen_rect, owner_id=None, speed=10, bounce_count=3, bullet_size=(10,10)):
		super().__init__()
		self.image = pygame.Surface(bullet_size)
		self.world_position = Vec2d(position)

		self.position = Vec2d(position)
		self.direction = Vec2d(direction)
		if self.direction.length() > 0:
			self.direction = self.direction.normalize()
		if self.image:
			self.rect = self.image.get_rect(center=(int(self.world_position.x), int(self.world_position.y)))
			self.image.fill((255, 0, 0))
		if self.rect:
			self.rect.center = (int(self.world_position.x), int(self.world_position.y))
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count
		self.speed = speed
		self.owner_id = owner_id

	def __repr__(self):
		return f'Bullet (pos: {self.position} direction: {self.direction} )'

	def update(self, *args, **kwargs):
		collidable_tiles = None
		if args:
			collidable_tiles = args[0]
		elif 'collidable_tiles' in kwargs:
			collidable_tiles = kwargs['collidable_tiles']
		self.world_position.x += self.direction.x * self.speed
		self.world_position.y += self.direction.y * self.speed

		# Then update rect position (for collision and rendering)
		if self.rect:
			self.rect.center = (int(self.world_position.x), int(self.world_position.y))

		# Check collisions with tiles
		if collidable_tiles and self.rect:
			tiles_iter = collidable_tiles.iter_collidable_in_rect(self.rect, pad_pixels=0)
			for tile in tiles_iter:
				if self.rect.colliderect(tile.rect):
					self.kill()
					return
