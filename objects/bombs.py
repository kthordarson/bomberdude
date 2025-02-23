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
from utils import gen_randid
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY
from particles import Particle, Flame

class Bomb(Sprite):
	def __init__(self, image=None, scale=1.0, bomber=None, timer=1000, eventq=None):
		super().__init__()
		self.image = pygame.image.load(image)
		self.rect = self.image.get_rect()
		self.eventq = eventq
		self.bomber = bomber
		self.timer = timer

	def update(self, scene, eventq=None):
		if self.timer <= 0:
			for k in range(PARTICLE_COUNT):
				p = Particle()
				p.rect.center = self.rect.center
				scene.add(p)
			for k in ['left', 'right', 'up', 'down']:
				f = Flame(flamespeed=FLAME_SPEED, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.rect.center = self.rect.center
				scene.add(f)
			event = {'event_time': 0, 'event_type': 'bombxplode', 'bomber': self.bomber, 'eventid': gen_randid()}
			self.eventq.put(event)
			self.kill()
		else:
			self.timer -= BOMBTICKER

class BiggerBomb(Sprite):
	def __init__(self, image=None, scale=1.0, bomber=None, timer=1000, eventq=None):
		super().__init__()
		self.image = pygame.image.load(image)
		self.rect = self.image.get_rect()
		self.eventq = eventq
		self.bomber = bomber
		self.timer = timer

	def update(self, scene):
		if self.timer <= 0:
			for k in range(PARTICLE_COUNT * 2):
				p = Particle(xtra=3)
				p.rect.center = self.rect.center
				scene.add(p)
			for k in ['left', 'right', 'up', 'down']:
				f = Flame(flamespeed=FLAME_SPEED * 2, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.rect.center = self.rect.center
				scene.add(f)
			event = {'event_time': 0, 'event_type': 'bombxplode', 'bomber': self.bomber, 'eventid': gen_randid()}
			self.eventq.put(event)
			self.kill()
		else:
			self.timer -= BOMBTICKER
