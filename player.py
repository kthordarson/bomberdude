import pygame
from pygame.sprite import Sprite
import socket
from pygame.math import Vector2
from globals import BasicThing, Block, gen_randid, Bomb
from loguru import logger
from signal import SIGPIPE, SIG_DFL 
from queue import Empty
from netutils import data_identifiers, DataSender, DataReceiver, get_ip_address
from globals import ResourceHandler
from threading import Thread, Event
from constants import *

class Player(BasicThing, Thread):
	def __init__(self, pos=None, image=None, client_id=None, stop_event=None):
		Thread.__init__(self, daemon=True, args=(stop_event,))
		if not client_id:
			self.client_id = gen_randid()
		else:
			self.client_id = client_id
		self.name = f'player{self.client_id}'
		BasicThing.__init__(self, pos, image)
		# Sprite.__init__(self)
		self.rm = ResourceHandler()
		image, rect = self.rm.get_image(filename=image, force=False)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(image, self.size)
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
		self.send_pos_count = 0
		self.kill = False
		self.dead = False
		self.gotmap = False
		self.connected = False
		self.net_players = {}
		self.cnt_sq_request = 0
		self.cnt_sq_sendyourpos = 0
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.kill = False
		self.server = ('192.168.1.122', 6666)
		self.localaddr = (get_ip_address()[0], 6669)
		self.connected = False
		self.ds = DataSender(s_socket=self.socket, server=self.server, name=self.client_id, stop_event=stop_event)
		self.dr = DataReceiver(r_socket=self.socket, server=self.server, localaddr=self.localaddr, name=self.client_id, stop_event=stop_event)
		self.pos = Vector2(pos)
		self.kill = False
		logger.debug(f'[p] client:{self} init pos:{pos} ')

	def __str__(self):
		return f'[player] {self.client_id}' #self.client_id

	def __repr__(self):
		return f'[player] id:{self.client_id} pos:{self.pos}' #str(self.client_id)

	def cmd_handler(self):
		pass

	def connect_to_server(self):
		# newclient clmsgid:clid clid:3d38a632df clmsg:connect
		try:
			self.socket.connect(self.server)
			self.dr.start()
			self.ds.start()
			self.sendmsg(msgid=1, msgdata='connect')
			logger.debug(f'[c-{self.client_id}] connecting s:{self.socket} sq:{self.ds.queue.qsize()} rq;{self.dr.queue.qsize()}')
		except ConnectionRefusedError as e:
			logger.warning(f'[c-{self.client_id}] {e}')
			self.connected = False
			return False
		
	def sendmsg(self, msgid=None, msgdata=None):
		data = f'{msgid}:{self.client_id}:{msgdata}'.encode('utf-8')
		self.ds.queue.put(data)
		# logger.debug(f'[sendtoq] m:{msgdata} d:{data} sq:{self.ds.queue.qsize()} rq:{self.dr.queue.qsize()}')

	def handle_incoming(self, data):		
		# clmsgid, clid, clmsg = data.split(':')
		msgid, clid, msgdata = None, None, None
		if data:
			try:
				datamsg, addr = data
			except ValueError:
				logger.error(f'[c-{self.client_id}] {e} {data} from {addr}')
				#msgid, clid = data
			try:
				msgid, clid, msgdata = datamsg.decode('utf-8').split(':')
			except ValueError as e:
				logger.warning(f'[c-{self.client_id}] {e} {data} from {addr}')
			if msgid:
				msgid = int(msgid)
				if msgid == 11:
					if msgdata == 'connectsuccess':
						self.connected = True
					else:
						self.connected = False
					logger.debug(f'[c-{self.client_id}] conn {self.connected} m:{msgdata} from {addr}')
				if msgid == 22:
					pass
					#logger.debug(f'[c] msgid:{msgid} clid:{clid} msgdata:{msgdata}')
				else:
					logger.debug(f'[c] msgid:{msgid} clid:{clid} msgdata:{msgdata}')

	def get_pos(self):
		#logger.debug(f'[p] get_pos() {self.pos}')
		return self.pos

	def runxx(self):
		logger.debug(f'[testclient] run id:{self.client_id} conn:{self.connected} sq:{self.ds.queue.qsize()} rc:{self.dr.queue.qsize()}')
		while True:
			playerpos = self.get_pos()
			# logger.debug(f'[testclient] sendpos:{playerpos} {self.playerone.pos}')
			#self.sendmsg(msgid=22, msgdata='pingfromclient')
			self.sendmsg(msgid=5, msgdata=self.pos)
			if self.kill:
				logger.debug(f'[testclient] id:{self.client_id} kill')
				self.ds.kill = True
				logger.debug(f'[testclient] id:{self.client_id} dskill {self.ds}')
				self.dr.kill = True
				logger.debug(f'[testclient] id:{self.client_id} drkill {self.dr}')
				break
			incoming = None
			outgoing = None
			if not self.dr.queue.empty():
				incoming = self.dr.queue.get()
				self.handle_incoming(data=incoming)
				# logger.debug(f'[c] incoming from  recvq:{incoming}')
				self.dr.queue.task_done()

	def runx(self):
		self.kill = False
		logger.debug(f'[p]{self.client_id} start ')
		while True:
			if self.kill:
				logger.debug(f'[pk] self.kill:{self.kill}')
				break

	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.rect.centerx, self.rect.centery))
			bomb = Bomb(pos=bombpos, bomber_id=self, bomb_power=self.bomb_power, reshandler=self.rm)
			# self.bombs.add(bomb)
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
		self.sendmsg(msgid=5, msgdata=self.pos)
		incoming = None
		outgoing = None
		if not self.dr.queue.empty():
			incoming = self.dr.queue.get()
			self.handle_incoming(data=incoming)
			# logger.debug(f'[c] incoming from  recvq:{incoming}')
			self.dr.queue.task_done()

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
