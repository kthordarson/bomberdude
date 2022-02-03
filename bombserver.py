import hashlib
import time
import os, sys
import random
import pickle
import struct
from queue import Queue, Empty
from threading import Thread
from globals import Gamemap
from globals import Block, data_identifiers
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE, inside_circle, Bomb, check_threads, stop_all_threads
from pygame.sprite import Group
from pygame.math import Vector2
from loguru import logger
# from __future__ import print_function
import socket
from netutils import receive_data, send_data


#fmt = "{time} | {level: <8} | {name: ^15} | {function: ^15} | {line: >3} | {message}"
#logger.add(sys.stdout, format=fmt)

def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it


def generate_map():
	grid = [[random.randint(0, 5) for k in range(GRIDSIZE[1] + 1)] for j in range(GRIDSIZE[0] + 1)]
	# set edges to solid blocks, 10 = solid blockwalkk
	for x in range(GRIDSIZE[0] + 1):
		grid[x][0] = 10
		grid[x][GRIDSIZE[1]] = 10
	for y in range(GRIDSIZE[1] + 1):
		grid[0][y] = 10
		grid[GRIDSIZE[0]][y] = 10
	return grid
class ClientThread(Thread):
	def __init__(self, clientaddr, clientconnection):
		Thread.__init__(self)
		self.name = f'ct {clientaddr}'
		self.gamemap = []
		self.blocks = Group()
		self.clientconnection = clientconnection
		self.clientaddr = clientaddr
		self.kill = False
		self.msg = ''
		self.client_connected = False
		self.client_data_ready = False
		self.maxping = 10
		self.buffersize = 9096
		self.net_players = []

	def run(self):
		while True:			
			if self.kill:
				break
			data = None
			try:
				data_id, payload = receive_data(self.clientconnection)
			except (ConnectionResetError, OSError) as e:
				logger.debug(f'[clt] err {e} {self.clientconnection.fileno()}')
			else:
				if payload:
					response = self.name
					try:
						clientmsg, clientdata, daraparams, *rest = payload.split(':')
					except Exception as e:
						logger.debug(f'[clt] {e} type: {type(payload)} payload: {len(payload)} ')
						clientmsg = payload
						clientdata = '<none>'
						daraparams = '0'
					if clientmsg == 'connect':
						response = f'connected:{self.name}:0'
						logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
						send_data(self.clientconnection, response, data_identifiers['info'])
						self.client_connected = True
					if clientmsg == 'disconnect':
						logger.debug(f'[clt] disconnect client:{payload[:10]}')
						self.client_connected = False
						self.clientconnection.close()
						self.kill = True
						return
					if clientmsg == 'confirm':
						response = f'confirmed:{self.name}:0'
						logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
						send_data(self.clientconnection, response, data_identifiers['info'])
					if clientmsg == 'pong':
						if int(daraparams) <= self.maxping:
							response = f'pong:{self.name}:0'
						else:
							response = f'stopping:{self.name}:0'
						response = f'ping:{self.name}:0'
						logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
						send_data(self.clientconnection, response, data_identifiers['info'])
					if clientmsg == 'ping':	
						if int(daraparams) <= self.maxping:
							response = f'pong:{self.name}:0'
						else:
							response = f'stopping:{self.name}:0'
						logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
						send_data(self.clientconnection, response, data_identifiers['info'])
					if clientmsg == 'request':
						data = ''
						logger.debug(f'{clientmsg} {clientdata}')
						if clientdata == 'gamemap':
							data = pickle.dumps({'gamemap':self.gamemap})
						if clientdata == 'blocks':
							data = pickle.dumps({'blocks':self.blocks})
						if clientdata == 'gamedata':
							data = pickle.dumps({'blocks':self.blocks, 'gamemap':self.gamemap})
							logger.debug(f'sending gamedata {len(payload)}')
						send_data(self.clientconnection, data, data_identifiers['data'])
					if clientmsg == 'playerpos':
						logger.debug(f'{clientmsg} {clientdata} {daraparams}')
			#self.clientconnection.close()

	def do_ping(self):
		send_data(str.encode('ping'))

	def getmsg(self):
		return self.msg

	def getsrv(self):
		return self.srv
	
	def sendmsg(self, msg):
		self.socket.sendto(bytes(msg, encoding='utf-8'), self.srv)
	
	def send_gamedata(self, data):
		send_data(data)

	def init_gamedata(self, blocks, gamemap):
		self.blocks = blocks
		self.gamemap = gamemap

	def get_netplayers(self):
		return self.net_players

	def new_player(self, player):
		self.net_players.append(player)
		#playerdata = {'newplayer':pickle.dumps(player)}
		#send_data(playerdata)
		#mapdata = pickle.dumps(gamemap)
		#data = f'gamedata:gamemap:{len(mapdata)}'.encode()
		#logger.debug(f'init_gamedata b:{type(blocks)} bl:{len(blocks)} m:{type(data)} dl:{len(data)} ml:{len(mapdata)}')
		#send_data(data)
	

class ServerThread(Thread):
	def __init__(self, name='serverthread', listenaddr='127.0.0.1', port=6666):
		Thread.__init__(self)
		self.name = name
		self.gamemap = None
		self.localaddr = (listenaddr, port)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.kill = False
		self.blocks = Group()
		self.players = Group()
		self.gamemap = [] #self.generate_map() #Gamemap()
		self.clients = []

	def run(self):
		self.socket.bind(self.localaddr)
		while True:
			clientconn = None
			clientaddr = None
			self.socket.listen(2)
			if self.kill:
				logger.debug(f'[srv] kill {self.kill}')
				break
			try:
				clientconn, clientaddr = self.socket.accept()
				cl = ClientThread(clientaddr, clientconn)
				self.clients.append(cl)
				cl.init_gamedata(blocks=self.blocks, gamemap=self.gamemap)
				cl.start()
				for client in self.clients:
					client.new_player(cl)
				logger.debug(f'[srv] new client {cl} total: {len(self.clients)}')
			except Exception as e:
				logger.debug(f'[srv] Err {e} cs:{clientconn} ca:{clientaddr}')
				#self.socket.close()
		#self.socket.close()
	
	def send_ping(self):
		for client in self.clients:
			client.do_ping()

	def init_blocks(self):
		_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]

	def player_action(self, player, action):
		pass



if __name__ == '__main__':
	mainthreads = []
	server = ServerThread('foo')
	mainthreads.append(server)
	server.daemon = True
	server.start()
	server.gamemap = generate_map()
	logger.debug(f'gamemap {len(server.gamemap)}')
	server.init_blocks()
	logger.debug(f'blocks {len(server.blocks)}')
	while check_threads(mainthreads):
		try:
			cmd = input(':')
			if cmd[:1] == 'q':
				stop_all_threads(mainthreads)
			if cmd[:1] == 'd':
				logger.debug(f'[d] server {server} {len(server.clients)}')
			if cmd[:1] == 's':
				pass
				# logger.debug(f'{server.backend}')
			if cmd[:1] == '1':
				pass
			if cmd[:1] == '2':
				pass
			if cmd[:1] == '3':
				pass
				#m.send_items_to_q()

		except KeyboardInterrupt as e:
			logger.debug(f'KeyboardInterrupt {e}')
			stop_all_threads(mainthreads)
		except Exception as e:
			logger.debug(f'E in main {e}')
			stop_all_threads(mainthreads)

