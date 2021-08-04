import socket
import pickle
import hashlib
import time
# import random
import threading
from weakref import WeakKeyDictionary
# from threading import Thread
# from multiprocessing import Queue
# import os
# import sys
# from ctypes import WinError
# import asyncio
from PodSixNet.Server import Server
from PodSixNet.Channel import Channel


class Client:
	def __init__(self, clientid, ipaddress, pos):
		self.clientid = clientid
		self.ipaddress = ipaddress
		self.inpackets = 0
		self.outpackets = 0
		self.pos = pos  # (self.posx, self.posy)

	def __str__(self):
		return f'clientid: {self.clientid}'

	def get_pos(self):
		return self.pos

	def set_pos(self, pos):
		self.pos = pos


class UDPServerold:
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
			# if c.clientid == clientid:
			if c == clientid:
				return True
		return False

	def get_clients(self):
		return self.clients

	def dumpclients(self):
		for client in self.clients:
			cl_id = self.clients.get(client).clientid
			cl_ipaddr = self.clients.get(client).ipaddress
			cl_in = self.clients.get(client).inpackets
			cl_out = self.clients.get(client).outpackets
			print(f'[CLIENT] {client} id:{cl_id} ip:{cl_ipaddr} in:{cl_in} out:{cl_out}')

	def parse_data(self, data, client_address):
		if len(self.clients) <= self.max_clients:
			clientid = data['id']
			clientpos = data['pos']
			client = Client(clientid=clientid, ipaddress=client_address, pos=clientpos)
			ret_port = self.port + len(self.clients) + 1
			if self.check_clientid(client.clientid):
				# print(f'[parse_data] update clientid: {clientid} pos: {clientpos}')
				self.clients[clientid].inpackets += 1
				self.clients[clientid].pos = clientpos

			else:
				# self.clients.append(client)
				self.clients[clientid] = client
				self.clients[clientid].pos = clientpos
			# print(f'[parse_data] newclient {client} clientconns: {len(self.clients)}')
			return f'[serverok] ret_port:{ret_port}'
		else:
			# print(f'[server] server full clients connected {len(self.clients)} max_clients={self.max_clients} ')
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
			# print(f'[server] sending {resp} to client {client_address}')
			self.sock.sendto(resp.encode('utf-8'), client_address)
		else:
			print(f'[server] could not get clientid')

	# with self.socket_lock:
	#    self.sock.sendto(resp.encode('utf-8'), client_address)
	#    print(f'[slock]')

	def shutdown_server(self):
		self.sock.close()

	def send_update(self):
		# print(f'[server] sending update to all [{len(self.clients)}] connected clients')
		d_port = self.port + 1
		for client in self.clients:
			# print(f'\t sending to client {client} {client.ipaddress}')
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


def oldmain():
	pass
	# udpserver = UDPServer('192.168.1.67', 4444)
	# udpserver.configure_server()
	# s_thread = threading.Thread(target=udpserver.wait_for_client, daemon=True)
	# # s_thread.daemon = True
	# # s_thread.start()
	# udpserver.running = True
	# s_thread.start()
	# while True:
	# 	try:
	# 		cmd = input('[SRV] > ')
	# 		if cmd[:1] == 'q':
	# 			udpserver.running = False
	# 			os._exit(0)
	# 		if cmd[:5] == 'start':
	# 			print(f'[server] starting udpserver.running {udpserver.running}')
	# 			if not udpserver.running:
	# 				s_thread = threading.Thread(target=udpserver.wait_for_client, daemon=True)
	# 				udpserver.running = True
	# 				s_thread.start()
	# 			else:
	# 				print(f'[server] status udpserver.running {udpserver.running}')
	# 		if cmd[:6] == 'status':
	# 			print(f'[serverstatus] threads: {threading.active_count()} clients: {len(udpserver.clients)}')
	# 		if cmd[:4] == 'send':
	# 			udpserver.send_update()
	# 		if cmd[:4] == 'dump':
	# 			udpserver.dumpclients()
	# 		if cmd[:4] == 'stop':
	# 			print(f'[r] stopping threads: {threading.active_count()}')
	# 			udpserver.running = False
	# 			s_thread.join()
	# 			s_thread = None
	# 			print(f'[r] stopped threads: {threading.active_count()}')
	# 	except KeyboardInterrupt:
	# 		udpserver.running = False
	# 		os._exit(0)


class ClientChannel(Channel):
	def __init__(self, *args, **kwargs):
		self.nickname = "anonymous"
		Channel.__init__(self, *args, **kwargs)
		self.id = str(self._server.get_unique_id())
		print(f'[cc] {self.nickname} {self.id}')

	# intid = int(self.id)
	# self.color = [(intid + 1) % 3 * 84, (intid + 2) % 3 * 84, (intid + 3) % 3 * 84]

	def network(self, data):
		print(f'[netdata] {data}')
		#pass

	def close(self):
		self._server.delete_player(self)

	# def Network_myaction(self, data):
	#     print(data)

	def network_update(self, data):
		self._server.move_player(data)


class UDPServer(Server):
	channelClass = ClientChannel

	def __init__(self, *args, **kwargs):
		Server.__init__(self, *args, **kwargs)
		self.players = WeakKeyDictionary()
		self.clients = []
		self.running = False
		print("Server launched")

	def get_clients(self):
		return self.clients

	def configure_server(self):
		pass

	def connection(self, channel, addr):
		print(f"New connection {addr}: ")
		print(f'channel: {channel}')
		self.add_player(channel)

	def add_player(self, player):
		print(f"New Player: {player.addr}")
		player.Send({"action": "set_id", "data": player.id})
		self.players[player] = True
		self.send_players()

	def delete_player(self, player):
		print("Deleting Player " + str(player.addr))
		self.send_to_all({"action": "del_player", "data": player.id})
		del self.players[player]

	def send_players(self):
		self.send_to_all({"action": "players", "players": [p.id for p in self.players]})

	def send_to_all(self, data):
		_ = [p.Send(data) for p in self.players]

	def send_to_all_origin(self, data, origin):
		_ = [p.Send(data) for p in self.players if p.id != origin]

	def get_unique_id(self):
		hashid = hashlib.sha1()
		hashid.update(str(time.time()).encode("utf-8"))
		return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it

	def move_player(self, data):
		self.send_to_all_origin(data, data["origin"])

	def run(self):
		self.running = True
		while True:
			self.Pump()
			time.sleep(0.0001)


if __name__ == '__main__':
	backend = UDPServer(localaddr=("localhost", 1234))
	backend.run()
