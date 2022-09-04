import socket
from signal import signal, SIGPIPE, SIG_DFL

import sys
from queue import Empty, Queue

from loguru import logger
from pygame.math import Vector2
from pygame.sprite import Group

from globals import Block, empty_queue
from globals import GRIDSIZE
from globals import Gamemap
from globals import gen_randid
from netutils import data_identifiers, DataReceiver, DataSender
from threading import Thread
from threading import enumerate as t_enumerate


class ClientThread(Thread):
	def __init__(self, clientaddr=None, clientconnection=None, blocks=None, gamemap=None, client_q=None):
		Thread.__init__(self, name='clthread')
		self.client_id = gen_randid()
		# StoppableThread.__init__(self, name=self.client_id)
		self.name = f'clthread-{self.client_id}'
		logger.debug(f'[s] cthread: {self.client_id} init ')

	def run(self):
		pass


class ConnectionHandler(Thread):
	def __init__(self, name='connhandler', socket=None, serverqueue=None, localaddr=None):
		Thread.__init__(self, name='connhandler')
		self.name = name
		self.socket = socket
		self.localaddr = localaddr
		self.kill = False

	def run(self):
		while True:
			pass

class ServerThread(Thread):
	def __init__(self, name='serverthread', listenaddr='127.0.0.1', port=6666, serverqueue=None, blocks=None, players=None, mainmap=None):
		Thread.__init__(self, name='serverthread')
		self.name = name
		self.localaddr = (listenaddr, port)
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.clients = []

	def run(self):
		self.socket.bind(self.localaddr)
		self.socket.listen(0)
		self.kill = False
		logger.debug(f'[s] {self.localaddr} run')
		while True:
			if self.kill:
				logger.debug(f'[s] killing self:{self.name} k:{self.kill}')
				self.connhandler.kill = True
				logger.debug(f'[s] stopped k:{self.kill}')
				self.socket.close()
				self.kill = True
				break

if __name__ == '__main__':
	mainthreads = []
	server = ServerThread(name='bombserver')
	server.daemon = True
	server.start()
	while True:
		try:
			cmd = input(f': ')
			if cmd[:1] == 'q':
				break
			if cmd[:1] == 'd':
				logger.debug(f'[d] ')
			if cmd[:1] == 'p':
				for k in range(10):
					pass # client.sq.put((data_identifiers['send_pos'], f'{client.pos}'))
			if cmd[:1] == 'f':
				for k in range(10):
					foo = f'foo{k}'
					logger.debug(f'sending {foo} to q')
					#pass #client.queue.put(foo)
			if cmd[:1] == '1':
				pass
			if cmd[:1] == '2':
				pass
			if cmd[:1] == '3':
				pass
				#m.send_items_to_q()
		except KeyboardInterrupt as e:
			logger.debug(f'KeyboardInterrupt {e}')
			break
		except Exception as e:
			logger.debug(f'E in main {e}')
			break


