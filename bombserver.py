#!/usr/bin/python
import enum
import struct
import asyncio
from typing import Dict, Tuple
from contextlib import suppress
import time
import os
import random
import socket
import sys
import json
from argparse import ArgumentParser
import threading
from threading import Thread, current_thread, Timer, active_count, _enumerate, Event
from queue import Queue, Empty
from loguru import logger
import re
import pickle
import arcade
from constants import *
from exceptions import *
from objects import gen_randid
from objects import PlayerEvent, PlayerState, GameState,KeysPressed
from asyncio import run, create_task, CancelledError

import zmq
from zmq.asyncio import Context, Socket
SERVER_UPDATE_TICK_HZ = 10
def generate_grid(gsz=GRIDSIZE):
	return json.loads(open('data/map.json','r').read())

class ServerSendException(Exception):
	pass

class HandlerException(Exception):
	pass

class TuiException(Exception):
	pass

_MAX_DATAGRAM_BODY = 32000


class _NetFlags(enum.IntFlag):
	DATA = 0x1
	ACK = 0x2
	NAK = 0x4
	EOM = 0x8
	UNRELIABLE = 0x10
	CTL = 0x8000


_SUPPORTED_FLAG_COMBINATIONS = (
	_NetFlags.DATA,    # Should work but I don't think it's been seen in the wild
	_NetFlags.DATA | _NetFlags.EOM,
	_NetFlags.UNRELIABLE,
	_NetFlags.ACK,
)

class DatagramError(Exception):
	pass


class RepeatedTimer():
	def __init__(self, interval, function, *args, **kwargs):
		self._timer     = None
		self.interval   = interval
		self.function   = function
		self.args       = args
		self.kwargs     = kwargs
		self.is_running = False
		self.start()

	def _run(self):
		self.is_running = False
		self.start()
		self.function(*self.args, **self.kwargs)

	def start(self):
		if not self.is_running:
			self._timer = Timer(self.interval, self._run)
			self._timer.start()
			self.is_running = True

	def stop(self):
		self._timer.cancel()
		self.is_running = False
		logger.warning(f'{self} stop')


class ServerTUI(Thread):
	def __init__(self, server, debugmode=False, gq=None):
		Thread.__init__(self, daemon=True, name='tui')
		self.gq = gq
		self.server = server
		self.debugmode = debugmode
		self._stop = Event()

	def __repr__(self):
		return f'ServerTUI (s:{self.stopped()})'

	def stop(self):
		self._stop.set()
		logger.warning(f'{self} stop')

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
		while not self.stopped():
			try:
				cmd = input(':> ')
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'p':
					self.dump_playerlist()
				elif cmd[:1] == 'q':
					logger.warning(f'{self} {self.server} tuiquit')
					self.gq.put({'msgtype':'quit'})
					# raise TuiException('tui killed')
					self.stop()
				# else:
				#	logger.info(f'[tui] {self} server: {self.server}')
			except KeyboardInterrupt:
				self.stop()
				break


class NewHandler(Thread):
	def __init__(self, conn=None, addr=None, handlerq=None, name=None, debugmode=False, server=None, client_id=None, gq=None):
		Thread.__init__(self,  daemon=True, name=f'Handler-{name}-{client_id}')
		self.gq = gq
		self.client_id = client_id
		self.server = server
		self.debugmode = debugmode
		self.conn = conn
		self.addr = addr
		self.connected = True
		self.handlerq = handlerq
		self.name = name
		self._stop = Event()
	def __repr__(self) -> str:
		return f'Handler ({self.client_id} {self.name} {self.connected} {self.handlerq.qsize()})'

	def stop(self):
		self._stop.set()
		logger.warning(f'{self} stop')

	def stopped(self):
		return self._stop.is_set()

	def send_ping(self):
		msg = {'msgtype': 'ping', 'client_id': self.client_id,}
		self.server.serverdq.put((self.conn, self.addr, msg))

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
				self.stop()
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
	def __init__(self, connq, mainsocket, lock, debugmode=False, gq=None):
		Thread.__init__(self,  daemon=True, name='gameserverthread')
		self.gq = gq
		self._stop = Event()
		self.debugmode = debugmode
		self.lock = lock
		self.mainsocket = mainsocket
		self.clients = []
		self.connq = connq
		self.serverdq = Queue()
		self.gridsize = 20
		self.grid = generate_grid(gsz=self.gridsize)
		self.playerlist = {}
		self.trgnpc = 0 # how often trigger_newplayer was called
		self.tui = ServerTUI(server=self)
		self.refresh_clients_timer = RepeatedTimer(interval=0.1, function=self.refresh_clients)

	def __repr__(self):
		return f'Gameserver (c:{len(self.clients)})'

	def stop(self):
		self._stop.set()
		logger.warning(f'{self} stop')

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
		# self.do_send(thread.conn, thread.addr, msg)
		self.serverdq.put((thread.conn, thread.addr, msg))
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
					# self.do_send(client.conn, client.addr, msg)
					self.serverdq.put((client.conn, client.addr, msg))
				except ServerSendException as e: # todo check and fix this...
					logger.warning(f'[!] {e} in {self} {client}')
					# self.playerlist.pop(clients.client_id)
					# self.clients.pop(self.clients.index(client))
				except Exception as e:
					logger.error(f'[!] {e} in {self} {client}')
					# self.playerlist.pop(clients.client_id)
					# self.clients.pop(self.clients.index(client))

	def refresh_clients(self):
		for client in self.clients:
			# logger.debug(f'sending refresh_playerlist to {client}')
			# update other clients... # todo exclude the new client
			msg = {'msgtype': 'refresh_playerlist', }
			try:
				# self.do_send(client.conn, client.addr, msg)
				self.serverdq.put((client.conn, client.addr, msg))
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

	# def do_send(self, socket, serveraddress, data):

	def do_send(self, item):
		socket, serveraddress, data = item
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
					logger.error(f'{e} msglenerror {msglen} {type(msglen)}  ')# \npayload = {type(payload)}\n{payload}\n')
					return
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
				self.msg_handler({'msgtype': 'disconnectplayer', 'client_id': data.get("client_id")})
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
						#self.do_send(client.conn, client.addr, data)
						self.serverdq.put((client.conn, client.addr, data))
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
						# self.do_send(client.conn, client.addr, data)
						self.serverdq.put((client.conn, client.addr, data))
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
			case 'valueerror' | 'JSONDecodeError' | 'rawmsglenempty' | 'disconnectplayer' | 'ConnectionResetError':
				client_id = data.get('client_id')
				logger.warning(f'{msgtype} disconnecting c: {client_id} ')# data: {data}')
				try:
					self.playerlist.pop(client_id)
					[k.stop() for k in self.clients if k.client_id == client_id]
					[self.clients.pop(self.clients.index(k)) for k in self.clients if k.client_id == client_id]
				except Exception as e:
					logger.error(f'{e} {type(e)} clid: {client_id} selfplayerlist={self.playerlist} selfclients={self.clients}')
			case _:
				logger.warning(f'unknown msgtype {msgtype} from {data.get("client_id")}\ndata: {data}')

	def run(self):
		# logger.info(f'{self} starting tui')
		# self.tui.start()
		logger.info(f'{self} started')
		while True:
			if self.tui.stopped(): # todo fix tuiquit
				logger.warning(f'{self} tui {self.tui} tuistopped')
				self.stop()
				break
			try:
				self.do_send(self.serverdq.get())
			except Empty:
				pass
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
	def __init__(self, server, lock, debugmode=False, gq=None):
		Thread.__init__(self, daemon=True, name='Bindthread')
		self.gq = gq
		self.debugmode = debugmode
		self.lock = lock
		self.server = server
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._stop = Event()

	def stop(self):
		self._stop.set()
		logger.warning(f'{self} stop')

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

def oldthreadmain():
	mainsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	mainsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	threads = []
	connq = Queue()
	gq = Queue()

	# lock = threading.Lock()
	# lt = Thread(target=locker_thread, args=(lock,), daemon=True, name='svlocker_thread')
	# threads.append(lt)
	lock = None
	gt = Gameserver(connq=connq, mainsocket=mainsocket, lock=lock, debugmode=args.debug, gq=gq)
	tui = ServerTUI(server=gt, debugmode=args.debug, gq=gq)
	threads.append(tui)
	# tui.run()
	threads.append(gt)
	bt = BindThread(server=gt, lock=lock, debugmode=args.debug, gq=gq)
	threads.append(bt)
	for t in threads:
		logger.info(f'starting {t}')
		t.start()
	data = None
	running = True
	while running:
		try:
			data = gq.get_nowait()
		except Empty:
			pass
		if data:
			print(data)
			msgtype = data.get('msgtype', 'none')
			match msgtype:
				case 'quit':
					#bt.join()
					# gt.join()
					#tui.join()
					#tui.stop()
					bt.stop()
					running = False
					gt.stop()
					break

class Player:
	def __init__(self, transport, addr):
		self.transport = transport
		self.addr = addr

	def send(self, new_state):
		self.transport.sendto(new_state, self.addr)

def handle_cancellation(f):
	async def inner(*args, **kwargs):
		with suppress(asyncio.CancelledError):
			return await f(*args, **kwargs)
	return inner


class ServerProtocol(asyncio.Protocol):
	def __init__(self, loop):
		self._loop = loop
		self.players: Dict[str, Player] = {}
		self.state_queue: asyncio.Queue[bytes] = asyncio.Queue()
		self.input_queue: asyncio.Queue[Tuple[Player, bytes]] = asyncio.Queue()
		self.brain_task = loop.create_task(self.game_brain())
		self.state_sender_task = loop.create_task(self.state_sender())
		self._recv_queue = asyncio.Queue()
		self._connected_future = asyncio.Future()
		self._transport = None
		self._send_reliable_queue = asyncio.Queue()
		self._send_reliable_ack_queue = asyncio.Queue()
		self._message_queue = asyncio.Queue()
		self._unreliable_send_seq = 0
		# self._udp = None

	def eof_received(self):
		logger.warning(f'eof_received')

	async def _recv_loop(self):
		header_fmt = ">HHL"
		header_size = struct.calcsize(header_fmt)

		recv_seq = 0
		unreliable_recv_seq = 0
		reliable_msg = b''



	async def send_reliable(self, data):
		acked_future = asyncio.Future()
		await self._send_reliable_queue.put((data, acked_future))
		await acked_future

	async def _send_reliable_loop(self):
		send_seq = 0

		while True:
			# Wait for the next message to be sent.
			data, fut = await self._send_reliable_queue.get()

			# Split the message into packets up to the maximum allowed.
			while data:
				# Send the packet
				payload, data = data[:_MAX_DATAGRAM_BODY], data[_MAX_DATAGRAM_BODY:]
				netflags = _NetFlags.DATA
				if not data:
					netflags |= _NetFlags.EOM
				packet = self._encap_packet(netflags, send_seq, payload)
				# self._udp.sendto(packet, (self._host, self._port))

				# Wait for an ACK
				while True:
					ack_seq = await self._send_reliable_ack_queue.get()
					if ack_seq != send_seq:
						logger.warning("Stale ACK received")
					else:
						break

				send_seq += 1

			# Let the caller know the result
			fut.set_result(None)
	async def _monitor_queues(self):
		pass
	def connection_made(self, transport):
		logger.info(f'{self} connection made transport: {transport}')
		self.transport = transport

		self._tasks = asyncio.gather(asyncio.create_task(self._send_reliable_loop()), asyncio.create_task(self._recv_loop()), asyncio.create_task(self._monitor_queues()))

	def connection_lost(self, transport):
		logger.info('Connection lost')

	@handle_cancellation
	async def game_brain(self):
		while True:
			player, new_input = await self.input_queue.get()
			new_state = b'new state!'  # This is a big calculation
			await self.state_queue.put(new_state)

	@handle_cancellation
	async def state_sender(self):
		# print('start up state sender')
		while True:
			new_state = await self.state_queue.get()
			# All players get the new game state
			for p in self.players.values():
				p.send(new_state)

	def datagram_received(self, data, addr):
		logger.info(f"Received from {addr} {data} rq: {self._recv_queue.qsize()}")
		asyncio.ensure_future(self._recv_queue.put((data, addr)), loop=self._loop)

	async def recvfrom(self):
		data, addr = await self._recv_queue.get()
		logger.debug(f"Received from {addr} {data}")
		return data, addr

	def xdata_received(self, data):
		logger.debug(f'data: {data}')

	def xdatagram_received(self, data, addr):
		logger.info(f'data:{data} qs:{self.input_queue.qsize()}')
		try:
			if data == b'JOIN':
				self.players[addr] = Player(self.transport, addr)
				# return
			elif data == b'LEAVE':
				del self.players[addr]
				return
		except Exception as e:
			logger.error(f'{e} {type(e)} {data} {addr}')
			return
		if data:
			# This means game input was received.
			try:
				message = data.decode()
			except UnicodeDecodeError as e:
				logger.warning(f'{e} {type(e)} {data} {addr}')
				message = data
			# logger.debug('Send %r to %s' % (message, addr))
			new_input = (self.players[addr], data)
			self.input_queue.put_nowait(new_input)
			logger.debug(f'Received {message} from {addr} qs:{self.input_queue.qsize()}')


async def oldmain(args, loop):
	listen = loop.create_datagram_endpoint(lambda: ServerProtocol(loop), local_addr=(args.listen, args.port))
	transport, protocol = await listen
	#listen = loop.create_server(ServerProtocol, host=args.listen, port=args.port)
	#transport = await listen
	try:
		await asyncio.sleep(100000)
	except asyncio.CancelledError:
		transport.close()

def apply_movement(speed, dt, curpos , key: KeysPressed):
	cx = 0
	cy = 0
	oldpos = [curpos[0], curpos[1]]
	newpos = [curpos[0], curpos[1]]
	# logger.info(f'curpos: {curpos} {type(curpos)} k:{key}')
	if key == arcade.key.UP or key == arcade.key.W or key == 119  or key.keys[119]:
		newpos[1] += PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.DOWN or key == arcade.key.S or key == 115  or key.keys[115]:
		newpos[1] -= PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.LEFT or key == arcade.key.A or key == 97 or key.keys[97]:
		newpos[0] -= PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.RIGHT or key == arcade.key.D or key == 100  or key.keys[100]:
		newpos[0] += PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.SPACE:
		pass
	
	return newpos
	# delta_position = (sum([k for k in kp.keys]),sum([k for k in kp.keys]))
	#return current_position + delta_position * speed * dt

def old_apply_movement(speed, dt, curpos , key: KeysPressed):
	cx = 0
	cy = 0
	oldpos = curpos
	logger.info(f'curpos: {curpos} {type(curpos)} k:{key}')
	if key == arcade.key.UP or key == arcade.key.W or key == 119:
		curpos[1] += PLAYER_MOVEMENT_SPEED
		logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos}')
	elif key == arcade.key.DOWN or key == arcade.key.S or key == 115:
		curpos[1] -= PLAYER_MOVEMENT_SPEED
		logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos}')
	elif key == arcade.key.LEFT or key == arcade.key.A or key == 97:
		curpos[0] -= PLAYER_MOVEMENT_SPEED
		logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos}')
	elif key == arcade.key.RIGHT or key == arcade.key.D or key == 100:
		curpos[0] += PLAYER_MOVEMENT_SPEED
		logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos}')
	elif key == arcade.key.SPACE:
		pass
	
	return curpos
	# delta_position = (sum([k for k in kp.keys]),sum([k for k in kp.keys]))
	#return current_position + delta_position * speed * dt

def update_game_state(gs: GameState, event: PlayerEvent):
	if isinstance(gs, str):
		logger.warning(f'wrongtype: {gs} {type(gs)} {event} {type(event)}')
		return
	player_state = gs.player_states[0]
	dt = time.time() # - (player_state.updated)
	current_position = (player_state.x, player_state.y)
	# current_position = apply_movement(player_state.speed, dt, current_position, event)
	current_position = apply_movement(PLAYER_MOVEMENT_SPEED, dt, current_position, event)
	player_state.x = current_position[0]
	player_state.y = current_position[1]
	player_state.updated = time.time()


async def update_from_client(gs, sock):
	try:
		while True:
			msg = await sock.recv_json()
			counter = msg['counter']
			event_dict = msg['event']
			# event_dict = await sock.recv_json()
			# print(f'Got event dict: {event_dict}')
			event = PlayerEvent(**event_dict)
			if 0:
				# impose fake latency
				asyncio.get_running_loop().call_later(0.2, update_game_state, gs, event)
			else:
				update_game_state(gs, event)
	except asyncio.CancelledError:
		pass


async def ticker(sock1, sock2):
	ps = PlayerState(speed=150)
	gs = GameState(player_states=[ps], game_seconds=1)
	logger.debug(f'tickergs: {gs}')
	# s = gs.to_json()
	# print(f's:{s}')

	# A task to receive keyboard and mouse inputs from players.
	# This will also update the game state, gs.
	t = create_task(update_from_client(gs, sock2))

	# Send out the game state to all players 60 times per second.
	try:
		while True:
			await sock1.send_string(gs.to_json())
			# print('.', end='', flush=True)
			await asyncio.sleep(1 / SERVER_UPDATE_TICK_HZ)
	except asyncio.CancelledError:
		t.cancel()
		await t



async def main(args):
	fut = asyncio.Future()
	# app = App(signal=fut)
	ctx = Context()

	sock_push_gamestate: Socket = ctx.socket(zmq.PUB)
	sock_push_gamestate.bind('tcp://127.0.0.1:9696')

	sock_recv_player_evts: Socket = ctx.socket(zmq.PULL)
	sock_recv_player_evts.bind('tcp://127.0.0.1:9697')

	ticker_task = asyncio.create_task(ticker(sock_push_gamestate, sock_recv_player_evts),)
	try:
		await asyncio.wait([ticker_task, fut],return_when=asyncio.FIRST_COMPLETED)
	except CancelledError:
		print('Cancelled')
	finally:
		ticker_task.cancel()
		await ticker_task
		sock_push_gamestate.close(1)
		sock_recv_player_evts.close(1)
		ctx.destroy(linger=1000)


if __name__ == '__main__':
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())	
	parser = ArgumentParser(description='server')
	parser.add_argument('--listen', action='store', dest='listen', default='localhost')
	parser.add_argument('--port', action='store', dest='port', default=9696, type=int)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()
	run(main(args))
	# loop = asyncio.get_event_loop()
	# loop.create_task(main(args, loop))
	# loop.run_forever()
	# loop.close()
