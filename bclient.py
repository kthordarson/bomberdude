import socket
from threading import Thread
from loguru import logger
from network import send_data, receive_data, dataid
class BombClient(Thread):
	def __init__(self, client_id=None, serveraddress=None, serverport=None, mainqueue=None, pos=None):
		Thread.__init__(self, daemon=True)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.client_id = client_id
		self.serveraddress = serveraddress
		self.serverport = serverport
		self.server = (self.serveraddress, self.serverport)
		self.kill = False
		self.connected = False
		self.pos = pos
		self.centerpos = pos
		self.netplayers = {}
		self.gamemap = None
		self.gotmap = False
		self.mainqueue = mainqueue

	def __str__(self):
		return f'id={self.client_id} pos={self.pos} center={self.centerpos} k:{self.kill} conn:{self.connected} gotmap:{self.gotmap}'

	def req_mapreset(self):
		# request server map reset
		if self.connected and not self.kill:
			reqmsg = {'data_id': dataid['resetmap'], 'client_id': self.client_id, 'pos': self.pos}
			send_data(conn=self.socket, payload=reqmsg)

	def send_bomb(self, pos=None):
		# send bomb to server
		if self.connected and not self.kill:
			payload = {'data_id':dataid['netbomb'], 'msgtype': dataid['bombdrop'], 'client_id':self.client_id, 'bombpos':pos}
			send_data(conn=self.socket, payload=payload)
			# logger.debug(f'[ {self} ] send_bomb pos={payload.get("bombpos")}')

	def send_reqpos(self):
		# get initial position from server
		if self.connected and not self.kill:
			reqmsg = {'data_id': dataid['reqpos'], 'client_id': self.client_id, 'payload': 'reqpos', 'pos':self.pos}
			send_data(conn=self.socket, payload=reqmsg)

	def send_mapreq(self):
		# request map from server
		if self.connected and not self.kill:
			regmsg = {'client_id':self.client_id, 'payload':'reqmap', 'data_id':dataid['reqmap'], 'pos':self.pos}
			send_data(conn=self.socket,  payload=regmsg)
			logger.debug(f'[ {self} ] send_mapreq')
			# self.send_reqpos()

	def send_pos(self, pos=None, center=None):
		# send pos to server
		if self.connected and not self.kill:		
			# logger.debug(f'{self} send_pos pos={pos} center={center}')
			self.pos = pos
			self.centerpos = center
			posmsg = {'data_id': dataid['playerpos'], 'client_id': self.client_id, 'pos': (pos[0], pos[1]), 'centerpos':center, 'kill':self.kill}
			send_data(conn=self.socket, payload=posmsg)

	def send_clientid(self):
		# send pos to server
		if self.connected and not self.kill:		
			cmsg = {'data_id': dataid['info'], 'client_id': self.client_id, 'pos': (self.pos[0], self.pos[1]), 'centerpos':self.centerpos, 'kill':self.kill}
			send_data(conn=self.socket, payload=cmsg)
			logger.info(f'[ {self} ] sending client_id ')

	def send_gridupdate(self, gridpos=None, blktype=None):
		# inform server about grid update
		# called after bomb explodes and kills block
		# gridpos=blk.gridpos, blktype=blk.block_type)
		if self.connected and not self.kill:
			gridmsg = {'data_id': dataid['gridupdate'], 'client_id': self.client_id, 'gridpos': gridpos, 'blktype': blktype, 'pos': self.pos}
			send_data(conn=self.socket, payload=gridmsg)
			logger.debug(f'[ {self} ] send_gridupdate {len(gridmsg)}')

	def disconnect(self):
		# send quitmsg to server
		quitmsg = {'data_id': dataid['clientquit'], 'client_id': self.client_id, 'payload': 'quit'}
		send_data(conn=self.socket, payload=quitmsg)
		self.kill = True
		self.connected = False
		self.socket.close()

	def connect_to_server(self):
		if not self.connected:
			logger.debug(f'[ {self} ] connect_to_server {self.server}')
			try:
				self.socket.connect(self.server)
			except Exception as e:
				logger.error(f'[ {self} ] connect_to_server err:{e}')
				self.connected = False
				return False
			self.connected = True
		return True

	def run(self):
		logger.debug(f'[ {self} ] run! ')
		while not self.kill:
			if self.kill or self.socket._closed:
				logger.debug(F'{self} killed')
				self.kill = True
				self.connected = False
				break
			if self.connected:
				#if not self.gotmap:
				#	self.send_mapreq()
				msgid, payload = None, None
				payload = receive_data(conn=self.socket)
				# logger.debug(f'[ {self} ]  payload:{payload}')
				if payload:
					msgid = payload.get('data_id')
					#logger.debug(f'[ {self} ] msgid:{msgid} payload:{payload}')
					# logger.debug(f'[ {self} ] payload:{payload}')
					if payload.get('msgtype') == 'bcgetid':
						if payload.get('payload') == 'sendclientid':
							# todo work on this....
							self.send_clientid()								
					elif payload.get('msgtype') == dataid['netplayers']:
						netplayers = None
						netplayers = payload.get('netplayers')
						if netplayers:
							#logger.debug(f'[ {self} ] netplayers {len(netplayers)} {netplayers}')
							# update netplayers
							for np in netplayers:
								self.netplayers[np] = netplayers[np]
					elif payload.get('msgtype') == 'netgridupdate':
						# received gridupdate from server
						gridpos = payload.get('gridpos')
						blktype = payload.get('blktype')
						logger.debug(f'[ {self} ] netgridupdate g={gridpos} b={blktype}')
						mapmsg = {'msgtype':'netgridupdate', 'client_id':self.client_id, 'gridpos':gridpos, 'blktype':blktype}
						# send grid update to mainqueue
						self.mainqueue.put_nowait(mapmsg)
						# update local grid
						self.gamemapgrid[gridpos[0]][gridpos[1]] = blktype
					elif payload.get('msgtype') == 'mapfromserver':
						# complete grid from server
						ng = None
						gamemapgrid = payload.get('gamemapgrid')
						ng = payload.get('newgrid')
						#pos = payload.get('pos')
						#self.pos = pos
						# self.gotmap = ng
						if ng:
							# new grid from server
							# todo fix player placemnt on newgrid
							logger.info(f'[ {self} ] newgridgromserver g={len(gamemapgrid)} ')
							mapmsg = {'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':gamemapgrid, 'pos':self.pos}
							self.mainqueue.put_nowait(mapmsg)							
							self.gamemapgrid = gamemapgrid
							self.gotmap = True
						elif not self.gotmap:
							# initial map from server
							logger.debug(f'[ {self} ] mapfromserver g={len(gamemapgrid)}')
							mapmsg = {'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':gamemapgrid, 'pos':self.pos}
							self.mainqueue.put_nowait(mapmsg)							
							self.gamemapgrid = gamemapgrid
							self.gotmap = True
						else:
							# should not land here
							logger.warning(f'[ {self} ] mapfromserver dupe g={len(gamemapgrid)} {ng}')

					elif payload.get('msgtype') == 'netbomb':
						# received bomb from server, forward to mainqueue
						# logger.debug(f'bombfromserver payload={payload}')
						bombmsg = {'msgtype':'netbomb', 'bombdata':payload, 'data_id':dataid['netbomb']}
						self.mainqueue.put_nowait(bombmsg)

					elif msgid == dataid['posupdate']:
						# received posupdate from server, forward to mainqueue
						logger.debug(f'[ {self} ] payload={payload}')
						posmsg = {'msgtype':'newnetpos', 'data_id':dataid['netpos'], 'posdata':payload, 'pos':self.pos}
						self.mainqueue.put_nowait(posmsg)
					elif payload.get('msgtype') == 'playerpos':
						# received playerpos from server, forward to mainqueue
						logger.debug(f'[ {self} ] payload={payload}')
						posmsg = {'msgtype':'newnetpos', 'data_id':dataid['netpos'], 'posdata':payload, 'pos':self.pos}
						self.mainqueue.put_nowait(posmsg)
					else:
						logger.warning(f'[ {self} ] unknownpayload msgid={msgid} p={payload}')
			else:
				logger.warning(f'[ {self} ] not connected')
