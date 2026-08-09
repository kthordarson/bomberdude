from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from constants import PARTICLE_GRAVITY

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
		if self.image:
			pygame.draw.circle(self.image, color, (radius, radius), radius)
			self.rect = self.image.get_rect(center=position)

	def update(self, *args, **kwargs):
		collidable_tiles = None
		if args:
			collidable_tiles = args[0]
		elif 'collidable_tiles' in kwargs:
			collidable_tiles = kwargs['collidable_tiles']
		# Update position
		self.position.x += self.velocity.x
		self.position.y += self.velocity.y

		# Update rect position early (collision checks need the new position)
		if self.rect:
			self.rect.center = (int(self.position.x), int(self.position.y))

		# Apply gravity
		self.velocity.y += PARTICLE_GRAVITY

		# Fade out over time. Adjust the existing Surface's alpha instead of
		# reallocating a new SRCALPHA Surface + redrawing the circle every
		# frame for every particle (cheap blit-flag change vs. an allocation
		# and draw call, and it now runs unconditionally instead of only
		# when collidable_tiles happens to be set).
		elapsed = pygame.time.get_ticks() / 1000 - self.born_time
		alpha = int(max(0.0, 255 * (1 - elapsed / self.life)))
		if self.image:
			self.image.set_alpha(alpha)

		# Handle wall collisions
		if collidable_tiles and self.rect:
			tiles_iter = collidable_tiles.iter_collidable_in_rect(self.rect, pad_pixels=0)
			for tile in tiles_iter:
				if self.rect.colliderect(tile.rect):
					# Simple bounce physics
					if abs(self.rect.right - tile.rect.left) < 5 or abs(self.rect.left - tile.rect.right) < 5:
						self.velocity.x *= -0.8  # Bounce with dampening
					if abs(self.rect.bottom - tile.rect.top) < 5 or abs(self.rect.top - tile.rect.bottom) < 5:
						self.velocity.y *= -0.8  # Bounce with dampening

		# Kill if lifetime is over
		if elapsed > self.life:
			self.kill()
