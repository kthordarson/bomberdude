import struct
import socket
import sys
import time
import multiprocessing
from multiprocessing import Queue
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

from queue import Queue as OldQueue



class BombClientHandler(Thread):
	def __init__(self, conn=None, serverq=None, addr=None):
		Thread.__init__(self)
		self.queue = serverq
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = None
		self.kill = False
		self.conn = conn
		self.addr = addr
		self.netplayers = {}
		self.pos = Vector2(0,0)
		logger.info(f'[BC] {self} BombClientHandler init conn:{self.conn} addr:{self.addr} client_id:{self.client_id}')

	def __str__(self):
		return f'[BCID] {self.client_id}'

	def sender(self):
		logger.info(f'[BC] {self} senderthread started')
		while True:
			if self.kill:
				logger.warning(f'[BC] {self} senderthread killed')
				break
			if not self.sendq.empty():
				payload = self.sendq.get()
				try:
					send_data(self.conn, payload={'msgtype':'bcnetupdate', 'payload':payload}, data_id=dataid['update'])
				except BrokenPipeError as e:
					logger.error(f'[BC] {self} senderthread BrokenPipeError:{e}')
					self.kill = True
					break
				# self.sendq.task_done()

	def get_client_id(self):
		payload = {'msgtype':'bcgetid', 'payload':'sendclientid'}
		self.sendq.put_nowait(payload)

	def run(self):
		logger.debug(f'[BC] {self.client_id} run ')
		st = Thread(target=self.sender, daemon=True)
		st.start()
		while True:
			if self.client_id is None:
				self.get_client_id()
			rid, resp = None, None
			if self.kill:
				logger.debug(F'[BC] {self} killed')
				self.kill = True
				break
			#if len(self.netplayers) >= 1:
			payload = {'msgtype':'bcpoll', 'payload':self.client_id, 'netplayers':self.netplayers}
			self.sendq.put_nowait(payload)
			#send_data(self.conn, payload={'msgtype':'bcupdate', 'payload':'kren'}, data_id=dataid['update'])
			try:
				rid, resp = receive_data(self.conn)
				# logger.debug(f'[BCH] {self} rid:{rid} resp:{resp}')
			except (ConnectionResetError, BrokenPipeError) as e:
				logger.error(f'[BC] {self} connection error:{e}')
				#self.kill = True
				#break
			rtype = dataid.get(rid, None)
			if rid == dataid.get('info'):
				self.queue.put({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos})
			elif rtype == dataid.get('playerpos') or rid == 3:
				s_clid = resp.get('client_id')
				s_pos = resp.get('pos')
				logger.debug(f"[BC] {self} playerpos {s_clid} {s_pos} {self.pos}")
				self.pos = s_pos
				self.queue.put({'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos})
			elif rtype == dataid.get('gameevent') or rid == 9:
				logger.debug(f'[BC] {self} gamevent received id:{rid} resp={resp}')
			elif rtype == dataid['auth'] or rid == 101:
				logger.debug(f'[BC] {self} auth received id:{rid} resp={resp}')
				clid = resp.get('client_id')
				self.client_id = clid
			elif rtype == dataid['UnpicklingError'] or rid == 1002:
				logger.warning(f'[BC] {self} UnpicklingError rid:{rid}')
			else:
				if resp:
					logger.error(f'[BC] {self} unknownevent rid:{rid} rtype:{rtype}  resp={len(resp)} resp={resp}')
				else:
					logger.error(f'[BC] {self} unknownevent noresp rid:{rid} rtype:{rtype}  resp={type(resp)}')

class BombServer(Thread):
	def __init__(self):
		Thread.__init__(self, daemon=True)
		self.bombclients  = []
		self.gamemap = Gamemap()
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.netplayers = {}

	def updater(self, queue):
		logger.info(f'[server] send_update thread started')
		netdata = None
		data = None
		while not self.kill:
			try:
				payload = {'msgtype':'update', 'payload':'kren'}
				self.sendq.put_nowait(payload)
				# send_data(self.conn, payload={'msgtype':'update', 'payload':'kren'}, dataid=dataid['update'])
			except OSError as e:
				pass
			try:
				netdata = self.conn.recv(1024)
			except OSError as e:
				pass
			if netdata:
				logger.debug(f'[server] received data:{netdata}')

	def run(self):
		#update_thread = Thread(target=self.updater, daemon=True, args=(self.queue,))
		#update_thread.start()
		logger.debug(f'[server] run')
		while not self.kill:
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
					bc = BombClientHandler(conn=conn,addr=addr, serverq=self.queue)
					logger.debug(f'[server] new player:{bc} cl:{len(self.bombclients)}')
					self.bombclients.append(bc)
					bc.start()
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
	while not server.kill:
		logger.debug(f'[bombserver] waiting for connection clients:{clients}')		
		try:
			if server.kill:
				break
#			try:
			rid, resp, clid, akey = None, None, None, None
			conn, addr = server.conn.accept()
			server.queue.put({'msgtype':'newclient', 'conn':conn, 'addr':addr})
			#send_data(conn, payload={'msgtype':'auth', 'msg':'doauth'}, data_id=dataid['auth'])
			#rid, resp = receive_data(conn)
			#if rid == dataid['UnpicklingError']:
		#		conn.close()
				#send_data(conn, payload={'msgtype':'auth', 'msg':'doauth'}, data_id=dataid['auth'])
				#rid, resp = receive_data(conn)
			# clid, akey = None,None
			# logger.debug(f'[s] new connection rid:{rid} resp:{resp}')
			# try:
			# 	if resp:
			# 		clid = resp.get('payload').get('client_id')
			# 		akey = resp.get('payload').get('authkey')
			# 		if not akey:
			# 			akey = resp.get('authkey')
			# 		if resp.get('msgtype') == 'engineupdate' or resp.get('msgtype') == 'auth' or rid == 101:
			# 			#logger.debug(f'[newconn] authkey={resp.get("authkey")} rid:{rid} resp:{resp} clid:{clid}')
			# 			server.queue.put({'msgtype':'newclient', 'clid':clid, 'conn':conn, 'addr':addr})
			# 			clients += 1
			# 		# elif akey == 'foobar':
			# 		# 	#pass
			# 		# 	logger.debug(f'[newconn] rid:{rid} resp:{resp} clid:{clid}')
			# 		elif resp.get('msgtype') == dataid['playerpos']:
			# 			logger.warning(f'[s] clid:{clid} rid:{rid} resp:{resp} ')
			# 			# serverq.put({'msgtype':'playerpos', 'clid':clid, 'conn':conn, 'addr':addr, 'payload':resp.get('payload')})
			# 		else:
			# 			logger.warning(f'[s] autherr authkey={akey} rid:{rid} resp:{resp}')
			# 			conn.close()
			# except AttributeError as e:
			# 	logger.warning(f'[s] AttributeError {e}')
			# 	#serverq.put({'msgtype':rid, 'clid':resp.get('client_id'), 'pos':resp.get('pos')})
			# 	conn.close()
			# except OSError as e:
			# 	logger.warning(f'[s] oserror {e}')
			# 	conn.close()
		except KeyboardInterrupt as e:
			logger.warning(f'KeyboardInterrupt:{e} serverq:{server.queue} server:{server}')
			server.kill = True
			#serverq.join()
			break

if __name__ == '__main__':
	main()
