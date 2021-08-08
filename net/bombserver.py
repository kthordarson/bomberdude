# import socket
# import pickle
import hashlib
import time
import os
import random
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
# from globals import gen_randid


def gen_randid():
	hashid = hashlib.sha1()
	hashid.update(str(time.time()).encode("utf-8"))
	return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it

class ServerChannel(Channel):
	def __init__(self, *args, **kwargs):
		self.nickname = "anonymous"
		Channel.__init__(self, *args, **kwargs)
		# self.id = str(self._server.get_unique_id())
		self.id = gen_randid()  # ''.join([''.join(str(k)) for k in gen_randid()])
		print(f'[cc] {self.nickname} {self.id}')

	# intid = int(self.id)
	# self.color = [(intid + 1) % 3 * 84, (intid + 2) % 3 * 84, (intid + 3) % 3 * 84]

	def Network(self, data):
		print(f'[netdata] {data}')
		#pass

	def Close(self):
		self._server.delete_player(self)

	# def Network_myaction(self, data):
	#     print(data)

	def Network_update(self, data):
		print(f'[netupdate] {data}')
		self._server.move_player(data)

	def PassOn(self, data):
		print(f'[passon] {data}')
		data.update({'id': self.id})
		print(f'[passon] sending {data}')
		self._server.SendToAll(data)

class UDPServer(Server):
	channelClass = ServerChannel
	def __init__(self, *args, **kwargs):
		Server.__init__(self, *args, **kwargs)
		#channelClass = ServerChannel()
		self.players = WeakKeyDictionary()
		self.clients = []
		self.running = False
		self.addr = ('192.168.1.222', 1234)
		print(f"udp server init args: {args} kwargs: {kwargs}")
		print(f'udp server addr {self.addr}')
		print(f'udp server chan {self.channelClass}')

	def get_clients(self):
		return self.clients

	def configure_server(self):
		pass

	def Connected(self, channel, addr):
		print(f"New connection {addr}: ")
		print(f'channel: {channel}')
		self.AddPlayer(channel)

	def AddPlayer(self, player):
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
		print(f'[sendplayers]')
		self.send_to_all({"action": "players", "players": [p.id for p in self.players]})

	def send_to_all(self, data):
		print(f'[sendall] {data}')
		_ = [p.Send(data) for p in self.players]

	def send_to_all_origin(self, data, origin):
		print(f'[sendallo] {data} {origin}')
		_ = [p.Send(data) for p in self.players if p.id != origin]

	def get_unique_id(self):
		hashid = hashlib.sha1()
		hashid.update(str(time.time()).encode("utf-8"))
		return hashid.hexdigest()[:10]  # just to shorten the id. hopefully won't get collisions but if so just don't shorten it

	def move_player(self, data):
		print(f'[move] {data}')
		self.send_to_all_origin(data, data["origin"])

class ServerThread(Thread):
	def __init__(self):
		Thread.__init__(self,name='serverthread')
		self.running = False
		self.kill = False
		# self.gameserver = gameserver
		# self.backend = UDPServer(localaddr=("192.168.1.222", 1234))
		# self.backend = Thread(target=UDPServer, args=(('192.168.1.222', 1234),),name='udpserver')
		self.backend = UDPServer(localaddr=("192.168.1.222", 1234))
		self.mainq = Queue()
		print(f'[ST] {self.name} init')

	def run(self):
		self.running = True
		print(f'[ST] {self.name} run {self.running}')
		# self.gameserver.run()
		# self.backend.start()
		while self.running:
			try:
				self.backend.Pump()
				if self.kill:
					self.running = False
				# print(f'[st] {self.name} {self.backend.name} ')
			except KeyboardInterrupt:
				print(f'[serverthread] keyboardint')
				self.backend.running = False
				self.running = False
				os._exit(0)

def check_threads(threads):
	return True in [t.is_alive() for t in threads]

def stop_all_threads(threads):
	print(f'stopping {threads}')
	for t in threads:
		print(f'waiting for {t}')
		t.kill = True
		t.join()

def start_all_threads(threads):
	print(f'starting {threads}')
	for t in threads:
		print(f'start {t}')
		t.run()

if __name__ == '__main__':
	# backend = UDPServer(localaddr=("192.168.1.222", 1234))
	#backend = Thread(target=UDPServer, args=(('192.168.1.222', 1234),),name='udpserver')
	server = ServerThread()
	mainthreads = list()
	# mainthreads.append(backend)
	mainthreads.append(server)
	# mainthreads.append(server.backend)
	# for t in mainthreads:
	# 	print(f'starting thread {t}')
	# 	t.start()
	server.start()
	while check_threads(mainthreads):
		try:
			cmd = input(':')
			if cmd[:1] == 'q':
				stop_all_threads(mainthreads)
			if cmd[:1] == 'd':
				print(f'[d] server {server}')
				print(f'[d] backend {server.backend}')
				print(f'[d] mainthreads {len(mainthreads)}')
			if cmd[:1] == 's':
				print(f'{server.backend}')
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
