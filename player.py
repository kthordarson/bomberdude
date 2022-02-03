import time
import pygame
from pygame.sprite import Group
import pickle
from pygame.math import Vector2
from globals import BasicThing, load_image, PLAYERSIZE, Block, gen_randid, Bomb
from loguru import logger
from threading import Thread
import socket
from netutils import receive_data, send_data



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
		self.net_players = []
		self.recv_thread = None
		self.blocks = Group()
		self.gamemap = []
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')

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

	def get_gamemap(self):
		logger.debug(f'get_gamemap {type(self.gamemap)} {len(self.gamemap)}')
		return self.gamemap

	def send(self, data):
		self.socket.sendto(data, self.server)

	def connect_to_server(self):
		self.socket.connect(self.server)
		hello = f'connect:{self.name}:{self.ticks}'
		send_data(self.socket, hello)
		self.connected = True
	def disconnect(self):
		disc = f'disconnect:{self.client_id}:0'
		send_data(self.socket, disc)
	def get_game_data(self):
		if self.connected:
			connstring = f'getgamedata:{self.client_id}:{self.pos}'.encode()
			while not self.game_ready:
				self.socket.sendall(connstring, self.server)
				data = self.socket.recv(1024).decode()

	def data_receiver(self):
		while self.connected:
			data_id, payload = receive_data(self.socket)
			logger.debug(f'data_receiver id: {data_id} payload:{payload[:10]}')
			if data_id == 1:
				self.handle_gamedata(payload)		
			else:
				data = payload
				servermsg, servername, serverparams = payload.split(':')
				if servermsg:
					# if servermsg == 'gamedata':
					# 	response = str.encode(f'confirm:{self.name}:{self.ticks}')
					# 	logger.debug(f'from server:{data} sending:{response}')
					# 	send_data(self.socket, response)
					if servermsg == 'connected':
						response = f'confirm:{self.name}:{self.ticks}'
						logger.debug(f'from server:{data} sending:{response}')
						send_data(self.socket, response)
					if servermsg == 'confirmed':
						response = f'conndone:{self.name}:{self.ticks}'
						logger.debug(f'from server:{data} sending:{response}')
						send_data(self.socket, response)
					if servermsg == 'stopping':
						response = f'stopping:{self.name}:{self.ticks}'
						logger.debug(f'from server:{data} sending:{response}')
						send_data(self.socket, response)
						self.pingcount = 0
					if servermsg == 'ping':
						response = f'pong:{self.name}:{self.pingcount}'
						logger.debug(f'from server:{data} sending:{response}')
						send_data(self.socket, response)
					if servermsg == 'pong':
						response = f'ping:{self.name}:{self.pingcount}'
						logger.debug(f'from server:{data} sending:{response}')
						self.pingcount += 1
						if self.pingcount == int(serverparams):
							pass
						else:
							send_data(self.socket, response)
			#self.socket.close()

	def request_data(self, datatype):
		request = f'request:{datatype}:{self.ticks}'
		send_data(self.socket, request)

	def handle_gamedata(self, datafromserver):
		logger.debug(f'datahandler: {type(datafromserver)} {len(datafromserver)}')
		try:
			data_p = pickle.loads(datafromserver, encoding='utf-8')
		except pickle.UnpicklingError as e:
			logger.debug(f'{e} {type(datafromserver)} {len(datafromserver)} {datafromserver[:10]}')
			data_p = 'None'
		gamemap = data_p.get('gamemap', 'err')
		blockdata = data_p.get('blocks', 'err')
		if gamemap != 'err':
			self.gamemap = gamemap
			logger.debug(f'gamemap {len(gamemap)} {type(gamemap)} {len(self.gamemap)} {type(self.gamemap)}')
		if blockdata != 'err':
			self.blocks = blockdata
			logger.debug(f'blockdata {len(blockdata)} {type(blockdata)} {len(self.blocks)} {type(self.blocks)}')
		# logger.debug(f'from server {type(datafromserver)} {len(datafromserver)} {type(data_p)} {len(data_p)}')

	def set_pos(self, pos):
		self.pos = pos

	def update(self, blocks):
		self.vel += self.accel
		self.pos.x += self.vel.x
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

	def run(self):
		self.connect_to_server()
		self.recv_thread = Thread(target=self.data_receiver, daemon=True)
		self.recv_thread.start()
		logger.debug(f'player run {self.recv_thread} conn:{self.connected}')

		while True:
			self.ticks += 1
			if self.kill:
				logger.debug(f'player quit {self.ticks}')
				self.disconnect()
				# self.socket.close()
				# self.recv_thread.join()
				return
			#updatemsg = str.encode(f'playerpos:{self.name}:{self.pos}:')
			#self.socket.sendall(updatemsg)
