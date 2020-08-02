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
from threading import Thread
from network import get_ip_address, UDP_Server
# from network import UDPServer, MyUDPServer

class Game_server():
	def __init__(self):
		super().__init__()
		self.name = 'server'
		self.serverloop = asyncio.get_event_loop()
		self.udp_server = UDP_Server()
		self.udp_server.get_socket()
	def get_loop(self):
		return self.serverloop


async def main_loop(server):
	while True:
		try:
#			for data in server.udp_server.data_pump():
#				print(f'[d] {data}')
			data = [data for data in server.udp_server.data_pump()]
			await asyncio.sleep(0.1)
			print(f'{self.name} {data}')
		except KeyboardInterrupt:
			return

def main(server):
	server_task = asyncio.Task(main_loop(server))
	server.serverloop.run_until_complete(server_task)


if __name__ == "__main__":
	server = Game_server()
	# init()
	try:
		main(server)
	finally:
		server.serverloop.stop()
