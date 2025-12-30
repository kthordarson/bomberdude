import random
from loguru import logger
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from utils import get_cached_image, gen_randid

class Upgrade(Sprite):
	def __init__(self, position, upgrade_id, life=10.0):
		super().__init__()
		self.image_name = 'data/heart.png'
		self.upgradetype = random.choice(['default', 'speed', 'power', 'range', 'extra_bomb'])
		self.position = position
		self.scale = 1.0
		self.client_id = gen_randid()
		self.life = life
		self.original_life = life
		self.born_time = pygame.time.get_ticks() / 1000
		self.killed = False
		self.id = upgrade_id

	def __repr__(self):
		return f'Upgrade {self.client_id} (type: {self.upgradetype} pos: {self.position} life: {self.life}  original_life: {self.original_life} born_time: {self.born_time})'

	async def async_init(self):
		self.image = await get_cached_image(self.image_name, scale=float(self.scale), convert=True)
		self.rect = self.image.get_rect()
		self.rect.topleft = self.position

	def update(self):
		elapsed = pygame.time.get_ticks() / 1000 - self.born_time
		# Kill if lifetime is over
		if elapsed > self.life:
			self.killed = True
			self.kill()

