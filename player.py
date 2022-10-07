import pygame
from pygame import USEREVENT
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import Group, spritecollide, Sprite
from globals import BasicThing, Block, Bomb
from loguru import logger
from globals import gen_randid
from threading import Thread
from constants import *
from network import dataid
import socket
from map import Gamemap
from network import send_data, receive_data

class Player(BasicThing, Thread):
	def __init__(self):
		Thread.__init__(self, daemon=False)
		super().__init__((0,0), (0,0))
		self.vel = Vector2(0, 0)
		self.pos = (0,0)
		self.gridpos = [0,0]
		#self.image = pygame.image.load('data/playerone.png')
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(pygame.image.load('data/playerone.png'), self.size)
		self.rect = pygame.Surface.get_rect(self.image, center=self.pos)
		self.surface = pygame.display.get_surface() # pygame.Surface(PLAYERSIZE)
		#self.rect = self.surface.fill(color=(90,90,90))
		# BasicThing.__init__(self, pos, self.image)
		self.ready = False
		self.client_id = gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		#self.rect = self.surface.get_rect() #pygame.Rect((self.pos[0], self.pos[1], PLAYERSIZE[0], PLAYERSIZE[1])) #self.image.get_rect()
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.speed = 3
		self.client = BombClient(client_id=self.client_id, serveraddress='localhost', serverport=9696,  pos=self.pos)
		self.gotmap = False
		self.gotpos = False

	def __str__(self):
		return f'player {self.client_id} pos={self.pos} {self.gridpos}'

	def movetogrid(self, movegrid):
		x,y = movegrid
		if x > 100 or y > 100:
			logger.error(f'movetogrid error: x={x} y={y} pos={self.pos} gridpos={self.gridpos}')
			return
		self.gridpos[0] = x
		self.gridpos[1] = y
		if self.client.gamemap.grid[x][y] == 20:
			self.take_powerup(powertype=20, gridpos=self.gridpos)

	def move(self, direction):
		if self.ready:
			gpx = int(self.pos[0] // BLOCK)
			gpy = int(self.pos[1] // BLOCK)
			if gpx > 100 or gpy > 100:
				logger.error(f'move error: gpx={gpx} gpy={gpy} pos={self.pos} gridpos={self.gridpos}')
				return
			self.gridpos = [gpx, gpy]
			x = self.gridpos[0]
			y = self.gridpos[1]
			newgridpos = [x, y]
			if x > 100 or y > 100:
				logger.error(f'move error: gpx={gpx} gpy={gpy} pos={self.pos} gridpos={self.gridpos}')
				return
			# logger.debug(f'{self} move {direction} {self.gridpos}')
			if direction == 'up':
				if self.client.gamemap.grid[x][y-1] in [11,20]:
					newgridpos = [x, y-1]
				else:
					pass
					#logger.warning(f'cant move {direction} to [{x}, {y-1}] g:{self.client.gamemap.grid[x][y-1]}')
			elif direction == 'down':
				if self.client.gamemap.grid[x][y+1] in [11,20]:
					newgridpos = [x, y+1]
				else:
					pass
					#logger.warning(f'cant move {direction} to [{x}, {y+1}] g:{self.client.gamemap.grid[x][y+1]}')
			elif direction == 'left':
				if self.client.gamemap.grid[x-1][y] in [11,20]:
					newgridpos = [x-1, y]
				else:
					pass
					#logger.warning(f'cant move {direction}to [{x-1}, {y}] g:{self.client.gamemap.grid[x-1][y]}')
			elif direction == 'right':
				if self.client.gamemap.grid[x+1][y] in [11,20]:
					newgridpos = [x+1, y]
				else:
					pass
					# logger.warning(f'cant move {direction}to [{x+1}, {y}] g:{self.client.gamemap.grid[x+1][y]}')
			#self.movetogrid(newgridpos)
			self.gridpos = newgridpos
			self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
			#self.pos[1] = self.gridpos[1] * BLOCK
			self.rect.x = self.pos[0]
			self.rect.y = self.pos[1]
			self.client.pos = self.pos
			self.client.gridpos = self.gridpos
			self.setpos(pos=self.pos, gridpos=self.gridpos)

	def hit_list(self, objlist):
		hlist = []
		for obj in objlist:
			if obj.rect.colliderect(self.rect):
				hlist.append(obj)
		return hlist

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions

	def start_client(self):
		self.client.start()

	def update(self, blocks=None):
		self.rect.topleft = (self.pos[0]+5, self.pos[1]+5)
		# self.gridpos = (int(self.pos[0] // BLOCK), int(self.pos[1] // BLOCK))
		if self.gridpos[0] > 100 or self.gridpos[1] > 100:
			logger.error(f'{self} invalid gridpos {self.gridpos} pos={self.pos}')
			return
		for netplayer in self.client.netplayers:
			np = self.client.netplayers[netplayer]
			# todo fix this....
			if np['gridpos'][0] > 100 or np['gridpos'][1] > 100:
				# logger.error(f'netplayer={netplayer} np={np} invalid np gridpos {self.gridpos} pos={self.pos}')
				self.client.netplayers[netplayer]['gridpos'][0] = int(self.client.netplayers[netplayer]['pos'][0] // BLOCK)
				self.client.netplayers[netplayer]['gridpos'][1] = int(self.client.netplayers[netplayer]['pos'][1] // BLOCK)
				#logger.warning(f'netplayer={netplayer} np={np} fixed gridpos {self.gridpos} pos={self.pos} fixgp={self.client.netplayers[netplayer]["gridpos"]} p={self.client.netplayers[netplayer]["pos"]}')

		if self.client.gotpos and self.client.gotmap:
			self.gotmap = self.client.gotmap
			if not self.gotpos: # self.gridpos[0] == 0 or self.gridpos[1] == 0:
				logger.info(f'resetgridpos  client:{self.client} pos = {self.client.pos} {self.client.gridpos}')
				self.pos = self.client.pos
				self.gridpos = self.client.gridpos
				self.gotpos = True
				self.ready = True
		if self.connected:
			self.client.send_pos(pos=self.pos, center=self.pos, gridpos=self.gridpos)

	def take_powerup(self, powertype=None, gridpos=None):
		x = gridpos[0]
		y = gridpos[1]
		if powertype == 20:
			self.client.cl_hearts += 1
			self.client.cl_score += 10
			oldbrick = self.client.gamemap.grid[x][y]
			self.client.gamemap.grid[x][y] = 11
			logger.info(f'player {self.client_id} got heart at gridpos={gridpos} griditem={self.client.gamemap.grid[x][y]} ob={oldbrick} hearts={self.client.cl_hearts}')
			self.client.send_gridupdate(gridpos=(x,y), blktype=11, grid_data=self.client.gamemap.grid)

	def add_score(self):
		self.client.cl_score += 1

	def setpos(self, pos, gridpos):
		if gridpos[0] > 100 or gridpos[1] > 100:
			logger.error(f'{self} setpos {pos} {gridpos}')
		else:
			#ngx = int(pos[0]*BLOCK)
			#ngy = int(pos[1]*BLOCK)
			#newgridpos = (ngx,ngy)
			# logger.info(f'{self} setpos {self.pos} to {pos} gp={gridpos} ogp={self.gridpos} ngp={gridpos} client {self.client.pos} {self.client.gridpos}')
			self.pos = pos
			self.gridpos = gridpos
			self.client.pos = self.pos
			self.client.gridpos = self.gridpos
			self.gotpos = True
			self.client.gotpos = True
			self.ready = True
			self.client.send_pos(pos=self.pos, center=self.pos, gridpos=self.gridpos)
			#logger.info(f'{self} setposdone {self.pos}gp={self.gridpos} client {self.client.pos} {self.client.gridpos}')

class BombClient(Thread):
	def __init__(self, client_id=None, serveraddress=None, serverport=None, pos=None):
		Thread.__init__(self, daemon=False)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.client_id = client_id
		self.serveraddress = serveraddress
		self.serverport = serverport
		self.server = (self.serveraddress, self.serverport)
		self.kill = False
		self.connected = False
		self.pos = pos
		self.centerpos = pos
		self.gridpos = [0, 0]
		self.netplayers = {}
		self.gamemap = Gamemap()
		self.gotmap = False
		self.gotpos = False
		self.bombs_left = 3
		self.cl_score = 0
		self.cl_hearts = 3
		self.sendcnt = 0
		self.recvcnt = 0

	def __str__(self):
		return f'bc id={self.client_id} pos={self.pos} gp={self.gridpos} bombs:{self.bombs_left} sendrecv={self.sendcnt}/{self.recvcnt}'

	def req_mapreset(self):
		# request server map reset
		if self.connected and not self.kill:
			reqmsg = {'data_id': dataid['resetmap'], 'client_id': self.client_id, 'pos': self.pos, 'gridpos': self.gridpos}
			send_data(conn=self.socket, payload=reqmsg)
			self.sendcnt += 1

	def send_bomb(self, pos=None):
		# send bomb to server
		if self.connected and not self.kill:
			if self.bombs_left > 0:
				payload = {'data_id':dataid['netbomb'], 'msgtype': dataid['bombdrop'], 'client_id':self.client_id, 'bombpos':pos, 'bombs_left':self.bombs_left}
				send_data(conn=self.socket, payload=payload)
				self.sendcnt += 1
			# logger.debug(f'[ {self} ] send_bomb pos={payload.get("bombpos")}')

	def send_reqpos(self):
		# get initial position from server
		if self.connected and not self.kill:
			if self.gridpos[0] > 100 or self.gridpos[1] > 100:
				logger.error(f'{self} gridpos out of range {self.gridpos}')
				return
			reqmsg = {'data_id': dataid['reqpos'], 'client_id': self.client_id, 'payload': 'reqpos', 'pos':self.pos, 'gridpos':self.gridpos}
			send_data(conn=self.socket, payload=reqmsg)
			self.sendcnt += 1

	def send_mapreq(self):
		# request map from server
		if self.connected and not self.kill:
			if self.gridpos[0] > 100 or self.gridpos[1] > 100:
				logger.error(f'{self} gridpos out of range {self.gridpos}')
				return
			regmsg = {'client_id':self.client_id, 'payload':'reqmap', 'data_id':dataid['reqmap'], 'pos':self.pos, 'gridpos':self.gridpos}
			send_data(conn=self.socket,  payload=regmsg)
			logger.debug(f'[ {self} ] send_mapreq')
			self.sendcnt += 1
			# self.send_reqpos()

	def send_refreshgrid(self):
		# request map from server
		if self.connected and not self.kill:
			if self.gridpos[0] > 100 or self.gridpos[1] > 100:
				logger.error(f'{self} gridpos out of range {self.gridpos}')
				return
			regmsg = {'client_id':self.client_id, 'payload':'refreshsgrid', 'data_id':dataid['refreshsgrid'], 'pos':self.pos, 'gridpos':self.gridpos}
			send_data(conn=self.socket,  payload=regmsg)
			logger.debug(f'[ {self} ] refreshsgrid')
			self.sendcnt += 1
			# self.send_reqpos()

	def send_pos(self, pos=None, center=None, gridpos=None):
		# send pos to server
		if self.connected and not self.kill:
			# logger.debug(f'{self} send_pos pos={pos} center={center}')
			if self.gridpos[0] > 100 or self.gridpos[1] > 100 or gridpos[0] > 100 or gridpos[1] > 100:
				logger.error(f'{self} gridpos out of range {self.gridpos}')
				return
			self.pos = pos
			self.centerpos = center
			self.gridpos = gridpos
			posmsg = {'data_id': dataid['playerpos'], 'client_id': self.client_id, 'pos': (pos[0], pos[1]), 'centerpos':center, 'kill':int(self.kill), 'gridpos':self.gridpos}
			send_data(conn=self.socket, payload=posmsg)
			self.sendcnt += 1
			# logger.debug(f'send_pos {pos} {gridpos}')

	def send_clientid(self):
		# send pos to server
		if self.connected and not self.kill:
			if self.gridpos[0] > 100 or self.gridpos[1] > 100:
				logger.error(f'{self} gridpos out of range {self.gridpos}')
				return
			cmsg = {'data_id': dataid['info'], 'client_id': self.client_id, 'pos': self.pos, 'centerpos':self.centerpos, 'kill':int(self.kill), 'gridpos':self.gridpos}
			send_data(conn=self.socket, payload=cmsg)
			logger.info(f'[ {self} ] sending client_id ')
			self.sendcnt += 1

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None):
		# inform server about grid update
		# called after bomb explodes and kills block
		# gridpos=blk.gridpos, blktype=blk.block_type)
		# if not blktype:
		# 	logger.error(f'[ {self} ] missing blktype gp={gridpos} b={blktype} grid_data={grid_data}')
		# 	blktype = 0
		if self.connected and not self.kill:
			self.gamemap.grid[gridpos[0]][gridpos[1]] = blktype
			gridmsg = {'data_id': dataid['gridupdate'], 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos}
			send_data(conn=self.socket, payload=gridmsg)
			self.sendcnt += 1
			# logger.debug(f'[ {self} ] send_gridupdate {len(gridmsg)}')

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
			for np in self.netplayers:
				npgridpos = self.netplayers[np]['gridpos']
				if npgridpos[0] > 100 or npgridpos[1] > 100:
					logger.warning(f'{self} gridpos out of range ngp={npgridpos} np={np} {self.netplayers[np]}')
			if self.kill or self.socket._closed:
				logger.debug(F'{self} killed')
				self.kill = True
				self.connected = False
				break
			if self.connected:
				#if not self.gotmap:
				#	self.send_mapreq()
				msgid, payload = None, None
				payloads = []
				payloads = receive_data(conn=self.socket)
				# logger.debug(f'[ {self} ]  payload:{payload}')
				if payloads:
					for payload in payloads:
						self.recvcnt += 1
						msgid = payload.get('data_id')
						#logger.debug(f'[ {self} ] msgid:{msgid} payload:{payload}')
						# logger.debug(f'[ {self} ] payload:{payload}')
						if payload.get('msgtype') == 'bcgetid':
							if payload.get('payload') == 'sendclientid':
								# todo work on this....
								#self.send_clientid()
								pass
						elif payload.get('msgtype') == dataid['netplayers']:
							netplayers = None
							netplayers = payload.get('netplayers')
							if netplayers:
								#logger.debug(f'[ {self} ] netplayers {len(netplayers)} {netplayers}')
								# update netplayers
								for np in netplayers:
									npgridpos = netplayers[np].get('gridpos')
									if npgridpos[0] > 100 or npgridpos[1] > 100:
										logger.error(f'{self} gridpos out of range for np={np}')
									self.netplayers[np] = netplayers[np]
						elif payload.get('msgtype') == 'netgridupdate':
							# received gridupdate from server
							gridpos = payload.get('blkgridpos')
							blktype = payload.get('blktype')
							bclid = payload.get('bclid')
							# update local grid
							self.gamemap.grid[gridpos[0]][gridpos[1]] = blktype
							if not blktype:
								logger.error(f'missing blktype gp={gridpos} b={blktype} payload={payload} bclid={bclid}')
								blktype = 11
							elif bclid == self.client_id:
								pass
								#logger.warning(f'netgridupdate from self={self.client_id} gp={gridpos} b={blktype} bclid={bclid} payload={payload}')
							else:
								logger.debug(f'netgridupdate g={gridpos} b={blktype} bclid={bclid} client_id={self.client_id}')
								mapmsg = Event(USEREVENT, payload={'msgtype':'netgridupdate', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid})
								pygame.event.post(mapmsg)
								# send grid update to mainqueue
						elif payload.get('msgtype') == 'mapfromserver':
							# complete grid from server
							gamemapgrid = payload.get('gamemapgrid', None)
							newpos = payload.get('newpos', None)
							newgridpos = payload.get('newgridpos', None)
							if newgridpos[0] > 100 or newgridpos[1] > 100 or self.gridpos[0] > 100 or self.gridpos[1] > 100:
								logger.error(f'newgridpos={newgridpos} payload={payload}')
							else:
								mapmsg = Event(USEREVENT, payload={'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':gamemapgrid, 'pos':self.pos, 'newpos':newpos, 'newgridpos':newgridpos})
								pygame.event.post(mapmsg)
								logger.debug(f'[ {self} ] mapfromserver g={len(gamemapgrid)} newpos={newpos} {newgridpos}')
								self.gamemap.grid = gamemapgrid
								self.gotmap = True
								if not self.gotpos:
									self.gotpos = True
									self.pos = newpos
									self.gridpos = newgridpos
									self.send_pos(pos=self.pos, center=self.centerpos, gridpos=self.gridpos)


						elif payload.get('msgtype') == 'netbomb':
							# received bomb from server, forward to mainqueue
							# logger.debug(f'bombfromserver payload={payload}')
							bombmsg = Event(USEREVENT, payload={'msgtype':'netbomb', 'bombdata':payload, 'data_id':dataid['netbomb']})
							pygame.event.post(bombmsg)

						elif msgid == dataid['posupdate']:
							# received posupdate from server, forward to mainqueue
							logger.warning(f'[ {self} ] posupdate payload={payload}')
							posmsg = Event(USEREVENT, payload={'msgtype':'newnetpos', 'data_id':dataid['netpos'], 'posdata':payload, 'pos':self.pos})
							pygame.event.post(posmsg)

						elif payload.get('msgtype') == 'playerpos':
							# received playerpos from server, forward to mainqueue
							if not self.gotpos:
								newpos = payload.get('pos')
								newgridpos = payload.get('newgridpos')
								if newgridpos[0] > 100 or newgridpos[1] > 100 or self.gridpos[0] > 100 or self.gridpos[1] > 100:
									logger.error(f'newgridpos={newgridpos} payload={payload}')
								else:
									self.pos = newpos
									self.gotpos = True
									logger.info(f'playerpos newpos={newpos} ngp={newgridpos} ogp={self.gridpos} payload={payload}')
									self.gridpos = newgridpos
									# elif newgridpos is None:
									# 	ngx = int(newpos[0] // BLOCK)
									# 	ngy = int(newpos[1] // BLOCK)
									# 	self.gridpos = (ngx, ngy)
									# 	newgridpos = self.gridpos
									# 	logger.warning(f'[ {self} ] playerpos newpos={newpos} ngp={newgridpos} payload={payload}')
									#logger.debug(f'[ {self} ] playerpos newpos={newpos} ngp={newgridpos} payload={payload}')
									posmsg = Event(USEREVENT, payload={'msgtype':'newnetpos', 'data_id':dataid['netpos'], 'posdata':payload, 'pos':self.pos, 'newpos':newpos, 'newgridpos':self.gridpos})
									pygame.event.post(posmsg)
						else:
							logger.warning(f'[ {self} ] unknownpayload msgid={msgid} p={payload}')
			else:
				logger.warning(f'[ {self} ] not connected')
