import time
import pygame
from pygame.sprite import Sprite
import socket
from pygame.math import Vector2
from globals import BasicThing, Block, Bomb
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
from bclient import BombClient

class Player(BasicThing, Thread):
	def __init__(self, pos=None, visible=False, mainqueue=None):
		Thread.__init__(self, daemon=True)
		self.image = pygame.image.load('data/playerone.png')
		BasicThing.__init__(self, pos, self.image)
		self.mainqueue = mainqueue
		self.visible = visible
		self.client_id = gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.pos = pos
		self.rect = self.image.get_rect(center=self.pos)
		self.speed = 3
		self.client = BombClient(client_id=self.client_id, serveraddress='127.0.0.1', serverport=9696, mainqueue=self.mainqueue)
		self.gotmap = False

	def start_client(self):
		self.client.start()

	def bombdrop(self):
		pass

	def update(self):
		self.client.pos = (self.pos[0], self.pos[1])
		self.pos += self.vel
		self.rect.center = self.pos
		if self.connected:
			self.client.send_pos((self.pos[0], self.pos[1]))
			if not self.gotmap:
				if self.client.gotmap:
					self.mainqueue.put_nowait({'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':self.client.gamemapgrid})
					self.gotmap = True
					logger.debug(f'[{self}] gotmap:{self.gotmap} grid:{len(self.client.gamemapgrid)}')


	def take_powerup(self, powerup=None):
		pass

	def add_score(self):
		self.score += 1
