import pygame
from pygame.math import Vector2
from PodSixNet.Connection import connection, ConnectionListener
from globals import BasicThing, load_image, PLAYERSIZE, Block, gen_randid
from loguru import logger

# from net.bombclient import UDPClient

class Player(ConnectionListener, BasicThing):
	def __init__(self, pos, dt, image):
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		# self.playerconnect()
		self.client_id = gen_randid()
		logger.debug(f'[player] init pos:{pos} dt:{dt} i:{image}  client_id:{self.client_id}')
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
		self.connected_to_server = False
		self.network_updates = []

	def __str__(self):
		return self.client_id

	def __repr__(self):
		return str(self.client_id)

	def Network(self, data):
		pass

	# logger.debug(f'[net] {data}')

	def Network_players(self, data):
		logger.debug(f'[setnetplayers] {data}')

	def Network_connected(self, data):
		logger.debug(f'[net] connected {data}')
		self.connected_to_server = True

	@staticmethod
	def Network_error(data):
		logger.debug(f'[net] error {data}')

	def Network_disconnected(self, data):
		logger.debug(f'[net] disconnect {data}')
		self.connected_to_server = False

	@staticmethod
	def Network_myaction(data):
		logger.debug(f'[net] action {data}')

	def Network_update(self, data):
		pass
		# logger.debug(f'[net] update {data}')

	def send(self, action, data):
		# logger.debug(f'[netsend] action: {action} origin {self.client_id} data: {data}')
		connection.Send({"action": action, "origin": self.client_id, "data": data})

	def Events(self):
		pass

	def Loop(self):
		try:
			self.Pump()
			connection.Pump()
		except AttributeError:
			pass
		# logger.debug(f'self.pump {e}')
		self.Events()

	def playerconnect(self):
		serverip = '127.0.0.1'
		serverport = 6666
		logger.debug(f'[player] connecting to server {serverip} {serverport}...')
		self.Connect((serverip, serverport))
		self.connected_to_server = True

	def set_pos(self, pos):
		self.pos = pos

	def set_clientid(self, clientid):
		pass

	# self.client.setid(clientid)

	def get_network_updates(self):
		updates = self.network_updates
		self.network_updates = []
		return updates

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
