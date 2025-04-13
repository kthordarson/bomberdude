import asyncio
import time
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import pygame
from utils import gen_randid

class Bomb(Sprite):
	def __init__(self, position, client_id, power=3, speed=10, timer=4, bomb_size=(10,10)):
		super().__init__()
		self.client_id = client_id
		# self.image = pygame.Surface(bomb_size)
		self.image = pygame.image.load('data/bomb5.png')
		self.rect = self.image.get_rect()
		self.position = Vec2d(position)
		self.timer = timer
		self.start_time = pygame.time.get_ticks() / 1000
		# self.rect.center = self.position
		self.rect.center = (int(self.position.x), int(self.position.y))
		self.exploded = False
		self.power = power

	def __repr__(self):
		return f'Bomb (pos: {self.position} )'

	def update(self, game_state):
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			# Create explosion particles if manager is provided
			if not self.exploded:
				game_state.explosion_manager.create_explosion(self.rect.center)
				game_state.explosion_manager.create_flames(self)
				self.exploded = True
			asyncio.create_task(self.explode(game_state))

	async def explode(self, gamestate):
		explosion_event = {
			"event_type": "bomb_exploded",
			"owner_id": self.client_id,
			"client_id": self.client_id,
			"position": (self.rect.x, self.rect.y),
			"event_time": time.time(),
			"handled": False,
			"event_id": gen_randid(),
		}
		await gamestate.event_queue.put(explosion_event)
		self.kill()
