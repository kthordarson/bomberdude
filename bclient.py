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
		payload = {'data_id':dataid['netbomb'], 'msgtype': dataid['bombdrop'], 'client_id':self.client_id, 'bombpos':pos}
		send_data(conn=self.socket, payload=payload)
		logger.debug(f'{self} send_bomb pos={payload.get("bombpos")}')
	
	def send_mapreq(self):
		regmsg = {'client_id':self.client_id, 'payload':'reqmap', 'data_id':dataid['reqmap']}
		send_data(conn=self.socket,  payload=regmsg)
		logger.debug(f'{self} send_mapreq conn:{self.connected} map:{self.gotmap} ')

	def send_pos(self, pos):
		self.pos = pos
		posmsg = {'data_id': dataid['playerpos'], 'client_id': self.client_id, 'pos': (pos[0], pos[1])}
		send_data(conn=self.socket, payload=posmsg)

	def send_gridupdate(self, gamemapgrid):
		gridmsg = {'data_id': dataid['gridupdate'], 'client_id': self.client_id, 'gamemapgrid': gamemapgrid}
		send_data(conn=self.socket, payload=gridmsg)
		logger.debug(f'{self} send_gridupdate {len(gridmsg)}')

	def disconnect(self):
		quitmsg = {'data_id': dataid['clientquit'], 'client_id': self.client_id, 'payload': 'quit'}
		send_data(conn=self.socket, payload=quitmsg)
		self.kill = True
		self.connected = False
		self.socket.close()

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
					msgid = payload.get('data_id')
					#logger.debug(f'{self} msgid:{msgid} payload:{payload}')
					if msgid:
						# logger.debug(f'{self} payload:{payload}')
						if payload.get('msgtype') == 'bcgetid':
							if payload.get('payload') == 'sendclientid':
								logger.debug(f'sending client_id ')
						elif payload.get('msgtype') == dataid['netplayers']:
							#logger.debug(f'[bc] {self} bcpoll resp={payload}')
							netplayers = None
							netplayers = payload.get('netplayers')
							if netplayers:
								for np in netplayers:
									self.netplayers[np] = netplayers[np]
						elif payload.get('msgtype') == 'mapfromserver' or payload.get('msgtype') == 'netgrid':
							gamemapgrid = payload.get('gamemapgrid')
							logger.debug(f'mapfromserver g={len(gamemapgrid)}')
							mapmsg = {'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':gamemapgrid}
							self.mainqueue.put_nowait(mapmsg)
							self.gamemapgrid = gamemapgrid
							self.gotmap = True
						elif payload.get('msgtype') == 'netbomb':
							# logger.debug(f'bombfromserver payload={payload}')
							bombmsg = {'msgtype':'netbomb', 'bombdata':payload, 'data_id':dataid['netbomb']}
							self.mainqueue.put_nowait(bombmsg)

						else:
							logger.warning(f'{self} unknownpayload msgid={msgid} p={payload}')
					else:
						logger.warning(f'{self} unknownmsgid={msgid} p={payload}')
			else:
				logger.warning(f'{self} not connected')
