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
from network import send_data, receive_data, Sender
from queue import SimpleQueue as Queue


class Player(BasicThing, Thread):
	def __init__(self, dummy=True, serverargs=None):
		Thread.__init__(self, daemon=True)
		super().__init__((0,0), (0,0))
		self.serverargs = serverargs
		self.serveraddress = self.serverargs.server
		self.serverport = self.serverargs.port
		self.server = (self.serveraddress, self.serverport)
		self.vel = Vector2(0, 0)
		self.pos = (0,0)
		self.gridpos = [0,0]
		self.size = PLAYERSIZE
		self.client_id = None #gen_randid()
		if not dummy:
			self.image = pygame.transform.scale(pygame.image.load('data/playerone.png').convert(), self.size)
			self.rect = pygame.Surface.get_rect(self.image, center=self.pos)
			self.surface = pygame.display.get_surface() # pygame.Surface(PLAYERSIZE)
			self.centerpos = (self.rect.center[0], self.rect.center[1])
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.receiver = Thread(target=self.receive_data, daemon=True)
			self.sender = Sender(client_id=self.client_id)# Thread(target=self.send_updates,daemon=True)
		if dummy:
			self.socket = None # socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.ready = False
		self.name = f'player{self.client_id}'
		self.connected = False
		self.kill = False
		self.speed = 3
		self.gotmap = False
		self.gotpos = False
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
		self.payloadqueue = Queue()
		self.cl_timer = 0
		self.status = 'idle'
		
	def __str__(self):
		return f'playerone={self.client_id} pos={self.pos} {self.gridpos} hearts={self.hearts} gotmap ={self.gotmap} gotpos={self.gotpos} ready={self.ready} '
	
	def draw(self, screen):
		pygame.Surface.blit(screen, self.image, self.rect)

	def flame_hit(self, flame):
		self.hearts -= 1

	def receive_data(self):
		while not self.kill:
			try:
				if self.connected:
					self.payloadqueue.put(receive_data(conn=self.socket))
					self.recvcnt += 1
			except Exception as e:
				logger.error(e)

	# def send_updates(self):
	# 	if self.connected:
	# 		#updates = []
	# 		if not self.eventqueue.empty():
	# 			#ev = self.eventqueue.get()
	# 			try:					
	# 				self.sender.queue.put((self.socket, self.eventqueue.get()))
	# 				#send_data(self.socket, self.eventqueue.get())
	# 				self.eventqueue.task_done()
	# 				self.sendcnt += 1
	# 			except Exception as e:
	# 				logger.error(f'error {e} eventq={self.eventqueue.qsize()} ')

	def send_bomb(self):
		# send bomb to server
		if self.bombs_left >= 0 and self.ready:
			bombpos = self.rect.center
			payload = {'msgtype': 'cl_bombdrop', 'client_id':self.client_id, 'bombpos':bombpos,'bombgridpos':self.gridpos, 'bombs_left':self.bombs_left, 'bombpower':self.bombpower}			
			#self.eventqueue.put(payload)
			self.sender.queue.put((self.socket, payload))
			logger.debug(f'send_bomb bombgridpos={payload.get("bombgridpos")} pos={payload.get("bombpos") } bombs_left={self.bombs_left}')

	def send_requestpos(self):
		# get initial position from server
		
		payload = {'msgtype': 'cl_reqpos', 'client_id': self.client_id, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		#self.eventqueue.put(payload)
		self.sender.queue.put((self.socket, payload))
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
		
		logger.debug(f'send_maprequest gridsize={gridsize} / p1gz={self.gamemap.gridsize}')
		payload = {'client_id':self.client_id, 'msgtype':'maprequest', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'gridsize':gridsize}
		self.sender.queue.put((self.socket, payload))
		#self.eventqueue.put(payload)
		
	def send_refreshgrid(self):
		# request map from server		
		payload = {'client_id':self.client_id, 'msgtype':'refreshsgrid', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos}
		#self.eventqueue.put(payload)
		self.sender.queue.put((self.socket, payload))

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None):
		# inform server about grid update
		# called after bomb explodes and kills block		
		self.gamemap.grid[gridpos[0]][gridpos[1]] = {'blktype':blktype, 'bomb':False}
		payload = {'msgtype':'cl_gridupdate', 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos}
		if self.ready:
			#self.eventqueue.put(payload)
			self.sender.queue.put((self.socket, payload))

	def set_clientid(self, clid):
		if not self.client_id:
			logger.info(f'set client_id to {clid} was {self.client_id}')
			self.client_id = clid
			self.sender.client_id = self.client_id
		else:
			logger.warning(f'dupe set client_id to {clid} was {self.client_id}')

	def disconnect(self):
		# send quitmsg to server
		
		payload = {'msgtype': 'clientquit', 'client_id': self.client_id, 'payload': 'quit'}
		logger.info(f'sending quitmsg payload={payload}')
		#self.eventqueue.put(payload)
		self.sender.queue.put((self.socket, payload))
		#send_data(conn=self.socket, payload=quitmsg)
		
		self.kill = True
		self.connected = False
		if self.socket:
			self.socket.close()

	def connect_to_server(self):
		if self.connected:
			logger.warning(f'{self} already connected')			
			return self.connected
		else:
			try:
				self.socket.connect(self.server)
			except Exception as e:
				logger.error(f'{self} connect_to_server err:{e}')
				self.connected = False
				self.ready = False
				self.gotmap = False
				self.gotpos = False				
				return self.connected
		self.connected = True
		logger.debug(f'{self} connect_to_server {self.server} sending maprequest')
		return self.connected

	def move(self, direction):
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
			self.gridpos = newgridpos
			self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
			self.rect.x = self.pos[0]
			self.rect.y = self.pos[1]
			#send_data(self.socket, payload)


	def handle_payloadq(self, payloads):
		if not payloads:
			return
		for payload in payloads:
			self.payloadcnt += 1
			msgtype = payload.get('msgtype')
			if msgtype == 'bcsetclid':
				clid = payload.get('client_id')
				self.set_clientid(clid)
			if msgtype == 's_netplayers':
				# logger.debug(f'netplayers payload={payload}')
				netplayers = payload.get('netplayers', None)
				if netplayers:
					self.netplayers = netplayers
			if msgtype == 's_ping':
				#logger.debug(f'{self} s_ping payload={payload}')
				bchtimer = payload.get('bchtimer')			
				#logger.debug(f's_ping payload={payload} bchtimer={bchtimer} cl_timer={self.cl_timer} sendq={self.sender.queue.qsize()}')
				clpongpayload = {
					'msgtype': 'cl_pong',
					'client_id': self.client_id,
					'cl_timer': self.cl_timer,
					}
				if self.ready:
					self.sender.queue.put((self.socket, clpongpayload))
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
					pygame.event.post(Event(USEREVENT, payload={'msgtype':'c_ngu', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid}))
					# send grid update to mainqueue
				
			if msgtype == 'bc_netbomb':
				# received bomb from server, forward to mainqueue
				# logger.debug(f'bombfromserver payload={payload}')
				pygame.event.post(Event(USEREVENT, payload={'msgtype':'netbomb', 'bombdata':payload}))				
				#pygame.event.post(bombmsg)

			if msgtype == 'posupdate':
				# received posupdate from server, forward to mainqueue
				logger.info(f'posupdate payload={payload}')
				pygame.event.post(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos}))				
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
				pygame.event.post(Event(USEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':newpos, 'newgridpos':self.gridpos,'griddata':self.gamemap.grid}))
				
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
				pygame.event.post(Event(USEREVENT, payload={'msgtype':'s_gamemapgrid', 'client_id':self.client_id, 'grid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'newgridpos':self.gridpos}))
				logger.debug(f's_grid g={len(self.gamemap.grid)} newpos={self.pos} {self.gridpos} p1={self}')

	def send_pos(self):
		pospayload = {
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
			'cl_timer': self.cl_timer,
			}
		if self.ready:
			self.sender.queue.put((self.socket, pospayload))
			# logger.debug(f'sending {pospayload.get("msgtype")} sendq={self.sender.queue.qsize()} ')

	def run(self):
		#conn = self.connect_to_server()
		self.receiver.start()	
		self.sender.start()
		logger.debug(f'{self} receiver = {self.receiver} sender = {self.sender}')
		# if not self.gotmap:
		self.send_maprequest(gridsize=15)
		# 	time.sleep(3)
		while not self.kill:			
			if not self.connected or self.kill:				
				logger.debug(F'{self} killed')
				self.kill = True
				self.connected = False
				break
			if not self.payloadqueue.empty():
				self.handle_payloadq(self.payloadqueue.get())
