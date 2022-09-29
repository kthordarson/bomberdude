import socket
from threading import Thread
from loguru import logger

class BombClient(Thread):
	def __init__(self, client_id=None, serveraddress=None, serverport=None):
		Thread.__init__(self)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.client_id = client_id
		self.serveraddress = serveraddress
		self.serverport = serverport
		self.server = (self.serveraddress, self.serverport)
		self.kill = False
		self.connected = False

	def __str__(self):
		return f'{self.client_id}'

	def connect_to_server(self):
		if not self.connected:
			logger.debug(f'[bc] {self} connect_to_server {self.server}')
			try:
				self.socket.connect(self.server)
			except Exception as e:
				logger.error(f'[bc] {self} connect_to_server err:{e}')
				return False
			return True

	def run(self):
		logger.debug(f'[bc] {self.client_id} run! ')
		while True:
			if self.kill:
				logger.debug(F'[bc] {self} killed')
				break
