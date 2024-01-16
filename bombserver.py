#!/usr/bin/python
import time
import os
import random
import socket
import sys
import json
from argparse import ArgumentParser
import threading
from threading import Thread, current_thread, Timer, active_count, _enumerate
from queue import Queue
from loguru import logger
import re
import pickle
import arcade
from constants import *
from exceptions import *
from objects import gen_randid

def generate_grid(gsz=GRIDSIZE):
	return json.loads(open('data/map.json','r').read())

class ServerSendException(Exception):
	pass

class HandlerException(Exception):
	pass

class TuiException(Exception):
	pass

class ServerTUI(Thread):
	def __init__(self, server, debugmode=False):
		Thread.__init__(self, daemon=True, name='tui')
		self.server = server
		self.killed = False
		self.debugmode = debugmode
		self._stop = threading.Event()

	def __repr__(self):
		return f'ServerTUI (s:{self.stopped()})'

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	def get_serverinfo(self):
		logger.info(f'playerlist={len(self.server.playerlist)} t:{active_count()}')
		for t in _enumerate():
			print(f'\t{t} {t.name} alive: {t.is_alive()}')

	def dump_playerlist(self):
		logger.info(f'playerlist: {len(self.server.playerlist)} clientlist: {len(self.server.clients)}')
		for p in self.server.playerlist:
			print(f'\tplayer: {p} pos: {self.server.playerlist[p].get("pos")} gp: {self.server.playerlist[p].get("gridpos")} b: {self.server.playerlist[p].get("bombsleft")} h: {self.server.playerlist[p].get("health")} uc: {self.server.playerlist[p].get("runcounter")} ')
		for c in self.server.clients:
			print(f'\tclient: {c.name} id: {c.client_id} connected: {c.connected} hqs: {c.handlerq.qsize()}')
			c.send_ping()

	def run(self):
		while True:
			if self.killed:
				break
			try:
				cmd = input(':> ')
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'p':
					self.dump_playerlist()
				elif cmd[:1] == 'q':
					self.killed = True
					self.server.killed = True
					logger.warning(f'{self} {self.server} tuikilled')
					# raise TuiException('tui killed')
					break
				# else:
				#	logger.info(f'[tui] {self} server: {self.server}')
			except KeyboardInterrupt:
				self.killed = True
				self.server.killed = True
				break


class NewHandler(Thread):
	def __init__(self, conn=None, addr=None, handlerq=None, name=None, debugmode=False, server=None, client_id=None):
		Thread.__init__(self,  daemon=True, name=f'Handler-{name}-{client_id}')
		self.client_id = client_id
		self.server = server
		self.debugmode = debugmode
		self.conn = conn
		self.addr = addr
		self.connected = True
		self.handlerq = handlerq
		self.name = name
		self._stop = threading.Event()
	def __repr__(self) -> str:
		return f'Handler ({self.client_id} {self.name} {self.connected} {self.handlerq.qsize()})'

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	def do_kill(self):
		self.connected = False
		logger.info(f'{self} dokill....')
		self.join()

	def send_ping(self):
		msg = {'msgtype': 'ping', 'client_id': self.client_id,}
		self.server.do_send(self.conn, self.addr, msg)

	def run(self):
		while self.connected:
			data = {'msgtype': 'none'}
			try:
				rawmsglen = self.conn.recv(PKTHEADER).decode(FORMAT)
			except ConnectionResetError as e:
				logger.warning(f'{self} {e} {type(e)} {e.errno}')
				self.connected = False
				data = {'msgtype': 'ConnectionResetError', 'client_id': self.client_id}
				rawmsglen = None
				self.handlerq.put(data)
				break
			except OSError as e:
				logger.warning(f'{self} {e} {type(e)}')
				self.connected = False
				break
			if rawmsglen == '':
				# rawmsglen2 = self.conn.recv(PKTHEADER * 2).decode(FORMAT)
				logger.warning(f'rawmsglenempty: {rawmsglen} {type(rawmsglen)} ' )
				data = {'msgtype': 'rawmsglenempty', 'client_id': self.client_id}
				rawmsglen = None
				self.connected = False
				self.handlerq.put(data)
				break
				# self.conn.close()
				# self.send_ping()
			if rawmsglen:
				try:
					msglen = int(re.sub('^0+','',rawmsglen))
				except ValueError as e:
					logger.error(f'error: {e} {type(e)} clientid: {self.client_id}  rawmsglen: {type(rawmsglen)} rawm: {rawmsglen}')
					data = {'msgtype': 'valueerror', 'error': e, 'client_id': self.client_id}
					msglen = None
					self.handlerq.put(data)
					# self.connected = False
					# self.conn.close()
					# break
				if msglen:
					try:
						rawmsg = self.conn.recv(msglen).decode(FORMAT)
					except OSError as e:
						logger.error(f'{self} {e} {type(e)} m:{msglen} rawmsglen: {type(rawmsglen)}\raw: {rawmsglen}')
						self.connected = False
						self.conn.close()
						break
					msgdata = re.sub('^0+','', rawmsg)
					try:
						data = json.loads(msgdata)
					except json.decoder.JSONDecodeError as e:
						logger.error(f'{e} msgdata: {msgdata}')
						data = {'msgtype': 'JSONDecodeError', 'error': e, 'msgdatabuffer' : msgdata, 'client_id': self.client_id}
					if self.handlerq.qsize() > 15:
						logger.warning(f"{self} handlerq: {self.handlerq.qsize()} data:\n{data}")
						# self.handlerq = Queue()
					self.handlerq.put(data)

class Gameserver(Thread):
	def __init__(self, connq, mainsocket, lock, debugmode=False):
		Thread.__init__(self,  daemon=True, name='gameserverthread')
		self._stop = threading.Event()
		self.debugmode = debugmode
		self.lock = lock
		self.mainsocket = mainsocket
		self.killed = False
		self.clients = []
		self.connq = connq
		self.serverdq = Queue()
		self.gridsize = 20
		self.grid = generate_grid(gsz=self.gridsize)
		self.playerlist = {}
		self.trgnpc = 0 # how often trigger_newplayer was called
		self.tui = ServerTUI(server=self)

	def __repr__(self):
		return f'Gameserver (c:{len(self.clients)})'

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	def trigger_newplayer(self, thread):
		self.trgnpc += 1
		thread.start()
		self.clients.append(thread)
		newpos = (110,101) # get_grid_pos(self.grid)
		self.playerlist[thread.client_id] = {'pos': newpos, 'bombsleft': 3, 'health': 100, 'runcounter': 0}
		# send this to the new client
		msg = {'msgtype': 'trigger_newplayer', 'clientname': thread.name, 'setpos': newpos, 'client_id': thread.client_id, 'playerlist': self.playerlist}
		logger.debug(f'trigger_newplayer c:{self.trgnpc} selfclients:{len(self.clients)} client: {thread.client_id}')
		self.do_send(thread.conn, thread.addr, msg)
		newplayer = {
			'client_id' : thread.client_id,
			'clientname' : thread.name,
			'pos' : newpos,
			}
		for client in self.clients:
			if client.client_id == thread.client_id:
				logger.info(f'skipping {client} {thread}')
			else:
				logger.debug(f'sending trigger_netplayers to {client}')
				# update other clients... # todo exclude the new client
				msg = {'msgtype': 'trigger_netplayers', 'clientname': client.name, 'client_id': client.client_id, 'newplayer': newplayer,}
				try:
					self.do_send(client.conn, client.addr, msg)
				except ServerSendException as e: # todo check and fix this...
					logger.warning(f'[!] {e} in {self} {client}')
					# self.playerlist.pop(clients.client_id)
					# self.clients.pop(self.clients.index(client))
				except Exception as e:
					logger.error(f'[!] {e} in {self} {client}')
					# self.playerlist.pop(clients.client_id)
					# self.clients.pop(self.clients.index(client))

	def refresh_playerlist(self, data):
		msgtype = data.get('msgtype')
		match msgtype:
			case 'playermove' | 'bombdrop' | 'on_update':
				# logger.debug(f'refresh_playerlist {data}')
				client_id = data.get('client_id')
				self.playerlist[client_id] = {'pos':data['pos']}
				#self.playerlist[data['client_id']] = {'client_id':data['client_id'],'pos':data['pos']}
				# logger.info(f'self.playerlist {self.playerlist}')
			case _:
				logger.warning(f'refresh_playerlist {data}')
		if len(self.clients) > 1:
			for client in self.clients:
				logger.debug(f'sending refresh_playerlist to {client}')
				# update other clients... # todo exclude the new client
				msg = {'msgtype': 'refresh_playerlist', 'playerlist': self.playerlist}
				try:
					self.do_send(client.conn, client.addr, msg)
				except ServerSendException as e: # todo check and fix this...
					logger.warning(f'[!] {e} in {self} {client}')
					# self.playerlist.pop(clients.client_id)
					# self.clients.pop(self.clients.index(client))
				except Exception as e:
					logger.error(f'[!] {e} in {self} {client}')
					# self.playerlist.pop(clients.client_id)
					# self.clients.pop(self.clients.index(client))
			# if client_id:
			# 	self.playerlist[client_id] = data
			# else:
			# 	logger.error(f'client_id not found in {data}')

	def do_send(self, socket, serveraddress, data):
		data['playerlist'] = self.playerlist
		data['grid'] = {}# self.grid
		try:
			payload = json.dumps(data).encode('utf8')
		except (ValueError, TypeError) as e:
			logger.error(f'{e} {type(e)} {data} {type(data)}')
			return
		if payload:
			try:
				# logger.debug(f'do_send {socket} {serveraddress} {payload}')

				msglenx = str(len(payload)).encode('utf8')
				msglen = msglenx.zfill(PKTHEADER)
				try:
					socket.sendto(msglen,serveraddress )
					# logger.debug(f'do_send_msglen {pmsgtype} len: {msglenx}')
				except TypeError as e:
					# logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
					raise ServerSendException(f'sendmsglen {e} {type(e)}')
				except OSError as e:
					logger.error(f'{e} msglenerror = {type(msglen)} {msglen} ')# \npayload = {type(payload)}\n{payload}\n')
					# raise ServerSendException(f'sendmsglen {e} {type(e)}')
				try:
					socket.sendto(payload,serveraddress)
					# logger.debug(f'do_send payload: {pmsgtype} {type(payload)}')
				except OSError as e:
					# logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
					raise ServerSendException(f'sendpayload {e} {type(e)}')
				except TypeError as e:
					# logger.error(f'{e} payloaderror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
					raise ServerSendException(f'sendpayload {e} {type(e)}')
			except ServerSendException as e:
				if self.debugmode:
					logger.warning(f'[!] {e} {type(e)} p: {len(payload)}')
				else:
					logger.warning(f'[!] {e} {type(e)}')
				# raise ServerSendException(e)#
			except Exception as e:
				logger.error(f'[!] {e} {type(e)} {type(payload)} p: {len(payload)}')

	def msg_handler(self, data):
		msgtype = data.get('msgtype')
		if not msgtype:
			logger.error(f'[!] msgtype not found in {data}')
		self.refresh_playerlist(data) # todo check disconnected clients
		match msgtype:
			case 'on_update':
				logger.info(f'{msgtype} from {data.get("client_id")} delta_time: {data.get("delta_time")} ')
			case 'playermove':
				logger.info(f'{msgtype} from {data.get("client_id")} pos: {data.get("pos")} ')
				for client in self.clients:
					try:
						self.do_send(client.conn, client.addr, data)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						# self.playerlist.pop(clients.client_id)
						# self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						# self.playerlist.pop(clients.client_id)
						# self.clients.pop(self.clients.index(client))
			case 'bombdrop':
				logger.info(f'{msgtype} from {data.get("bomber")} pos: {data.get("pos")}')
				for client in self.clients:
					try:
						self.do_send(client.conn, client.addr, data)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						# self.playerlist.pop(clients.client_id)
						# self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						# self.playerlist.pop(clients.client_id)
						# self.clients.pop(self.clients.index(client))
			case 'onkeypress':
				logger.info(f'{msgtype} ')
			case 'getservermap':
				logger.info(f'{msgtype} ')
			case 'valueerror' | 'JSONDecodeError' | 'rawmsglenempty':
				logger.warning(f'{msgtype} data: {data}')
			case _:
				logger.warning(f'unknown msgtype {msgtype} from {data.get("client_id")}\ndata: {data}')

	def run(self):
		# logger.info(f'{self} starting tui')
		# self.tui.start()
		logger.info(f'{self} started')
		while True:
			if self.tui.killed: # todo fix tuiquit
				logger.warning(f'{self} tui {self.tui} killed')
				self.killed = True
				self.stop()
				# self.mainsocket.close()
				break
				# sys.exit(1)
			if self.killed:
				logger.warning(f'{self} killed')
				self.stop()
				break
			for c in self.clients:
				if not c.handlerq.empty():
					datafromq = c.handlerq.get()
					c.handlerq.task_done()
					try:
						# data = json.loads(datafromq)
						self.msg_handler(datafromq)
					except json.decoder.JSONDecodeError as e:
						logger.error(f'{e} {type(e)} {type(datafromq)} {datafromq}')
						continue
					# logger.debug(f'{self} msghanlder {data}')

def get_grid_pos(grid):
	# find a random spot on the map to place the player
	validpos = False
	invcntr = 0
	gpx, gpy = 0,0
	while not validpos:
		# find a random spot on the map to place the player
		gpx = random.randint(1, len(grid)-1)
		gpy = random.randint(1, len(grid)-1)
		try:
			if grid[gpx][gpy] == 2:
				validpos = True
				# logger.info(f'valid {invcntr} pos gpx:{gpx} gpy:{gpy} grid={grid[gpx][gpy]}')
				return (gpx, gpy)
		except (IndexError, ValueError, AttributeError) as e:
			logger.error(f'Err: {e} {type(e)} gl={len(grid)} gpx={gpx} gpy={gpy} ')

def bind_thread(server):
	pass

class BindThread(Thread):
	def __init__(self, server, lock, debugmode=False):
		Thread.__init__(self, daemon=True, name='Bindthread')
		self.debugmode = debugmode
		self.lock = lock
		self.server = server
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._stop = threading.Event()

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()


	def run(self):
		try:
			self.socket.bind((args.listen,args.port))
		except OSError as e:
			logger.error(e)
			sys.exit(1)
		except Exception as e:
			logger.error(e)
			sys.exit(1)
		conncounter = 0
		while True:
			self.socket.listen()
			try:
				conn, addr = self.socket.accept()
			except KeyboardInterrupt as e:
				logger.warning(f'{e}')
				break
			except Exception as e:
				logger.warning(f'{e} {type(e)}')
				break
			client_id =  gen_randid()
			thread = NewHandler(conn=conn, addr=addr, handlerq=Queue(), name=f'clthrd{conncounter}', server=self.server, client_id=client_id)
			# self.server.clients.append(thread)
			# thread.start()
			conncounter += 1
			logger.info(f'newconnection thread: {client_id} {thread} conn: {conncounter} serverc: {len(self.server.clients)}')
			self.server.trigger_newplayer(thread)


def locker_thread(lock):
    logger.debug('locker_thread Starting')

if __name__ == '__main__':
	parser = ArgumentParser(description='server')
	parser.add_argument('--listen', action='store', dest='listen', default='localhost')
	parser.add_argument('--port', action='store', dest='port', default=9696, type=int)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()

	mainsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	mainsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	threads = []
	connq = Queue()

	# lock = threading.Lock()
	# lt = Thread(target=locker_thread, args=(lock,), daemon=True, name='svlocker_thread')
	# threads.append(lt)
	lock = None
	gt = Gameserver(connq=connq, mainsocket=mainsocket, lock=lock, debugmode=args.debug)
	tui = ServerTUI(server=gt, debugmode=args.debug)
	threads.append(tui)
	# tui.run()
	threads.append(gt)
	bt = BindThread(server=gt, lock=lock, debugmode=args.debug)
	threads.append(bt)
	for t in threads:
		logger.info(f'starting {t}')
		t.start()
	killserver = False
	while not killserver:
		for t in threads:
			try:
				if t.stopped():
					logger.warning(f'{t} killed')
					killserver = True
					break
			except Exception as e:
				logger.error(f'{e} {type(e)} t: {t}')
				killserver = True
