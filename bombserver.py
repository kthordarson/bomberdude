from itertools import chain
import socket
from signal import signal, SIGPIPE, SIG_DFL
from random import randint
import sys
import time
from queue import Empty, Queue

from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group

from things import Block
from constants import GRIDSIZE
from map import Gamemap
from globals import gen_randid
from netutils import data_identifiers, DataReceiver, DataSender,get_ip_address
from threading import Thread, Event
from threading import enumerate as t_enumerate
import pickle



class ClientHandler(Thread):
	def __init__(self, name=None, clientaddr=None, connection_socket=None, packet_trace=False, data=None):
		Thread.__init__(self, name=f'chthread-{name}', daemon=True)
		self.name = name
		self.clid = self.name
		self.kill = False
		self.data = data
		#self.clmsgid, self.clid, self.clmsg = 1,2,3
		self.tick_count = 0
		self.s_count = 0
		self.r_count = 0
		self.dork_count = 0
		self.packet_trace = packet_trace
		self.csocket = connection_socket
		self.caddr = clientaddr
		self.remote = self.caddr
		self.clpos = Vector2()
		self.pos_list = {}
		logger.debug(f'[ch] id:{self.clid} init r:{self.caddr} d:{data}')

	def __repr__(self) -> str:
		return f'[ch] id:{self.clid} r:{self.remote} n:{self.name} t:{self.tick_count}'

	def get_dorks(self):
		self.dork_count += 1
		return f'{self} clid:{self.clid} n:{self.name} t:{self.tick_count} rs:{self.r_count}/{self.s_count} dorks:{self.dork_count}'

	def set_packet_trace(self, state=2): # 0=off, 1=on, 2=toggle
		if state == 0:
			self.packet_trace = False
		if state == 1:
			self.packet_trace = True
		if state == 2:
			self.packet_trace ^= True
		logger.debug(f'[ch] id:{self.clid} s:{state} pkt:{self.packet_trace}')

	def get_clpos(self):
		return self.clpos

	def get_clid(self):
		return self.clid

	def update_tick(self):
		self.tick_count += 1

	def handle_incoming(self, rawdata=None):
		# logger.debug(f'[clch] incoming:{dataraw}')
		data = rawdata.decode('utf-8')
		try:
			msgid, clid, msgdata, *_ = data.split(':')
		except ValueError as e:
			# logger.error(f'[chincoming] {e} rd:{rawdata} rawlen:{len(rawdata)} d:{data} dlen:{len(data)}')
			return
		try:
			msgid = int(msgid)
		except ValueError as e:
			pass
		if msgid == 1:
			pass
		elif msgid == 2:
			pass
		elif msgid == 2:
			pass
		elif msgid == 5:
			#logger.debug(f'[chincoming] pos clid:{clid} msgid:{msgid} mt:{type(msgid)} m:{msgdata} r:{rawdata}')
			x = float(msgdata.strip().replace('(','').replace(')','').split(',')[0])
			y = float(msgdata.strip().replace('(','').replace(')','').split(',')[1])
			clpos = Vector2(x,y)
			#self.pos_list[clid] = clpos
			#logger.debug(f'[chincoming] pos:{clpos} from clid:{clid} m:{msgdata}')
		elif msgid == 6:
			logger.debug(f'[chincoming] getnetplayers clid:{clid} msgid:{msgid} mt:{type(msgid)} m:{msgdata} r:{rawdata}')
		elif msgid == 155:
			logger.debug(f'[chincoming] getserverinfo clid:{clid} msgid:{msgid} mt:{type(msgid)} m:{msgdata} r:{rawdata}')
		else:
			if self.packet_trace:
				logger.warning(f'[chincoming] unknownmsgid clid:{clid} msgid:{msgid} mt:{type(msgid)} m:{msgdata} r:{rawdata}')

	def run(self):
		while not self.kill:
			if self.kill:
				break
			if self.csocket._closed or self.kill:
				logger.warning(f'[ch] socket closed sclosed:{self.csocket._closed} kill:{self.kill}')
				self.kill = True
				break
			else:
				self.tick_count += 1
				rawdata = None
				msg = self.tick_count
				try:
					self.sendmsg(msgid=96, msgdata=msg)
				except BrokenPipeError as e:
					logger.error(f'[ch] {e} sclosed:{self.csocket._closed} kill:{self.kill}')
					self.csocket.close()
					break
				try:
					rawdata = self.csocket.recv(1024)
				except OSError as e:
					logger.error(f'[connh] {e} sclosed:{self.csocket._closed} kill:{self.kill}')
					self.csocket.close()
					self.kill = True
					break
				if rawdata:
					self.handle_incoming(rawdata=rawdata)
					self.r_count += 1
					# logger.debug(f'[srvclh] got data:{rawdata}')

	def sendmsg(self, msgid=None, msgdata=None):
		if self.csocket._closed:
			logger.warning(f'[ch] socket closed sclosed:{self.csocket._closed} kill:{self.kill}')
			self.kill = True
			return
		data = f'{msgid}:{self.clid}:{msgdata}'.encode('utf-8')
		if self.packet_trace:
			logger.debug(f'[ch] send data:{data} msgid:{msgid} msgdata:{msgdata} clid:{self.clid}')
		try:
			self.csocket.send(data)
			self.s_count += 1
		except OSError as e:
			logger.error(f'[ch] send err {e} msgid:{msgid} msgdata:{msgdata} socket:{self.csocket} sclosed:{self.csocket._closed} kill:{self.kill}')
			self.csocket.close()
			self.kill = True
		# self.ds.queue.put(data)

	def sendmsgx(self, msgid=None, msgdata=None):
		#data = f'ch-{self.clid}:{msg}'.encode('utf-8')
		data = f'{msgid}:{self.clid}:{msgdata}'.encode('utf-8')
		if self.packet_trace:
			logger.debug(f'[connh] id:{self.clid} sending mid:{msgid} m:{msgdata} d:{data} to:{self.remote}')
		#self.socket.sendto(data, self.remote)

class BListener(Thread):
	def __init__(self, socket=None, localaddr=None, packet_trace=None):
		Thread.__init__(self, name='blistener', daemon=True)
		self.localaddr = localaddr
		self.socket = socket
		self.packet_trace = packet_trace
		self.kill = False
		self.queue = Queue()
	
	def run(self):
		self.socket.bind(self.localaddr)
		self.socket.listen()
		while not self.kill:
			connectionSocket = None
			clientAddress = None
			conn_counter = 0
			try:
				try:
					(connectionSocket, clientAddress) = self.socket.accept()
				except (TimeoutError, BlockingIOError) as e:
					logger.warning(f'[server] {e}')
				if connectionSocket:
					newclient = ClientHandler(name=f'bdclient{conn_counter}', clientaddr=clientAddress, connection_socket=connectionSocket, packet_trace=self.packet_trace)
					self.queue.put(newclient)
			except KeyboardInterrupt as e:
				logger.error(e)
	
class BombServer(Thread):
	def __init__(self, name='BombServer', listenaddr='192.168.1.122', port=6666, serverqueue=None, enginequeue=None, stop_event=None):
		Thread.__init__(self, name='BombServer', args=(stop_event,), daemon=True)
		self.serverq = serverqueue
		self.enginequeue = enginequeue
		self.name = name
		self.localaddr = (listenaddr, port)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.packet_trace = False
		self.listener = BListener(socket=self.socket, localaddr=self.localaddr, packet_trace=self.packet_trace)
		self.clients = []
		self.clist = {}
		self.kill = False
		self.stop_event = stop_event

	def __repr__(self):
		return f'[s] {self.name} {self.localaddr} {len(self.clients)} {len(self.clist)}'

	def get_client_count(self):
		return len(self.clients)

	def get_clients(self):
		return self.clients

	def run(self):
		self.listener.start()
		conn_counter = 0
		while True:
			if not self.listener.queue.empty():
				newclient = self.listener.queue.get()
				logger.debug(f'[qitem] {newclient} {type(newclient)}') 
				connectionSocket, clientAddress = None, None
				conn_counter += 1
				self.listener.queue.task_done()
				self.clients.append(newclient)
				newclient.start()
				logger.debug(f'[newconn] {newclient} clients:{len(self.clients)} cs:{newclient.csocket} caddr:{newclient.caddr}')


if __name__ == '__main__':
	mainthreads = []
	squeue = Queue()
	server = BombServer(name='bombserver', serverqueue=squeue)
	server.daemon = True
	server.start()
	while True:
		try:
			cmd = input(f': ')
			if cmd[:1] == 'q':
				break
			if cmd[:1] == 'd':
				logger.debug(f'[maindebug]')
				for cl in server.clients:
					logger.debug(f'\t[d] client:{cl} server.clients:{len(server.clients)} cl:{cl.remote}')
					cl.sendmsg(msgid=99, msgdata='debugfromserver')
				logger.debug(f'[dorkdebug]')
				for ch in server.clients:
					dorks = ch.get_dorks()
					logger.debug(f'\t[chd] {ch} dorks:{dorks}')
			if cmd[:1] == 'p':
				logger.debug(f'[clientlist] total:{len(server.clients)}')
				for cl in server.clients:
					logger.debug(f'\tclient: {cl} ')
				logger.debug(f'[clist] total:{len(server.clist)}')
				for cl in server.clist:
					logger.debug(f'\tc: {cl} {server.clist[cl]}')
			if cmd[:2] == 't0':
				server.packet_trace = False
				logger.debug(f'[pkt] packet_trace:{server.packet_trace}')
				[ch.set_packet_trace(state=0) for ch in server.clients]
			if cmd[:2] == 't1':
				server.packet_trace = True
				logger.debug(f'[pkt] packet_trace:{server.packet_trace}')
				[ch.set_packet_trace(state=1) for ch in server.clients]
			if cmd[:2] == 't2':
				server.packet_trace ^= True
				logger.debug(f'[pkt] packet_trace:{server.packet_trace}')
				[ch.set_packet_trace(state=2) for ch in server.clients]
			if cmd[:1] == '1':
				pass
			if cmd[:1] == '2':
				pass
			if cmd[:1] == '3':
				pass
				#m.send_items_to_q()
		except KeyboardInterrupt as e:
			logger.debug(f'KeyboardInterrupt {e}')
			break
		except Exception as e:
			logger.debug(f'E in main {e}')
			#break


				#newclient = ClientHandler(name=f'bdclient{conn_counter}', clientaddr=clientAddress, connection_socket=connectionSocket, packet_trace=self.packet_trace)
