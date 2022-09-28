import time
import pygame
from pygame.sprite import Sprite
import socket
from pygame.math import Vector2
from things import BasicThing, Block, Bomb
from loguru import logger
from signal import SIGPIPE, SIG_DFL
# from netutils import dataid, DataSender, DataReceiver, get_ip_address
from globals import ResourceHandler, gen_randid
from threading import Thread, Event
from constants import *
import pickle
from network import send_data, receive_data, dataid
# from multiprocessing import Queue
from queue import Full

class Player(BasicThing, Thread):
	def __init__(self, pos=None, visible=False, mainqueue=None):
		Thread.__init__(self, daemon=True)
		BasicThing.__init__(self, pos)
		self.mainqueue = mainqueue
		self.visible = visible
		self.client_id = gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.image = pygame.image.load('data/playerone.png')
		self.pos = pos
		self.rect = self.image.get_rect(center=self.pos)
		self.speed = 3


	# def run(self):
	# 	self.visible = True
	# 	logger.debug(f'[player] run c:{self.connected}')
	# 	while True:
	# 		if self.connected:
	# 			self.mainqueue.put_nowait({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos})

	def bombdrop(self):
		pass

	def update(self):
		self.pos += self.vel
		self.rect.center = self.pos
		if self.connected:
			self.mainqueue.put_nowait({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos})

	def take_powerup(self, powerup=None):
		pass

	def add_score(self):
		self.score += 1
