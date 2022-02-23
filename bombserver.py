import socket
from signal import signal, SIGPIPE, SIG_DFL

import sys
from queue import Empty, Queue

from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group

from globals import Block
from globals import GRIDSIZE
from globals import Gamemap
from globals import StoppableThread
from globals import gen_randid
from netutils import data_identifiers, DataReceiver, DataSender
from threading import enumerate, Thread



class ClientThread(Thread):
	def __init__(self, clientaddr=None, clientconnection=None, blocks=None, gamemap=None, client_q=None):
		Thread.__init__(self, name='clthread')
		self.client_id = gen_randid()
		# StoppableThread.__init__(self, name=self.client_id)
		self.name = f'clthread-{self.client_id}'
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
		self.net_players = {}
		self.hbcount = 0
		self.pos = Vector2()
		self.rq = Queue()
		self.sq = Queue()
		self.client_q = client_q
		self.recv_thread = DataReceiver(r_socket=self.clientconnection, queue=self.rq, name=self.client_id)
		self.send_thread = DataSender(s_socket=self.clientconnection, queue=self.sq, name=self.client_id)
		self.tlist = []
		logger.debug(f'clientthread: {self.client_id} init ')

	def run(self):
		self.tlist.append(self.recv_thread)
		self.tlist.append(self.send_thread)
		self.recv_thread.start()
		self.send_thread.start()
		while True:
			if self.kill:
				logger.debug(f'killing self:{self.name}')
				for t in self.tlist:
					logger.debug(f'killing self:{self.name} {t}')
					t.kill = True
				break
			data_id = None
			payload = None
			try:
				data_id, payload = self.rq.get_nowait()
			except Empty:
				pass
				# logger.debug(f'[{self.name}] rq:{self.rq.qsize()} ')
			if data_id:
				# logger.debug(f'[{self.name}] rq:{self.rq.qsize()} got id:{data_id} p:{payload}')
				self.process_data(data_id=data_id, payload=payload)
			# 	logger.error(f'[{self.client_id}] {e} rq:{self.rq.qsize()} ')
			# srv_q_cmd = None
			# try:
			# 	srv_q_cmd = self.client_q.get_nowait()
			# except Empty:
			# 	pass
			# if srv_q_cmd:
			# 	if 'player' in srv_q_cmd:
			# 		self.add_net_player(srv_q_cmd)

	def get_pos(self):
		return self.pos

	def send_clientid(self):
		self.sq.put((data_identifiers['setclientid'], self.client_id))
		logger.debug(f'[{self.client_id}] send_clientid sq:{self.sq.qsize()} rq:{self.rq.qsize()} srvq:{self.client_q.qsize()}')

	def handle_connection(self, payload):
		logger.debug(f'[{self.client_id}] connection payload: {payload}')
		payload_pid = payload.split(':')[0]
		self.pos = payload.split(':')[2]
		if payload_pid == '-2':
			self.sq.put((data_identifiers['setclientid'], self.client_id))
			logger.debug(f'sending setclientid: {self.client_id} sq:{self.sq.qsize()} rq:{self.rq.qsize()} srvq:{self.client_q.qsize()} pos:{self.pos}')

	def send_gamemapgrid(self):
		logger.debug(f'[{self.client_id}] sending gamedata mapgrid {len(self.gamemap.grid)} sq:{self.sq.qsize()} rq:{self.rq.qsize()} srvq:{self.client_q.qsize()}')
		# send_data(conn=self.clientconnection, payload=data, data_id=data_identifiers['data'])
		self.sq.put((data_identifiers['mapdata'], self.gamemap.grid))

	def handle_posdata(self, payload):
		playerid = payload.split(':')[0]
		# x, y = payload.split("[")[1][:-1].split(",")
		x, y = payload.split("(")[1][:-1].split(",")
		x = int(x)
		y = int(y)
		playerpos = Vector2((x, y))
		self.net_players[playerid] = playerpos
		newpayload = f'{playerid}:{playerpos}'
		self.client_q.put((data_identifiers['netplayer'], newpayload))
		# logger.debug(f'[{self.client_id}] x{x} y{y} payload:{payload} npl:{newpayload} self.pos: {self.pos} np:{len(self.net_players)} pid:{playerid} plpos:{playerpos} {self.client_q.qsize()}')
		# for np in self.net_players:
		#	newpayload = f'{np}:{playerpos}'
		#	self.sq.put((data_identifiers['netplayer'], newpayload))
			#print(f'{np} {newpayload}')
#		if x != 300:
#			logger.debug(f'[{self.client_id}]{x} {y} payload:{payload} self.pos: {self.pos} np:{len(self.net_players)} pid:{playerid} plpos:{playerpos}')

		# self.pos = payload
		#self.net_players[self.client_id] = playerpos
		# self.net_players[]
		#for np in self.net_players:
		#	newpayload = f'{self.client_id}:{np}:{playerpos}'
		#	self.sq.put((data_identifiers['netplayer'], newpayload))
		# self.pos = [k for k in payload.values()][0]

	def process_data(self, data_id=None, payload = None):
		if data_id == data_identifiers['connect']:
			self.handle_connection(payload)
		if data_id == data_identifiers['request'] and payload == 'getclientid':
			self.send_clientid()
		if data_id == data_identifiers['request'] and payload == 'gamemapgrid':
			self.send_gamemapgrid()
		if data_id == data_identifiers['request'] and payload == 'gamemap':
			self.send_gamemapgrid()
		if data_id == data_identifiers['send_pos']:
			self.handle_posdata(payload)
		if data_id == data_identifiers['heartbeat'] and payload[:9] == 'heartbeat':
			self.hbcount = int(payload[10:])
			self.sq.put((data_identifiers['heartbeat'], 'beatheart'))
		# self.sq.all_tasks_done()


class ConnectionHandler(Thread):
	def __init__(self, name='connhandler', socket=None, serverqueue=None, localaddr=None):
		Thread.__init__(self, name='connhandler')
		self.name = name
		self.socket = socket
		self.serverqueue = serverqueue
		self.localaddr = localaddr
		self.kill = False
		self.connections = []

	def run(self):
		while True:
			clientconn = None
			clientaddr = None
			# self.socket.listen(1)
			if self.kill:
				logger.debug(f'{self.name} kill {self.kill}')
				break
			try:
				clientconn, clientaddr = self.socket.accept()
				self.serverqueue.put(('socket', clientconn))
			except Exception as e:
				logger.error(f'[srv] Err {e} cs:{clientconn} ca:{clientaddr}')
		# clientconn.close()


class ServerThread(Thread):
	def __init__(self, name='serverthread', listenaddr='127.0.0.1', port=6666, serverqueue=None, blocks=None, players=None, mainmap=None):
		Thread.__init__(self, name='serverthread')
		self.name = name
		self.serverqueue = serverqueue
		self.client_q = Queue()
		self.localaddr = (listenaddr, port)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.kill = False
		self.blocks = blocks
		self.players = players
		self.gamemap = mainmap
		self.clients = []
		self.net_players = {}
		self.connhandler = ConnectionHandler(name='connhandler', socket=self.socket, serverqueue=self.serverqueue, localaddr=self.localaddr)
		self.daemon = True
		self.connhandler.daemon = True

	def get_net_players(self):
		return self.net_players
	
	def get_clients(self):
		return self.clients

	def get_connh_connections(self):
		return self.connhandler.clients

	def get_net_players_count(self):
		return len(self.net_players)
	
	def get_client_count(self):
		return len(self.clients)

	def get_connh_count(self):
		return len(self.connhandler.connections)

	def set_blocks(self, blocks):
		logger.debug(f'{self.name} got {len(blocks)} blocks')
		self.blocks = blocks

	def set_gamemap(self, gamemap):
		logger.debug(f'{self.name} got gamemap')
		self.gamemap = gamemap

	def kill_server(self):
		logger.debug(f'[srv] kill self: {self.name}')
		idx = 0
		totcl = len(self.clients)
		for cl in self.clients:
			logger.debug(f'{self.name} killing clients {idx}/{totcl} sending kill signal to {cl}')
			idx += 1
			cl.kill = True
		self.kill = True

	def run(self):
		self.socket.bind(self.localaddr)
		self.socket.listen(0)
		self.connhandler.start()
		self.kill = False
		while True:
			if self.kill:
				logger.debug(f'server killing self:{self.name} k:{self.kill}')
				self.connhandler.kill = True
				logger.debug(f'server stopped k:{self.kill}')
				self.socket.close()
				self.kill = True
				break
			clientconn = ''
			clientaddr = None
			sqdata = ''
			try:
				sqdata = self.serverqueue.get_nowait()
			except Empty:
				pass
			if 'socket' in sqdata:
				clientconn = sqdata[1]
				cl = ClientThread(clientaddr, clientconn, self.blocks, self.gamemap, self.client_q)
				self.clients.append(cl)
				# self.net_players[cl.client_id] = Vector2()
				# cl.net_players = self.net_players
				cl.start()
				#for cl in self.clients:
				#	cl.net_players = self.net_players
				logger.debug(f'[srv] new client id:{cl.client_id} total: {len(self.clients)} sq:{cl.client_q.qsize()}')
			client_qdata = None
			try:
				data_id, payload = self.client_q.get_nowait()
			except Empty:
				pass
			if client_qdata:
				self.client_q.task_done()
				# logger.debug(f'client_qdata: {payload} {self.client_q.qsize()}')
				if data_id == data_identifiers['netplayer']:
					playerid = payload.split(':')[0]
					npl_id = payload.split(':')[0]
					x, y = payload.split("[")[1][:-1].split(",")
					x = int(x)
					y = int(y)
					playerpos = Vector2((x, y))
					for cl in self.clients:
						cl.net_players[playerid] = playerpos
						logger.debug(f'client_qdata: {payload} {self.client_q.qsize()} {cl} {playerid} {playerpos}')
					# self.net_players[playerid] = playerpos
					# player1.net_players[npl_id] = playerpos
					# player1.net_players[player1.client_id] = player1.pos



if __name__ == '__main__':
	mainthreads = []
	serverqueue = Queue()
	mainmap = Gamemap()
	server = ServerThread(name='bombserver', serverqueue=serverqueue, mainmap=mainmap)
	mainthreads.append(server)
	server.daemon = True
	server.connhandler.daemon = True
	server.start()

	server.gamemap.grid = server.gamemap.generate()
	logger.debug(f'gamemap {len(server.gamemap.grid)} ')
	server_running = True
	while server_running:
		try:
			cmd = input(':')
			if cmd[:1] == 'q':
				# server.kill_server()
				logger.debug('quitting')
				server.connhandler.kill = True
				logger.debug('connhandler killed')
				server.kill = True
				logger.debug('server killed')
				server_running = False
			# stop_all_threads(mainthreads)
			if cmd[:1] == 'd':
				# t_count = len(enumerate())
				logger.debug(f'[d] server {server.name} severclients:{len(server.clients)} msq:{server.serverqueue.qsize()}')
				idx1 = 0
				for cl in server.clients:
					logger.debug(f'[client {idx1}/{len(server.clients)}] {cl.client_id} pos:{cl.pos} netp:{len(cl.net_players)} clsq:{cl.sq.qsize()} clrq:{cl.rq.qsize()} clsvrq:{cl.client_q.qsize()}')
					idx1 += 1
					idxnp = 0
					for np in cl.net_players:
						logger.debug(f'[clnp {idx1}/{len(server.clients)}] {cl.client_id} n:{idxnp}/{len(cl.net_players)} netp: {np} {cl.net_players[np]} clsq:{cl.sq.qsize()} clrq:{cl.rq.qsize()} clsvrq:{cl.client_q.qsize()}')
						idxnp += 1
			if cmd[:1] == 'p':
				server.serverqueue.put(({'servercmd': 'pingall'}))
			if cmd[:1] == 't':
				all_threads = enumerate()
				idx = 0
				logger.debug(f'Thread dump total threads {len(all_threads)}')
				for t in all_threads:
					logger.debug(f'[{idx}/{len(all_threads)}] {t}')
					idx += 1
			if cmd[:1] == '1':
				pass
			if cmd[:1] == '2':
				pass
			if cmd[:1] == '3':
				pass
		except KeyboardInterrupt as e:
			logger.error(f'KeyboardInterrupt {e}')
			sys.exit()
		except Exception as e:
			logger.error(f'Exception in main {e}')
			sys.exit()

	sys.exit()
