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
from constants import PKTHEADER, FORMAT
from map import generate_grid



class ServerSendException(Exception):
	pass

class HandlerException(Exception):
	pass

class TuiException(Exception):
	pass

class ServerTUI(Thread):
	def __init__(self, server):
		Thread.__init__(self, daemon=True, name='tui')
		self.server = server
		self.killed = False

	def __repr__(self):
		return f'ServerTUI (k:{self.killed} server: {self.server})'

	def get_serverinfo(self):
		logger.info(f'playerlist={len(self.server.playerlist)} t:{active_count()}')
		for t in _enumerate():
			print(f'{t} {t.name} {t.is_alive()}')

	def dump_playerlist(self):
		logger.info(f'playerlist={len(self.server.playerlist)} ')
		for p in self.server.playerlist:
			logger.info(f'{p} {self.server.playerlist[p].get("client_id")} pos: {self.server.playerlist[p].get("pos")} {self.server.playerlist[p].get("gridpos")} b: {self.server.playerlist[p].get("bombsleft")} h: {self.server.playerlist[p].get("health")} {self.server.playerlist[p].get("updcntr")} ')

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
				else:
					logger.info(f'[S] cmds: s serverinfo, p playerlist, q quit')
			except KeyboardInterrupt:
				self.killed = True
				self.server.killed = True
				break


class NewHandler(Thread):
	def __init__(self, conn, addr, dataq, name):
		Thread.__init__(self,  daemon=True, name=name)
		self.conn = conn
		self.addr = addr
		self.connected = True
		self.dataq = dataq
		self.name = name
		self.client_id = None

	def __repr__(self) -> str:
		return f'Handler ({self.client_id} {self.name} {self.connected} {self.dataq.qsize()})'

	def run(self):
		while self.connected:
			try:
				rawmsglen = self.conn.recv(PKTHEADER).decode(FORMAT)
			except ConnectionResetError as e:
				logger.warning(f'{self} {e}')
				self.connected = False
				self.conn.close()
				break
			try:
				msglen = int(re.sub('^0+','',rawmsglen))
			except ValueError as e:
				logger.error(f'{self.client_id} disconnected {e} {type(e)}') # \nrawmsglen: {type(rawmsglen)}\nrawm: {rawmsglen}')
				self.connected = False
				# self.conn.close()
				break
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
			if not self.client_id:
				self.client_id = data.get('client_id', None)
				logger.info(f'{self} setclid client_id: {self.client_id} ')
			self.dataq.put(data)
			if self.dataq.qsize() > 5:
				logger.warning(f"{self} dataq: {self.dataq.qsize()}")

class Gameserver(Thread):
	def __init__(self, connq, mainsocket, lock):
		Thread.__init__(self,  daemon=True, name='gameserverthread')
		self.lock = lock
		self.mainsocket = mainsocket
		self.killed = False
		self.clients = []
		self.connq = connq
		self.dataq = Queue()
		self.grid = generate_grid()
		self.playerlist = {}
		self.updcntr = 0
		self.tui = ServerTUI(server=self)

	def __repr__(self):
		return f'Gameserver (c:{len(self.clients)})'

	def trigger_newplayer(self):
		self.updcntr += 1
		for client in self.clients:
			logger.debug(f'trigger_newplayer c:{self.updcntr} client: {client}')
			newpos = get_grid_pos(self.grid)
			msg = {'msgtype': 'trigger_newplayer', 'clientname': client.name, 'setpos': newpos, 'client_id': client.client_id}
			try:
				# self.do_send(client._args[0], client._args[1], msg)
				self.do_send(client.conn, client.addr, msg)
			except ServerSendException as e: # todo check and fix this...
				logger.warning(f'[!] {e} in {self} {client}')
				# self.playerlist.pop(clients.client_id)
				# self.clients.pop(self.clients.index(client))
			except Exception as e:
				logger.error(f'[!] {e} in {self} {client}')
				# self.playerlist.pop(clients.client_id)
				# self.clients.pop(self.clients.index(client))

	def refresh_clients(self):
		# logger.info(f'playerlist {self.playerlist}\nclients: {self.clients}\n' )
		for cl in self.clients:
			# logger.info(f'cl: {cl} ')
			if not cl.client_id:
				pass
				# logger.warning(f'needclientid {cl} {self.clients}')
				# continue
			else:
				try:
					if not cl.connected:
						self.playerlist.pop(cl.client_id) # ]['connected'] = False
						self.clients.pop(self.clients.index(cl))
						logger.warning(f'{self} {cl.client_id} disconnected playerlist: {len(self.playerlist)}')
						# self.playerlist.pop(self.playerlist.index(cl))
					elif cl.connected:
						pass
						# self.playerlist[cl.client_id]['connected'] = True
				except KeyError as e:
					logger.error(f'{e} {type(e)} {cl} {self.playerlist} {self.clients}')
					continue


	def refresh_playerlist(self, data):
		# logger.debug(f'refresh_playerlist {data}')
		clid = data.get('client_id')
		if clid:
			self.playerlist[clid] = data
		else:
			logger.error(f'clid not found in {data}')

	def do_send(self, socket, serveraddress, payload):
		payload['playerlist'] = self.playerlist
		payload['grid'] = self.grid
		payload['updcntr'] = self.updcntr
		try:
			# logger.debug(f'do_send {socket} {serveraddress} {payload}')
			payload = json.dumps(payload).encode('utf8')
			msglenx = str(len(payload)).encode('utf8')
			msglen = msglenx.zfill(PKTHEADER)
			try:
				socket.sendto(msglen,serveraddress )
				# logger.debug(f'do_send_msglen {pmsgtype} len: {msglenx}')
			except TypeError as e:
				logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
			except OSError as e:
				logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
			try:
				socket.sendto(payload,serveraddress)
				# logger.debug(f'do_send payload: {pmsgtype} {type(payload)}')
			except OSError as e:
				logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
			except TypeError as e:
				logger.error(f'{e} payloaderror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
		except Exception as e:
			logger.error(f'[!] {e} {type(e)} {type(payload)} {payload}')
			raise ServerSendException(e)

	def msg_handler(self, data):
		msgtype = data.get('msgtype')
		if not msgtype:
			logger.error(f'[!] msgtype not found in {data}')
		self.refresh_playerlist(data) # todo check disconnected clients
		match msgtype:
			case 'requestnewgrid': # client requests new grid, send to all clients
				self.grid = generate_grid()
				for client in self.clients:
					newpos = get_grid_pos(self.grid)
					msg = {'msgtype': 'newgridresponse', 'clientname': client.name, 'setpos': newpos, 'client_id': client.client_id}
					# logger.debug(f'{self} {msgtype} from {data.get("client_id")} sendingto: {client.name} ')
					try:
						# self.do_send(client._args[0], client._args[1], msg)
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} {type(e)} in {self} {client}\ndata: {type(data)} {data}\nmsg: {type(msg)} {msg}\n')
						self.clients.pop(self.clients.index(client))
			case 'playertimer' | 'ackserveracktimer' | 'cl_playermove':
				msg = {'msgtype': 'serveracktimer'}
				if not data.get('gotgrid'):
					logger.warning(f'need grid data from {data.get("client_id")}')
				if not data.get('gotpos'):
					# find a random spot on the map to place the player
					newpos = get_grid_pos(self.grid)
					msg['setpos'] = newpos
					logger.warning(f'needpos {data.get("client_id")} newpos: {newpos}')
				for client in self.clients:
					msg['clientname'] = client.name
					# logger.debug(f'{self} {msgtype} from {data.get("client_id")} sendingto: {client.name} ')
					try:
						# self.do_send(client._args[0], client._args[1], msg)
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} {type(e)} in {self} {client}\ndata: {type(data)} {data}\nmsg: {type(msg)} {msg}\n')
						self.clients.pop(self.clients.index(client))
			case 'cl_playerbomb': # player sent bomb, update others
				if not data.get('gotgrid'):
					logger.warning(f'data: {data}')
				logger.info(f'{msgtype} dclid: {data.get("client_id")} clbombpos: {data.get("clbombpos")}')
				for client in self.clients:
					msg = {'msgtype': 'ackplrbmb', 'client': client.name, 'data': data}
					try:
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
			case 'cl_gridupdate': # gridupdate from client....
				self.grid = data.get('grid')
				for client in self.clients:
					msg = {'msgtype': 'sv_gridupdate', 'grid': self.grid,}
					# logger.info(f'sv_gridupdate to {client.name} dclid: {data.get("client_id")} ')
					try:
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
			case 'cl_playerkilled': # cl_playerkilled from client, send update to others....
				self.playerlist = data.get('playerlist')
				logger.info(f'{msgtype} dclid: {data.get("client_id")} ') # playerlist: {self.playerlist}
				for client in self.clients:
					msg = {'msgtype': 'sv_playerlist', 'playerlist': self.playerlist,}
					try:
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
			case _:
				logger.warning(f'unknown msgtype {msgtype} from {data.get("client_id")}\ndata: {data}')
				for client in self.clients:
					msg = {'msgtype': 'serveracktimer', 'client': client.name, 'data': data}
					try:
						# self.do_send(client._args[0], client._args[1], msg)
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))

	def run(self):
		# logger.info(f'{self} starting tui')
		# self.tui.start()
		logger.info(f'{self} started')
		while True:
			if self.tui.killed: # todo fix tuiquit
				logger.warning(f'{self} tui {self.tui} killed')
				self.killed = True
				# self.mainsocket.close()
				break
				# sys.exit(1)
			if self.killed:
				logger.warning(f'{self} killed')
				break
			try:
				self.refresh_clients()
			except Exception as e:
				logger.error(f'{self} {e} {type(e)}')
			if not self.dataq.empty():
				datafromq = self.dataq.get()
				self.dataq.task_done()
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
	def __init__(self, server, lock):
		Thread.__init__(self, daemon=True, name='bindthread')
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
			thread = NewHandler(conn,addr, self.server.dataq, name=f'clthrd{conncounter}')
			self.server.clients.append(thread)
			thread.start()
			conncounter += 1
			logger.info(f'{self.server} started {thread} {conncounter}')
			self.server.trigger_newplayer()

def locker_thread(lock):
    logger.debug('locker_thread Starting')
    while True:
        lock.acquire()
        try:
            # logger.debug('locker_thread Locking')
            time.sleep(0.1)
        finally:
            # logger.debug('locker_thread Not locking')
            lock.release()
        time.sleep(0.1)
    return

if __name__ == '__main__':
	parser = ArgumentParser(description='server')
	parser.add_argument('--listen', action='store', dest='listen', default='localhost')
	parser.add_argument('--port', action='store', dest='port', default=9696, type=int)
	args = parser.parse_args()

	mainsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	mainsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	threads = []
	connq = Queue()

	lock = threading.Lock()
	lt = Thread(target=locker_thread, args=(lock,), daemon=True)
	threads.append(lt)

	gt = Gameserver(connq, mainsocket, lock)
	tui = ServerTUI(server=gt)
	threads.append(tui)
	# tui.run()
	threads.append(gt)
	bt = BindThread(gt, lock)
	threads.append(bt)
	for t in threads:
		logger.info(f'starting {t}')
		t.start()
	killserver = False
	while not killserver:
		for t in threads:
			if not t.is_alive():
				logger.warning(f'{t} killed')
				killserver = True
				break
	# try:
	# 	mainsocket.bind((args.listen,args.port))
	# except OSError as e:
	# 	logger.error(e)
	# 	sys.exit(1)
	# conncounter = 0
	# while True:
	# 	mainsocket.listen()
	# 	try:
	# 		conn, addr = mainsocket.accept()
	# 	except KeyboardInterrupt as e:
	# 		logger.warning(f'{e}')
	# 		break
	# 	except Exception as e:
	# 		logger.warning(f'{e} {type(e)}')
	# 		break
	# 	thread = NewHandler(conn,addr, server.dataq, name=f'clthrd{conncounter}')
	# 	server.clients.append(thread)
	# 	thread.start()
	# 	conncounter += 1
	# 	logger.info(f'{server} started {thread} {conncounter}')
	# 	server.trigger_newplayer()
