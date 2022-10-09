import time
import pygame
from pygame import USEREVENT
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import spritecollide
from globals import BasicThing
from loguru import logger
from globals import gen_randid
from threading import Thread
from constants import *
import socket
from map import Gamemap
from network import send_data, receive_data

class Player(BasicThing, Thread):
	def __init__(self):
		Thread.__init__(self, daemon=True)
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
		self.client_id = None# gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		#self.rect = self.surface.get_rect() #pygame.Rect((self.pos[0], self.pos[1], PLAYERSIZE[0], PLAYERSIZE[1])) #self.image.get_rect()
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.speed = 3
		self.gotmap = False
		self.gotpos = False
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.serveraddress = 'localhost'
		self.serverport = 9696
		self.server = (self.serveraddress, self.serverport)
		self.netplayers = {}
		self.gamemap = Gamemap()
		self.bombs_left = 3
		self.bombpower = 10
		self.score = 0
		self.hearts = 3
		self.sendcnt = 0
		self.recvcnt = 0
		self.mapreqcnt = 0

	def __str__(self):
		return f'player {self.client_id} pos={self.pos} {self.gridpos} heats={self.hearts}'

	def flame_hit(self, flame):
		self.hearts -= 1

	def send_bomb(self):
		# send bomb to server
		if self.bombs_left > 0:
			self.gamemap.grid[self.gridpos[0]][self.gridpos[1]] = 11
			bombpos = self.rect.center			
			payload = {'msgtype': 'bombdrop', 'client_id':self.client_id, 'bombpos':bombpos,'bombgridpos':self.gridpos, 'bombs_left':self.bombs_left, 'bombpower':self.bombpower}
			send_data(conn=self.socket, payload=payload)
			self.sendcnt += 1
			logger.debug(f'send_bomb bombgridpos={payload.get("bombgridpos")} pos={payload.get("bombpos")}')
	# if self.playerone.bombs_left > 0:
	# 	candrop = True
	# 	for bomb in self.bombs:
	# 		logger.info(f'bomb={bomb} bombgridpos={self.playerone.gridpos}')
	# 		bgpos = (bomb.gridpos[0], bomb.gridpos[1])
	# 		ngbpos = (self.playerone.gridpos[0], self.playerone.gridpos[1])
	# 		if bgpos == ngbpos:
	# 			logger.warning(f'bomb={bomb} already exists at {self.playerone.gridpos}')
	# 			candrop = False

	def send_requestpos(self):
		# get initial position from server
		reqmsg = {'client_id': self.client_id, 'payload': 'reqpos', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		send_data(conn=self.socket, payload=reqmsg)
		self.sendcnt += 1

	def send_mapreset(self):
		# request server map reset
		reqmsg = {'msgtype': 'resetmap', 'client_id': self.client_id, 'pos': self.pos, 'gridpos': self.gridpos}
		send_data(conn=self.socket, payload=reqmsg)
		self.sendcnt += 1

	def send_maprequest(self):
		# request map from server
		regmsg = {'client_id':self.client_id, 'msgtype':'maprequest', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		send_data(conn=self.socket,  payload=regmsg)
		self.mapreqcnt += 1
		# payloads = None
		# payloads = receive_data(conn=self.socket)
		# if payloads:
		# 	# logger.debug(f'[ {self} ] send_maprequest payloads={len(payloads)}')
		# 	for payload in payloads:
		# 		if payload.get('msgtype') == 'mapfromserver':
		# 			# complete grid from server
		# 			gamemapgrid = payload.get('gamemapgrid', None)
		# 			newpos = payload.get('newpos', None)
		# 			newgridpos = payload.get('newgridpos', None)
		# 			pygame.event.post(Event(USEREVENT, payload={'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':gamemapgrid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':newpos, 'newgridpos':newgridpos}))
		# 			#pygame.event.post(mapmsg)
		# 			logger.debug(f'{self.mapreqcnt} mapfromserver g={len(gamemapgrid)} newpos={newpos} {newgridpos}')
		# 			self.gamemap.grid = gamemapgrid
		# 			self.gotmap = True
		# 			self.gotpos = True
		# 			self.pos = newpos
		# 			self.gridpos = newgridpos
		# 			self.sendcnt += 1
		# 		else:
		# 			pygame.event.clear()
		# 			logger.debug(f'{self.mapreqcnt} not map response payload={payload}')
		# 			#time.sleep(0.1)
		# 			#send_data(conn=self.socket,  payload=regmsg)
		# 			# self.send_maprequest()

	def send_refreshgrid(self):
		# request map from server
		regmsg = {'client_id':self.client_id, 'msgtype':'refreshsgrid', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		send_data(conn=self.socket,  payload=regmsg)
		logger.debug(f'[ {self} ] refreshsgrid')
		self.sendcnt += 1
		# self.send_requestpos()

	def send_pos(self, pos=None, center=None, gridpos=None):
		# send pos to server
		if self.gotpos:
			# logger.debug(f'{self} send_pos pos={pos} center={center}')
			posmsg = {'msgtype': 'playerpos', 'client_id': self.client_id, 'pos': self.pos, 'centerpos':self.centerpos, 'kill':self.kill, 'gridpos':self.gridpos, 'gotmap':self.gotmap,'gotpos':self.gotpos}
			send_data(conn=self.socket, payload=posmsg)
			self.sendcnt += 1
			# logger.debug(f'send_pos {pos} {gridpos}')

	def set_clientid(self, clid):
		self.client_id = clid
		cmsg = {'msgtype': 'info', 'client_id': self.client_id, 'pos': self.pos, 'centerpos':self.centerpos, 'kill':self.kill, 'gridpos':self.gridpos, 'gotmap':self.gotmap,'gotpos':self.gotpos}
		send_data(conn=self.socket, payload=cmsg)
		logger.info(f'[ {self} ] sending client_id ')
		self.sendcnt += 1

	def send_clientid(self):
		# send pos to server
		cmsg = {'msgtype': 'info', 'client_id': self.client_id, 'pos': self.pos, 'centerpos':self.centerpos, 'kill':self.kill, 'gridpos':self.gridpos, 'gotmap':self.gotmap,'gotpos':self.gotpos}
		send_data(conn=self.socket, payload=cmsg)
		logger.info(f'[ {self} ] sending client_id ')
		self.sendcnt += 1

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None):
		# inform server about grid update
		# called after bomb explodes and kills block
		self.gamemap.grid[gridpos[0]][gridpos[1]] = blktype
		gridmsg = {'msgtype':'gridupdate', 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos}
		send_data(conn=self.socket, payload=gridmsg)
		self.sendcnt += 1
		# logger.debug(f'[ {self} ] send_gridupdate {len(gridmsg)}')

	def disconnect(self):
		# send quitmsg to server
		quitmsg = {'msgtype': 'clientquit', 'client_id': self.client_id, 'payload': 'quit'}
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

	def movetogrid(self, movegrid):
		if self.ready:
			x,y = movegrid
			self.gridpos[0] = x
			self.gridpos[1] = y
			if self.gamemap.grid[x][y] >= 20:
				self.take_powerup(powertype=self.gamemap.grid[x][y], gridpos=self.gridpos)

	def move(self, direction):
		if self.ready and self.gotmap and self.gotpos:
			gpx = int(self.pos[0] // BLOCK)
			gpy = int(self.pos[1] // BLOCK)
			self.gridpos = [gpx, gpy]
			x = self.gridpos[0]
			y = self.gridpos[1]
			newgridpos = [x, y]
			# logger.debug(f'{self} move {direction} {self.gridpos}')
			if direction == 'up':
				if self.gamemap.grid[x][y-1] > 10:
					newgridpos = [x, y-1]
				else:
					pass
					#logger.warning(f'cant move {direction} to {newgridpos} g:{self.gamemap.grid[x][y-1]}')
			elif direction == 'down':
				if self.gamemap.grid[x][y+1] > 10:
					newgridpos = [x, y+1]
				else:
					pass
					#logger.warning(f'cant move {direction} to [{x}, {y+1}] g:{self.gamemap.grid[x][y+1]}')
			elif direction == 'left':
				if self.gamemap.grid[x-1][y] > 10:
					newgridpos = [x-1, y]
				else:
					pass
					#logger.warning(f'cant move {direction}to [{x-1}, {y}] g:{self.gamemap.grid[x-1][y]}')
			elif direction == 'right':
				if self.gamemap.grid[x+1][y] > 10:
					newgridpos = [x+1, y]
				else:
					pass
					# logger.warning(f'cant move {direction}to [{x+1}, {y}] g:{self.gamemap.grid[x+1][y]}')
			#self.movetogrid(newgridpos)
			self.gridpos = newgridpos
			self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
			#self.pos[1] = self.gridpos[1] * BLOCK
			self.rect.x = self.pos[0]
			self.rect.y = self.pos[1]
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

	# def update(self, blocks=None):
	# 	self.gridpos = (self.pos[0] // BLOCK, self.pos[1] // BLOCK)
	# 	#self.rect.topleft = (self.pos[0], self.pos[1])
	# 	# self.gridpos = (int(self.pos[0] // BLOCK), int(self.pos[1] // BLOCK))
	# 	for netplayer in self.netplayers:
	# 		np = self.netplayers[netplayer]
	# 	if self.connected:
	# 		self.send_pos()

	def take_powerup(self, powertype=None, gridpos=None):
		x,y = gridpos
		if powertype == 20:
			self.hearts += 1
			self.score += 2
			self.gamemap.grid[x][y] = 11
		elif powertype == 21:
			self.bombs_left += 1
			self.gamemap.grid[x][y] = 11
		logger.info(f'player {self.client_id} got extrabomb at gridpos={gridpos} griditem={self.gamemap.grid[x][y]} hearts={self.hearts} bombsleft={self.bombs_left}')
		self.send_gridupdate(gridpos=(x,y), blktype=11, grid_data=self.gamemap.grid)

	def add_score(self):
		self.score += 1

	def setpos(self, pos, gridpos):
		self.pos = pos
		self.gridpos = gridpos
		self.gotpos = True
		# logger.info(f'{self} setposdone {self.pos}gp={self.gridpos} client {self.pos} {self.gridpos}')
		self.send_pos()

	def get_payloadq(self, payloads):
		eventq = []
		for payload in payloads:
			self.recvcnt += 1
			#logger.debug(f'[ {self} ] msgid:{msgid} payload:{payload}')
			# logger.debug(f'[ {self} ] payload:{payload}')
			if payload.get('msgtype') == 'bcgetid':
				if payload.get('payload') == 'sendclientid':
					# todo work on this....
					self.send_clientid()
					#pass
			if payload.get('msgtype') == 'bcsetclid':
				clid = payload.get('client_id')
				self.set_clientid(clid)
			elif payload.get('msgtype') == 'netplayers':
				netplayers = None
				netplayers = payload.get('netplayers')
				if netplayers:
					self.netplayers = netplayers
					# #logger.debug(f'[ {self} ] netplayers {len(netplayers)} {netplayers}')
					# # update netplayers
					# for np in netplayers:
					# 	npgridpos = netplayers[np].get('gridpos')
					# 	self.netplayers[np] = netplayers[np]
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
					eventq.append(Event(USEREVENT, payload={'msgtype':'netgridupdate', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid}))
					#pygame.event.post(mapmsg)
					# send grid update to mainqueue
			elif payload.get('msgtype') == 'mapfromserver':
				# complete grid from server
				self.gamemap.grid = payload.get('gamemapgrid', None)
				self.pos = payload.get('newpos', None)
				self.gridpos = payload.get('newgridpos', None)
				self.gotmap = True
				self.ready = True
				self.gotpos = True
				eventq.append(Event(USEREVENT, payload={'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'newgridpos':self.gridpos}))
				#pygame.event.post(mapmsg)
				logger.debug(f'[ {self} ] mapfromserver g={len(self.gamemap.grid)} newpos={self.pos} {self.gridpos}')

			elif payload.get('msgtype') == 'netbomb':
				# received bomb from server, forward to mainqueue
				# logger.debug(f'bombfromserver payload={payload}')
				eventq.append(Event(USEREVENT, payload={'msgtype':'netbomb', 'bombdata':payload}))
				#pygame.event.post(bombmsg)

			elif payload.get('msgtype') == 'posupdate':
				# received posupdate from server, forward to mainqueue
				logger.warning(f'[ {self} ] posupdate payload={payload}')
				eventq.append(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos}))
				#pygame.event.post(posmsg)

			elif payload.get('msgtype') == 'playerpos':
				# received playerpos from server, forward to mainqueue
				if not self.gotpos:
					newpos = payload.get('pos')
					newgridpos = payload.get('newgridpos')
					self.pos = newpos
					self.gotpos = True
					self.rect.x = self.pos[0]
					self.rect.y = self.pos[1]
					logger.info(f'playerpos newpos={newpos} ngp={newgridpos} ogp={self.gridpos} payload={payload}')
					self.gridpos = newgridpos
					eventq.append(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':newpos, 'newgridpos':self.gridpos}))
					#pygame.event.post(posmsg)
			else:
				logger.warning(f'[ {self} ] unknownpayload p={payload}')
		return eventq


	def run(self):
		self.ready = True
		while not self.kill:
			for np in self.netplayers:
				npgridpos = self.netplayers[np]['gridpos']
			if self.kill or self.socket._closed:
				logger.debug(F'{self} killed')
				self.kill = True
				self.connected = False
				break
			if self.connected:
				self.send_pos()
				msgid, payload = None, None
				payloads = []
				payloads = receive_data(conn=self.socket)
				# logger.debug(f'[ {self} ]  payload:{payload}')
				if payloads:
					eventq = self.get_payloadq(payloads)
					for event in eventq:
						logger.debug(f'{len(eventq)} events in eventq event={event.type}')
						pygame.event.post(event)
			else:
				logger.warning(f'[ {self} ] not connected')

