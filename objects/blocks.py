from numpy._core.defchararray import center
import random
from loguru import logger
from pygame.sprite import Sprite
from pygame.math import Vector2 as Vec2d
# from pymunk import Vec2d
import pygame
from utils import get_cached_image, gen_randid, async_get_cached_image
from constants import BLOCK

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

		tile_x = (int(position[0]) // BLOCK) * BLOCK + BLOCK // 2
		tile_y = (int(position[1]) // BLOCK) * BLOCK + BLOCK // 2
		self.position = Vec2d(tile_x, tile_y)

		# self.position = (int(position[0]), int(position[1]))
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
				self.rect.center = (int(self.position[0]), int(self.position[1]))

	def upgrade_init(self):
		self.image = get_cached_image(self.image_name, scale=float(self.scale), convert=True)
		if self.image:
			self.rect = self.image.get_rect()
			if self.rect:
				self.rect.center = (int(self.position[0]), int(self.position[1]))

	def update(self, *args, **kwargs):
		elapsed = pygame.time.get_ticks() / 1000 - self.born_time
		# Kill if lifetime is over
		new_scale = max(0.1, self.scale * (1 - elapsed / self.original_life))
		self.image = get_cached_image(self.image_name, scale=float(new_scale), convert=True)
		if self.image:
			self.rect = self.image.get_rect(center=(int(self.position[0]), int(self.position[1])))
			if self.rect:
				self.rect.center = (int(self.position[0]), int(self.position[1]))
				# self.scale = new_scale
		if elapsed > self.life:
			self.killed = True
			self.kill()

