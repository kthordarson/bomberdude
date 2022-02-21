import pygame, time
from pygame.sprite import Group, Sprite

from pygame.math import Vector2
from globals import BasicThing, Block, gen_randid, Bomb, Gamemap
from loguru import logger
import socket
from signal import signal, SIGPIPE, SIG_DFL 
from queue import Queue, Empty
from netutils import DataReceiver, DataSender, data_identifiers
from globals import ResourceHandler
from threading import Thread
from constants import *

class Player(BasicThing, Thread):
	def __init__(self, pos=None, dt=None, image=None):
		Thread.__init__(self, name='player')
		self.name = 'player'
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.client_id = None
		self.dt = dt
		self.rm = ResourceHandler()
		self.image, self.rect = self.rm.get_image(filename=image, force=False)
		self.pos = Vector2(pos)
		self.vel = Vector2(0, 0)
		self.accel = Vector2(0, 0)
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
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.send_pos_count = 0
		self.rq = Queue()
		self.sq = Queue()
		self.recv_thread = DataReceiver(r_socket=self.socket, queue=self.rq, name=self.name)
		self.send_thread = DataSender(s_socket=self.socket, queue=self.sq, name=self.name)
		self.connected = False
		self.gotmap = False
		self.kill = False
		self.dead = False
		self.net_players = {}
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')

	def __str__(self):
		return self.client_id

	def __repr__(self):
		return str(self.client_id)

	def connect_server(self):
		server = ('127.0.0.1', 6666)		
		logger.debug(f'connecting to {server}')
		self.socket.connect(server)
		self.recv_thread.daemon = True
		self.send_thread.daemon = True
		self.recv_thread.start()
		self.send_thread.start()
		self.connected = True
	
	def get_server_data(self):
		pass

	def get_server_blocks(self):
		self.sq.put_nowait((data_identifiers['request'], 'gameblocks'))

	def get_server_map(self):
		self.sq.put_nowait((data_identifiers['request'], 'gamemap'))

	def send_pos(self):
		self.send_pos_count += 1
		self.sq.put_nowait((data_identifiers['send_pos'], self.pos))
		# logger.debug(f'[{self.client_id}] send_pos {self.pos}')

	def get_net_players(self):
		return self.net_players

	def handle_data(self, data_id=None, payload=None):
		if data_id == -1:
			pass
		elif data_id == data_identifiers['sendyourpos']:
			self.sq.put_nowait_nowait((data_identifiers['posupdate'], self.pos))
		elif data_id == data_identifiers['debugdump'] or data_id == 16:
			pass
			# self.debugdump(payload)
		elif data_id == data_identifiers['nplpos']:
			pass
			# logger.debug(f'npl: {payload}')
		elif data_id == data_identifiers['bcastmsg']:
			logger.debug(f'bcastmsg: {payload}')
		elif data_id == data_identifiers['player']:
			playerid = payload.split(':')[0]
			playerpos = payload.split(':')[1]
			self.net_players[playerid] = playerpos
			logger.debug(f'[{self.client_id}] npl:{len(self.net_players)} got playerdata dataid: {data_id} payload: {payload} playerid:{playerid} playerpos:{playerpos}')
		elif data_id == data_identifiers['send_pos']:
			logger.debug(f'[{self.client_id}] got {data_id} {payload}')				
		elif data_id == data_identifiers['setclientid']:
			logger.debug(f'[{self.client_id}] got client_id dataid: {data_id} payload: {payload}')
			self.client_id = payload
			logger.debug(f'[{self.client_id}] client_id set')
		elif data_id == data_identifiers['gamemapgrid'] or data_id == 14:
			self.mapgrid = payload
			logger.debug(f'gotmapgrid: {len(self.mapgrid)} c:{self.connected}')
			self.connected = True
			self.gotmap = True
		else:
			# pass
			logger.error(f'[{self.client_id}] got unknown type: {type({data_id})} id: {data_id} payload: {payload}')
	
	def server_request(self, request=None):
		self.sq.put_nowait((data_identifiers['request'], request))

	def run(self):
		self.kill = False
		logger.debug(f'Player {self.client_id} start')
		while True:
			data_id = None
			payload = None
			if self.kill:
				logger.debug(f'player kill')
				break
			try:
				data_id, payload = self.rq.get_nowait()
			except Empty:
				pass
			if data_id:
				self.handle_data(data_id=data_id, payload=payload)
			self.send_pos()

	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.rect.centerx, self.rect.centery))
			bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=self, bomb_power=self.bomb_power, reshandler=self.rm)
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
