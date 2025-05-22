import pygame
from pygame.math import Vector2 as Vec2d

class Shockwave:
	def __init__(self, position, max_radius=150, duration=1.0, color=(255, 255, 255, 180), expansion_rate=None):
		"""
		Create a shockwave effect

		Args:
			position: Center position of the shockwave
			max_radius: Maximum radius the shockwave will expand to
			duration: Time in seconds for the wave to reach max radius
			color: RGBA color tuple with alpha for transparency
		"""
		self.position = Vec2d(position)
		self.max_radius = max_radius
		self.duration = duration
		self.color = color
		self.current_radius = 0
		self.life = 0
		self.alive = True

		# Use either provided expansion rate or calculate from duration
		if expansion_rate is not None:
			self.expansion_rate = expansion_rate
			self.duration = max_radius / expansion_rate
		else:
			self.duration = duration
			self.expansion_rate = max_radius / duration

	def update(self, delta_time):
		"""Update shockwave size and opacity"""
		if not self.alive:
			return

		self.life += delta_time
		self.current_radius = self.life * self.expansion_rate

		# Fade out as it expands
		alpha = max(0, int(255 * (1.0 - self.life / self.duration)))
		self.color = (*self.color[:3], alpha)
		# self.color = [k-k*0.1 for k in self.color]  # Reduce color intensity

		# Kill when duration exceeded
		if self.life >= self.duration:
			self.alive = False

	def draw(self, screen, camera):
		"""Draw the shockwave to the screen"""
		if not self.alive or self.current_radius <= 0:
			return

		# Create a surface for the shockwave with per-pixel alpha
		surf_size = int(self.current_radius * 2)
		if surf_size <= 0:
			return

		surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)

		# Draw the wave as a circle with a thin outline
		center = (surf_size // 2, surf_size // 2)
		thickness = max(1, int(self.current_radius * 0.07))  # Thin line, scales with radius
		pygame.draw.circle(surf, self.color, center, self.current_radius - thickness // 2, thickness)

		# Create a temporary rect for the shockwave position
		temp_rect = pygame.Rect(int(self.position.x - self.current_radius), int(self.position.y - self.current_radius), surf_size, surf_size)

		# Use the camera's apply method with our rect
		screen_pos = camera.apply(temp_rect)
		screen.blit(surf, screen_pos)
