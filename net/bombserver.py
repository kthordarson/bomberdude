import hashlib
import time
import os
import random
from queue import Queue, Empty
from weakref import WeakKeyDictionary
from threading import Thread
# from PodSixNet.Server import Server
from PodSixNet.Channel import Channel
from globals import Gamemap
from globals import Block
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE, inside_circle, Bomb
from pygame.sprite import Group
from pygame.math import Vector2
from loguru import logger
# from __future__ import print_function
import socket

from PodSixNet.asyncwrapper import poll, asyncore
from PodSixNet.Channel import Channel

def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


class Server(asyncore.dispatcher):
	channelClass = Channel
	
	def __init__(self, channelClass=None, localaddr=("127.0.0.1", 5071), listeners=5):
		if channelClass:
			self.channelClass = channelClass
		self._map = {}
		self.channels = []
		self.localaddr = localaddr
		self.listeners = listeners
		asyncore.dispatcher.__init__(self, map=self._map)

	def sock_init(self):
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		self.set_reuse_addr()
		self.bind(self.localaddr)
		self.listen(self.listeners)
	
	def handle_accept(self):
		try:
			conn, addr = self.accept()
		except socket.error:
			print('warning: server accept() threw an exception')
			return
		except TypeError:
			print('warning: server accept() threw EWOULDBLOCK')
			return
		print("connection")
		self.channels.append(self.channelClass(conn, addr, self, self._map))
		self.channels[-1].Send({"action": "connected"})
		if hasattr(self, "Connected"):
			self.Connected(self.channels[-1], addr)
	
	def Pump(self):
		[c.Pump() for c in self.channels]
		poll(map=self._map)



class ServerChannel(Channel):
	def __init__(self, *args, **kwargs):
		self.nickname = "anonymous"
		Channel.__init__(self, *args, **kwargs)
		self.id = gen_randid()  # ''.join([''.join(str(k)) for k in gen_randid()])
		logger.debug(f'[cc] {self.nickname} {self.id}')

	def Network(self, data):
		pass

	# logger.debug(f'[netdata] {data}')
	# pass

	def Close(self):
		self._server.delete_player(self)

	# def Network_myaction(self, data):
	#     logger.debug(data)

	def Network_update(self, data):
		# logger.debug(f'[netupdate] {data}')
		self._server.move_player(data)

	def PassOn(self, data):
		logger.debug(f'[passon] {data}')
		data.update({'id': self.id})
		logger.debug(f'[passon] sending {data}')
		self._server.SendToAll(data)


class UDPServer(Server):
	channelClass = ServerChannel

	def __init__(self, *args, **kwargs):
		Server.__init__(self, *args, **kwargs)
		# channelClass = ServerChannel()
		self.players = WeakKeyDictionary()
		self.clients = []
		self.running = False
		self.localaddr = ('127.0.0.1', 6666)
		logger.debug(f"[udpserver] ip: {self.localaddr} ch: {self.channelClass} chl: {len(self.channels)} init args: {args} kwargs: {kwargs}")

	def get_clients(self):
		return self.clients

	def configure_server(self):
		pass

	def Connected(self, channel, addr):
		logger.debug(f"[udpserver]  New connection:{addr} ch: {channel}")
		self.AddPlayer(channel)

	def AddPlayer(self, player):
		logger.debug(f"[udpserver]  New Player: {player.addr}")
		player.Send({"action": "set_id", "data": player.id})
		self.players[player] = True
		self.send_players()

	def delete_player(self, player):
		logger.debug(f"[udpserver] Deleting Player {player.addr}")  # + str(player.addr))
		self.send_to_all({"action": "del_player", "data": player.id})
		try:
			del self.players[player]
		except KeyError as e:
			logger.debug(f'[delplayer] err {e}')

	def send_players(self):
		logger.debug(f'[udpserver] sendplayers')
		self.send_to_all({"action": "players", "players": [p.id for p in self.players]})

	def send_to_all(self, data):
		logger.debug(f'[udpserver] [sendall] {data}')
		_ = [p.Send(data) for p in self.players]

	def send_to_all_origin(self, data, origin):
		# logger.debug(f'[sendallo] {data} {origin}')
		_ = [p.Send(data) for p in self.players if p.id != origin]

	def get_unique_id(self):
		hashid = hashlib.sha1()
		hashid.update(str(time.time()).encode("utf-8"))
		return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it

	def move_player(self, data):
		# logger.debug(f'[move] {data}')
		self.send_to_all_origin(data, data["origin"])


class ServerThread(Thread):
	def __init__(self, name, dt):
		Thread.__init__(self)
		self.running = False
		self.kill = False
		self.name = name
		self.dt = dt
		self.blocks = Group()
		self.players = Group()
		self.backend = UDPServer(localaddr=("127.0.0.1", 6666))
		self.mainq = Queue()
		logger.debug(f'[ST] {self.name} init')
		self.gamemap = [] #self.generate_map() #Gamemap()

	def start_backend(self):
		self.backend.sock_init()

	def init_blocks(self):
		_ = [self.blocks.add(Block(gridpos=(j, k), dt=self.dt, block_type=str(self.gamemap[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]

	def clear_spot(self):
		x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
		y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
		# x = int(x)
		grid = self.generate_map()
		grid[x][y] = 0
		# make a clear radius around spawn point
		for block in list(inside_circle(3, x, y)):
			try:
				# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
				grid[block[0]][block[1]] = 0
			except Exception as e:
				logger.debug(f"exception in place_player {block} {e}")
		# self.gamemap = grid
		# self.init_blocks()

	def place_player(self, location=0):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridgamemap
		if location == 0:  # center pos
			x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
			y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
			# x = int(x)
			self.gamemap[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					self.gamemap[block[0]][block[1]] = 0
				except Exception as e:
					logger.debug(f"exception in place_player {block} {e}")
			return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))
		if location == 1:  # top left
			x = 5
			y = 5
			# x = int(x)
			self.gamemap[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					self.gamemap[block[0]][block[1]] = 0
				except Exception as e:
					logger.debug(f"exception in place_player {block} {e}")
			return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))
		
	def generate_map(self):
		# self.blocks = Group()
		#self.gamemap = self.generate_map() #Gamemap()
		#_ = [self.blocks.add(Block(gridpos=(j, k), dt=self.dt, block_type=str(self.gamemap[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
		grid = [[random.randint(0, 5) for k in range(GRIDSIZE[1] + 1)] for j in range(GRIDSIZE[0] + 1)]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(GRIDSIZE[0] + 1):
			grid[x][0] = 10
			grid[x][GRIDSIZE[1]] = 10
		for y in range(GRIDSIZE[1] + 1):
			grid[0][y] = 10
			grid[GRIDSIZE[0]][y] = 10
		# _ = [self.blocks.add(Block(gridpos=(j, k), dt=self.dt, block_type=str(self.gamemap[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
		return grid

	def player_bombdrop(self, player):
		pass
	def _player_movement(self, player, action):
		pass

	def place_bomb(self, player):
		if player.bombs_left > 0:
			bombpos = Vector2((player.rect.centerx, player.rect.centery))
			bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=player, bomb_power=player.bomb_power)
			# self.bombs.add(bomb)
			player.bombs_left -= 1
			return bomb
		else:
			return 0

	def player_action(self, player, action):
		# logger.debug(f'[server] p:{player} a:a:{action} {player.pos} {player.vel} {player.accel} ')
		if action == 'd':
			player.vel.y = player.speed
		if action == 'u':
			player.vel.y = -player.speed
		if action == 'r':
			player.vel.x = player.speed
		if action == 'l':
			player.vel.x = -player.speed
		if action == 'b':
			return self.place_bomb(player)
		# player.move(self.blocks, self.dt)
		# logger.debug(f'[server] p:{player} a:a:{action} {player.pos} {player.vel} {player.accel} ')

	def add_player(self, player):
		self.players.add(player)

	def run(self):
		self.running = True
		logger.debug(f'[ST] {self.name} run {self.running} backend: {self.backend}')
		#self.generate_map()
		while self.running:
			try:
				self.backend.Pump()
				if self.kill:
					self.running = False
			# logger.debug(f'[st] {self.name} {self.backend.name} ')
			except KeyboardInterrupt:
				logger.debug(f'[serverthread] keyboardint')
				self.backend.running = False
				self.running = False
				# noinspection PyProtectedMember
				os._exit(0)


def check_threads(threads):
	return True in [t.is_alive() for t in threads]


def stop_all_threads(threads):
	logger.debug(f'stopping {threads}')
	for t in threads:
		logger.debug(f'waiting for {t}')
		t.kill = True
		t.join()


def start_all_threads(threads):
	logger.debug(f'starting {threads}')
	for t in threads:
		logger.debug(f'start {t}')
		t.run()

# if __name__ == '__main__':
# 	# backend = UDPServer(localaddr=("127.0.0.1", 6666))
# 	#backend = Thread(target=UDPServer, args=(('127.0.0.1', 6666),),name='udpserver')
# 	server = ServerThread()
# 	mainthreads = list()
# 	# mainthreads.append(backend)
# 	mainthreads.append(server)
# 	# mainthreads.append(server.backend)
# 	# for t in mainthreads:
# 	# 	logger.debug(f'starting thread {t}')
# 	# 	t.start()
# 	server.start()
# 	while check_threads(mainthreads):
# 		try:
# 			cmd = input(':')
# 			if cmd[:1] == 'q':
# 				stop_all_threads(mainthreads)
# 			if cmd[:1] == 'd':
# 				logger.debug(f'[d] server {server}')
# 				logger.debug(f'[d] backend {server.backend}')
# 				logger.debug(f'[d] mainthreads {len(mainthreads)}')
# 			if cmd[:1] == 's':
# 				logger.debug(f'{server.backend}')
# 			if cmd[:1] == '1':
# 				logger.debug(f'[s1] {len(mainthreads)}')
# 			if cmd[:1] == '2':
# 				logger.debug(f'[s2] {len(mainthreads)}')
# 			if cmd[:1] == '3':
# 				pass
# 				#m.send_items_to_q()

# 		except KeyboardInterrupt as e:
# 			logger.debug(f'KeyboardInterrupt {e}')
# 			stop_all_threads(mainthreads)
# 		except Exception as e:
# 			logger.debug(f'E in main {e}')
# 			stop_all_threads(mainthreads)


# srvcmd.run()
# backend.run()

# while backend.running:
# 	try:
# 		cmd = input('> ')
# 		if cmd[:1] == 'q':
# 			backend.running = False
# 		if cmd[:1] == 'd':
# 			logger.debug(f'[s] run {backend.running}')
# 	except KeyboardInterrupt:
# 		self.running = False
# 		os._exit(0)
