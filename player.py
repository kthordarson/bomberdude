from multiprocessing import dummy
import time
import pygame
from pygame.sprite import Group
import pickle
from pygame.sprite import Group

from pygame.math import Vector2
from globals import BasicThing, load_image, PLAYERSIZE, Block, gen_randid, Bomb, Gamemap
from loguru import logger
from threading import Thread
import socket
from queue import Queue
from netutils import receive_data, send_data, DataReceiver, DataSender, data_identifiers
from globals import StoppableThread
class DummyPlayer(BasicThing):
	def __init__(self, dummy_id=-1, pos=Vector2(300,300), image='dummyplayer.png'):
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.dummy_id = dummy_id
		self.pos = pos
		self.image = image
		self.image, self.rect = load_image(image, -1)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y

	def draw(self, screen):
		screen.blit(self.image, self.pos)


class Player(BasicThing, StoppableThread):
	def __init__(self, pos, dt, image):
		StoppableThread.__init__(self)
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		self.client_id = gen_randid()
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.dt = dt
		self.image, self.rect = load_image(image, -1)
		if pos is None:
			self.pos = Vector2(300, 300)
		else:
			self.pos = Vector2(pos)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 15
		self.speed = 1
		self.health = 100
		self.dead = False
		self.score = 0
		self.font = pygame.font.SysFont("calibri", 10, True)
		self.connected = False
		self.game_ready = False
		self.network_updates = []
		self.server = ('127.0.0.1', 6666)
		self.ticks = 0
		self.pingcount = 0
		self.pongcount = 0
		self.maxping = 10
		self.buffersize = 9096
		self.kill = False
		self.net_players = {}
		self.recv_thread = None
		self.blocks = Group()
		self.gamemap = Gamemap()
		self.connected = False
		self.rq = Queue()
		self.sq = Queue()
		self.recv_thread = DataReceiver(self.socket, self.rq)
		self.send_thread = DataSender(self.socket, self.sq)
		self.recv_thread.daemon = True
		self.send_thread.daemon = True
		self.heartbeat = False
		self.dummies = Group()
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')

	def process_recvq(self):
		if not self.rq.empty():
			data_id, payload = self.rq.get()
			# logger.debug(f'recv q {data_id} size: {len(payload)} {type(payload)}')
			if data_id == data_identifiers['data']:
				#logger.debug(f'recv q {data_id} pl:{payload}')
				#logger.debug(f'recv q {data_id} size: {len(payload["blocks"])} {type(payload["blocks"])} {type(payload["mapgrid"])}')
				self.blocks = payload['blocks']
				self.gamemap.grid = payload['mapgrid']
				# self.rq.task_done()
				# return
			if data_id == data_identifiers['heartbeat']:
				logger.debug(f'recvHB q {data_id} {payload}')
				# self.rq.task_done()
				# return
			if data_id == data_identifiers['player']:
				logger.debug(f'[{self.client_id}] dataid:{data_id} {payload}')
				clid = [k for k in payload.keys()][0][0]
				#if clid != self.client_id:
				clpos = [k for k in payload.values()][0]
				self.net_players[clid] = clpos			
				if clid in self.net_players:
					self.net_players[clid] = clpos
					for dp in self.dummies:
						if dp.dummy_id == clid:
							dp.pos = clpos
							logger.debug(f'[{self.client_id}] update dummy clid:{clid} clpos:{clpos} np:{len(self.net_players)} du:{len(self.dummies)}')
				else:
					d = DummyPlayer(dummy_id=clid, pos=clpos)
					self.dummies.add(d)
					self.net_players[d.dummy_id] = clpos
					logger.debug(f'[{self.client_id}] new dummyid: {d.dummy_id} pos:{d.pos} np:{len(self.net_players)} du:{len(self.dummies)}')
				#self.rq.task_done()
				#return
			# else:
			# 	logger.error(f'unknown data id:{data_id} p:{payload}')
			# 	# logger.debug(f'recv netpl {data_id} {payload}')
			# 	#self.rq.task_done()
			# 	return

	def run(self):
		self.connect_to_server()
		while True:
			if self.kill or self.socket.fileno() == -1:
				self.socket.close()
				break
			self.process_recvq()
			if self.heartbeat:
				pass
				#self.sq.put_nowait((data_identifiers['heartbeat'], f'heartbeat-{self.ticks}'))
				#self.ticks += 1

			#updatemsg = str.encode(f'playerpos:{self.name}:{self.pos}:')
			#self.socket.sendall(updatemsg)

	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.rect.centerx, self.rect.centery))
			bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=self, bomb_power=self.bomb_power)
			# self.bombs.add(bomb)
			self.bombs_left -= 1
			return bomb
		else:
			return 0

	# mixer.Sound.play(self.snd_bombdrop)

	def __str__(self):
		return self.client_id

	def __repr__(self):
		return str(self.client_id)

	def player_action(self, player, action):
		pass

	def get_blocks(self):
		logger.debug(f'get_blocks {type(self.blocks)} {len(self.blocks)}')
		return self.blocks

	def set_mapgrid(self, mapgrid):
		logger.debug(f'set_mapgrid {type(self.gamemap.grid)} ')
		self.gamemap.grid = mapgrid

	def get_mapgrid(self):
		logger.debug(f'get_mapgrid gamemap: {type(self.gamemap)} grid:{type(self.gamemap.grid)} ')
		return self.gamemap.grid

	def set_netplayers(self, netplayers):
		self.net_players = netplayers
		logger.debug(f'{type(netplayers)} {len(netplayers)} {type(self.net_players)} {len(self.net_players)}')

	def get_netplayers(self):
		# logger.debug(f'{type(self.net_players)} {len(self.net_players)}')
		return self.net_players

	def send(self, data):
		self.socket.sendto(data, self.server)

	def connect_to_server(self):
		if self.connected:
			logger.debug('already connected')
			return
		self.socket.connect(self.server)
		self.send_thread.start()
		self.recv_thread.start()
		connstr = f'connect:{self.client_id}:{self.ticks}'
		self.sq.put_nowait((data_identifiers['connect'], connstr))
		self.sq.task_done()
		self.connected = True
		logger.debug(f'playerid: {self.client_id} connected: {self.connected} t:{self.ticks}')

	def start_heartbeat(self):
		self.heartbeat = True

	def stop_heartbeat(self):
		self.heartbeat = False

	def heartbeat_pump(self, count):
		for k in range(count):
			self.sq.put_nowait((data_identifiers['heartbeat'], f'hearbeat-{k}'))
			logger.debug(f'pump hearbeat-{k}')

	def request_data(self, datatype):
		self.sq.put_nowait((data_identifiers['request'], datatype))
		# send_data(self.socket, request)

	def set_pos(self, pos):
		self.pos = pos

	def send_pos(self):
		pass
		# self.sq.put_nowait((data_identifiers['send_pos'], {self.client_id:self.pos}))

	def update(self, blocks):
		self.vel += self.accel
		self.pos.x += self.vel.x
		self.rect.x = int(self.pos.x)
		if self.connected:
			self.sq.put_nowait((data_identifiers['send_pos'], {self.client_id:self.pos}))
		# self.network_updates.append(['move', (self.pos.x, self.pos.y)])
		block_hit_list = self.collide(blocks, self.dt)
		for block in block_hit_list:
			if isinstance(block, Block):
				if self.vel.x > 0 and block.solid:
					self.rect.right = block.rect.left
				elif self.vel.x < 0 and block.solid:
					self.rect.left = block.rect.right
				self.pos.x = self.rect.x
		self.pos.y += self.vel.y
		self.rect.y = int(self.pos.y)
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			if self.vel.y > 0 and block.solid:
				self.rect.bottom = block.rect.top
			elif self.vel.y < 0 and block.solid:
				self.rect.top = block.rect.bottom
			self.pos.y = self.rect.y

	# logger.debug(f'[player] move sp:{self.speed} vel:{self.vel} p:{self.pos}')

	def take_powerup(self, powerup=None):
		# pick up powerups...
		if powerup == 1:
			if self.max_bombs < 10:
				self.max_bombs += 1
				self.bombs_left += 1
		if powerup == 2:
			self.speed += 1
		if powerup == 3:
			self.bomb_power += 10

	def add_score(self):
		self.score += 1
