import socket
import pickle
import hashlib
import time
import os
# import random
import threading
from queue import Queue, Empty
from weakref import WeakKeyDictionary
from threading import Thread
# from multiprocessing import Queue
# import os
# import sys
# from ctypes import WinError
# import asyncio
from PodSixNet.Server import Server
from PodSixNet.Channel import Channel

class ServerChannel(Channel):
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
	channelClass = ServerChannel

	def __init__(self, *args, **kwargs):
		Server.__init__(self, *args, **kwargs)
		self.players = WeakKeyDictionary()
		self.clients = []
		self.running = False
		print("udp server init")

	def get_clients(self):
		return self.clients

	def configure_server(self):
		pass

	def Connected(self, channel, addr):
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
		try:
			del self.players[player]
		except KeyError as e:
			print(f'[delplayer] err {e}')

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
		print(f'[server] run:{self.running}')
		while self.running:
			self.Pump()
			time.sleep(0.0001)

	def runold(self):
		self.running = True
		print(f'[server] run:{self.running}')
		while self.running:
			self.Pump()
			time.sleep(0.0001)
			try:
				cmd = input('[S]> ')
				if cmd[:1] == 'q':
					self.running = False
			except KeyboardInterrupt:
				self.running = False
				os._exit(0)

class ServerThread(Thread):
	def __init__(self, gameserver):
		Thread.__init__(self)
		self.running = False
		self.kill = False
		self.gameserver = gameserver
		self.mainq = Queue()
		print(f'[ST] serverthread init')
	def run(self):
		print(f'[ST] serverthread run')
		while self.running:
			try:
				cmd = input('> ')
				if cmd[:1] == 'q':
					self.gameserver.running = False
					self.running = False
				if cmd[:1] == 'd':
					print(f'[s] run {self.gameserver.running}')
			except KeyboardInterrupt:
				self.gameserver.running = False
				self.running = False
				os._exit(0)

def check_threads(threads):
	return True in [t.is_alive() for t in threads]

def stop_all_threads(threads):
	for t in threads:
		t.kill = True
		t.join()

if __name__ == '__main__':
	# backend = UDPServer(localaddr=("192.168.1.222", 1234))
	backend = Thread(target=UDPServer, args=(('localaddr="192.168.1.222"', 1234),))
	server = ServerThread(backend)
	mainthreads = list()
	mainthreads.append(backend)
	mainthreads.append(server)
	for t in mainthreads:
		t.start()
	while check_threads(mainthreads):
		try:
			cmd = input(':')
			if cmd[:1] == 'q':
				stop_all_threads(mainthreads)
			if cmd[:1] == 'd':
				print(f'[d] backend {backend}')
				print(f'[d] server {server}')
			if cmd[:1] == '1':
				print(f'[s1] {len(mainthreads)}')
			if cmd[:1] == '2':
				print(f'[s2] {len(mainthreads)}')
			if cmd[:1] == '3':
				pass
				#m.send_items_to_q()
				
		except KeyboardInterrupt as e:
			print(f'KeyboardInterrupt {e}')
			stop_all_threads(mainthreads)
		except Exception as e:
			print(f'E in main {e}')
			stop_all_threads(mainthreads)



	# srvcmd.run()
	# backend.run()

	# while backend.running:
	# 	try:
	# 		cmd = input('> ')
	# 		if cmd[:1] == 'q':
	# 			backend.running = False
	# 		if cmd[:1] == 'd':
	# 			print(f'[s] run {backend.running}')
	# 	except KeyboardInterrupt:
	# 		self.running = False
	# 		os._exit(0)
