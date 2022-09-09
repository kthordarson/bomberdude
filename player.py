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
from testclient import BombClient

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
		self.kill = False
		#self.connected = False
		self.netplayers = []
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

	def cmd_handler(self):
		pass

	def get_netdebug(self):
		debugdata = '' #  {'connatts': self.conn_atts, 'dsq':self.ds.queue.qsize(), 'drq':self.dr.queue.qsize(), 'dspkt':self.ds.sendpkts, 'drpkt':self.dr.rcvpkts}
		return debugdata

	def run(self):
		# self.ds.start()
		# self.dr.start()
		# self.socket.settimeout(2)
		while True:
			if self.connected:
				self.sendmsg(msgid=5, msgdata=self.pos)
			else:
				self.connect_to_server()
			incoming = None
			outgoing = None
			if not self.dr.queue.empty():
				incoming = self.dr.queue.get()
				self.handle_incoming(data=incoming)
				# logger.debug(f'[c] incoming from  recvq:{incoming}')
				self.dr.queue.task_done()

	def connect_to_server(self):
		self.conn_atts += 1
		if self.conn_atts < 10:
			self.sendmsg(msgid=1, msgdata='connect')			
			logger.debug(f'[p] {self} connect attempt {self.conn_atts}')
		else:
			time.sleep(1)
			logger.warning(f'[p] {self} connect attempt {self.conn_atts}')

	def get_server_info(self):
		reqmsg = 'getserverinfo'
		self.sendmsg(msgid=155, msgdata=reqmsg)

	def refresh_netplayers(self):
		reqmsg = 'getnetplayers'
		self.sendmsg(msgid=6, msgdata=reqmsg)

	def sendmsg(self, msgid=None, msgdata=None):
		data = f'{msgid}:{self.client_id}:{msgdata}'.encode('utf-8')
		self.ds.queue.put(data)
		# logger.debug(f'[sendtoq] m:{msgdata} d:{data} sq:{self.ds.queue.qsize()} rq:{self.dr.queue.qsize()}')

	def handle_incoming(self, data):		
		# clmsgid, clid, clmsg = data.split(':')
		msgid, clid, msgdata = None, None, None
		if data:
			# logger.deubg(data)
			try:
				datamsg, addr = data
			except ValueError:
				logger.error(f'[c-{self.client_id}] {e} {data} from {addr} len:{len(data)} type:{type(data)}')
				#msgid, clid = data
			try:
				msgid, clid, msgdata, *_ = datamsg.decode('utf-8').split(':')
			except ValueError as e:
				logger.warning(f'[c-{self.client_id}] {e} {data} from {addr} len:{len(data)} type:{type(data)}')
			if msgid:
				msgid = int(msgid)
				if msgid == 156:
					# serverinfo = pickle.loads(msgdata)
					logger.debug(f'[c-{self.client_id}] msgdata:{msgdata} d:{data}')
				if msgid == 7:
					print(msgid)
					# netplayers todo fixme
					try:
						logger.debug(f'[c-{self.client_id}] netplayer m:{msgid} clid:{clid} m:{msgdata} from {addr} ')
					except ValueError as e:
						logger.error(f'[c-{self.client_id}] {e} d:{data} dmsg:{datamsg} from {addr} len:{len(data)} type:{type(data)}')
				if msgid == 11:
					logger.debug(f'[c-{self.client_id}] m:{msgid} clid:{clid} m:{msgdata} from {addr} ')
					if 'connectsuccess' in msgdata:
						# self.ds.start()
						# self.dr.start()
						self.connected = True
						# self.ds.update_server(server_addr=self.server[0], server_port=6667)
						logger.debug(f'[c-{self.client_id}] conn {self.connected} m:{msgdata} from {addr}')
				if msgid == 22:
					self.connected = True
					#logger.debug(f'[c] msgid:{msgid} clid:{clid} msgdata:{msgdata}')
				else:
					pass
					#logger.debug(f'[c] msgid:{msgid} clid:{clid} msgdata:{msgdata}')

	def get_pos(self):
		#logger.debug(f'[p] get_pos() {self.pos}')
		return self.pos


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



