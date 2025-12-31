import random
from loguru import logger
from pygame.sprite import Sprite
# from pymunk import Vec2d
import pygame
from utils import get_cached_image, gen_randid, async_get_cached_image

class Upgrade(Sprite):
	def __init__(self, position, upgrade_id, upgradetype, life=10.0):
		super().__init__()
		if upgradetype == 20:
			self.image_name = 'data/heart.png'
		elif upgradetype == 21:
			self.image_name = 'data/newbomb2.png'
		elif upgradetype == 22:
			self.image_name = 'data/bombpwr.png'
		else:
			self.image_name = 'data/skull.png'
		self.upgradetype = upgradetype
		self.position = position
		self.scale = 1.0
		self.client_id = gen_randid()
		self.life = life
		self.original_life = life
		self.born_time = pygame.time.get_ticks() / 1000
		self.killed = False
		self.upgrade_id = upgrade_id
		self.id = upgrade_id

	def __repr__(self):
		return f'Upgrade {self.client_id} (type: {self.upgradetype} pos: {self.position} life: {self.life}  original_life: {self.original_life} born_time: {self.born_time} killed: {self.killed})'

	async def async_init(self):
		self.image = await async_get_cached_image(self.image_name, scale=float(self.scale), convert=True)
		if self.image:
			self.rect = self.image.get_rect()
			if self.rect:
				self.rect.topleft = self.position

	def upgrade_init(self):
		self.image = get_cached_image(self.image_name, scale=float(self.scale), convert=True)
		if self.image:
			self.rect = self.image.get_rect()
			if self.rect:
				self.rect.topleft = self.position

	def update(self, *args, **kwargs):
		elapsed = pygame.time.get_ticks() / 1000 - self.born_time
		# Kill if lifetime is over
		if elapsed > self.life:
			self.killed = True
			self.kill()

