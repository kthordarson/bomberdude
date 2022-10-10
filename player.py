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
from queue import Queue, Empty

class get_netpayloads():
	def __init__(self, conn):
		self.conn = conn
		self.payloads = []

	def get_payloads(self):
		try:
			self.payloads = receive_data(self.conn)
		except Exception:
			pass
		return self.payloads

class Player(BasicThing, Thread):
	def __init__(self):
		Thread.__init__(self, daemon=False)
		super().__init__((0,0), (0,0))
		self.vel = Vector2(0, 0)
		self.pos = (0,0)
		self.gridpos = [0,0]
		#self.image = pygame.image.load('data/playerone.png')
		self.size = PLAYERSIZE
		self.image = pygame.transform.scale(pygame.image.load('data/playerone.png').convert(), self.size)
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
		self.bombpower = round(BLOCK * 1.5)
		self.score = 0
		self.hearts = 3
		self.sendcnt = 0
		self.recvcnt = 0
		self.mapreqcnt = 0
		self.eventqueue = Queue()
		self.np= {
			'src':'client',
			'client_id':self.client_id, 
			'pos':self.pos, 
			'kill':self.kill, 
			'gridpos':self.gridpos, 
			'hearts':self.hearts, 
			'score':self.score,
			'bombpower':self.bombpower,
			'events':[]}


	def __str__(self):
		return f'playerone={self.client_id} pos={self.pos} {self.gridpos} hearts={self.hearts} gotmap ={self.gotmap} gotpos={self.gotpos} ready={self.ready}'

	def flame_hit(self, flame):
		self.hearts -= 1

	def send_update(self):
		updates = []
		try:
			updates = self.eventqueue.get()
		except Empty:
			pass
		for update in updates:
			# logger.info(f'sending update {update}')
			send_data(self.socket, update)
			try:
				self.eventqueue.task_done()
			except ValueError as e:
				logger.error(f'ValueError {e} updates={len(updates)} update={update}')

	def send_bomb(self):
		# send bomb to server
		if self.bombs_left > 0 and self.ready:
			self.gamemap.grid[self.gridpos[0]][self.gridpos[1]] = 11
			bombpos = self.rect.center
			payload = {'msgtype': 'bombdrop', 'client_id':self.client_id, 'bombpos':bombpos,'bombgridpos':self.gridpos, 'bombs_left':self.bombs_left, 'bombpower':self.bombpower}		
			self.eventqueue.put([payload])
			# send_data(conn=self.socket, payload=payload)
			# self.sendcnt += 1
			logger.debug(f'send_bomb bombgridpos={payload.get("bombgridpos")} pos={payload.get("bombpos")}')

	def send_request_clid(self):
		if not self.client_id:
			msgtype = 'requestclid'
			payload = {'msgtype': msgtype, 'client_id': self.client_id, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
			self.eventqueue.put([payload])
			#send_data(conn=self.socket, payload=reqmsg)
			logger.debug(f'sending {msgtype} payload={payload}')
			self.sendcnt += 1
		else:
			logger.warning(f'client_id already set {self.client_id}')

	def send_requestpos(self):
		# get initial position from server
		msgtype = 'reqpos'
		payload = {'client_id': self.client_id, 'payload': msgtype, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		self.eventqueue.put([payload])
		if not self.gotpos:
			logger.debug(f'sending {msgtype} payload={payload}')
			#send_data(conn=self.socket, payload=reqmsg)
			#self.sendcnt += 1
		else:
			logger.warning(f'{msgtype} already gotpos={self.gotpos} pos={self.pos} {self.gridpos}')

	def send_mapreset(self, gridsize):
		# request server map reset
		msgtype = 'resetmap'
		payload = {'msgtype': msgtype, 'client_id': self.client_id, 'pos': self.pos, 'gridpos': self.gridpos, 'gridsize': gridsize}
		self.eventqueue.put([payload])
		logger.debug(f'sending {msgtype} payload={payload}')
		#send_data(conn=self.socket, payload=reqmsg)
		#self.sendcnt += 1

	def send_maprequest(self, gridsize):
		# request map from server
		if not gridsize:
			logger.error(f'gridsize not set')
			return
		payload = {'client_id':self.client_id, 'msgtype':'maprequest', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'gridsize':gridsize}
		self.eventqueue.put([payload])
		#logger.info(f'mapreqcnt={self.mapreqcnt} gotmap={self.gotmap} gridsize={gridsize} payload={reqmsg}')
		#send_data(conn=self.socket,  payload=reqmsg)
		#self.mapreqcnt += 1
			# logger.debug(f'{self} sending maprequest:{self.mapreqcnt} payload={reqmsg}')
			# if self.mapreqcnt >= 3:
			# 	time.sleep(int(self.mapreqcnt//10))

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
		# 			logger.debug(f'{self.mapreqcnt} pl={len(payloads)} not map response payload={payload}')
		# 			time.sleep(1)
		# 			#time.sleep(0.1)
		# 			#send_data(conn=self.socket,  payload=regmsg)
		# 			# self.send_maprequest()

	def send_refreshgrid(self):
		# request map from server
		payload = {'client_id':self.client_id, 'msgtype':'refreshsgrid', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		self.eventqueue.put([payload])
		#send_data(conn=self.socket,  payload=regmsg)
		#logger.debug(f'refreshsgrid payload={regmsg}')
		#self.sendcnt += 1
		# self.send_requestpos()

	def send_pos(self):
		# send pos to server

		payload = {
			'msgtype': 'playerpos', 
			'client_id': self.client_id, 
			'pos': self.pos, 
			'kill':self.kill, 'gridpos':self.gridpos, 
			'gotmap':self.gotmap,
			'gotpos':self.gotpos,
			'score':self.score,
			'bombs_left':self.bombs_left,
			'hearts':self.hearts,
			'bombpower':self.bombpower,
			}
		if self.ready:
			self.eventqueue.put([payload])
			#send_data(conn=self.socket, payload=posmsg)

	def set_clientid(self, clid):
		if not self.client_id:
			logger.info(f'set client_id to {clid} was {self.client_id}')
			self.client_id = clid
		else:
			logger.warning(f'dupe set client_id to {clid} was {self.client_id}')

	def send_clientid(self):
		pass
		# self.send_pos()

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None):
		# inform server about grid update
		# called after bomb explodes and kills block
		self.gamemap.grid[gridpos[0]][gridpos[1]] = blktype
		payload = {'msgtype':'gridupdate', 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos}
		self.eventqueue.put([payload])
		#send_data(conn=self.socket, payload=gridmsg)
		#self.sendcnt += 1

	def disconnect(self):
		# send quitmsg to server
		payload = {'msgtype': 'clientquit', 'client_id': self.client_id, 'payload': 'quit'}
		logger.info(f'sending quitmsg payload={payload}')
		self.eventqueue.put([payload])
		#send_data(conn=self.socket, payload=quitmsg)
		self.kill = True
		self.connected = False
		self.socket.close()

	def connect_to_server(self):
		if not self.connected:
			try:
				self.socket.connect(self.server)
			except Exception as e:
				logger.error(f'[ {self} ] connect_to_server err:{e}')
				self.connected = False
				return False
			self.connected = True
		logger.debug(f'[ {self} ] connect_to_server {self.server}')
		return True

	def movetogrid(self, movegrid):
		if self.ready:
			x,y = movegrid
			self.gridpos[0] = x
			self.gridpos[1] = y
			#if self.gamemap.grid[x][y] >= 20:
			#	self.take_powerup(powertype=self.gamemap.grid[x][y], gridpos=self.gridpos)

	def move(self, direction):
		if self.ready and self.gotmap and self.gotpos:
			gpx = round(self.pos[0] // BLOCK)
			gpy = round(self.pos[1] // BLOCK)
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
			self.send_pos()

	def hit_list(self, objlist):
		hlist = []
		for obj in objlist:
			if obj.rect.colliderect(self.rect):
				hlist.append(obj)
		return hlist

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions

	def update(self, blocks=None):
		# self.gridpos = (self.pos[0] // BLOCK, self.pos[1] // BLOCK)
		#self.rect.topleft = (self.pos[0], self.pos[1])
		# self.gridpos = (round(self.pos[0] // BLOCK), round(self.pos[1] // BLOCK))
		if self.connected:
			self.send_pos()

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

	def setposx(self, pos, gridpos):
		self.pos = pos
		self.gridpos = gridpos
		self.gotpos = True
		# logger.info(f'{self} setposdone {self.pos}gp={self.gridpos} client {self.pos} {self.gridpos}')

	def handle_payloadq(self, payloads):
		eventq = []
		for payload in payloads:
			self.recvcnt += 1
			if payload.get('msgtype') == 'bcsetclid':
				clid = payload.get('client_id')
				self.set_clientid(clid)
			elif payload.get('msgtype') == 'netplayers':
				# logger.debug(f'netplayers payload={payload}')
				netplayers = payload.get('netplayers', None)
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

			elif payload.get('msgtype') == 'posfromserver':
				# received playerpos from server, forward to mainqueue
				if self.gotpos:
					logger.warning(f'{self} playerpos gotpos already set payload={payload}')
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
			elif payload.get('msgtype') == 'mapfromserver':
				# complete grid from server
				self.gamemap.grid = payload.get('gamemapgrid', None)
				if not self.gamemap.grid:
					logger.warning(f'no grid from server payload={payload}')
					return
				self.pos = payload.get('newpos', None)
				self.gridpos = payload.get('newgridpos', None)
				self.rect.x = self.pos[0]
				self.rect.y = self.pos[1]
				self.gotmap = True
				self.gotpos = True
				self.ready = True
				#eventq.append(Event(USEREVENT, payload={'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'newgridpos':self.gridpos}))
				pygame.event.post(Event(USEREVENT, payload={'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'newgridpos':self.gridpos}))
				logger.debug(f'[ {self} ] mapfromserver g={len(self.gamemap.grid)} newpos={self.pos} {self.gridpos}')

			else:
				logger.warning(f'[ {self} ] unknownpayload p={payload}')
		return eventq


	def run(self):
		self.connect_to_server()
		self.send_request_clid()
		self.send_maprequest(gridsize=15)
		payloads = []
		#rcvr = Thread(target=get_netpayloads, args=(self.socket,), daemon=True)
		#rcvr.start()
		while not self.kill:
			if self.kill or self.socket._closed or not self.connected:
				logger.debug(F'{self} killed')
				self.kill = True
				self.connected = False
				break			
			if not self.client_id:
				#logger.warning(f'{self} no client_id')
				self.send_request_clid()
			if not self.gotmap:
				#logger.warning(f'{self} no map')
				#self.send_maprequest()
				pass
			if not self.ready:
				pass
				#logger.warning(f'{self} not ready')				
			if not self.gotpos:
				logger.warning(f'{self} no pos')				
			
			# logger.debug(f'[ {self} ]  payload:{payload}')
			self.send_update()
			try:
				payloads = receive_data(conn=self.socket)
				#payloads = rcvr.get_payloads()
			except Exception:
				pass
			if payloads:
				eventq = self.handle_payloadq(payloads)
				for event in eventq:
					logger.debug(f'{len(eventq)} events in eventq event={event.type}')
					pygame.event.post(event)



