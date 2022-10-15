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
		Thread.__init__(self, daemon=True)
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
		self.client_id = None #gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		#self.rect = self.surface.get_rect() #pygame.Rect((self.pos[0], self.pos[1], PLAYERSIZE[0], PLAYERSIZE[1])) #self.image.get_rect()
		self.centerpos = (self.rect.center[0], self.rect.center[1])
		self.speed = 3
		self.gotmap = False
		self.gotpos = False
		self.socket = None # socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
		self.updates = []

	def __str__(self):
		return f'playerone={self.client_id} pos={self.pos} {self.gridpos} hearts={self.hearts} gotmap ={self.gotmap} gotpos={self.gotpos} ready={self.ready} eq={self.eventqueue.qsize()}'

	def flame_hit(self, flame):
		self.hearts -= 1

	def receive_data(self):
		while not self.kill:
			payloads = []
			try:
				payloads.append(receive_data(conn=self.socket))
				#payloads = rcvr.get_payloads()
			except Exception as e:
				logger.error(e)
			if payloads:
				# logger.info(f'payloads={len(payloads)}')
				if len(payloads) >= 5:
					logger.warning(f'[P] payloads={len(payloads)} eventq={self.eventqueue.qsize()}')
				for p in payloads:
					if p:
						# logger.info(f'payload={p}')
						for event in self.handle_payloadq(p):
							# logger.debug(f'payloads={len(payloads)}/{len(p)} events in eventq event={event.type} eventq={self.eventqueue.qsize()}')
							pygame.event.post(event)

	def send_updates(self):
		while not self.kill:
			#updates = []
			while not self.eventqueue.empty():
				ev = self.eventqueue.get()
				self.updates.append(ev)
				self.eventqueue.task_done()
			if self.eventqueue.qsize() >= 10:
				logger.warning(f'[EQ] self.updates={len(self.updates)} eventq={self.eventqueue.qsize()}')				
			if len(self.updates) >= 10:
				logger.warning(f'[U] self.updates={len(self.updates)} eventq={self.eventqueue.qsize()}')
			for update in self.updates:
				# logger.info(f'updates={len(self.updates)} eventq={self.eventqueue.qsize()} sending update {update}')
				try:
					send_data(self.socket, update)
				except Exception as e:
					logger.error(f'error {e} eventq={self.eventqueue.qsize()} self.updates={len(self.updates)} update={update}')
					break
			self.updates = []

	def update(self, blocks=None):
		# self.gridpos = (self.pos[0] // BLOCK, self.pos[1] // BLOCK)
		#self.rect.topleft = (self.pos[0], self.pos[1])
		# self.gridpos = (round(self.pos[0] // BLOCK), round(self.pos[1] // BLOCK))
		payload = {
			'msgtype': 'cl_playerpos', 
			'client_id': self.client_id, 
			'pos': self.pos, 
			'kill':self.kill, 
			'gridpos':self.gridpos, 
			'gotmap':self.gotmap,
			'gotpos':self.gotpos,
			'score':self.score,
			'bombs_left':self.bombs_left,
			'hearts':self.hearts,
			'bombpower':self.bombpower,
			'eventqueue':self.eventqueue.qsize(),
			}
		if self.ready:
			self.eventqueue.put(payload)

	def send_bomb(self):
		# send bomb to server
		if self.bombs_left > 0 and self.ready:
			bombpos = self.rect.center
			payload = {'msgtype': 'bombdrop', 'client_id':self.client_id, 'bombpos':bombpos,'bombgridpos':self.gridpos, 'bombs_left':self.bombs_left, 'bombpower':self.bombpower}		
			self.eventqueue.put(payload)
			logger.debug(f'send_bomb bombgridpos={payload.get("bombgridpos")} pos={payload.get("bombpos")}')

	def send_requestpos(self):
		# get initial position from server
		payload = {'msgtype': 'cl_reqpos', 'client_id': self.client_id, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		self.eventqueue.put(payload)
		if not self.gotpos:
			logger.debug(f'sending cl_reqpos payload={payload}')
			#send_data(conn=self.socket, payload=reqmsg)
			#self.sendcnt += 1
		else:
			logger.warning(f'cl_reqpos already gotpos={self.gotpos} pos={self.pos} {self.gridpos}')

	def send_mapreset(self, gridsize):
		# request server map reset
		payload = {'msgtype': 'resetmap', 'client_id': self.client_id, 'pos': self.pos, 'gridpos': self.gridpos, 'gridsize': gridsize}
		self.eventqueue.put(payload)
		logger.debug(f'sending resetmap payload={payload}')
		#send_data(conn=self.socket, payload=reqmsg)
		#self.sendcnt += 1

	def send_maprequest(self, gridsize):
		# request map from server
		if not gridsize:
			logger.error(f'gridsize not set')
			return
		payload = {'client_id':self.client_id, 'msgtype':'maprequest', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'gridsize':gridsize}
		self.eventqueue.put(payload)

	def send_refreshgrid(self):
		# request map from server
		payload = {'client_id':self.client_id, 'msgtype':'refreshsgrid', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		self.eventqueue.put(payload)

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None):
		# inform server about grid update
		# called after bomb explodes and kills block
		self.gamemap.grid[gridpos[0]][gridpos[1]] = blktype
		payload = {'msgtype':'gridupdate', 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos}
		self.eventqueue.put(payload)

	def set_clientid(self, clid):
		if not self.client_id:
			logger.info(f'set client_id to {clid} was {self.client_id}')
			self.client_id = clid
		else:
			logger.warning(f'dupe set client_id to {clid} was {self.client_id}')


	def disconnect(self):
		# send quitmsg to server
		payload = {'msgtype': 'clientquit', 'client_id': self.client_id, 'payload': 'quit'}
		logger.info(f'sending quitmsg payload={payload}')
		self.eventqueue.put(payload)
		#send_data(conn=self.socket, payload=quitmsg)
		self.kill = True
		self.connected = False
		self.socket.close()

	def connect_to_server(self):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		if not self.connected:
			try:
				self.socket.connect(self.server)
			except Exception as e:
				logger.error(f'[ {self} ] connect_to_server err:{e}')
				self.connected = False
				return False
			self.connected = True
		logger.debug(f'[ {self} ] connect_to_server {self.server}')
		self.send_maprequest(gridsize=15)
		time.sleep(3)
		return True

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

	def hit_list(self, objlist):
		hlist = []
		for obj in objlist:
			if obj.rect.colliderect(self.rect):
				hlist.append(obj)
		return hlist

	def collide(self, items=None):
		self.collisions = spritecollide(self, items, False)
		return self.collisions


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

	def handle_payloadq(self, payloads):
		eventq = []
		if not payloads:
			logger.warning(f'{self} no payloads')
			return eventq
		else:
			for payload in payloads:
				# logger.info(f'{len(payloads)} payload={payload}')
				self.recvcnt += 1
				if payload.get('msgtype') == 'bcsetclid':
					clid = payload.get('client_id')
					self.set_clientid(clid)
				elif payload.get('msgtype') == 'netplayers':
					# logger.debug(f'netplayers payload={payload}')
					netplayers = payload.get('netplayers', None)
					if netplayers:
						self.netplayers = netplayers
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
					else:
						logger.debug(f'netgridupdate g={gridpos} b={blktype} bclid={bclid} client_id={self.client_id}')
						eventq.append(Event(USEREVENT, payload={'msgtype':'netgridupdate', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid}))
						# send grid update to mainqueue
				elif payload.get('msgtype') == 'netbomb':
					# received bomb from server, forward to mainqueue
					# logger.debug(f'bombfromserver payload={payload}')
					eventq.append(Event(USEREVENT, payload={'msgtype':'netbomb', 'bombdata':payload}))
					#pygame.event.post(bombmsg)

				elif payload.get('msgtype') == 'posupdate':
					# received posupdate from server, forward to mainqueue
					logger.info(f'posupdate payload={payload}')
					eventq.append(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos}))
					#pygame.event.post(posmsg)

				elif payload.get('msgtype') == 'posfromserver':
					# received playerpos from server, forward to mainqueue
					newpos = payload.get('pos')
					newgridpos = payload.get('newgridpos')
					self.gamemap.grid = payload.get('griddata')
					self.pos = newpos
					self.gotpos = True
					self.rect.x = self.pos[0]
					self.rect.y = self.pos[1]
					self.gridpos = newgridpos
					eventq.append(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':newpos, 'newgridpos':self.gridpos,'griddata':self.gamemap.grid}))
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
		conn = self.connect_to_server()
		logger.debug(f'connected = {conn}')
		payloads = []
		recvr = Thread(target=self.receive_data, daemon=True)
		recvr.start()
		logger.debug(f'receiver = {recvr}')
		st = Thread(target=self.send_updates,daemon=True)
		st.start()
		logger.debug(f'sender = {st}')
		logger.debug(f'receiver = {recvr} sender = {st}')
		while not self.kill:
			if self.kill or self.socket._closed or not self.connected:
				logger.debug(F'{self} killed')
				self.kill = True
				self.connected = False
				break			
			# if not self.gotmap:
			# 	logger.warning(f'{self} no map')
			# 	#self.send_maprequest()
			# 	# time.sleep(0.1)
			# 	#pass
			# if not self.ready:
			# 	#pass
			# 	logger.warning(f'{self} not ready')				
			# 	# time.sleep(0.1)
			# if not self.gotpos:
			# 	logger.warning(f'{self} no pos')				
				# time.sleep(0.1)
			
			# logger.debug(f'[ {self} ]  payload:{payload}')



