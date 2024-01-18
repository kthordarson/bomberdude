import struct
import enum
import asyncio
from typing import Dict, Tuple
from contextlib import suppress

import socket
import time
from threading import Thread
from threading import Event
from queue import Queue
import re
import json
from loguru import logger

from constants import *
from exceptions import *
from objects import gen_randid, Bomberplayer

class Client(Thread):
	def __init__(self, serveraddress=None, eventq=None):
		super().__init__(daemon=True, name='BombClientThread')
		self._stop = Event()
		self.client_id = None#  gen_randid()
		self.serveraddress = serveraddress
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.connected = False
		self.eventq = eventq
		self.receiverq = Queue()
		self.send_queue = Queue()
		self.receiver = ReceiverThread(receiverq=self.receiverq, socket=self.socket)
		self.sendcounter = 0
		self.runcounter = 0
		self.pos = (0,0)
		self.health = 100
		self.gridpos = (0,0)
		self.bombsleft = 33
		self.gotgrid = False
		self.gotpos = False
		self.sendqsize = self.send_queue.qsize()
		self.runcounter = 0
		self.playerlist = {}
		# self.player = Bomberplayer("data/playerone.png",scale=0.9) # arcade.Sprite("data/playerone.png",scale=1)

	def __repr__(self):
		return f'Client(id: {self.client_id} conn:{self.connected} stop:{self.stopped()} sqs:{self.send_queue.qsize()} rqs:{self.receiverq.qsize()} rr:{self.receiver.recvcounter} rc:{self.runcounter} uc:{self.runcounter})'

	def stop(self):
		self._stop.set()
		logger.info(f'STOP {self} socket:{self.socket}')

	def stopped(self):
		return self._stop.is_set()

	def do_connect(self, reconnect=False):
		c_cnt = 0
		if reconnect:
			self.stop()
			self.receiver.stop()
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.receiver.socket = self.socket
			self.connected = False
			logger.warning(f'{self} reconnecting...')
		while not self.connected:
			c_cnt += 1
			logger.info(f'do_connect c_cnt: {c_cnt}')
			if c_cnt >= 10:
				logger.error(f'{self} do_connect {c_cnt}')
				return False
			try:
				self.socket.connect(self.serveraddress)
				self.connected = True
				self.receiver.connected = True
				logger.info(f'{self} connected c_cnt: {c_cnt} r:{self.receiver}')
				if not reconnect:
					self.receiver._stop.clear()
					self._stop.clear()
				return True
			except Exception as e:
				logger.error(f'{self} doconnect {e} {type(e)} {c_cnt}')
				return False

	def get_servermap(self):
		c_cnt = 0
		gotservermap = False
		while not gotservermap:
			c_cnt += 1
			logger.info(f'get_servermap c_cnt: {c_cnt}')
			if gotservermap:
				logger.debug(f'{self} get_servermap c_cnt: {c_cnt}')
				return True
			if c_cnt >= 10:
				logger.error(f'get_servermap error {c_cnt}')
				return False
			try:
				self.send_queue.put({'msgtype': 'getservermap'})
				time.sleep(1)
			except Exception as e:
				logger.error(f'{self} get_servermap {e} {type(e)} {c_cnt}')
				return False

	def do_send(self, payload):
		if not self.connected:
			logger.warning(f'{self} notconnected p: {payload}')
			return
		payload['runcounter'] = self.runcounter
		payload['runcounter_r'] = self.receiver.runcounter
		payload['client_id'] = self.client_id
		#payload['pos'] = (self.pos[0],self.pos[1])
		#payload['bombsleft'] = self.bombsleft
		#payload['health'] = self.health
		#payload['gridpos'] = self.gridpos
		#payload['gotgrid'] = self.gotgrid
		#payload['gotpos'] = self.gotpos
		#payload['sendqsize'] = self.send_queue.qsize()
		#payload['connected'] = self.connected
		try:
			payload = json.dumps(payload).encode('utf8')
		except Exception as e:
			logger.error(f'{self} jsondumps {e} {type(e)} payload:\n{payload}')
			return
		msglen = str(len(payload)).encode('utf8').zfill(PKTHEADER)
		try:
			self.socket.sendto(msglen,self.serveraddress)
			self.socket.sendto(payload,self.serveraddress)
			self.sendcounter += 1
		except Exception as e:
			logger.error(f'{self} sendto {e} {type(e)} msglen:{msglen} payload:\n{payload}')
		# logger.debug(f'playerdosendpayload {outmsgtype} lenx:{msglenx} {len(payload)} c_pktid: {self.lastpktid}')

	def msg_handler(self, jresp):
		# logger.debug(f'jresp:\n {jresp}\n')
		try:
			msgtype = jresp.get('msgtype')
			# logger.debug(f'msgtype: {msgtype}')
		except AttributeError as e:
			logger.error(f'{e} {type(e)} jresp: {jresp}')
			msgtype = ''
		match msgtype:
			case 'bombdrop':
				# logger.info(f'{msgtype} {jresp}') # todo makebombs
				self.eventq.put(jresp)
			case 'playermove':
				# logger.info(f'{msgtype} {jresp}') # todo makebombs
				self.eventq.put(jresp)
			case 'ping':
				logger.debug(f'got ping from {jresp.get("client_id")} griddatalen: {len(jresp.get("grid"))}') # serverdebugping
			case 'ackplrbmb':
				bomb_client_id = jresp.get('data').get('client_id')
				clbombpos = jresp.get('data').get('clbombpos')
				if bomb_client_id != self.client_id: # not a bomb from me...
					# pass
					logger.info(f'{self} otherplayerbomb {msgtype} from {bomb_client_id} bombpos: {clbombpos}')
				elif bomb_client_id == self.client_id: # my bomb
					logger.info(f'{self} ownbomb {msgtype} bombpos: {clbombpos}')
					self.bombsleft -= 1
				else:
					logger.warning(f'{self} bomberclientid! {msgtype} jresp: {jresp}')
			case 'newgridresponse':
				grid = jresp.get('grid')
				if grid:
					self.gotgrid = True
					self.grid = grid
					logger.info(f'gotgrid {self.gotgrid} {msgtype} ')
				else:
					logger.warning(f'nogrid in {jresp}')
				newpos = jresp.get('setpos')
				if newpos:
					self.gotpos = True
					self.gridpos = newpos
					self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
					logger.info(f'gotpos {msgtype} newpos: {newpos} {self.gridpos} {self.pos}')
			case 'trigger_netplayers':
				self.eventq.put(jresp)
			case 'refresh_playerlist':
				self.eventq.put(jresp)
			case 'trigger_newplayer': # when new player joins
				client_id = jresp.get('client_id')
				# logger.info(f'{msgtype} {jresp}')
				if not self.client_id: # set client_id if not set
					self.client_id = client_id
					self.pos = jresp.get('setpos')
					self.grid = jresp.get('grid')
					self.gotgrid = True
					self.gotpos = True
					self.playerlist[jresp.get('client_id')] = {'setpos':jresp.get('setpos')}
					logger.info(f'{self} {msgtype} name: {jresp.get("clientname")} client_id: {jresp.get("client_id")} setpos: {jresp.get("setpos")} ')
					self.eventq.put(jresp)
			case 'serveracktimer':
				# logger.debug(f'{self} {msgtype} {jresp}')
				# playerlist = None
				# data = jresp.get('data')
				playerlist = jresp.get('playerlist', None)
				self.playerlist = playerlist

				grid = jresp.get('grid', None)
				self.grid = grid
				self.gotgrid = True
				self.gotpos = True
				# self.update_run()
			case 'sv_serverdebug': # got debuginfo from server
				self.debuginfo['server'] = jresp.get('dbginfo')
			case 'error': # got debuginfo from server
				logger.error(jresp)
				conn = self.do_connect(reconnect=True)
				if conn:
					logger.info(f'{self} reconnected')
				else:
					logger.error(f'{self} not reconnected')
					self.stop()
			case _:
				logger.warning(f'missingmsgtype jresp: {jresp} ')

	def update_run(self):
		if not self.send_queue.empty():
			sqdata = self.send_queue.get()
			if sqdata:
				# logger.debug(f'{sqdata.get("msgtype")} rqs: {self.receiverq.qsize()} recvrc:{self.receiver.runcounter} sqs: {self.send_queue.qsize()} runc:{self.runcounter} sendc:{self.sendcounter} ')
				# logger.info(f'rqs: {self.receiverq.qsize()} sqs: {self.send_queue.qsize()} data:\n {sqdata}')
				try:
					self.do_send(sqdata)
				except OSError as e:
					logger.error(f'senderror {e} data: {sqdata}')
					if e.errno == 32:
						# logger.error(f'errno32 {e} data: {sqdata}')
						self.connected = False
						self.receiver.connected = False
						self.receiver.join(timeout=0)
						self.stop()
						return
				self.send_queue.task_done()

	def update_run_recv(self):
		if not self.receiverq.empty():
			rqdata = self.receiverq.get()
			if rqdata:
				# logger.info(f'{rqdata.get("msgtype")} rqs: {self.receiverq.qsize()} sqs: {self.send_queue.qsize()} ')
				self.msg_handler(rqdata)
				self.receiverq.task_done()


class ReceiverThread(Thread):
	def __init__(self, receiverq=None, socket=None):
		super().__init__(daemon=True, name='ReceiverThread')
		self.receiverq = receiverq
		self.socket = socket
		self.name = 'ReceiverThread'
		self.connected = False
		self.recvcounter = 0
		self._stop = Event()
		self.runcounter = 0

	def __repr__(self):
		return f'{self.name} ( rqs:{self.receiverq.qsize()} {self.recvcounter} runc:{self.runcounter})'

	def stop(self):
		self.connected = False
		self._stop.set()
		logger.info(f'STOP {self}  socket:{self.socket}')

	def stopped(self):
		return self._stop.is_set()

	def run(self):
		while True:
			self.runcounter += 1
			if self.stopped():
				return
			else:
				try:
					replen = self.socket.recv(PKTHEADER).decode('utf8')
					datalen = int(re.sub('^0+','',replen))
					response = self.socket.recv(datalen).decode('utf8')
					jresp = json.loads(response)
					self.receiverq.put(jresp)
					self.recvcounter += 1
				except Exception as e:
					# logger.error(f'{self} get_jresp {e} {type(e)} response: {response}')
					errmsg = f'get_jresp {e} {type(e)} response: {response}'
					logger.error(errmsg)
					msg = {'msgtype': 'error', 'errmsg':errmsg}
					self.receiverq.put(msg)


class _GenericUdpProtocol(asyncio.Protocol):
	def __init__(self, loop):
		self._loop = loop
		self._connected_future = asyncio.Future()
		self._transport = None
		self._recv_queue = asyncio.Queue()

	def connection_made(self, transport):
		print('connection_made: {transport}')
		self._transport = transport
		self._connected_future.set_result(None)

	async def wait_until_connected(self):
		await self._connected_future

	def datagram_received(self, data, addr):
		logger.info(f"Received from {addr}: {data} ({data.hex()})")
		asyncio.ensure_future(self._recv_queue.put((data, addr)), loop=self._loop)

	async def recvfrom(self):
		data, addr = await self._recv_queue.get()
		logger.debug(f"Received from {addr}: {data} ({data.hex()})")
		return data, addr

	def sendto(self, data, addr):
		logger.debug(f"Sending: {data} ({data.hex()}) rq: {self._recv_queue.qsize()}")
		self._transport.sendto(data, addr)

	def connection_lost(self, exc):
		assert False, "UDP cannot close connection?"


class BombClientProtocol:
	def __init__(self, loop):
		self.loop = loop
		self._transport = None
		# self._loop = loop
		self._connected_future = asyncio.Future()
		self._transport = None
		self._recv_queue = asyncio.Queue()

	def connection_made(self, transport):
		print('connection_made: {transport}')
		self._transport = transport
		self._connected_future.set_result(None)
		# print('starting script task')
		# loop.create_task(self.script())

	async def script(self):
		self._transport.sendto(b'JOIN')
		for i in range(10):
			await asyncio.sleep(1)
			self._transport.sendto(b'BLAH')

		# await asyncio.sleep(1)
		# self.transport.sendto(b'LEAVE')
		# self.transport.close()

	async def wait_until_connected(self):
		await self._connected_future

	def datagram_received(self, data, addr):
		asyncio.ensure_future(self._recv_queue.put((data, addr)), loop=self._loop)

	def xdatagram_received(self, data, addr):
		print("Received:", data.decode())

	def error_received(self, exc):
		print('Error received:', exc)

	def connection_lost(self, exc):
		print("Socket closed, stop the event loop")
		loop = asyncio.get_event_loop()
		loop.stop()

	async def recvfrom(self):
		data, addr = await self._recv_queue.get()
		logger.debug(f"Received from {addr}: {data} ({data.hex()})")
		return data, addr

	def sendto(self, data, addr):
		logger.debug(f"Sending: {data}")
		self._transport.sendto(data, addr)

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



class DatagramConnection:
	def __init__(self, udp_protocol):
		self._host = None
		self._port = None
		self._udp = udp_protocol
		self._send_reliable_queue = asyncio.Queue()
		self._send_reliable_ack_queue = asyncio.Queue()
		self._message_queue = asyncio.Queue()
		self._unreliable_send_seq = 0

	async def _monitor_queues(self):
		while True:
			await asyncio.sleep(1)
			logging.debug(f"Dgram Queue lengths: send={self._send_reliable_queue.qsize()} ack={self._send_reliable_ack_queue.qsize()} out={self._message_queue.qsize()}")

	def _make_connection_request_body(self):
		return b'\x01bomberdude\x00\x03'

	async def _connect(self, host, port):
		host = socket.gethostbyname(host)
		await self._udp.wait_until_connected()

		# Request a connection, and wait for a response
		response_received = False
		while not response_received:
			body = self._make_connection_request_body()
			logger.info(f"Sending connection request to {host} {port}. body:{body}")
			header_fmt = ">HH"
			header_size = struct.calcsize(header_fmt)
			header = struct.pack(header_fmt, _NetFlags.CTL, len(body) + header_size)
			# self._udp.sendto(header + body, (host, port))
			rawpkt = b'JOIN'
			self._udp.sendto(rawpkt, (host, port))
			try:
				packet, addr = await asyncio.wait_for(self._udp.recvfrom(), 1.0)
				response_received = True
				logger.info(f'Received response from {addr} packet: {packet}')
			except asyncio.TimeoutError:
				pass

		# Parse the response.
		if addr != (host, port):
			raise DatagramError("Spoofed packet received")
		netflags, size = struct.unpack(header_fmt, packet[:header_size])
		netflags = _NetFlags(netflags)
		body = packet[header_size:]
		if size != len(packet):
			raise DatagramError("Invalid packet size")
		if netflags != _NetFlags.CTL:
			raise DatagramError(f"Unexpected net flags: {netflags}")

		# All going well, the body should contain a new port to communicate with.
		if body[0] != 0x81:
			raise DatagramError(f"Expected CCREP_ACCEPT message, not {body[0]}")
		self._port, = struct.unpack("<L", body[1:5])
		self._host = host

		if len(body) > 5:
			mod_version = body[6] if len(body) > 6 else 0
			mod_flags = body[7] if len(body) > 7 else 0
			logger.info("Server mod: 0x%x, version: 0x%x, flags: 0x%x", body[5], mod_version, mod_flags)
		logger.info("Connected")

		# Spin up required tasks.
		self._tasks = asyncio.gather(
			asyncio.create_task(self._send_reliable_loop()),
			asyncio.create_task(self._recv_loop()),
			asyncio.create_task(self._monitor_queues()))

	@classmethod
	async def connect(cls, host, port):
		host = socket.gethostbyname(host)
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		body = b'bomberdude'
		header_fmt = ">HH"
		header_size = struct.calcsize(header_fmt)
		header = struct.pack(header_fmt, _NetFlags.CTL, len(body) + header_size)
		logger.info(f'{cls} connecting to {host} {port}')
		sock.sendto(header + body, (host, port))
		while True:
			packet, addr = await sock.recvfrom(1024)
			body = packet[header_size:]
			new_port, = struct.unpack("<L", body[1:])
			logger.debug(f'got packet: {packet} from {addr} {body} {new_port}')
		return cls(sock, host, newport)

	# def oldconnect(cls, host, port):
	# 	loop = asyncio.get_running_loop()
	# 	transport, protocol = await loop.create_datagram_endpoint(lambda: _GenericUdpProtocol(loop),family=socket.AF_INET)
	# 	logger.debug(f'connection made: {transport} {protocol}')
	# 	conn = cls(protocol)
	# 	await conn._connect(host, port)
	# 	logger.debug(f'connection: {conn} {transport} {protocol}')
	# 	for msg in conn.iter_messages():
	# 		while msg:
	# 			logger.info(f'got msg: {msg}')

	# 	return conn

	async def wait_until_disconnected(self):
		try:
			await self._tasks
		except asyncio.CancelledError:
			pass

	def _encap_packet(self, netflags, seq_num, payload):
		logger.debug(f"Sending packet: {netflags} {seq_num}  {payload}" )
		header_fmt = ">HHL"
		header_size = struct.calcsize(header_fmt)
		header = struct.pack(header_fmt, netflags, len(payload) + header_size, seq_num)
		return header + payload

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
				self._udp.sendto(packet, (self._host, self._port))

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

	async def send_reliable(self, data):
		acked_future = asyncio.Future()
		await self._send_reliable_queue.put((data, acked_future))
		await acked_future

	def send(self, data):
		if len(data) > _MAX_DATAGRAM_BODY:
			raise DatagramError(f"Datagram too big: {len(body)}")
		packet = self._encap_packet(_NetFlags.UNRELIABLE, self._unreliable_send_seq, data)
		self._udp.sendto(packet, (self._host, self._port))
		self._unreliable_send_seq += 1

	def _send_ack(self, seq_num):
		packet = self._encap_packet(_NetFlags.ACK, seq_num, b'')
		self._udp.sendto(packet, (self._host, self._port))

	async def _recv_loop(self):
		header_fmt = ">HHL"
		header_size = struct.calcsize(header_fmt)

		recv_seq = 0
		unreliable_recv_seq = 0
		reliable_msg = b''

		while True:
			packet, addr = await self._udp.recvfrom()
			if addr != (self._host, self._port):
				raise DatagramError("Spoofed packet received")

			netflags, size, seq_num = struct.unpack(header_fmt, packet[:header_size])
			netflags = _NetFlags(netflags)
			body = packet[header_size:]
			logger.debug(f"Received packet: {netflags} {seq_num} {body}")

			if len(packet) != size:
				raise DatagramError(f"Packet size {len(packet)} does not match header {size}")

			if netflags not in _SUPPORTED_FLAG_COMBINATIONS:
				raise DatagramError(f"Unsupported flag combination: {netflags}")

			if _NetFlags.UNRELIABLE in netflags:
				if seq_num < unreliable_recv_seq:
					logger.warning("Stale unreliable message received")
				else:
					if seq_num != unreliable_recv_seq:
						logger.warning(f"Skipped {self._unreliable_recv_seq - seq_num} unreliable messages")
					unreliable_recv_seq = seq_num + 1
					await self._message_queue.put(body)
			elif _NetFlags.ACK in netflags:
				await self._send_reliable_ack_queue.put(seq_num)
			elif _NetFlags.DATA in netflags:
				self._send_ack(seq_num)
				if seq_num != recv_seq:
					logger.warning("Duplicate reliable message received")
				else:
					reliable_msg += body
					recv_seq += 1

				if _NetFlags.EOM in netflags:
					await self._message_queue.put(reliable_msg)
					reliable_msg = b''

	async def read_message(self):
		return await self._message_queue.get()

	def disconnect(self):
		self.send(b'\x02')
		self._tasks.cancel()

