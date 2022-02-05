from fnmatch import fnmatch
import hashlib
import queue
import time
import os, sys
import random
import pickle
import struct
from queue import Queue, Empty
from globals import StoppableThread
from threading import Thread, Event
from globals import Gamemap
from globals import Block
from globals import gen_randid
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE, inside_circle, Bomb, check_threads, stop_all_threads
from pygame.sprite import Group
from pygame.math import Vector2
from loguru import logger
from queue import Queue
# from __future__ import print_function
import socket
from netutils import receive_data, send_data, data_identifiers
from netutils import DataReceiver, DataSender

#fmt = "{time} | {level: <8} | {name: ^15} | {function: ^15} | {line: >3} | {message}"
#logger.add(sys.stdout, format=fmt)


class ClientThread(StoppableThread):
	def __init__(self, clientaddr=None, clientconnection=None, blocks=None, gamemap=None, queue=None):
		StoppableThread.__init__(self)
		self.name = f'ct {clientaddr}'
		self.client_id = gen_randid()
		self.queue = queue
		self.gamemap = Gamemap()
		if gamemap is not None:
			self.gamemap.grid = gamemap.grid
		self.blocks = blocks
		self.clientconnection = clientconnection
		self.clientaddr = clientaddr
		self.kill = False
		self.msg = ''
		self.client_connected = False
		self.client_data_ready = False
		self.maxping = 10
		self.buffersize = 9096
		self.net_players = {}
		self.hbcount = 0
		self.pos = Vector2((300,300))
		self.rq = Queue()
		self.sq = Queue()
		self.recv_thread = DataReceiver(self.clientconnection, self.rq)
		self.send_thread = DataSender(self.clientconnection, self.sq)
		self.recv_thread.daemon = True
		self.send_thread.daemon = True

	def server_init(self, clients):
		self.clients = clients
		logger.debug(f'client init, got {clients} from server')
	
	def process_recvq_foo(self):
		pass

	def run(self):
		while True:
			if self.kill:
				return
			self.process_recvq()

	def process_recvq(self):
		if not self.rq.empty():
			data_id, payload = self.rq.get()
			if self.kill:
				return
			if payload:
				if data_id == data_identifiers['connect']:
					self.client_id = payload
					logger.debug(f'clientid:{payload} connected. {self.client_id}')
#					self.rq.task_done()
#					return
				if payload == 'gamedata':
					data = {'blocks':self.blocks, 'mapgrid':self.gamemap.grid}
					logger.debug(f'sending gamedata {len(payload)}')
					#send_data(conn=self.clientconnection, payload=data, data_id=data_identifiers['data'])
					self.sq.put_nowait((data_identifiers['data'], data))
#					self.rq.task_done()
#					return
				if data_id == data_identifiers['heartbeat'] and payload[:9] == 'heartbeat':
					self.hbcount = int(payload[10:])
					# logger.debug(f'client heartbeat {self.hbcount} id:{data_id} type: {type(payload)} size: {len(payload)}')
					#send_data(conn=self.clientconnection, payload='beatheart', data_id=data_identifiers['heartbeat'])
					self.sq.put_nowait((data_identifiers['heartbeat'], 'beatheart'))
#					self.rq.task_done()
#					return
				if data_id == data_identifiers['send_pos']:
					self.pos = [k for k in payload.values()][0]
					# logger.debug(f'pos {self.pos} payloadpos {payload}')
#					self.rq.task_done()
#					return
				if data_id == data_identifiers['request'] and payload == 'getnetplayers':
					for np in self.net_players:
						#pd = {np.client_id:np.pos}
						#send_data(conn=self.clientconnection, payload=pd, data_id=data_identifiers['player'])
						self.sq.put_nowait((data_identifiers['player'], np))
#						self.rq.task_done()
#						return

	def getmsg(self):
		return self.msg

	def getsrv(self):
		return self.srv

	def get_netplayers(self):
		return self.net_players

	def new_player(self, player):
		self.net_players.append(player)

class Serverq_Handler(StoppableThread):
	def __init__(self, queue):
		StoppableThread.__init__(self)
		self.queue = queue
		self.kill = False

	def process_q(self):
		if not self.queue.empty():
			qdata = self.queue.get()
			params = qdata['servercmd']
			logger.debug(f'serverq: {qdata["servercmd"]} p:{params}')
			# send_data(self.socket, payload, data_id)
			if params == 'killserver':
				self.kill = True
				logger.debug(f'killing self')
			self.queue.task_done()

	def run(self):
		while not self.kill:
			if self.kill:
				logger.debug(f'server qthread killed')
				return
			self.process_q()
		logger.debug(f'server qthread run end')
		

class ServerThread(StoppableThread):
	def __init__(self, name='serverthread', listenaddr='127.0.0.1', port=6666, queue=None):
		StoppableThread.__init__(self)
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
		self.qthread = Serverq_Handler(self.queue)

	def kill_server(self):
		self.kill = True
		logger.debug(f'[srv] kill {self.kill}')
		for cl in self.clients:
			logger.debug(f'[srv] stopping {cl}')
			cl.stop()
			cl.kill = True
			# cl.join()
		logger.debug('[srv] stopping queuethread')
		self.qthread.stop()

	def run(self):
		self.socket.bind(self.localaddr)
		# self.qthread.daemon = True
		self.qthread.start()
		while True:
			clientconn = None
			clientaddr = None
			self.socket.listen(2)
			if self.kill:
				logger.debug(f'[srv] kill {self.kill}')
				for cl in self.clients:
					cl.stop()
					cl.kill = True
				self.qthread.stop()
				break
			try:
				clientconn, clientaddr = self.socket.accept()
			except Exception as e:
				logger.error(f'[srv] Err {e} cs:{clientconn} ca:{clientaddr}')
				clientconn.close()
			cl = ClientThread(clientaddr, clientconn, self.blocks, self.gamemap, self.queue)
			self.clients.append(cl)
			logger.debug(f'[srv] new client {cl} total: {len(self.clients)}')
			for client in self.clients:
				cl.net_players[cl.client_id] = Vector2(222,222)
			cl.send_thread.start()
			cl.recv_thread.start()
			cl.start()
				#self.socket.close()
		#self.socket.close()

	def init_blocks(self):
		_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]

	def player_action(self, player, action):
		pass



if __name__ == '__main__':
	mainthreads = []
	serverq = Queue()
	server = ServerThread(name = 'fooserver', queue=serverq)
	server.daemon = True
	mainthreads.append(server)
	# server.daemon = True
	server.start()
	server.gamemap.grid = server.gamemap.generate()
	server.init_blocks()
	logger.debug(f'gamemap {len(server.gamemap.grid)} blocks {len(server.blocks)}')	
	server_running = True
	while server_running:
		try:
			cmd = input(':')
			if cmd[:1] == 'q':
				#sys.exit()
				server.queue.put_nowait({'servercmd':'killserver'})
				server.stop()
				server.kill_server()
				server.kill = True
				server_running = False
				#stop_all_threads(mainthreads)
			if cmd[:1] == 'd':
				logger.debug(f'[d] server {server} cl:{len(server.clients)}')
				for cl in server.clients:
					logger.debug(f'[d] {cl.clientaddr} hbc:{cl.hbcount} pos:{cl.pos} netp:{len(cl.net_players)}')
					for np in cl.net_players:
						logger.debug(f'[dnp] {cl.clientaddr} hbc:{cl.hbcount} pos:{cl.pos} netp:{len(cl.net_players)} {np}')
			if cmd[:1] == 'p':
				server.queue.put_nowait(({'servercmd':'pingall'}))
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
			# stop_all_threads(mainthreads)
		except Exception as e:
			logger.error(f'E in main {e}')
			# stop_all_threads(mainthreads)
	sys.exit()

