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
from netutils import data_identifiers, DataReceiver, DataSender
from threading import Thread, Event
from threading import enumerate as t_enumerate



class ConnectionHandler(Thread):
	def __init__(self, name=None, remote=None, serverqueue=None, data=None, srvsock=None, stop_event=None):
		Thread.__init__(self, name=f'chthread-{name}', daemon=True, args=(stop_event,))
		self.name = name
		#self.socket = socket
		#self.localaddr = localaddr
		self.kill = False
		self.serverq = serverqueue
		self.remote = (remote[0], 6669)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.clmsgid, self.clid, self.clmsg = data
		self.tick_count = 0
		self.client_pos = Vector2()
		logger.debug(f'[ch] id:{self.clid} init r:{self.remote} d:{data}')

	def __repr__(self) -> str:
		return f'[ch] id:{self.clid} r:{self.remote} n:{self.name} t:{self.tick_count}'

	def get_clid(self):
		return self.clid

	def update_tick(self):
		self.tick_count += 1
		# logger.debug(f'[ch] uptick:{self.tick_count}')

	def run(self):
		while True:
			data = None
			addr = None
			try:
				# clmsgid, clid, clmsg = data.split(':')
				self.sendmsg(msgid=2, msgdata=self.tick_count)
				data, addr = self.socket.recvfrom(1024)
			except socket.error as e:
				logger.error(f'[s] {e}')
			if data:
				logger.debug(f'[ch] got data:{data} from:{addr}')
			if self.kill:
				logger.debug(f'[ch] got kill signal')
				# self.join(0)
				break

	def sendmsg(self, msgid=None, msgdata=None):
		#data = f'ch-{self.clid}:{msg}'.encode('utf-8')
		data = f'{msgid}:{self.clid}:{msgdata}'.encode('utf-8')
		# logger.debug(f'[connh] id:{self.clid} sending m:{msgdata} d:{data} to:{self.remote}')
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

	def __repr__(self):
		return f'[s] {self.name} {self.localaddr} {len(self.clients)} {len(self.clist)}'

	def get_client_count(self):
		return len(self.clients)

	def get_clients(self):
		return self.clients

	def run(self):
		self.socket.bind(self.localaddr)
		# self.socket.listen(0)
		self.kill = False
		logger.debug(f'[s] run {self} {self.localaddr}')
		while True:
			data = None
			addr = None
			clmsgid, clid, clmgs = None,None,None
			[ch.sendmsg(msgid=22, msgdata='pingfromserver') for ch in self.clients]
			try:
				data, addr = self.socket.recvfrom(1024)
			except socket.error as e:
				logger.error(f'[s] {e}')
			if data:				
				data = data.decode('utf-8')
				#logger.debug(data)
				try:
					clmsgid, clid, clmsg = data.split(':')
				except (TypeError, ValueError) as e:
					logger.warning(f'[s] {e} data:{data}')
				if clmsgid:
					clmsgid = int(clmsgid)
					# logger.debug(f'[s] data:{data} addr:{addr} {clmsgid} {clid} {clmsg}')
					ctest = self.clist.get(clid)
					if not ctest:
						self.clist[clid] = {'clid':clid, 'ticks':0, 'pos':Vector2(), 'msgbuf':''}
					if clmsgid == 1: # new client connect						
						if ctest:
							self.clist.get(clid)['ticks'] += 1
						else:
							
							logger.debug(f'[s] newclient clmsgid:{clmsgid} clid:{clid} clmsg:{clmsg} clients:{len(self.clients)} {len(self.clist)}')
							ch = ConnectionHandler(remote=addr, serverqueue=self.serverq, data=(clmsgid, clid, clmsg), srvsock=self.socket, stop_event=self.stop_event)
							ch.start()
							ch.sendmsg(msgid=11, msgdata='connectsuccess')
							self.clients.append(ch)
							ch.ch_connect()
					if clmsgid == 6:
						# send netplayers
						for ch in self.clients:
							#data = {'clist': self.clist, 'clients': len(self.clients)}
							try:
								clspos = self.clist.get(clid)['pos']
							except TypeError as e:
								logger.error(f'[s] {e} clid:{clid} clist:{self.clist} ch:{ch}')
								return
							data = f'{ch.clid}-{clid} pos={clspos}'
							ch.sendmsg(msgid=7, msgdata=data)
					if clmsgid == 5:
						#logger.debug(f'[s{clmsgid}] p:{clmsg} cl:{clid} from:{addr}')
						self.clist.get(clid)['msgbuf'] = clmsg
						self.clist.get(clid)['ticks'] += 1
					if clmsgid == 3: # movement
						pass
						#logger.debug(f'[s] got movemsg:{clmsg} from:{addr} msgid:{clmsgid} data:{data}')
					if clmsgid == 2: # ticker
						pass
						#logger.debug(f'[s] got tick:{clmsg} from:{addr} msgid:{clmsgid} data:{data}')						
					if clmsgid == 22: # ping
						pass
						#logger.debug(f'[s] got ping:{clmsg} from:{addr} msgid:{clmsgid} data:{data}')						
						#self.clist[clid].update_tick()
#						else:
							# logger.debug(f'[s] client clmsgid:{clmsgid} clid:{clid} clmsg:{clmsg}')
#							self.clist[clid] += 1
#							[cl.update_tick() for cl in self.clients if cl.get_clid() == clid]

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
					logger.info(f'[s] got msg:{msg}')
					self.serverq.task_done()
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
					logger.debug(f'[d] client:{cl} server.clients:{len(server.clients)} cl:{cl.remote}')
					cl.sendmsg(msgid=99, msgdata='debugfromserver')
			if cmd[:1] == 'p':
				logger.debug(f'[clientlist] total:{len(server.clients)}')
				for cl in server.clients:
					logger.debug(f'\tclient: {cl} ')
				logger.debug(f'[clist] total:{len(server.clist)}')
				for cl in server.clist:
					logger.debug(f'\tc: {cl} {server.clist[cl]}')
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


