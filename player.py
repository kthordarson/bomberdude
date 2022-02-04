import time
import pygame
from pygame.sprite import Group
import pickle
from pygame.math import Vector2
from globals import BasicThing, load_image, PLAYERSIZE, Block, gen_randid, Bomb, Gamemap
from loguru import logger
from threading import Thread
import socket
from queue import Queue
from netutils import receive_data, send_data, data_identifiers, data_receiver


class Player(BasicThing, Thread):
	def __init__(self, pos, dt, image):
		Thread.__init__(self)
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		# self.playerconnect()
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.client_id = gen_randid()
		self.dt = dt
		self.image, self.rect = load_image(image, -1)
		if pos is None:
			self.pos = Vector2(1, 1)
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
		self.net_players = []
		self.recv_thread = None
		self.blocks = Group()
		self.gamemap = Gamemap()
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')

	def run(self):
		self.connect_to_server()
		self.recv_thread = Thread(target=data_receiver(self.socket))
		logger.debug(f'player run {self.recv_thread} conn:{self.connected}')
		self.recv_thread.start()
		while True:
			self.ticks += 1
			if self.kill:
				logger.debug(f'player quit {self.ticks}')
				return

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
		logger.debug(f'set_mapgrid {type(self.gamemap.grid)} {len(self.gamemap.grid)}')
		self.gamemap.grid = mapgrid

	def get_mapgrid(self):
		logger.debug(f'get_mapgrid {type(self.gamemap.grid)} {len(self.gamemap.grid)}')
		return self.gamemap.grid

	def update_net_players(self):
		request = f'getnetplayers:{self.name}:{self.ticks}'
		send_data(self.socket, request, data_identifiers['player'])

	def set_netplayers(self, netplayers):
		self.net_players = netplayers
		logger.debug(f'{type(netplayers)} {len(netplayers)} {type(self.net_players)} {len(self.net_players)}')

	def get_netplayers(self):
		# logger.debug(f'{type(self.net_players)} {len(self.net_players)}')
		return self.net_players

	def send(self, data):
		self.socket.sendto(data, self.server)

	def connect_to_server(self):
		self.socket.connect(self.server)
		hello = f'connect:{self.name}:{self.ticks}'
		send_data(self.socket, hello)

	# self.connected = True

	def request_data(self, datatype):
		request = f'request:{datatype}:{self.ticks}'
		send_data(self.socket, request)

	def handle_gamedata(self, datafromserver):
		logger.debug(f'datahandler: {type(datafromserver)} {len(datafromserver)}')
		try:
			data_p = pickle.loads(datafromserver, encoding='utf-8')
		except pickle.UnpicklingError as e:
			logger.error(f'{e} {type(datafromserver)} {len(datafromserver)} {datafromserver[:10]}')
			data_p = 'None'
		gamemap = data_p.get('gamemap', 'err')
		blockdata = data_p.get('blocks', 'err')
		if gamemap != 'err':
			self.gamemap = gamemap
			logger.error(f'gamemap {len(gamemap)} {type(gamemap)} {len(self.gamemap)} {type(self.gamemap)}')
		if blockdata != 'err':
			self.blocks = blockdata
			logger.error(f'blockdata {len(blockdata)} {type(blockdata)} {len(self.blocks)} {type(self.blocks)}')

	# logger.debug(f'from server {type(datafromserver)} {len(datafromserver)} {type(data_p)} {len(data_p)}')

	def set_pos(self, pos):
		self.pos = pos

	def update(self, blocks):
		self.vel += self.accel
		self.pos.x += self.vel.x
		if self.connected:
			data = f'setpos:{self.pos}:{self.ticks}'
			send_data(self.socket, data)
		self.rect.x = int(self.pos.x)
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
