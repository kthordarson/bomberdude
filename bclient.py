import time
import socket
from threading import Thread
from loguru import logger
from network import send_data, receive_data, dataid
class BombClient(Thread):
	def __init__(self, client_id=None, serveraddress=None, serverport=None):
		Thread.__init__(self, daemon=True)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.client_id = client_id
		self.serveraddress = serveraddress
		self.serverport = serverport
		self.server = (self.serveraddress, self.serverport)
		self.kill = False
		self.connected = False
		self.pos = (0,0)
		self.netplayers = {}
		self.gamemap = None
		self.gotmap = False

	def __str__(self):
		return f'[bc] {self.client_id}'

	def send_bomb(self):
		payload = {'msgtype': dataid['bombdrop'], 'client_id':self.client_id, 'bombpos':self.pos}
		send_data(conn=self.socket, data_id=dataid['update'], payload=payload)
		logger.debug(f'{self} send_bomb {payload}')
	
	def send_mapreq(self):
		send_data(conn=self.socket, data_id=dataid['reqmap'], payload={'client_id':self.client_id, 'payload':'reqmap'})
		logger.debug(f'{self} send_mapreq conn:{self.connected} map:{self.gotmap} ')

	def send_pos(self, pos):
		payload = {'client_id': self.client_id, 'pos': pos}
		send_data(conn=self.socket, data_id=dataid['playerpos'], payload=payload)
		#send_data(conn=self.socket, data_id=dataid['reqmap'], payload={'client_id':self.client_id, 'payload':'reqmap'})
		# logger.debug(f'{self} sendpos conn:{self.connected} map:{self.gotmap} p={self.pos}')

	def connect_to_server(self):
		if not self.connected:
			logger.debug(f'{self} connect_to_server {self.server}')
			try:
				self.socket.connect(self.server)
			except Exception as e:
				logger.error(f'{self} connect_to_server err:{e}')
				self.connected = False
				return False
			self.connected = True
			#logger.debug(f'[bc] sending auth')
			#authpayload = {'client_id': self.client_id, 'pos': (100,100)}
			#send_data(conn=self.socket, data_id=dataid['auth'], payload=authpayload)
			# msgid,payload = receive_data(conn=self.socket)
			return True

	def run(self):
		logger.debug(f'{self} run! conn:{self.connected} map:{self.gotmap} ')
		while True:
			if self.kill:
				logger.debug(F'{self} killed')
				break
			if self.connected:
				if not self.gotmap:
					self.send_mapreq()
					#payload = {'msgtype': dataid['reqmap'], 'payload':self.client_id}
					#send_data(conn=self.socket, data_id=dataid['reqmap'], payload={'client_id':self.client_id})
					#logger.debug(f'[bc] {self.client_id} gotmap conn:{self.connected} map:{self.gotmap} ')
#				testpayload = {'client_id': self.client_id, 'pos': self.pos}
#				send_data(conn=self.socket, data_id=dataid['playerpos'], payload=testpayload)
				# self.send_pos()
				msgid, payload = None, None
				msgid,payload = receive_data(conn=self.socket)
				if msgid == 4:
					if payload.get('msgtype') == 'bcnetupdate':
						if payload.get('payload').get('msgtype') == 'bcgetid':
							if payload.get('payload').get('payload') == 'sendclientid':
								logger.debug(f'sending client_id ')
								authpayload = {'client_id': self.client_id, 'pos': self.pos}
								#send_data(conn=self.socket, data_id=dataid['auth'], payload=authpayload)
						elif payload.get('payload').get('msgtype') == 'bcpoll':
							#logger.debug(f'[bc] {self} bcpoll resp={payload}')
							testpayload = {'client_id': self.client_id, 'pos': self.pos}
							#send_data(conn=self.socket, data_id=dataid['playerpos'], payload=testpayload)
							netplayers = None
							netplayers = payload.get('payload').get('netplayers')
							if netplayers:
								for np in netplayers:
									self.netplayers[np] = netplayers[np]
						elif payload.get('payload').get('msgtype') == 'mapfromserver':
							gamemap = payload.get('payload').get('gamemap')
							logger.debug(f'mapfromserver p={payload} g={gamemap}')
							self.gamemap = gamemap
							self.gotmap = True
							testpayload = {'client_id': self.client_id, 'pos': self.pos}
							#send_data(conn=self.socket, data_id=dataid['playerpos'], payload=testpayload)
						else:
							logger.warning(f'{self} unknown msgtype {msgid} {payload}')
					else:
						logger.warning(f'{self} unknown msgtype {msgid} {payload}')
				else:
					logger.warning(f'{self} resp={payload}')
			else:
				logger.warning(f'{self} not connected')
