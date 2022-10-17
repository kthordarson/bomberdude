import asyncio
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


class Player(BasicThing, Thread):
	def __init__(self, dummy=True, serverargs=None):
		Thread.__init__(self, daemon=True)
		super().__init__((0,0), (0,0))
		self.serverargs = serverargs
		self.serveraddress = self.serverargs.server
		self.serverport = self.serverargs.port
		self.server = (self.serveraddress, self.serverport)
		#print(self.serverargs)
		self.vel = Vector2(0, 0)
		self.pos = (0,0)
		self.gridpos = [0,0]
		#self.image = pygame.image.load('data/playerone.png')
		self.size = PLAYERSIZE
		if not dummy:
			self.image = pygame.transform.scale(pygame.image.load('data/playerone.png').convert(), self.size)
			self.rect = pygame.Surface.get_rect(self.image, center=self.pos)
			self.surface = pygame.display.get_surface() # pygame.Surface(PLAYERSIZE)
			self.centerpos = (self.rect.center[0], self.rect.center[1])
		#self.rect = self.surface.fill(color=(90,90,90))
		# BasicThing.__init__(self, pos, self.image)
		self.ready = False
		self.client_id = None #gen_randid()
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		#self.rect = self.surface.get_rect() #pygame.Rect((self.pos[0], self.pos[1], PLAYERSIZE[0], PLAYERSIZE[1])) #self.image.get_rect()
		self.speed = 3
		self.gotmap = False
		self.gotpos = False
		self.socket = None # socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.netplayers = {}
		self.gamemap = Gamemap()
		self.bombs_left = 3
		self.bombpower = round(BLOCK * 1.5)
		self.score = 0
		self.hearts = 3
		# counters
		self.rcnt = 0
		self.sendcnt = 0
		self.recvcnt = 0
		self.payloadcnt = 0
		self.mapreqcnt = 0

		self.eventqueue = Queue()
		self.updates = []
		self.cl_timer = pygame.time.get_ticks()-self.start_time
		self.status = 'idle'

	def __str__(self):
		return f'playerone={self.client_id} pos={self.pos} {self.gridpos} hearts={self.hearts} gotmap ={self.gotmap} gotpos={self.gotpos} ready={self.ready} eq={self.eventqueue.qsize()}'

	def flame_hit(self, flame):
		self.hearts -= 1

	def receive_data(self):
		while not self.kill:
			payloads = []
			try:
				payloads.append(receive_data(conn=self.socket))
				self.recvcnt += 1
				#payloads = rcvr.get_payloads()
			except Exception as e:
				logger.error(e)
			if payloads:
				if len(payloads) >= 2:
					logger.info(f'payloads={len(payloads)}')
				if len(payloads) >= 5:
					logger.warning(f'[P] payloads={len(payloads)} eventq={self.eventqueue.qsize()}')
				for p in payloads:
					if p:
						# logger.info(f'payload={p}')
						# self.status = f'recvdata payloads={len(payloads)} eventq={self.eventqueue.qsize()}'
						events = self.handle_payloadq(p)
						# self.status = f'recvdata payloads={len(payloads)} events={len(events)} eventq={self.eventqueue.qsize()}'
						for event in events:
							# logger.debug(f'payloads={len(payloads)}/{len(p)} events in eventq event={event.type} eventq={self.eventqueue.qsize()}')
							# self.status = f'postevent payloads={len(payloads)} events={len(events)} eventq={self.eventqueue.qsize()}'
							pygame.event.post(event)

	def send_updates(self):
		while self.connected:
			#updates = []
			while not self.eventqueue.empty():
				ev = self.eventqueue.get()
				self.updates.append(ev)
				# self.status = f'send_update eventq={self.eventqueue.qsize()} self.updates={len(self.updates)}'
				self.eventqueue.task_done()
			if self.eventqueue.qsize() >= 5:
				logger.warning(f'[EQ] self.updates={len(self.updates)} eventq={self.eventqueue.qsize()}')
			if len(self.updates) >= 5:
				logger.warning(f'[U] self.updates={len(self.updates)} eventq={self.eventqueue.qsize()}')
			for update in self.updates:
				# logger.info(f'updates={len(self.updates)} eventq={self.eventqueue.qsize()} sending update {update}')
				try:
					# self.status = f'send_updates={len(self.updates)} eventq={self.eventqueue.qsize()}'
					send_data(self.socket, update)
					self.sendcnt += 1
				except Exception as e:
					logger.error(f'error {e} eventq={self.eventqueue.qsize()} self.updates={len(self.updates)} update={update}')
					break
			## self.status = f'send_update r={self.rcnt} scount={self.sendcnt} rcount={self.recvcnt} pcnt={self.payloadcnt} updates={len(self.updates)} eventq={self.eventqueue.qsize()}'
			self.updates = []

	async def update(self, blocks=None):
		# self.gridpos = (self.pos[0] // BLOCK, self.pos[1] // BLOCK)
		#self.rect.topleft = (self.pos[0], self.pos[1])
		# self.gridpos = (round(self.pos[0] // BLOCK), round(self.pos[1] // BLOCK))
		self.cl_timer = pygame.time.get_ticks()-self.start_time
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
			'cl_timer': self.cl_timer,
			'cl_status': self.status,
			}
		if self.ready:
			self.eventqueue.put_nowait(payload)
			## self.status = f'update r={self.rcnt} sc={self.sendcnt} rc={self.recvcnt} pcnt={self.payloadcnt} u={len(self.updates)} eq={self.eventqueue.qsize()}'
		else:
			pass
			# self.status = f'update not ready r={self.rcnt} sc={self.sendcnt} rc={self.recvcnt} pcnt={self.payloadcnt} u={len(self.updates)} eq={self.eventqueue.qsize()}'

	def send_bomb(self):
		# send bomb to server
		if self.bombs_left <= 0:
			return
		if self.bombs_left > 0 and self.ready:
			bombpos = self.rect.center
			payload = {'msgtype': 'cl_bombdrop', 'client_id':self.client_id, 'bombpos':bombpos,'bombgridpos':self.gridpos, 'bombs_left':self.bombs_left, 'bombpower':self.bombpower}
			# self.status = f'sendbomb eventq={self.eventqueue.qsize()}'
			self.eventqueue.put_nowait(payload)
			logger.debug(f'send_bomb bombgridpos={payload.get("bombgridpos")} pos={payload.get("bombpos")}')

	def send_requestpos(self):
		# get initial position from server
		# self.status = f'cl_reqpos eventq={self.eventqueue.qsize()}'
		payload = {'msgtype': 'cl_reqpos', 'client_id': self.client_id, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		self.eventqueue.put_nowait(payload)
		if not self.gotpos:
			logger.debug(f'sending cl_reqpos payload={payload}')
		else:
			logger.warning(f'cl_reqpos already gotpos={self.gotpos} pos={self.pos} {self.gridpos}')

	def send_maprequest(self, gridsize):
		if not self.connected:
			logger.error(f'{self} not connected')
			return
		# request map from server
		if not gridsize:
			logger.error(f'gridsize not set')
			return
		# self.status = f'send_maprequest gz={gridsize} connected={self.connected} eventq={self.eventqueue.qsize()}'
		logger.debug(f'{self} send_maprequest gridsize={gridsize} / p1gz={self.gamemap.gridsize}')
		payload = {'client_id':self.client_id, 'msgtype':'maprequest', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'gridsize':gridsize}
		self.eventqueue.put_nowait(payload)
		# self.status = f'maprequest waiting for response gz={gridsize} connected={self.connected} eventq={self.eventqueue.qsize()}'


	def send_refreshgrid(self):
		# request map from server
		# self.status = f'sending refreshgrid connected={self.connected} eventq={self.eventqueue.qsize()}'
		payload = {'client_id':self.client_id, 'msgtype':'refreshsgrid', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		self.eventqueue.put_nowait(payload)

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None):
		# inform server about grid update
		# called after bomb explodes and kills block
		# self.status = f'sending gridupdate connected={self.connected} eventq={self.eventqueue.qsize()}'
		self.gamemap.grid[gridpos[0]][gridpos[1]] = {'blktype':blktype, 'bomb':False}
		payload = {'msgtype':'cl_gridupdate', 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos}
		self.eventqueue.put_nowait(payload)

	def set_clientid(self, clid):
		if not self.client_id:
			logger.info(f'set client_id to {clid} was {self.client_id}')
			self.client_id = clid
		else:
			logger.warning(f'dupe set client_id to {clid} was {self.client_id}')


	def disconnect(self):
		# send quitmsg to server
		# self.status = 'disconnecting'
		payload = {'msgtype': 'clientquit', 'client_id': self.client_id, 'payload': 'quit'}
		logger.info(f'sending quitmsg payload={payload}')
		self.eventqueue.put_nowait(payload)
		#send_data(conn=self.socket, payload=quitmsg)
		# self.status = 'disconnected'
		self.kill = True
		self.connected = False
		if self.socket:
			self.socket.close()

	def connect_to_server(self):
		# self.status = f'connecting'
		if self.connected:
			logger.warning(f'{self} already connected')
			# self.status = f'connected={self.connected}'
			return self.connected
		elif not self.connected:
			try:
				self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.socket.connect(self.server)
				self.connected = True
				logger.debug(f'{self} connect_to_server {self.server} sending maprequest')
				# self.status = f'connected'
				return self.connected
			except Exception as e:
				logger.error(f'{self} connect_to_server err:{e}')
				self.connected = False
				self.ready = False
				self.gotmap = False
				self.gotpos = False
				# self.status = f'connection error={e} {self}'
				return self.connected


	def move(self, direction):
		# self.status = f'moving {direction} eventq={self.eventqueue.qsize()}'
		if self.ready and self.gotmap and self.gotpos:
			gpx = round(self.pos[0] // BLOCK)
			gpy = round(self.pos[1] // BLOCK)
			self.gridpos = [gpx, gpy]
			x = self.gridpos[0]
			y = self.gridpos[1]
			newgridpos = [x, y]
			# logger.debug(f'{self} move {direction} {self.gridpos}')
			# = {'blktype':blktype, 'bomb':False}
			if direction == 'up':
				if self.gamemap.grid[x][y-1].get('blktype') > 10:
					newgridpos = [x, y-1]
				else:
					pass
					#logger.warning(f'cant move {direction} to {newgridpos} g:{self.gamemap.grid[x][y-1]}')
			elif direction == 'down':
				if self.gamemap.grid[x][y+1].get('blktype') > 10:
					newgridpos = [x, y+1]
				else:
					pass
					#logger.warning(f'cant move {direction} to [{x}, {y+1}] g:{self.gamemap.grid[x][y+1]}')
			elif direction == 'left':
				if self.gamemap.grid[x-1][y].get('blktype') > 10:
					newgridpos = [x-1, y]
				else:
					pass
					#logger.warning(f'cant move {direction}to [{x-1}, {y}] g:{self.gamemap.grid[x-1][y]}')
			elif direction == 'right':
				if self.gamemap.grid[x+1][y].get('blktype') > 10:
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

	def handle_payloadq(self, payloads):
		eventq = []
		# self.status = f'handle_payloadq eventq={self.eventqueue.qsize()} eq={len(eventq)} p={len(payloads)}'
		if not payloads:
			logger.warning(f'{self} no payloads')
			return eventq
		else:
			for payload in payloads:
				# self.status = f'handle_payloadq eventq={self.eventqueue.qsize()} eq={len(eventq)} p={len(payloads)}'
				self.payloadcnt += 1
				msgtype = payload.get('msgtype')
				if msgtype == 'bcsetclid':
					clid = payload.get('client_id')
					self.set_clientid(clid)
				if msgtype == 'netplayers':
					# logger.debug(f'netplayers payload={payload}')
					netplayers = payload.get('netplayers', None)
					if netplayers:
						self.netplayers = netplayers
						# self.status = f'handle_payloadq netplayers={len(self.netplayers)} eventq={self.eventqueue.qsize()} eq={len(eventq)} p={len(payloads)}'
				if msgtype == 's_netgridupdate':
					# received gridupdate from server
					gridpos = payload.get('blkgridpos')
					blktype = payload.get("blktype")
					bclid = payload.get('bclid')
					# update local grid
					self.gamemap.grid[gridpos[0]][gridpos[1]] = {'blktype':blktype, 'bomb':False}
					if not blktype:
						logger.error(f'missing blktype gp={gridpos} b={blktype} payload={payload} bclid={bclid}')
						return
					else:
						logger.debug(f'{msgtype} g={gridpos} b={blktype} bclid={bclid} client_id={self.client_id}')
						eventq.append(Event(USEREVENT, payload={'msgtype':'c_ngu', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid}))
						# send grid update to mainqueue
					# self.status = f'handle_payloadq eq={len(eventq)} payloads={len(payloads)} payload={payload} self.recvcnt={self.recvcnt} eventq={self.eventqueue.qsize()}'
				if msgtype == 'bc_netbomb':
					# received bomb from server, forward to mainqueue
					# logger.debug(f'bombfromserver payload={payload}')
					eventq.append(Event(USEREVENT, payload={'msgtype':'netbomb', 'bombdata':payload}))
					# self.status = f'handle_payloadq eq={len(eventq)} payloads={len(payloads)} payload={payload} self.recvcnt={self.recvcnt} eventq={self.eventqueue.qsize()}'
					#pygame.event.post(bombmsg)

				if msgtype == 'posupdate':
					# received posupdate from server, forward to mainqueue
					logger.info(f'posupdate payload={payload}')
					eventq.append(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos}))
					# self.status = f'handle_payloadq eq={len(eventq)} payloads={len(payloads)} payload={payload} self.recvcnt={self.recvcnt} eventq={self.eventqueue.qsize()}'
					#pygame.event.post(posmsg)

				if msgtype == 's_pos':
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
					# self.status = f'handle_payloadq payloads={len(payloads)} payload={payload} self.recvcnt={self.recvcnt} eventq={self.eventqueue.qsize()}'
				if msgtype == 's_grid':
					# complete grid from server
					grid = payload.get('gamemapgrid', None)
					if not grid:
						logger.warning(f'no grid from server payload={payload}')
						return
					self.gamemap.grid = grid
					self.pos = payload.get('newpos', None)
					self.gridpos = payload.get('newgridpos', None)
					self.rect.x = self.pos[0]
					self.rect.y = self.pos[1]
					self.gotmap = True
					self.gotpos = True
					self.ready = True
					#eventq.append(Event(USEREVENT, payload={'msgtype':'gamemapgrid', 'client_id':self.client_id, 'gamemapgrid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'newgridpos':self.gridpos}))
					pygame.event.post(Event(USEREVENT, payload={'msgtype':'s_gamemapgrid', 'client_id':self.client_id, 'grid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'newgridpos':self.gridpos}))
					# self.status = f'handle_payloadq msgtype={msgtype} payloads={len(payloads)} payload={payload} self.recvcnt={self.recvcnt} eventq={self.eventqueue.qsize()}'
					logger.debug(f's_grid g={len(self.gamemap.grid)} newpos={self.pos} {self.gridpos}')
			# self.status = f'handle_payloadq sending eventq={len(eventq)}'
			return eventq


	def run(self):
		# self.status = 'run'
		conn = self.connect_to_server()
		if not conn:
			self.kill = True
			return
		# self.status = f'run conn={conn} eventq={self.eventqueue.qsize()}'

		recvr = Thread(target=self.receive_data, daemon=True)
		recvr.start()
		# self.status = f'run conn={conn} r={recvr} eventq={self.eventqueue.qsize()}'

		st = Thread(target=self.send_updates,daemon=True)
		st.start()
		logger.debug(f'receiver = {recvr} sender = {st}')
		while not self.gotmap:
			# self.status = f'sending maprequest gotmap={self.gotmap} ready={self.ready} eventq={self.eventqueue.qsize()}'
			self.send_maprequest(gridsize=15)
			# self.status = f'maprequest sent gotmap={self.gotmap} ready={self.ready} eventq={self.eventqueue.qsize()}'
			time.sleep(6)
		while not self.kill:
			if self.ready and self.gotmap and self.gotpos:
				## self.status = f'run r={self.rcnt} sc={self.sendcnt} rc={self.recvcnt} pcnt={self.payloadcnt} u={len(self.updates)} rq={self.eventqueue.qsize()}'
				self.rcnt += 1
			else:
				pass
				# self.status = f'notready r={self.rcnt} sc={self.sendcnt} rc={self.recvcnt} pcnt={self.payloadcnt} u={len(self.updates)} rq={self.eventqueue.qsize()}'
			if self.kill or self.socket._closed or not self.connected:
				logger.debug(F'{self} killed')
				# self.status = 'killed'
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

			# logger.debug(f'{self}  payload:{payload}')



