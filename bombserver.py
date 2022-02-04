import hashlib
import queue
import time
import os, sys
import random
import pickle
import struct
from queue import Queue, Empty
from threading import Thread
from globals import Gamemap
from globals import Block
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE, inside_circle, Bomb, check_threads, stop_all_threads, Gamemap
from pygame.sprite import Group
from pygame.math import Vector2
from loguru import logger
from queue import Queue
# from __future__ import print_function
import socket
from netutils import receive_data, send_data, data_identifiers


#fmt = "{time} | {level: <8} | {name: ^15} | {function: ^15} | {line: >3} | {message}"
#logger.add(sys.stdout, format=fmt)


class ClientThread(Thread):
	def __init__(self, clientaddr=None, clientconnection=None, blocks=None, gamemap=None, queue=None):
		Thread.__init__(self)
		self.name = f'ct {clientaddr}'
		self.queue = queue
		self.gamemap = gamemap
		self.blocks = blocks
		self.clientconnection = clientconnection
		self.clientaddr = clientaddr
		self.kill = False
		self.msg = ''
		self.client_connected = False
		self.client_data_ready = False
		self.maxping = 10
		self.buffersize = 9096
		self.net_players = []
		self.hbcount = 0
		self.pos = Vector2((1,2))

	def server_init(self, clients):
		self.clients = clients
		logger.debug(f'client init, got {clients} from server')
		
	def run(self):
		while True:
			clientmsg = None
			clientdata = None
			daraparams = None
			rest = None
			if self.kill:
				break
			try:
				data_id, payload = receive_data(self.clientconnection)
				# logger.debug(f'client got id:{data_id} type: {type(payload)} size: {len(payload)} {payload}')
			except (ConnectionResetError, OSError) as e:
				logger.error(f'[clt] err {e} socketstatus: {self.clientconnection.fileno()}')
				self.kill = True
				return
			else:
				if payload:
					if payload == 'gamedata':
						data = {'blocks':self.blocks, 'mapgrid':self.gamemap}
						logger.debug(f'sending gamedata {len(payload)}')
						send_data(conn=self.clientconnection, payload=data, data_id=data_identifiers['data'])
					if data_id == 7 and payload[:9] == 'heartbeat':
						self.hbcount = int(payload[10:])
						# logger.debug(f'client heartbeat {self.hbcount} id:{data_id} type: {type(payload)} size: {len(payload)}')
						send_data(conn=self.clientconnection, payload='beatheart', data_id=data_identifiers['heartbeat'])
					if data_id == 8:
						self.pos = payload
						logger.debug(f'pos {self.pos} payloadpos {payload}')

					#if payload == ''

			# 		response = self.name
			# 		try:
			# 			clientmsg, clientdata, daraparams, *rest = payload.split(':')
			# 			if data_id != 0:
			# 				logger.debug(f'did:{data_id} msg:{clientmsg} cld:{clientdata} dp:{daraparams}')
			# 		except Exception as e:
			# 			logger.error(f'[clt] {e} type: {type(payload)} payload: {len(payload)} ')
			# 		if clientmsg == 'connect':
			# 			response = f'connected:{self.name}:0'
			# 			logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
			# 			send_data(self.clientconnection, response, data_identifiers['info'])
			# 			self.client_connected = True
			# 		if clientmsg == 'confirm':
			# 			response = f'confirmed:{self.name}:0'
			# 			logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
			# 			send_data(self.clientconnection, response, data_identifiers['info'])
			# 		if clientmsg == 'pong':
			# 			if int(daraparams) <= self.maxping:
			# 				response = f'pong:{self.name}:0'
			# 			else:
			# 				response = f'stopping:{self.name}:0'
			# 			response = f'ping:{self.name}:0'
			# 			logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
			# 			send_data(self.clientconnection, response, data_identifiers['info'])
			# 		if clientmsg == 'ping':
			# 			if int(daraparams) <= self.maxping:
			# 				response = f'pong:{self.name}:0'
			# 			else:
			# 				response = f'stopping:{self.name}:0'
			# 			logger.debug(f'[clt] from client:{payload[:10]} sending:{response}')
			# 			send_data(self.clientconnection, response, data_identifiers['info'])
			# 		if clientmsg == 'getnetplayers':
			# 			data = []
			# 			for p in self.net_players:
			# 				data.append({'netplayer': p.clientaddr, 'netpos':p.net_pos})
			# 				#logger.debug(f'gnp {p.clientaddr} {p.net_pos}')
			# 			send_data(self.clientconnection, data, data_identifiers['player'])
			# 			logger.debug(f'sending net_players {len(self.net_players)} {len(data)}')
			# 		if clientmsg == 'setpos':
			# 			self.net_pos = clientdata
			# 		if clientmsg == 'request':
			# 			data = ''
			# 			logger.debug(f'{clientmsg} {clientdata}')
			# 			if clientdata == 'mapgrid':
			# 				data = {'mapgrid':self.gamemap}
			# 			if clientdata == 'blocks':
			# 				data = {'blocks':self.blocks}
			# 			if clientdata == 'gamedata':
			# 				data = {'blocks':self.blocks, 'mapgrid':self.gamemap}
			# 				logger.debug(f'sending gamedata {len(payload)}')
			# 			send_data(self.clientconnection, data, data_identifiers['data'])
			# 		if clientmsg == 'playerpos':
			# 			logger.debug(f'{clientmsg} {clientdata} {daraparams}')
			# #self.clientconnection.close()

	def do_ping(self):
		send_data(conn=self.clientconnection, payload='pingpingpingpingping', data_id=0)

	def getmsg(self):
		return self.msg

	def getsrv(self):
		return self.srv

	def send_gamedata(self, data):
		send_data(data)

	def get_netplayers(self):
		return self.net_players

	def new_player(self, player):
		self.net_players.append(player)

class ServerThread(Thread):
	def __init__(self, name='serverthread', listenaddr='127.0.0.1', port=6666, queue=None):
		Thread.__init__(self)
		self.name = name
		self.queue = queue
		self.localaddr = (listenaddr, port)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.kill = False
		self.blocks = Group()
		self.players = Group()
		self.gamemap = Gamemap()
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
				cl = ClientThread(clientaddr, clientconn, self.blocks, self.gamemap, self.queue)
				self.clients.append(cl)
				logger.debug(f'[srv] new client {cl} total: {len(self.clients)}')
				for client in self.clients:
					cl.net_players.append(client)
				cl.start()
			except Exception as e:
				logger.error(f'[srv] Err {e} cs:{clientconn} ca:{clientaddr}')
				#self.socket.close()
		#self.socket.close()

	def ping_all(self):
		for client in self.clients:
			client.do_ping()

	def init_blocks(self):
		_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]

	def player_action(self, player, action):
		pass



if __name__ == '__main__':
	mainthreads = []
	serverq = Queue()
	server = ServerThread(name = 'fooserver', queue=serverq)
	mainthreads.append(server)
	server.daemon = True
	server.start()
	server.gamemap.grid = server.gamemap.generate()
	logger.debug(f'gamemap {len(server.gamemap.grid)}')
	# server.init_blocks()
	logger.debug(f'blocks {len(server.blocks)}')
	while check_threads(mainthreads):
		try:
			cmd = input(':')
			if cmd[:1] == 'q':
				stop_all_threads(mainthreads)
			if cmd[:1] == 'd':
				logger.debug(f'[d] server {server} cl:{len(server.clients)}')
				for cl in server.clients:
					logger.debug(f'[d] {cl.clientaddr} hbc:{cl.hbcount} pos:{cl.pos} netp:{len(cl.net_players)}')
					for np in cl.net_players:
						logger.debug(f'[dnp] {cl.clientaddr} hbc:{cl.hbcount} pos:{cl.pos} netp:{len(cl.net_players)} {np}')
			if cmd[:1] == 'p':
				server.ping_all()
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
			logger.error(f'E in main {e}')
			stop_all_threads(mainthreads)

