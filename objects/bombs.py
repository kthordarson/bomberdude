import asyncio
import time
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import pygame
from utils import gen_randid, get_cached_image
from constants import BLOCK

class Bomb(Sprite):
	def __init__(self, position, client_id, power=3, speed=10, timer=4, bomb_size=(10,10)):
		super().__init__()
		self.client_id = client_id
		# self.image = pygame.Surface(bomb_size)
		self.image = get_cached_image('data/bomb5.png', convert=True)
		self.rect = self.image.get_rect()
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
		self.rect.center = (int(self.position.x), int(self.position.y))

		self.exploded = False
		self.power = power

	def __repr__(self):
		return f'Bomb (pos: {self.position} )'

	def update(self, game_state):
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			# Create explosion particles if manager is provided
			if not self.exploded:
				game_state.explosion_manager.create_explosion(self.rect.center, count=2)
				game_state.explosion_manager.create_flames(self)
				self.exploded = True
			asyncio.create_task(self.explode(game_state))

	async def explode(self, gamestate):
		explosion_event = {
			"event_type": "bomb_exploded",
			"owner_id": self.client_id,
			"client_id": self.client_id,
			"position": self.rect.center,  # Use center instead of top-left
			"event_time": time.time(),
			"handled": False,
			"event_id": gen_randid(),
		}
		# Apply locally so the owner immediately gets bomb capacity back
		try:
			if hasattr(gamestate, "update_game_event"):
				await gamestate.update_game_event(explosion_event)
		except Exception:
			pass
		await gamestate.event_queue.put(explosion_event)
		self.kill()
