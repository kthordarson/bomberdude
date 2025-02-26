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
