import socket
from signal import signal, SIGPIPE, SIG_DFL
from random import randint
import sys
import time
from queue import Empty, Queue

from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group

from globals import Block, empty_queue
from globals import GRIDSIZE
from globals import Gamemap
from globals import gen_randid
from netutils import data_identifiers, DataReceiver, DataSender
from threading import Thread, Event
from threading import enumerate as t_enumerate



class ConnectionHandler(Thread):
	def __init__(self, name='connhandler', remote=None, serverqueue=None, data=None, srvsock=None, stop_event=None):
		Thread.__init__(self, name='connhandler', daemon=True, args=(stop_event,))
		self.name = name
		#self.socket = socket
		#self.localaddr = localaddr
		self.kill = False
		self.serverq = serverqueue
		self.remote = (remote[0], 6669)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.clmsgid, self.clid, self.clmsg = data
		self.tick_count = 0
		logger.debug(f'[ch] id:{self.clid} init r:{self.remote} d:{data}')

	def __repr__(self) -> str:
		return f'[ch] id:{self.clid} r:{self.remote} n:{self.name} t:{self.tick_count}'

	def get_clid(self):
		return self.clid

	def update_tick(self):
		self.tick_count += 1
		logger.debug(f'[ch] uptick:{self.tick_count}')

	def run(self):
		while True:
			data = None
			addr = None
			try:
				self.sendmsg(f'connh:{randint(1,1000)}:donk')
				data, addr = self.socket.recvfrom(1024)
			except socket.error as e:
				logger.error(f'[s] {e}')
			if data:
				logger.debug(f'[ch] got data:{data} from:{addr}')
			if self.kill:
				logger.debug(f'[ch] got kill signal')
				# self.join(0)
				break

	def sendmsg(self, msg):
		data = f'ch-{self.clid}:{msg}:fret'.encode('utf-8')
		logger.debug(f'[connh] id:{self.clid} m:{msg} d:{data} to:{self.remote}')
		self.socket.sendto(data, self.remote)
	
	def ch_connect(self):
		pass
		# try:
		# 	self.socket.connect((self.remote[0], 6669))
		# 	self.sendmsg(msg='hellofromserver')
		# except ConnectionRefusedError as e:
		# 	logger.warning(f'[ch] {e} remote:{self.remote}')

class BombServer(Thread):
	def __init__(self, name='BombServer', listenaddr='192.168.1.122', port=6666, serverqueue=None, enginequeue=None, stop_event=None):
		Thread.__init__(self, name='BombServer', args=(stop_event,), daemon=True)
		self.serverq = serverqueue
		self.enginequeue = enginequeue
		self.name = name
		self.localaddr = (listenaddr, port)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.clients = []
		self.clist = {}
		self.kill = False
		self.stop_event = stop_event

	def get_clients(self):
		return self.clients

	def run(self):
		self.socket.bind(self.localaddr)
		# self.socket.listen(0)
		self.kill = False
		logger.debug(f'[s] {self.localaddr} run')
		while True:
			data = None
			addr = None
			clmsgid, clid, clmgs = None,None,None
			try:
				data, addr = self.socket.recvfrom(1024)
			except socket.error as e:
				logger.error(f'[s] {e}')
			if data:
				# logger.debug(f'[s] conn:{data} addr:{addr}')
				data = data.decode('utf-8')
				try:
					clmsgid, clid, clmsg = data.split(':')
				except TypeError as e:
					logger.error(f'[s] {e} data:{data}')
				if clid:
					
					if clid not in self.clist:
						self.clist[clid] = 1
						logger.debug(f'[s] clmsgid:{clmsgid} clid:{clid} clmsg:{clmsg}')
						ch = ConnectionHandler(remote=addr, serverqueue=self.serverq, data=(clmsgid, clid, clmsg), srvsock=self.socket, stop_event=self.stop_event)
						ch.start()
						self.clients.append(ch)
						ch.ch_connect()
					else:
						self.clist[clid] += 1
						[cl.update_tick() for cl in self.clients if cl.get_clid() == clid]

			if self.kill:
				logger.debug(f'[s] killing self:{self.name} k:{self.kill}')
				for ch in self.clients:
					ch.kill = True
					logger.debug(f'[s] killing ch:{ch} ')
					ch.join(0)
				self.connhandler.kill = True
				logger.debug(f'[s] stopped k:{self.kill}')
				self.socket.close()
				self.kill = True
				# self.join(0)
				break
			if not self.serverq.empty():
				msg = None
				try:
					msg = self.serverq.get_nowait()
				except Empty:
					pass

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
				for cl in server.clients:
					logger.debug(f'[d] server.clients:{len(server.clients)} cl:{cl.remote}')
					cl.sendmsg(msg='debugfromserver')
			if cmd[:1] == 'p':
				logger.debug(f'[clientlist] total:{len(server.clients)}')
				for cl in server.clients:
					logger.debug(f'\tclient: {cl} ')
				logger.debug(f'[clist] total:{len(server.clist)}')
				for cl in server.clist:
					logger.debug(f'\tc: {cl} {server.clist[cl]}')
			if cmd[:1] == 'f':
				for k in range(10):
					foo = f'foo{k}'
					logger.debug(f'sending {foo} to q')
					#pass #client.queue.put(foo)
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


