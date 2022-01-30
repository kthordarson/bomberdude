import pygame
from pygame.math import Vector2
from PodSixNet.Connection import connection, ConnectionListener
from globals import BasicThing, load_image, PLAYERSIZE, Block, gen_randid
# from net.bombclient import UDPClient

class Player(ConnectionListener, BasicThing):
	def __init__(self, pos, dt, image, bot, game):
		BasicThing.__init__(self)
		pygame.sprite.Sprite.__init__(self)
		# self.playerconnect()
		self.client_id = gen_randid()
		print(f'[player] init pos:{pos} dt:{dt} i:{image} bot:{bot} game:{game} client_id:{self.client_id}')
		self.game = game
		self.dt = dt
		self.image, self.rect = load_image(image, -1)
		if pos is None:
			self.pos = Vector2(1,1)
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
		self.bot = False
		self.bot_chdir = False
#		if client_id is None:
#			self.client_id = gen_randid()  # ''.join([''.join(str(k)) for k in gen_randid()])
#		else:
#			self.client_id = client_id
		self.connected_to_server = False
		self.network_updates = []

	def __str__(self):
		return self.client_id

	def __repr__(self):
		return str(self.client_id)

	def Network(self, data):
		pass
		# print(f'[net] {data}')

	def Network_players(self, data):
		print(f'[setnetplayers] {data}')
		self.game.set_players(data["players"])

	def Network_connected(self, data):
		print(f'[net] connected {data}')
		self.connected_to_server = True

	def Network_error(self, data):
		print(f'[net] error {data}')

	def Network_disconnected(self, data):
		print(f'[net] disconnect {data}')
		self.connected_to_server = False

	def Network_myaction(self, data):
		print(f'[net] action {data}')

	def Network_update(self, data):
		# print(f'[net] update {data}')
		self.game.move_players(data)

	def send(self, action, data):
		# print(f'[netsend] action: {action} origin {self.client_id} data: {data}')
		connection.Send({"action": action, "origin": self.client_id, "data": data})

	def Events(self):
		pass

	def Loop(self):
		try:
			self.Pump()
			connection.Pump()
		except AttributeError as e:
			pass
			#print(f'self.pump {e}')
		self.Events()

	def playerconnect(self):
		serverip = '192.168.1.222'
		serverport = 1234
		print(f'[player] connecting to server {serverip} {serverport}...')
		self.Connect((serverip, serverport))
		self.connected_to_server = True

	def bot_move(self, blocks, dt):
		pass

	def set_pos(self, pos):
		self.pos = pos

	def set_clientid(self, clientid):
		pass
		# self.client.setid(clientid)

	def get_network_updates(self):
		updates = self.network_updates
		self.network_updates = []
		return updates

	def move(self, blocks, dt):
		self.vel += self.accel
		self.pos.x += self.vel.x
		self.rect.x = int(self.pos.x)
		# self.client.set_pos(self.pos)
		# if self.client.connected:
		# 	self.client.send_pos(self.pos)
		# if self.connected_to_server:
		self.network_updates.append(['move', (self.pos.x, self.pos.y)])
		block_hit_list = self.collide(blocks, dt)
		for block in block_hit_list:
			if isinstance(block, Block):
				if self.vel.x > 0 and block.solid:
					self.rect.right = block.rect.left
					self.bot_chdir = True
				elif self.vel.x < 0 and block.solid:
					self.rect.left = block.rect.right
					self.bot_chdir = True
				self.pos.x = self.rect.x
			# self.vel.x = 0
		self.pos.y += self.vel.y
		self.rect.y = int(self.pos.y)
		block_hit_list = self.collide(blocks)
		for block in block_hit_list:
			self.bot_chdir = True
			if self.vel.y > 0 and block.solid:
				self.rect.bottom = block.rect.top
				self.bot_chdir = True
			elif self.vel.y < 0 and block.solid:
				self.rect.top = block.rect.bottom
				self.bot_chdir = True
			# self.change_y = 0
			self.pos.y = self.rect.y
		# self.vel.y = 0

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
