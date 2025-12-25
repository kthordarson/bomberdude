from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from utils import get_cached_image

class Upgrade(Sprite):
	def __init__(self, upgradetype, image, position, scale, timer=1000, client_id='UpgradeBlock'):
		super().__init__()
		self.image_name = image
		self.upgradetype = upgradetype
		self.position = position
		self.timer = timer
		self.scale = scale
		self.client_id = client_id

	async def async_init(self):
		self.image = await get_cached_image(self.image_name, scale=float(self.scale), convert=True)
		self.rect = self.image.get_rect()
		self.rect.topleft = self.position

	def update(self):
		if self.timer <= 0:
			self.kill()
		else:
			self.timer -= 1
