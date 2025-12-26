import random
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from utils import get_cached_image

class Upgrade(Sprite):
	def __init__(self, position, life=1.0, client_id='UpgradeBlock', upgradetype=None):
		super().__init__()
		self.image_name = 'data/newbomb.png'
		self.upgradetype = upgradetype or random.choice(['default', 'speed', 'power', 'range'])
		self.position = position
		self.scale = 1.0
		self.client_id = client_id
		self.life = life
		self.original_life = life
		self.born_time = pygame.time.get_ticks() / 1000

	async def async_init(self):
		self.image = await get_cached_image(self.image_name, scale=float(self.scale), convert=True)
		self.rect = self.image.get_rect()
		self.rect.topleft = self.position

	def update(self):
		elapsed = pygame.time.get_ticks() / 1000 - self.born_time
		# Kill if lifetime is over
		if elapsed > self.life:
			self.kill()

