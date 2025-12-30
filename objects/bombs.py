import asyncio
from loguru import logger
import time
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import pygame
from utils import gen_randid, get_cached_image, async_get_cached_image
from constants import BLOCK

class Bomb(Sprite):
	def __init__(self, position, client_id, power=3, speed=10, timer=4, bomb_size=(10,10)):
		super().__init__()
		self.client_id = client_id
		# self.image = pygame.Surface(bomb_size)
		# self.position = Vec2d(position)
		self.timer = timer
		self.start_time = pygame.time.get_ticks() / 1000
		# self.rect.center = self.position
		# Ensure position is centered on a map tile.
		# IMPORTANT: snapping must use the actual tile size (BLOCK), not a scaled sprite size.
		tile_size = BLOCK
		tile_x = (int(position[0]) // tile_size) * tile_size + tile_size // 2
		tile_y = (int(position[1]) // tile_size) * tile_size + tile_size // 2
		self.position = Vec2d(tile_x, tile_y)
		self.exploded = False
		self.power = power

	async def async_init(self):
		self.image = await async_get_cached_image('data/bomb5.png', convert=True)
		if self.image:
			self.rect = self.image.get_rect()
		if self.rect:
			self.rect.center = (int(self.position.x), int(self.position.y))

	def __repr__(self):
		return f'Bomb (pos: {self.position} )'

	def update(self, *args, **kwargs):
		game_state = None
		if args:
			game_state = args[0]
		elif 'game_state' in kwargs:
			game_state = kwargs['game_state']
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			# Create explosion particles if manager is provided
			if not self.exploded and game_state and game_state.explosion_manager and self.rect:
				game_state.explosion_manager.create_explosion(self.rect.center, count=2)
				game_state.explosion_manager.create_flames(self)
				self.exploded = True
			asyncio.create_task(self.explode(game_state))

	async def explode(self, gamestate):
		explosion_event = {
			'event_type': "bomb_exploded",
			"owner_id": self.client_id,
			"client_id": self.client_id,
			"position": self.rect.center if self.rect else (int(self.position.x), int(self.position.y)),  # Use center instead of top-left
			"event_time": time.time(),
			"handled": False,
			"event_id": gen_randid(),
		}
		# Apply locally so the owner immediately gets bomb capacity back
		await gamestate.update_game_event(explosion_event)
		self.kill()
