from pygame.math import Vector2 as Vec2d
import pygame

class Bullet(pygame.sprite.Sprite):
	def __init__(self, position, direction, screen_rect, speed=10, bounce_count=3, bullet_size=(10,10)):
		super().__init__()
		self.image = pygame.Surface(bullet_size)
		# self.image = pygame.transform.scale(self.image, bullet_size)
		# self.image.fill((255, 0, 0))
		self.world_position = Vec2d(position)

		self.position = Vec2d(position)
		self.direction = Vec2d(direction)
		if self.direction.length() > 0:
			self.direction = self.direction.normalize()
		self.rect = self.image.get_rect(center=(int(self.world_position.x), int(self.world_position.y)))
		self.rect.center = (self.world_position.x, self.world_position.y)

		self.screen_rect = screen_rect
		self.bounce_count = bounce_count
		self.speed = speed

	def __repr__(self):
		return f'Bullet (pos: {self.position} direction: {self.direction} )'

	def update(self, collidable_tiles):
		self.world_position.x += self.direction.x * self.speed
		self.world_position.y += self.direction.y * self.speed

		# Then update rect position (for collision and rendering)
		self.rect.center = (int(self.world_position.x), int(self.world_position.y))

		# Check collisions with tiles
		for tile in collidable_tiles:
			if self.rect.colliderect(tile.rect):
				self.kill()
				return
