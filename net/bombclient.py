import random
import socket
import pickle
import time
import datetime
import threading
from threading import Thread
from multiprocessing import  Queue
import os
import sys
import pygame

#from bdude import Game
#from player import Player

def gen_randid(seed=None):
	randid = []
	for k in range(0,7):
		n = random.randint(1,99)
		randid.append(n)
	return randid

class Player(): # placeholder for player object
	def __init__(self):
		self.client_id = ''.join([''.join(str(k)) for k in gen_randid()])

class Game(Thread): # placeholder for game object, contains player object for testing
	def __init__(self):
		super(Game, self).__init__()
		self.player = Player()
		self.client = UDPClient('192.168.1.67', 4444)
		# self.client = BombClient(server='192.168.1.67', server_port=9999, player=self.player)


class UDPClient:
	def __init__(self, host='192.168.1.67', port=4444):
		self.server_address = host
		self.server_port = port
		self.listen_port = 0
		self.listen_sock = None
		self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.server_sock.setblocking(False)
		# self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.client_id = ''.join([''.join(str(random.randint(0,99))) for k in range(10)])
		self.connected = False
		self.listening = False
		self.clnt_inpackets = 0
		self.clnt_outpackets = 0
		self.posx = 0
		self.posy = 0
		self.pos = (0,0)

		print(f'[UDPClient] {self.client_id} init server:{host}:{port}')

	def listener(self):
		print(f'[UDPClient] listener starting...')
		if self.connected:
			self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.listen_sock.setblocking(False)
			self.listen_sock.bind(('0.0.0.0', self.listen_port))
			data = None
			self.listening = True
			print(f'[UDPClient] listener ok {self.listen_sock}')
			while self.connected:
				try:
					data, server_address = self.listen_sock.recvfrom(1024)
				except OSError as err:
					data = None
				if data:
					#print(f'[listener] got {data}')
					self.clnt_inpackets += 1
		else:
			print(f'[UDPClient] listener failed not connected ...')

	def is_connected(self):
		return self.connected

	def set_pos(self, pos):
		self.pos = pos

	def setid(self, clientid):
		self.client_id = clientid

	def send_pos(self, pos):
		if self.connected:
			self.clnt_outpackets += 1
			data = pickle.dumps({'id' : self.client_id, 'pos': pos})
			# print(f'[bcl] sending {data}')
			try:
				self.server_sock.sendto(data, (self.server_address, self.server_port))
				# time.sleep(0.1)
				resp, server_address = self.server_sock.recvfrom(1024)
				#print(f'[send_pos] r: {resp.decode()}')
			except OSError as err:
				pass
		else:
			print(f'[send_pos] not connected')

	def connect(self):
		if self.connected:
			print(f'[client] already connected')
			return
		else:
			connectstring = pickle.dumps({'id' : self.client_id, 'request': 'connect', 'pos': [0,0]})
			#print(f'[client] sending connection string {connectstring}')
			try:
				self.server_sock.sendto(connectstring, (self.server_address, self.server_port))
				time.sleep(0.5)
				resp, server_address = self.server_sock.recvfrom(1024)
				response = resp.decode('utf-8')
				#print(f'[client] conn resp: {resp} {server_address}')
				if '[serverok]' in response:
					lport = response.split(':')[1]
					self.listen_port = int(lport)
					self.connected = True
					#print(f'[client] connection ok lport:{self.listen_port}')
					l_thread = threading.Thread(target=self.listener, daemon=True)
					l_thread.start()
				else:
					print(f'[client] connection error')
					self.connected = False
			except OSError as err:
				self.connected = False

	def send_data(self, extradata=None):
		if self.connected:
			self.clnt_outpackets += 1
			self.posx = random.randint(1, 32)
			self.posy = random.randint(1, 32)
			data = pickle.dumps({'id' : self.client_id, 'pos': [self.posx, self.posy]})
			# print(f'[bcl] sending {data}')
			try:
				self.server_sock.sendto(data, (self.server_address, self.server_port))
				# time.sleep(0.1)
				resp, server_address = self.server_sock.recvfrom(1024)
				#print(f'[send_data] r: {resp.decode()}')
			except OSError as err:
				pass
		else:
			print(f'[send_data] not connected')

	def send_garbage(self):
		if self.connected:
			#self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			#self.server_sock.setblocking(False)
			data = b'foobarbadbeef'
			# data = pickle.dumps(data)
			try:
				self.clnt_outpackets += 1
				self.server_sock.sendto(data, (self.server_address, self.server_port))
				resp, server_address = self.server_sock.recvfrom(1024)
				print(f'[RECEIVED] {resp.decode()}')
			except OSError as err:
				pass
				# print(f'[send_data] OSERR {err}')
			#except KeyboardInterrupt:
			#    self.server_sock.close()
			#finally:
			#    self.server_sock.close()
		else:
			print(f'[client] garb not connected')
			return



if __name__ == "__main__":
	print('[bombclient]')
	game = Game()
#    print(f'cl {client}')
	game.client.connect()
	while True:
		cmd = input('[CLNT] > ')
		if cmd[:1] == 'q':
			os._exit(0)
		if cmd[:1] == 's':
			game.client.send_data()
		if cmd[:1] == 'c':
			game.client.connect()
		if cmd[:1] == 'g':
			game.client.send_garbage()
		if cmd[:1] == 'r':
			pass
