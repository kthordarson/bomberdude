import hashlib
import math
import os
import random
import sys
import time
from threading import Thread, Event, Event
# from multiprocessing import Queue
import pygame
import pygame.locals as pl
from pygame.sprite import Group, spritecollide, Sprite
from loguru import logger
from pygame.math import Vector2

from constants import BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, GRIDSIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID


def random_velocity(direction=None):
	while True:
		vel = Vector2((random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0)))
		if direction == "left":
			vel.x = random.uniform(-3.0, -1)
		if direction == "right":
			vel.x = random.uniform(1, 3.0)
		if direction == "down":
			vel.y = random.uniform(1, 3.0)
		if direction == "up":
			vel.y = random.uniform(-3.0, -1)
		if vel.y != 0 and vel.x != 0:
			return vel
		else:
			logger.debug(f"[vel] {vel}")


def rot_center(image, rect, angle):
	"""rotate an image while keeping its center"""
	rot_image = pygame.transform.rotate(image, angle)
	rot_rect = rot_image.get_rect(center=rect.center)
	return rot_image, rot_rect


def get_entity_angle(e_1, e_2):
	dif_x = e_2.x - e_1.x
	dif_y = e_2.y - e_1.y
	return math.atan2(dif_y, dif_x)


def get_angle(pos_1, pos_2):
	dif_x = pos_2[0] - pos_1[0]
	dif_y = pos_2[1] - pos_1[1]
	return math.atan2(dif_y, dif_x)




def load_image(name, colorkey=None):
	fullname = os.path.join("data", name)
	image = pygame.image.load(fullname)
	# image = image.convert()
	return image, image.get_rect()


class ResourceHandler:
	def __init__(self):
		self.name = 'ResourceHandler'
		self.__images = {}

	def get_image(self, filename=None, force=False):
		if force or filename not in list(self.__images.keys()):
			img = pygame.image.load(filename)
			rect = img.get_rect()
			self.__images[filename] = (img, rect)
			return img, rect
		else:
			return self.__images[filename]


def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


def stop_all_threads(threads):
	logger.debug(f'stopping {threads}')
	for t in threads:
		logger.debug(f'waiting for {t}')
		t.kill = True
		t.join(0)
	sys.exit()


def start_all_threads(threads):
	logger.debug(f'starting {threads}')
	for t in threads:
		logger.debug(f'start {t}')
		t.run()

