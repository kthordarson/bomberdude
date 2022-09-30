import struct
import socket
import sys
import time
import multiprocessing
from multiprocessing import Queue as mQueue
from xml.sax import ContentHandler
from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group
from threading import Thread, Event
import pickle

from things import Block
from constants import GRIDSIZE
from map import Gamemap
from globals import gen_randid
from network import receive_data, send_data, dataid

from queue import Queue

class Sender(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.kill = False
		self.queue = Queue()
		self.sendcount = 0
		logger.info(f'[BC] {self} senderthread init')

	def __str__(self):
		return f'[sender] count={self.sendcount} sq:{self.queue.qsize()}'
	
	# def send(self, conn, payload):
	# 	logger.debug(f'[send] {self} {conn} {payload}')
	# 	try:
	# 		send_data(conn, payload={'msgtype':'bcnetupdate', 'payload':payload}, data_id=dataid['update'])
	# 	except BrokenPipeError as e:
	# 		logger.error(f'[BC] {self} senderthread BrokenPipeError:{e}')
	# 		self.kill = True
	# 	return

	def run(self):
		logger.info(f'{self} run')
		while True:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			if not self.queue.empty():
				conn, payload = self.queue.get()
				# logger.debug(f'{self} senderthread sending payload:{payload}')
				try:
					send_data(conn, payload={'msgtype':'bcnetupdate', 'payload':payload}, data_id=dataid['update'])
				except ConnectionResetError as e:
					logger.error(f'{self} senderr {e}')
				self.sendcount += 1
				self.queue.task_done()

class Servercomm(Thread):
	def __init__(self, queue=None):
		Thread.__init__(self)
		self.kill = False
		self.queue = queue
		self.netplayers = {}
		self.srvcount = 0
		logger.info(f'[BC] {self} server_comm init')

	def __str__(self):
		return f'[scomm] count={self.srvcount} np={len(self.netplayers)} sq:{self.queue.qsize()}'

	def run(self):
		logger.info(f'{self} server_comm run')
		while True:
			if self.kill:
				logger.warning(f'{self} server_comm killed')
				break
			payload = None
			if not self.queue.empty():
				payload = self.queue.get()
				self.srvcount += 1
				if payload:
					if payload.get('msgtype') == 'netplayers':
						netplayers = payload.get('netplayers')
						for np in netplayers:
							self.netplayers[np] = netplayers[np]
				#logger.debug(f'{self} payload:{payload}')


class BombClientHandler(Thread):
	def __init__(self, conn=None,  addr=None, gamemap=None):
		Thread.__init__(self)
		self.queue = Queue()
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = None
		self.kill = False
		self.conn = conn
		self.addr = addr
		self.netplayers = {}
		self.pos = Vector2(0,0)
		self.gamemap = gamemap
		self.st = Sender()
		self.srvcomm = Servercomm(self.queue)
		logger.info(f'[BC] {self} BombClientHandler init conn:{self.conn} addr:{self.addr} client_id:{self.client_id}')

	def __str__(self):
		return f'[BCH] {self.client_id} sq:{self.queue.qsize()} sqs:{self.sendq.qsize()} {self.st} {self.srvcomm}'

	def send_map(self):
		payload = {'msgtype':'mapfromserver', 'gamemap':self.gamemap}
		#self.st.send(self.conn, payload)
		self.st.queue.put_nowait((self.conn, payload))


	def get_client_id(self):
		payload = {'msgtype':'bcgetid', 'payload':'sendclientid'}
		self.st.queue.put_nowait((self.conn, payload))
		logger.debug(f'{self} sent payload:{payload}')
		#self.st.send(self.conn, payload)
		rid, resp = None, None
		try:
			rid, resp = receive_data(self.conn)
			if rid == dataid['UnpicklingError']:
				logger.warning(f'{self} UnpicklingError rid={rid} resp={resp}')
				return
			if resp or rid:
				logger.debug(f'{self} rid:{rid} resp:{resp}')
				clid = resp.get('client_id')
				self.client_id = clid
				logger.info(f'{self} rid:{rid} resp:{resp}')
				if resp.get('payload') == 'reqmap':
					self.send_map()
		except (ConnectionResetError, BrokenPipeError, struct.error, EOFError) as e:
			logger.error(f'{self} receive_data error:{e}')
		#self.sendq.put_nowait(payload)

	def run(self):
		self.get_client_id()
		logger.debug(f'[BC] {self.client_id} run ')
		#st = Thread(target=self.sender, daemon=True)
		#st.start()
		#srvcomm = Thread(target=self.server_comms, daemon=True)
		#srvcomm.start()
		self.st.start()
		self.srvcomm.start()
		while True:
			self.netplayers = self.srvcomm.netplayers
			# logger.debug(f'{self} np={self.netplayers}')
			if self.client_id is None:
				self.get_client_id()
			rid, resp = None, None
			if self.kill:
				logger.debug(F'{self} killed')
				self.kill = True
				break
			#if len(self.netplayers) >= 1:
			payload = {'msgtype':'bcpoll', 'payload':self.client_id, 'netplayers':self.netplayers}
			# self.sendq.put_nowait(payload)
			#self.st.send(self.conn, payload)
			self.st.queue.put_nowait((self.conn, payload))
			#send_data(self.conn, payload={'msgtype':'bcupdate', 'payload':'kren'}, data_id=dataid['update'])
			try:
				rid, resp = receive_data(self.conn)
				# logger.debug(f'{self} rid:{rid} resp:{resp}')
			except (ConnectionResetError, BrokenPipeError, struct.error, EOFError) as e:
				logger.error(f'{self} receive_data error:{e}')
				payload = {'msgtype':'bcpoll', 'payload':self.client_id, 'netplayers':self.netplayers}
				#self.sendq.put_nowait(payload)
				#self.st.send(self.conn, payload)
				# self.st.queue.put_nowait((self.conn, payload))
				#self.kill = True
				#break
			rtype = dataid.get(rid, None)
			if rid == dataid.get('info') or rid == 0:
				self.srvcomm.queue.put({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos})
			elif rtype == dataid.get('playerpos') or rid == 3:
				s_clid = resp.get('client_id')
				s_pos = resp.get('pos')
				#logger.debug(f"[BC] {self} playerpos {s_clid} {s_pos} {self.pos}")
				self.pos = s_pos
				self.srvcomm.queue.put({'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos})
			elif rtype == dataid.get('update') or rid == 4:
				logger.debug(f'{self} bomb received id:{rid} resp={resp}')
			elif rtype == dataid['reqmap'] or rid == 7:
				#logger.debug(f'{self} reqmap received id:{rid} resp={resp}')
				#self.sendq.put_nowait({'msgtype':'mapfromserver', 'gamemap':self.gamemap})
				self.send_map()
				#payload = {'msgtype':'mapfromserver', 'gamemap':self.gamemap}
				#self.st.send(self.conn, payload)
				#self.st.queue.put_nowait((self.conn, payload))
			elif rtype == dataid.get('gameevent') or rid == 9:
				logger.debug(f'{self} gamevent received id:{rid} resp={resp}')
			elif rtype == dataid['auth'] or rid == 101:
				logger.debug(f'{self} auth received id:{rid} resp={resp}')
				clid = resp.get('client_id')
				self.client_id = clid
			elif rtype == dataid['UnpicklingError'] or rid == 1002:
				logger.warning(f'{self} UnpicklingError rid:{rid}')
				payload = {'msgtype':'bcpoll', 'payload':self.client_id, 'netplayers':self.netplayers}
				# self.sendq.put_nowait(payload)
				#self.st.send(self.conn, payload)
				# self.st.queue.put_nowait((self.conn, payload))
			else:
				if resp:
					logger.error(f'{self} unknownevent rid:{rid} rtype:{rtype}  resp={len(resp)} resp={resp}')
				else:
					logger.error(f'{self} unknownevent noresp rid:{rid} rtype:{rtype}  resp={type(resp)}')

class BombServer(Thread):
	def __init__(self):
		Thread.__init__(self, daemon=True)
		self.bombclients  = []
		self.gamemap = Gamemap()
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.netplayers = {}


	def run(self):
		logger.debug(f'[server] run')
		while not self.kill:
			for bc in self.bombclients:
				if bc.client_id:
					np = {'client_id':bc.client_id, 'pos':bc.pos}
					self.netplayers[bc.client_id] = np
					payload = {'msgtype':'netplayers', 'netplayers':self.netplayers}
					bc.srvcomm.queue.put(payload)
			if self.kill:
				logger.debug(f'[server] killed')
				for c in self.bombclients:
					logger.debug(f'[server] killing {c}')
					c.kill = True
				break
			if not self.queue.empty():
				data = self.queue.get()
				# logger.debug(f'[server] getq data:{data}')
				type = data.get('msgtype')
				# self.queue.task_done()
				if type == 'newclient':
					# logger.debug(f'[server] q: {data}')
					conn = data.get('conn')
					addr = data.get('addr')
					# clid = data.get('clid')
					bc = BombClientHandler(conn=conn, addr=addr, gamemap=self.gamemap)
					logger.debug(f'[server] new player:{bc} cl:{len(self.bombclients)}')
					self.bombclients.append(bc)
					bc.start()
				else:
					logger.warning(f'[server] q: {data}')
				# if type == 'playerpos':
				# 	# logger.debug(f'[server] q: {data}')
				# 	for bc in self.bombclients:
				# 		clid = data.get('client_id')
				# 		pos = data.get('pos')
				# 		if clid != bc.client_id:
				# 			bc.netplayers[clid] = {'pos':pos}
				# 			self.netplayers[clid] = {'pos':pos}
					#foo=[f'{k} {self.netplayers[k].get("pos")}' for k in self.netplayers]
					#logger.debug(f'[server] netplayers {foo}')
			# try:
			# 	cmd = input(f'[{len(self.bombclients)}]> ')
			# 	if cmd[:1] == 'd':
			# 		logger.info(f'[dump] ')
			# 	if cmd[:1] == 'u':
			# 		pass
			# 	if cmd[:1] == 'q':
			# 		logger.info(f'quit')
			# 		self.kill = True
			# except KeyboardInterrupt as e:
			# 	logger.warning(f'KeyboardInterrupt:{e}')
			# 	self.kill = True
			# 	return


def main():
	mainthreads = []
	key_message = 'bomberdude'
	logger.debug(f'[bombserver] started')
	clients = 0
	# serverq = Queue()
	server = BombServer()
	server.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.conn.bind(('127.0.0.1', 9696))
	server.conn.listen()
	server.start()
	while True:
		logger.debug(f'[bombserver] waiting for connection clients:{clients}')
		try:
			if server.kill:
				break
			conn, addr = server.conn.accept()
			server.queue.put({'msgtype':'newclient', 'conn':conn, 'addr':addr})
		except KeyboardInterrupt as e:
			server.conn.close()
			logger.warning(f'KeyboardInterrupt:{e} serverq:{server.queue} server:{server}')
			for bc in server.bombclients:
				logger.warning(f'kill bc:{bc}')
				bc.kill = True
				bc.join()
			server.kill = True
			server.join()
			logger.warning(f'kill server:{server}')
			return

if __name__ == '__main__':
	logger.info('start')
	main()
	logger.info('done')
	sys.exit(0)
