from dataclasses import dataclass, field
import asyncio
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import json
import math
import pygame
import random
import time
from utils import gen_randid, load_image
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY

class Bomb(Sprite):
	def __init__(self, position, speed=10, timer=3, bomb_size=(10,10)):
		super().__init__()
		# self.image = pygame.Surface(bomb_size)
		self.image = pygame.image.load('data/bomb.png')
		self.rect = self.image.get_rect()

		# self.image, self.rect = load_image('data/bomb.png')
		# self.image.fill((255, 0, 0))
		self.position = Vec2d(position)
		# self.rect = self.image.get_rect(center=self.position)
		self.timer = timer
		self.start_time = pygame.time.get_ticks() / 1000
		self.rect.topleft = self.position

	def __repr__(self):
		return f'Bomb (pos: {self.position} )'

	def update(self):
		# print(f'[pu] {dt  - self.start_time} {self.timer}')
		if pygame.time.get_ticks() / 1000 - self.start_time >= self.timer:
			logger.info(f'{self} BOOM!')
			self.kill()
