import pygame, time
from pygame.sprite import Group, Sprite

from pygame.math import Vector2
from globals import BasicThing, load_image, PLAYERSIZE, Block, gen_randid, Bomb, Gamemap
from loguru import logger
import socket
from signal import signal, SIGPIPE, SIG_DFL 
#Ignore SIG_PIPE and don't throw exceptions on it... (http://docs.python.org/library/signal.html)
signal(SIGPIPE,SIG_DFL) 
from queue import Queue
from netutils import DataReceiver, DataSender, data_identifiers
from globals import StoppableThread
from threading import Thread

class DummyPlayer(BasicThing):
	def __init__(self, client_id=-1, pos=Vector2(300,300), image='dummyplayer.png'):
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.client_id = client_id
		self.pos = pos
		self.image = image
		self.image, self.rect = load_image(image, -1)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(self.image, self.size)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y

#	def draw(self, screen):
#		screen.blit(self.image, self.pos)


class Player(BasicThing, Thread):
	def __init__(self, pos, dt, image):
		Thread.__init__(self, name='player')
		# StoppableThread.__init__(self, name='player')
		self.name = 'player'
		BasicThing.__init__(self)
		Sprite.__init__(self)
		self.client_id = '-2' # gen_randid()
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
		self.got_blocks = False
		self.gamemap = Gamemap(genmap=False)
		self.got_gamemap = False
		self.connected = False
		self.connecting = False
		self.rq = Queue()
		self.sq = Queue()
		self.recv_thread = DataReceiver(self.socket, self.rq, name=self.name)
		self.send_thread = DataSender(self.socket, self.sq, name=self.name)
		self.recv_thread.daemon = True
		self.send_thread.daemon = True
		self.heartbeat = False
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')

	def __str__(self):
		return self.client_id

	def __repr__(self):
		return str(self.client_id)

	def player_action(self, player, action):
		pass

	def get_netplayer_pos(self, client_id):
		data = f'{self.net_players[client_id]}'
		# print(data)
		return data
		
	def get_blocks(self):
		logger.debug(f'[{self.client_id}]  get_blocks {type(self.blocks)} {len(self.blocks)}')
		return self.blocks

	def set_mapgrid(self, mapgrid):
		logger.debug(f'[{self.client_id}]  set_mapgrid {type(self.gamemap.grid)} ')
		self.gamemap.grid = mapgrid

	def get_mapgrid(self):
		logger.debug(f'[{self.client_id}] get_mapgrid gamemap: {type(self.gamemap)} grid:{type(self.gamemap.grid)} ')
		return self.gamemap.grid

	def get_clientid(self):
		self.sq.put((data_identifiers['getclientid'], 'getclientid'))
		return self.client_id

	def connect_to_server(self):
		if self.connected:
			logger.debug('[{self.client_id}] connect_to_server already connected')
			return self.client_id
		self.connecting = True
		logger.debug(f'[{self.client_id}] connect_to_server attempt playerid: {self.client_id} conn:{self.connected}/{self.connecting} t:{self.ticks} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
		try:
			self.socket.connect(self.server)
		except ConnectionRefusedError as e:
			logger.error(f'{e}')
			return -3
		connstr = f'{self.client_id}:{self.pos}:{self.ticks}'
		self.sq.put((data_identifiers['connect'], connstr))
		logger.debug(f'[{self.client_id}] connect_to_server playerid: {self.client_id} conn:{self.connected}/{self.connecting} t:{self.ticks} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
		self.connected = True
		self.recv_thread.start()
		self.send_thread.start()
		# time.sleep(0.5)
		# self.sq.put((data_identifiers['gameblocks'], 'gameblocks'))
		# self.request_data('gameblocks')
		# time.sleep(0.5)
		self.request_data('gamemapgrid')
		#self.sq.put((data_identifiers['gamemapgrid'], 'gamemapgrid'))
		# time.sleep(0.5)
		return self.client_id

	def start_heartbeat(self):
		self.heartbeat = True

	def stop_heartbeat(self):
		self.heartbeat = False

	def heartbeat_pump(self, count):
		for k in range(count):
			self.sq.put((data_identifiers['heartbeat'], f'hearbeat-{k}'))
			logger.debug(f'[{self.client_id}]  pump hearbeat-{k}')

	def request_data(self, datatype):
		# logger.debug(f'sending request {datatype}')
		self.sq.put((data_identifiers['request'], datatype))
		# send_data(self.socket, request)

	def send_pos(self, posdata):
		self.sq.put((data_identifiers['send_pos'], posdata))

	def process_recvq(self):
		if not self.rq.empty():
			data_id, payload = self.rq.get_nowait()
			# if 'error' in payload:
			#	logger.error(f'dataid:{data_id} payload:{payload} rq:{self.rq.qsize()} sq:{self.sq.qsize()}')
			if data_id == data_identifiers['setclientid']:
				logger.debug(f'[{self.client_id}] 1 setclientid {payload} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
				self.client_id = payload
				logger.debug(f'[{self.client_id}] 2 setclientid {payload} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
				self.connected = True
			if data_id == data_identifiers['blockdata']:
				logger.debug(f'got blockdata {len(payload)} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
				self.blocks = payload
				self.got_blocks = True
			if data_id == data_identifiers['mapdata']:
				logger.debug(f'got mapdata {len(payload)} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
				self.gamemap.grid = payload
				self.got_gamemap = True
			if data_id == data_identifiers['heartbeat']:
				logger.debug(f'recvHB q {data_id} {payload} sq:{self.sq.qsize()} rq:{self.rq.qsize()}')
			if data_id == data_identifiers['player']:
				clid, clpos, clidx = payload.split(':')
				self.net_players[clid] = clpos
				# logger.debug(f'[{self.client_id}] got playerdata {clidx} id:{data_id} p:{payload} netp:{len(self.net_players)}')
			if data_id == data_identifiers['newplayer']:
				senderid, clid, clpos = payload.split(':')
				self.net_players[clid] = clpos
				logger.debug(f'[{self.client_id}] got newplayer from {senderid} newid:{clid} p:{payload} netp:{len(self.net_players)}')
		return self.rq.qsize()

	def run(self):
		self.kill = False
#		self.start()
		while True:
			if self.kill:
				logger.debug(f'player kill')
				self.recv_thread.kill = True
				self.send_thread.kill = True
				break
			if self.client_id == '-2':
				self.request_data('getclientid')
				time.sleep(1)
			if self.connected or self.connecting:
				rqs = self.process_recvq()
				self.request_data('get_net_players')
				# logger.debug(f'[{self.client_id}] rqsize: {rqs}')

	def bombdrop(self):
		if self.bombs_left > 0:
			bombpos = Vector2((self.rect.centerx, self.rect.centery))
			bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=self, bomb_power=self.bomb_power)
			# self.bombs.add(bomb)
			self.bombs_left -= 1
			return bomb
		else:
			return 0

	def update(self, blocks):
		self.vel += self.accel
		self.pos.x += self.vel.x
		self.rect.x = int(self.pos.x)
		if self.connected:
			posdata = f'{self.client_id}:{self.pos}'
			self.send_pos(posdata)
		block_hit_list = self.collide(blocks)
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
