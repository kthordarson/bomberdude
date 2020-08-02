# netstuff
import socket
import os
import time
from threading import Thread, Event

import pickle
import random
import io
import datetime

import asyncio
import socket
from collections import deque
import datetime


def get_ip_address():
	# returns the 'most real' ip address
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	time.sleep(0.5)
	s.connect(("8.8.8.8", 80))
	time.sleep(0.5)
	return s.getsockname()[0]

class UDP_Server(Thread):
	def __init__(self,host='127.0.0.1', port=9000):
		super(UDP_Server, self).__init__()
		self.host = host
		self.port = port
		#self.s.bind((host, port))
		#self.s.setblocking(False)
		self.setDaemon(True)
		self.kill = False
		self.clients = {}
		self.connections = []
		self.name = '[UDPSERVER]'
		self.data_rcv = 0
		self.data_snd = 0
	def get_socket(self):
		self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		#self.s.setblocking(False)
		self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.s.bind((self.host, self.port))
		print(f'{self.name} get_socket')
	def data_pump(self):
		print(f'{self.name} data_pump')
		self.s.setblocking(True)
		while True:
			data = None
			addr = None
			if self.kill:
				return
			try:
				(data, addr) = self.s.recvfrom(128*1024)
			except OSError as e:
				print(f'{self.name}[data_pump] OSERROR {e}')
				self.s = None
				self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			if addr:
				self.connections.append(addr)
				self.data_rcv += 1
				try:
					conn = self.clients[addr]
				except KeyError:
					self.clients[addr] = {'connected':True, 'in':0, 'out':0}			
				self.clients.get(addr)['in'] += 1
				# print(f'[] {self.clients}')
				for client in self.connections:
					response = str.encode(f'{self.name} to {client} data {data}')
					# print(f'[data_pumping] to {client} response: {response}')
					self.s.sendto(response, client)
					self.data_snd += 1
				#print(f'data_pump {addr} {data}')
				yield (addr, data)
	

class UDPServer():
	def __init__(self, upload_speed=0, download_speed=0, recv_max_size=256 * 1024, ipaddress='localhost', server_address='localhost', name='[UDPSERVER]'):
		self.name = name
		print(f'{self.name} init')
		self._upload_speed = upload_speed
		self._download_speed = download_speed
		self._recv_max_size = recv_max_size
		self.ipaddress = ipaddress
		self.server_address = server_address

		self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._sock.setblocking(False)
		self._send_event = asyncio.Event()
		self._send_queue = deque()
		self._subscribers = {}

	# region Interface
	def run(self, host, port, loop):
		print(f'{self.name} run')
		self.loop = loop
		try:
			self._sock.bind((host, port))
		except Exception as e:
			print(f'{self.name} {e}')
			print(f'{self.name} host {host} port {port}')
			os._exit(-1)
		self._connection_made()
		self._run_future(self._send_periodically(), self._recv_periodically())

	def subscribe(self, fut):
		self._subscribers[id(fut)] = fut

	def unsubscribe(self, fut):
		self._subscribers.pop(id(fut), None)

	def send(self, data, addr):
		# print(f'{self.name} send {data} {addr}')
		self._send_queue.append((data, addr))
		self._send_event.set()
		# print(f'{self.name} done send {data} {addr}')

	def _run_future(self, *args):
		for fut in args:
			asyncio.ensure_future(fut, loop=self.loop)

	def _sock_recv(self, fut=None, registered=False):
		fd = self._sock.fileno()
		if fut is None:
			fut = self.loop.create_future()
		if registered:
			self.loop.remove_reader(fd)
		data = None
		addr = None
		try:
			data = self._sock.recvfrom(self._recv_max_size)
			print(f'[data] {data}')
			#data, addr = self._sock.recvfrom(self._recv_max_size)
		except (BlockingIOError, InterruptedError, NotImplementedError) as e:
			print(f'{e}')
			print(F'data:{data} addr:{addr}')
			fut.set_result(0)
			self._socket_error(e)
#			os._exit(2)

		try:
			self.loop.add_reader(fd, self._sock_recv, fut, True)
		except (BlockingIOError, InterruptedError, NotImplementedError) as e:
			print(f'{e}')
			print(F'data:{data} addr:{addr}')
			fut.set_result(0)
			self._socket_error(e)
#			os._exit(2)
		except Exception as e:
			fut.set_result(0)
			self._socket_error(e)

		else:
			fut.set_result((data, addr))
		return fut

	def _sock_send(self, data, addr, fut=None, registered=False):
		fd = self._sock.fileno()
		if fut is None:
			fut = self.loop.create_future()
		if registered:
			self.loop.remove_writer(fd)
		if not data:
			return
		try:
			bytes_sent = self._sock.sendto(data, addr)
		except (BlockingIOError, InterruptedError):
			self.loop.add_writer(fd, self._sock_send, data, addr, fut, True)
		except Exception as e:
			fut.set_result(0)
			self._socket_error(e)
		else:
			fut.set_result(bytes_sent)
		return fut

	async def _throttle(self, data_len, speed=0):
		delay = (data_len / speed) if speed > 0 else 0
		await asyncio.sleep(delay)

	async def _send_periodically(self):
		while True:
			await self._send_event.wait()
			try:
				while self._send_queue:
					data, addr = self._send_queue.popleft()
					bytes_sent = await self._sock_send(data, addr)
					await self._throttle(bytes_sent, self._upload_speed)
			finally:
				self._send_event.clear()

	async def _recv_periodically(self):
		while True:
			data, addr = await self._sock_recv()
			self._notify_subscribers(*self._datagram_received(data, addr))
			await self._throttle(len(data), self._download_speed)

	def _connection_made(self):
		pass

	def _socket_error(self, e):
		pass

	def _datagram_received(self, data, addr):
		return data, addr

	def _notify_subscribers(self, data, addr):
		self._run_future(*(fut(data, addr) for fut in self._subscribers.values()))

class MyUDPServer:
	def __init__(self, server, loop, ipaddress, server_address, name):
		self.name = name
		self.server = server
		self.server_address = server_address
		self.ipaddress = ipaddress
		self.loop = loop
		self.debug = False
		self.commands = []
		# Subscribe for incoming udp packet event
		self.server.subscribe(self.on_datagram_received)
		self.data_rcv = 0
		self.data_snd = 0
		self.listen = False
		self.clients = {}
		asyncio.ensure_future(self.do_send(), loop=self.loop)
		print(f'{self.name} init')

	async def on_datagram_received(self, data, addr):
		self.data_rcv += 1
		conn = None
		if self.listen:
			try:
				conn = self.clients[addr[0]]
			except KeyError:
				self.clients[addr[0]] = {'connected':True, 'in':0, 'out':0}
			
			self.clients.get(addr[0])['in'] += 1
			command = data.decode()
			#print(f'[servercmd] {command} {data} {command}')
			if command[:10] == '[p_update]':
				# [p_update]:id:{player.player_id}:pos:{player.pos}
				# [id:33:pos:(180, 320)] from ('192.168.1.35', 55285)
				#print(f'[{command[11:]}] from {addr} clients: {len(self.clients)}')
				self.update_clients(command[10:])
			if self.debug:
				pass
				#print(f'[dgrrcv] [{datetime.datetime.now()}], {addr}, {data}')
			
		else:
			print(f'{self.name} got data but not listening...')
	
	def update_clients(self, command):
		for client in self.clients:
			print(f'{self.name} sending update {command} to {client}')
			self.server.send(command, client)

	def send_player_update(self, player, server): # player = class Player
		# construct data packet from Player object
		command = str.encode(f'{self.name}[p_update]:id:{player.player_id}:pos:{player.pos}')
		#print(f'[send_update][{datetime.datetime.now()}] {command} server: {self.serverAddressPort}')
		self.server.send(command, server.ipaddress)
		# self.socket.sendto(command, self.serverAddressPort)
		self.data_snd += 1
		
	async def do_send(self):
		print(f'{self.name} do_send')
#		while True:
		await asyncio.sleep(0.1)
		payload = None
		for cmd in self.commands:
			if cmd == 'foo':
				payload = b'FOFOFOFOFOF'
				self.server.send(payload, (self.server_address, 10101))
				self.data_snd += 1
			if cmd == 'send':
				payload = b'd1:ad2:id20:k'
				self.server.send(payload, (self.server_address, 10101))
				self.data_snd += 1
				# cmd = cmd[1:]
			if cmd == 'sendfoo':
				payload = b'XXXXXXXXXXXXXXXXXXXXXXXXXx'
				self.server.send(payload, (self.server_address, 10101))
				self.data_snd += 1
				# cmd = cmd[1:]
			self.commands = self.commands[1:]

class Client():
	def __init__(self, server, name='Client'):
		super(Client, self).__init__()
		# self.bytesToSend = str.encode(self.msgFromClient)
		#self.serverAddressPort = ("127.0.0.1", 10102)
		self.name = name
		self.server = server
		self.serverip = server[0]
		self.serverport = server[1]
		self.bufferSize = 1024
		self.connected = False
		self.hostname = socket.gethostname()
		# self.ipaddress = socket.gethostbyname(self.hostname)
		self.ipaddress = get_ip_address()
		self.client_id = 0
		self.foundservers =[]
		self.new_map = None
		self.got_new_map = False
		self.got_socket = False
		self.data_rcv = 0
		self.data_snd = 0

	def create_socket(self):
		try:
			self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
			self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.socket.setblocking(False)
			#self.socket.bind((self.serverip, self.serverport))
			self.socket.bind(self.server)
			self.got_socket = True
			print(f'{self.name} socket created: {self.socket}')
		except Exception as e:
			print(f'{self.name}[create_socket] exception {e}')
			self.connected = False
			self.got_socket = False		

	def run(self):
		print(f'{self.name}[run]....')
		while True and self.got_socket:
			dataraw = None
			try:
				dataraw = self.socket.recvfrom(self.bufferSize)                
			except Exception as e:
				print(f'{self.name}[run] {e} gotsocket:{self.got_socket}')
				break
				#os._exit(-1)
			if not dataraw:
				break
			if dataraw is None:
				break
#			else:
			chunks = []
			data = dataraw[0].decode()
			print(f'{self.name}[got_data] {data}')
			self.data_rcv += 1
			if data[:17] == '[serveripaddress]':
				self.foundservers.append('')
				print(f'{self.name}[foundserver] {data}')
			if data[:8] == '[mapend]':
				print(f'{self.name}[mapend] {data}')

	def send(self, msg):
		if self.client_id != 0:
			self.socket.sendto(str.encode(msg), self.server)
			# time.sleep(0.001)

	def send_foo(self):
		command = str.encode('[foobar]')
		self.socket.sendto(command, self.server)

	def send_player_update(self, player, server): # player = class Player
		# construct data packet from Player object
		command = str.encode(f'[p_update]:id:{player.player_id}:pos:{player.pos}')
		# print(f'{self.name}[send_update][{datetime.datetime.now()}] {command} server: {self.serverAddressPort}')
		self.socket.sendto(command, self.server)
		self.data_snd += 1

	def scan_network(self):
		# scan local network for servers
		iplist = [self.ipaddress.split('.')[0] + '.' + self.ipaddress.split('.')[1] + '.' + self.ipaddress.split('.')[2] + '.' + str(k) for k in range(1,255)]
