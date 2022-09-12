import time
import pygame
from pygame.sprite import Sprite
import socket
from pygame.math import Vector2
from things import BasicThing, Block, Bomb
from loguru import logger
from signal import SIGPIPE, SIG_DFL
from queue import Empty
from netutils import data_identifiers, DataSender, DataReceiver, get_ip_address
from globals import ResourceHandler, gen_randid
from threading import Thread, Event
from constants import *
import pickle
from testclient import BombClient, DummyBombClient

class Player(BasicThing, Thread):
	def __init__(self, pos=None, image=None, client_id=None, stop_event=None, is_dummy=False, visible=False):
		Thread.__init__(self, daemon=True, args=(stop_event,))
		self.is_dummy = is_dummy
		self.visible = visible
		if not client_id:
			self.client_id = gen_randid()
		else:
			self.client_id = client_id
		self.name = f'player{self.client_id}'
		BasicThing.__init__(self, pos, image)
		self.rm = ResourceHandler()
		self.image, self.rect = self.rm.get_image(filename=image, force=False)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 15
		self.speed = 5
		self.health = 100
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.kill = False
		#self.connected = False
		self.netplayers = []
		if self.is_dummy:
			self.bombclient = DummyBombClient(name=self.client_id)
		else:
			self.bombclient = BombClient(name=self.client_id)
		#self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		#self.server = ('192.168.1.122', 6666)
		#self.localaddr = (get_ip_address()[0], 6669)
		#self.ds = DataSender(s_socket=self.socket, server=self.server, name=self.client_id, stop_event=stop_event)
		#self.dr = DataReceiver(r_socket=self.socket, server=self.server, localaddr=self.localaddr, name=self.client_id, stop_event=stop_event)
		#self.pos = Vector2(pos)
		#self.conn_atts = 0
		logger.debug(f'[p] client:{self} init pos:{pos} ')

	def __str__(self):
		return f'[player] {self.client_id}' #self.client_id

	def __repr__(self):
		return f'[player] id:{self.client_id} pos:{self.pos}' #str(self.client_id)

	def draw(self, screen):
		if self.visible:
			screen.blit(self.image, self.pos)

	def cmd_handler(self):
		pass

	def get_netdebug(self):
		debugdata = '' #  {'connatts': self.conn_atts, 'dsq':self.ds.queue.qsize(), 'drq':self.dr.queue.qsize(), 'dspkt':self.ds.sendpkts, 'drpkt':self.dr.rcvpkts}
		return debugdata

	def run(self):
		self.visible = True
		while True:
			if self.bombclient.connected:
				self.bombclient.sendmsg(msgid=5, msgdata=(self.pos.x, self.pos.y))
			else:
				pass
				#self.bombclient.connect_to_server()

	def connect_to_server(self):
		pass

	def get_server_info(self):
		reqmsg = 'getserverinfo'
		self.bombclient.sendmsg(msgid=155, msgdata=reqmsg)

	def refresh_netplayers(self):
		reqmsg = 'getnetplayers'
		self.bombclient.sendmsg(msgid=6, msgdata=reqmsg)

	def sendmsg(self, msgid=None, msgdata=None):
		pass

	def handle_incoming(self, data):
		pass
	def get_pos(self):
		#logger.debug(f'[p] get_pos() {self.pos}')
		return self.pos


	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.pos.x+PLAYERSIZE[0]//2, self.pos.y+PLAYERSIZE[1]//2))
			bomb = Bomb(pos=bombpos, bomber_id=self, bomb_power=self.bomb_power, reshandler=self.rm)
			self.bombs_left -= 1
			return bomb
		else:
			return 0

	def update(self, blocks):
		# self.vel += self.accel
		oldy = self.rect.y
		oldx = self.rect.x
		self.pos.x += self.vel.x
		self.pos.y += self.vel.y
		self.rect.x = self.pos.x
		self.rect.y = self.pos.y
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			if isinstance(block, Block):
				if self.vel.x != 0 and self.vel.y != 0 and block.solid:
					self.vel.x = 0
					self.vel.y = 0
					self.rect.x = oldx
					self.rect.y = oldy
					break
				if self.vel.x > 0 and block.solid:
					self.rect.right = block.rect.left
					self.vel.x = 0
				if self.vel.x < 0 and block.solid:
					self.rect.left = block.rect.right
					self.vel.x = 0
				if self.vel.y > 0 and block.solid:
					self.rect.bottom = block.rect.top
					self.vel.y = 0
				if self.vel.y < 0 and block.solid:
					self.rect.top = block.rect.bottom
					self.vel.y = 0
				#elif self.vel.x != 0 and self.vel.y != 0:
				#	self.vel.x = 0
				#	self.vel.y = 0
		self.pos.y = self.rect.y
		self.pos.x = self.rect.x

	def take_powerup(self, powerup=None):
		# pick up powerups...
		if powerup == 1:
			if self.max_bombs < 10:
				self.max_bombs += 1
				self.bombs_left += 1
		if powerup == 2:
			pass
			#self.speed += 1
		if powerup == 3:
			self.bomb_power += 10

	def add_score(self):
		self.score += 1


class DummyPlayer(BasicThing, Thread):
	def __init__(self, pos=None, image=None, client_id=None, stop_event=None, is_dummy=True):
		Thread.__init__(self, daemon=True, args=(stop_event,))
		self.is_dummy = is_dummy
		if not client_id:
			self.client_id = gen_randid()
		else:
			self.client_id = client_id
		self.name = f'dummyplayer{self.client_id}'
		BasicThing.__init__(self, pos, image)
		# Sprite.__init__(self)
		self.rm = ResourceHandler()
		self.image, self.rect = self.rm.get_image(filename=image, force=False)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 15
		self.speed = 5
		self.health = 100
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.kill = False
		self.netplayers = []
		if self.is_dummy:
			self.bombclient = DummyBombClient(name=self.client_id)
		else:
			self.bombclient = BombClient(name=self.client_id)
		logger.debug(f'[p] client:{self} init pos:{pos} ')

	def __str__(self):
		return f'[dummyplayer] {self.client_id}' #self.client_id

	def __repr__(self):
		return f'[dummyplayer] id:{self.client_id} pos:{self.pos}' #str(self.client_id)

	def cmd_handler(self):
		pass

	def get_netdebug(self):
		debugdata = ''
		return debugdata

	def run(self):
		while True:
			pass

	def connect_to_server(self):
		pass

	def get_server_info(self):
		pass

	def refresh_netplayers(self):
		pass

	def sendmsg(self, msgid=None, msgdata=None):
		pass

	def handle_incoming(self, data):
		pass

	def get_pos(self):
		return self.pos

	def bombdrop(self):
		return 0

	def update(self, blocks):
		pass

	def take_powerup(self, powerup=None):
		pass

	def add_score(self):
		self.score += 1


