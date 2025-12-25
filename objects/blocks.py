from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from utils import get_cached_image

class Upgrade(Sprite):
	async def __init__(self, upgradetype, image, position, scale, timer=1000):
		super().__init__()
		self.image = await get_cached_image(image, scale=float(scale), convert=True)
		self.rect = self.image.get_rect()
		self.upgradetype = upgradetype
		self.position = position
		self.rect.topleft = self.position
		self.timer = timer

	def update(self):
		if self.timer <= 0:
			self.kill()
		else:
			self.timer -= 1
