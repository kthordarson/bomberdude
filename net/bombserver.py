import socket
import pickle
import random
import threading
from threading import Thread
from multiprocessing import Queue
import os
import sys
from ctypes import WinError
import asyncio


class Client:
	def __init__(self, clientid, ipaddress):
		self.clientid = clientid
		self.ipaddress = ipaddress
		self.inpackets = 0
		self.outpackets = 0

	def __repr__(self):
		return self.clientid


class UDPServer:
	def __init__(self, host='192.168.1.67', port=4444):
		self.host = host
		self.port = port
		self.sock = None
		self.running = False
		self.clients = {}
		self.max_clients = 4
		self.socket_lock = None

	def configure_server(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setblocking(False)
		self.sock.bind((self.host, self.port))
		# self.sock.setsockopt(level, optname, value)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket_lock = threading.Lock()
		print(f'Server {self.host}:{self.port}...')

	def check_clientid(self, clientid):
		for c in self.clients:
			#if c.clientid == clientid:
			if c == clientid:
				return True
		return False
	
	def dumpclients(self):
		for client in self.clients:
			cl_id = self.clients.get(client).clientid
			cl_ipaddr = self.clients.get(client).ipaddress
			cl_in = self.clients.get(client).inpackets
			cl_out = self.clients.get(client).outpackets
			print(f'[CLIENT] {client} id:{cl_id} ip:{cl_ipaddr} in:{cl_in} out:{cl_out}')

	def parse_data(self, data, client_address):
		if len(self.clients) <= self.max_clients:
			client = Client(clientid=data['id'], ipaddress=client_address)
			ret_port = self.port + len(self.clients) + 1
			if self.check_clientid(client.clientid):
				print(f'[parse_data] update clientid: {data["id"]} pos: {data["pos"]}')
				self.clients[data['id']].inpackets += 1
			else:
				#self.clients.append(client)
				self.clients[data['id']] = client
				print(f'[parse_data] newclient {client} clientconns: {len(self.clients)}')
			return f'[serverok] ret_port:{ret_port}'
		else:
			print(f'[server] server full clients connected {len(self.clients)} max_clients={self.max_clients} ')
			return '[serverfull]'

	def handle_request(self, data, client_address):
		# print(f'[server] client: {client_address} sent: {data["id"]}')
		clientid = None
		try:
			clientid = data['id']
		except Exception as e:
			print(f'[server] clientid err {e}')
		if clientid:
			resp = self.parse_data(data, client_address)
			print(f'[server] sending {resp} to client {client_address}')
			self.sock.sendto(resp.encode('utf-8'), client_address)
		else:
			print(f'[server] could not get clientid')
		# with self.socket_lock:
		#    self.sock.sendto(resp.encode('utf-8'), client_address)
		#    print(f'[slock]')

	def shutdown_server(self):
		self.sock.close()

	def send_update(self):
		print(f'[server] sending update to all [{len(self.clients)}] connected clients')
		d_port = self.port + 1
		for client in self.clients:
			print(f'\t sending to client {client} {client.ipaddress}')
			update = 'beef'.encode('utf-8')
			# self.sock.sendto(update, client.ipaddress)
			self.sock.sendto(update, ('192.168.1.67', d_port))
			d_port += 1

	def wait_for_client(self):
		data = None
		datapickled = None
		client_address = None
		print(f'[wait_for_client] run: {self.running}')
		while self.running:
			try:
				data, client_address = self.sock.recvfrom(1024)
				datapickled = pickle.loads(data)
			except OSError as err:
				# print(f'[server] oserr {err}')
				datapickled = None
				data = None
			except pickle.UnpicklingError as e:
				print(f'[server] pickle ERR {e}')
				data = None
				datapickled = None
			#            except Exception as e:
			# self.running = False
			# print(f'[server] err {e}')
			except KeyboardInterrupt:
				data = None
				datapickled = None
				self.running = False
				self.shutdown_server()
			if datapickled is not None:
				c_thread = threading.Thread(target=self.handle_request, args=(datapickled, client_address))
				c_thread.daemon = True
				c_thread.start()


if __name__ == '__main__':
	udpserver = UDPServer('192.168.1.67', 4444)
	udpserver.configure_server()
	s_thread = threading.Thread(target=udpserver.wait_for_client, daemon=True)
	# s_thread.daemon = True
	# s_thread.start()
	udpserver.running = True
	s_thread.start()
	while True:
		try:
			cmd = input('[SRV] > ')
			if cmd[:1] == 'q':
				udpserver.running = False
				os._exit(0)
			if cmd[:5] == 'start':
				print(f'[server] starting udpserver.running {udpserver.running}')
				if not udpserver.running:
					s_thread = threading.Thread(target=udpserver.wait_for_client, daemon=True)
					udpserver.running = True
					s_thread.start()
				else:
					print(f'[server] status udpserver.running {udpserver.running}')
			if cmd[:6] == 'status':
				print(f'[serverstatus] threads: {threading.active_count()} clients: {len(udpserver.clients)}')
			if cmd[:4] == 'send':
				udpserver.send_update()
			if cmd[:4] == 'dump':
				udpserver.dumpclients()
			if cmd[:4] == 'stop':
				print(f'[r] stopping threads: {threading.active_count()}')
				udpserver.running = False
				s_thread.join()
				s_thread = None
				print(f'[r] stopped threads: {threading.active_count()}')
		except KeyboardInterrupt:
			udpserver.running = False
			os._exit(0)
