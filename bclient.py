import time
import socket
from threading import Thread
from loguru import logger
from network import send_data, receive_data, dataid
class BombClient(Thread):
	def __init__(self, client_id=None, serveraddress=None, serverport=None, mainqueue=None):
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
		self.mainqueue = mainqueue

	def __str__(self):
		return f'[bc] {self.client_id}'

	def send_bomb(self, pos=None):
		payload = {'data_id':dataid['update'], 'msgtype': dataid['bombdrop'], 'client_id':self.client_id, 'bombpos':pos}
		send_data(conn=self.socket, data_id=dataid['update'], payload=payload)
		logger.debug(f'{self} send_bomb {payload}')
	
	def send_mapreq(self):
		send_data(conn=self.socket, data_id=dataid['reqmap'], payload={'client_id':self.client_id, 'payload':'reqmap', 'data_id':dataid['reqmap']})
		logger.debug(f'{self} send_mapreq conn:{self.connected} map:{self.gotmap} ')

	def send_pos(self, pos):
		payload = {'data_id': dataid['playerpos'], 'client_id': self.client_id, 'pos': (pos[0], pos[1])}
		send_data(conn=self.socket, data_id=dataid['playerpos'], payload=payload)

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
				msgid, payload = None, None
				payload = receive_data(conn=self.socket)
				# logger.debug(f'{self}  payload:{payload}')
				if payload:
					msgid = payload.get('payload').get('data_id')
					#logger.debug(f'{self} msgid:{msgid} payload:{payload}')
					if msgid == 4 or payload.get('msgtype') == 'bcnetupdate':
						# logger.debug(f'{self} payload:{payload}')
						if payload.get('payload').get('msgtype') == 'bcgetid':
							if payload.get('payload').get('payload') == 'sendclientid':
								logger.debug(f'sending client_id ')
						elif payload.get('payload').get('msgtype') == 'bcpoll':
							#logger.debug(f'[bc] {self} bcpoll resp={payload}')
							netplayers = None
							netplayers = payload.get('payload').get('netplayers')
							if netplayers:
								for np in netplayers:
									self.netplayers[np] = netplayers[np]
						elif payload.get('payload').get('msgtype') == 'mapfromserver':
							gamemapgrid = payload.get('payload').get('gamemapgrid')
							logger.debug(f'mapfromserver g={len(gamemapgrid)}')
							self.gamemapgrid = gamemapgrid
							self.gotmap = True
						elif payload.get('payload').get('msgtype') == 'netbomb':
							# logger.debug(f'bombfromserver payload={payload}')
							bombmsg = {'msgtype':'netbomb', 'bombdata':payload.get('payload')}
							self.mainqueue.put_nowait(bombmsg)

						else:
							logger.warning(f'{self} unknownpayload msgid={msgid} p={payload}')
					else:
						logger.warning(f'{self} unknownmsgid={msgid} resp={payload}')
			else:
				logger.warning(f'{self} not connected')
