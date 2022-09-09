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


class ConnectionHandler(Thread):
	def __init__(self, name=None, remote=None, serverqueue=None, data=None, srvsock=None, stop_event=None, packet_trace=False):
		Thread.__init__(self, name=f'chthread-{name}', daemon=True, args=(stop_event,))
		self.name = name
		#self.socket = socket
		#self.localaddr = localaddr
		self.kill = False
		self.serverq = serverqueue
		self.remote = remote # (remote[0], 6669)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.clmsgid, self.clid, self.clmsg = data
		self.tick_count = 0
		self.client_pos = Vector2()
		self.packet_trace = packet_trace
		self.server = ('192.168.1.122', 6666)
		self.localaddr = self.server # (get_ip_address()[0], 6667)
		self.ds = DataSender(s_socket=self.socket, server=self.remote, name=self.clid, stop_event=stop_event)
		self.dr = DataReceiver(r_socket=self.socket, server=self.remote, localaddr=self.localaddr, name=self.clid, stop_event=stop_event)
		logger.debug(f'[ch] id:{self.clid} init r:{self.remote} d:{data}')

	def __repr__(self) -> str:
		return f'[ch] id:{self.clid} r:{self.remote} n:{self.name} t:{self.tick_count}'

	def set_packet_trace(self, state=2): # 0=off, 1=on, 2=toggle
		if state == 0:
			self.packet_trace = False
		if state == 1:
			self.packet_trace = True
		if state == 2:
			self.packet_trace ^= True
		logger.debug(f'[ch] id:{self.clid} s:{state} pkt:{self.packet_trace}')

	def get_clpos(self):
		pass

	def get_clid(self):
		return self.clid

	def update_tick(self):
		self.tick_count += 1
		# logger.debug(f'[ch] uptick:{self.tick_count}')

	def handle_incoming(self, data):
		logger.debug(f'[ch] incoming:{data}')

	def run(self):
		self.ds.start()
		self.dr.start()
		while True:
			data = None
			addr = None
			try:
				# clmsgid, clid, clmsg = data.split(':')
				self.sendmsg(msgid=2, msgdata=self.tick_count)
				incoming = None
				outgoing = None
				if not self.dr.queue.empty():
					incoming = self.dr.queue.get()
					self.handle_incoming(data=incoming)
					# logger.debug(f'[c] incoming from  recvq:{incoming}')
					self.dr.queue.task_done()
				# data, addr = self.socket.recvfrom(1024)
			except socket.error as e:
				logger.error(f'[s] {e}')
			if data:
				if self.packet_trace:
					logger.debug(f'[ch] got data:{data} from:{addr}')
			if self.kill:
				logger.debug(f'[ch] got kill signal')
				# self.join(0)
				break

	def sendmsg(self, msgid=None, msgdata=None):
		data = f'{msgid}:{self.clid}:{msgdata}'.encode('utf-8')
		self.ds.queue.put(data)

	def sendmsgx(self, msgid=None, msgdata=None):
		#data = f'ch-{self.clid}:{msg}'.encode('utf-8')
		data = f'{msgid}:{self.clid}:{msgdata}'.encode('utf-8')
		if self.packet_trace:
			logger.debug(f'[connh] id:{self.clid} sending mid:{msgid} m:{msgdata} d:{data} to:{self.remote}')
		self.socket.sendto(data, self.remote)

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
		self.packet_trace = False

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
				if self.packet_trace:
					logger.debug(f'[pkt] packet:{data} from:{addr}')
				data = data.decode('utf-8')
				try:
					clmsgid, clid, clmsg = data.split(':')
				except (TypeError, ValueError) as e:
					logger.warning(f'[s] {e} data:{data}')
				if clmsgid:
					clmsgid = int(clmsgid)
					if clmsgid == 1: # new client connect										
						if clid not in self.clist:
							logger.debug(f'[s] newclient clmsgid:{clmsgid} clid:{clid} clmsg:{clmsg} clients:{len(self.clients)} {len(self.clist)} clist:{self.clist}')
							self.clist[clid] = {'clid':clid, 'ticks':0, 'pos':Vector2(), 'msgbuf':'', 'clport':6669}
							self.clist[clid]['clport'] += 1
							ch = ConnectionHandler(remote=addr, serverqueue=self.serverq, data=(clmsgid, clid, clmsg), srvsock=self.socket, stop_event=self.stop_event, packet_trace=self.packet_trace)
							ch.start()
							# clport = 6669+len(self.clients)+1
							ch.sendmsg(msgid=11, msgdata=f'connectsuccess-{self.clist[clid]["clport"]}')
							self.clients.append(ch)
						else:
							self.clist.get(clid)['ticks'] += 1
							for ch in self.clients:
								chmsg = f'connectsuccess-{self.clist[clid]["clport"]}'
								ch.sendmsg(msgid=11, msgdata=chmsg)
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
					if clmsgid == 155: #getserverinfo
						serverinfo = {
							'name': self.name,
							'laddr': self.localaddr,
							'clients': len(self.clients),
							'clist': len(self.clist),
							'clist': self.clist
						}
						for ch in self.clients:
							ch.sendmsg(msgid=156, msgdata=serverinfo)
							logger.debug(f'[s] sent serverinfo:{serverinfo} to:{ch} r:{ch.remote}')
						# data = pickle.dumps(serverinfo)
						#[ch.sendmsg(msgid=156, msgdata=serverinfo) for ch in self.clients]
						#pass
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


