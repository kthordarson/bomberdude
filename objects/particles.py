from dataclasses import dataclass, field
import asyncio
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import orjson as json
import math
import pygame
import random
import time
from utils import gen_randid
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY

class Particle(Sprite):
	def __init__(self, my_list=None, xtra=0):
		super().__init__()
		color = (123,123,123)  # random.choice(PARTICLE_COLORS)
		self.image = pygame.Surface((PARTICLE_RADIUS * 2, PARTICLE_RADIUS * 2), pygame.SRCALPHA)
		pygame.draw.circle(self.image, color, (PARTICLE_RADIUS, PARTICLE_RADIUS), PARTICLE_RADIUS)
		self.rect = self.image.get_rect()
		speed = random.random() * PARTICLE_SPEED_RANGE + PARTICLE_MIN_SPEED
		direction = random.randrange(360)
		self.change_x = math.sin(math.radians(direction)) * speed + xtra
		self.change_y = math.cos(math.radians(direction)) * speed + xtra
		self.my_alpha = 255
		self.my_list = my_list

	def update(self):
		if self.my_alpha <= 0:
			self.kill()
		else:
			self.my_alpha -= PARTICLE_FADE_RATE
			self.image.set_alpha(self.my_alpha)
			self.rect.x += self.change_x
			self.rect.y += self.change_y
			self.change_y -= PARTICLE_GRAVITY

class oldFlame(Sprite):
	def __init__(self, flamespeed=10, timer=3000, direction='', bomber=None):
		super().__init__()
		self.image = pygame.Surface((FLAMEX, FLAMEY))
		self.image.fill((255, 165, 0))  # ORANGE equivalent
		self.rect = self.image.get_rect()
		self.bomber = bomber
		self.speed = flamespeed
		self.timer = timer
		self.direction = direction
		if self.direction == 'left':
			self.change_y = 0
			self.change_x = -self.speed
		if self.direction == 'right':
			self.change_y = 0
			self.change_x = self.speed
		if self.direction == 'up':
			self.change_y = -self.speed
			self.change_x = 0
		if self.direction == 'down':
			self.change_y = self.speed
			self.change_x = 0

	def update(self):
		if self.timer <= 0:
			self.kill()
		else:
			self.timer -= FLAME_RATE
			self.rect.x += self.change_x
			self.rect.y += self.change_y

