import socket
from threading import Thread
from queue import SimpleQueue as Queue
import json
import pygame
from loguru import logger
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import spritecollide

from constants import BLOCK, PLAYEREVENT, PLAYERSIZE
from globals import BasicThing, gen_randid, BlockNotFoundError
from map import Gamemap
from network import Sender, receive_data, send_data, Receiver

class NewPlayer(Thread):
	def __init__(self, serveraddress='127.0.0.1'):
		Thread.__init__(self, daemon=True)
		self.client_id = 'newplayer1'
		self.kill = False
		self.connected = False
		self.serveraddress = serveraddress
		self.qm = Thread(target=self.queue_monitor, daemon=True)
		self.queue = Queue()
		self.pos = [0,0]
		self.gridpos = [0,0]
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sender = Sender(client_id=self.client_id, s_type=f'snp:{self.client_id}', socket=self.socket)
		# sender thread, put data in client sender queue and sender thread sends data to client
		# self.receiver = Thread(target=self.receive_data, daemon=True)
		self.receiver = Receiver(socket=self.socket, client_id=self.client_id, s_type=f'rnp:{self.client_id}')
		# receiver thread, receives data from server and puts data in receiver queue

	def __repr__(self) -> str:
		return f'NewPlayer(pos:{self.pos})'

	def run(self):
		while not self.kill:
			payload = None
			if self.kill:
				logger.warning(f'{self} killed')
				break
			while not self.receiver.queue.empty():
				payload = self.receiver.queue.get()
				if payload:
					# logger.debug(f'{self} payload:{payload}')
					self.handle_payloadq(payload)


	def handle_payloadq(self, payloads):
		if not payloads:
			return
		for idx,payload in enumerate(payloads):
			if len(payload) == 0:
				# logger.warning(f'{idx}/{len(payloads)} payload empty {len(payload)} {type(payload)} : {payload}')
				# logger.warning(f'payloads:\n\n{payloads}\n\n')
				continue
			if len(payload) == 1:
				# logger.warning(f'{idx}/{len(payloads)} payload {len(payload)} {type(payload)} : {payload}')
				# logger.warning(f'payloads:\n\n{payloads}\n\n')
				continue
			try:
				msgtype = payload.get('msgtype')
				in_pktid = payload.get('pktid')
			except AttributeError as e:
				logger.error(f'{idx}/{len(payloads)}  {e} payload: {type(payload)} {payload}')
				logger.error(f'payloads:\n\n{payloads}\n\n')
				break
			if msgtype == 'bcsetclid':
				logger.debug(f'{idx}/{len(payloads)}  bcsetclid payload={payload}')
				# clid = payload.get('client_id')
				# self.set_clientid(clid)
			if msgtype == 's_netplayers':
				# logger.debug(f'netplayers payload={payload}')
				netplayers = payload.get('netplayers', None)
				# if netplayers:
				# 	self.netplayers = netplayers
			if msgtype == 'olds_ping':
				#logger.debug(f'{self} s_ping payload={payload}')
				pass
				# bchtimer = payload.get('bchtimer')
				# pktid = payload.get('pktid')
				# #logger.debug(f's_ping payload={payload} bchtimer={bchtimer} cl_timer={self.cl_timer} sendq={self.sender.queue.qsize()}')
				# clpongpayload = {
				# 	'msgtype': 'cl_pong',
				# 	'client_id': self.client_id,
				# 	'cl_timer': self.cl_timer,
				# 	'in_pktid': pktid,
				# 	'c_pktid': gen_randid(),
				# 	}
				# if self.ready:
				# 	self.sender.queue.put((self.socket, clpongpayload))
			if msgtype == 's_netgridupdate':
				# received gridupdate from server
				gridpos = payload.get('blkgridpos')
				blktype = payload.get("blktype")
				bclid = payload.get('bclid')
				# update local grid
				# self.gamemap.grid[gridpos[0]][gridpos[1]] = {'blktype':blktype, 'bomb':False}
				# logger.debug(f'{msgtype} g={gridpos} b={blktype} bclid={bclid} client_id={self.client_id}')
				# pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'c_ngu', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid}))
				# send grid update to bdude

			if msgtype == 'bc_netbomb':
				# received bomb from server
				# if payload.get('client_id') == self.client_id:
				# 	self.bombs_left -= 1
				# pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'bc_netbomb', 'bombdata':payload}))
				logger.info(f'{idx}/{len(payloads)}  {msgtype} payload={payload}')

			if msgtype == 's_posupdate':
				# received posupdate from server
				logger.info(f'posupdate payload={payload}')
				# pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos}))
				#pygame.event.post(posmsg)

			if msgtype == 's_pos':
				# received playerpos from server
				self.pos = payload.get('pos')
				self.rect.x = self.pos[0]
				self.rect.y = self.pos[1]
				self.gridpos = payload.get('gridpos')
				self.gamemap.grid = payload.get('grid')
				self.gotpos = True
				self.gotmap = True
				# pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'gridpos':self.gridpos, 'grid':self.gamemap.grid}))

			if msgtype == 's_grid':
				# complete grid from server
				self.gamemap.grid = payload.get('grid')
				self.gridpos = payload.get('gridpos')
				self.pos = payload.get('pos')
				self.rect.x = self.pos[0]
				self.rect.y = self.pos[1]
				self.gotmap = True
				self.gotpos = True
				self.ready = True
				# pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'s_gamemapgrid', 'client_id':self.client_id, 'grid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'gridpos':self.gridpos}))
				logger.debug(f'{idx}/{len(payloads)}  s_grid g={len(self.gamemap.grid)} newpos={self.pos} {self.gridpos} p1={self}')

	def connect(self):
		attemtps = 0
		try:
			self.socket.connect((self.serveraddress, 9696))
		except ConnectionRefusedError as e:
			logger.error(f'{self} {e}')
			return False
		while not self.connected:
			attemtps += 1
			logger.debug(f'attemtps: {attemtps}')
			if attemtps >= 10:
				logger.warning(f'attemtps: {attemtps}')
				return False
			payload = {'msgtype' : 'cl_newplayer', 'client_id': self.client_id, 'c_pktid': gen_randid(), 'attempts': attemtps}
			data = json.dumps(payload).encode('utf-8')
			self.socket.send(data)
			rawdata_sock = None
			logger.debug(f'sent: {payload}')
			try:
				rawdata_sock = self.socket.recv(256).decode('utf-8')
			except Exception as e:
				logger.error(f'{e} {type(e)}')
				return False
			if rawdata_sock:
				# logger.debug(f'rawdata_sock: {rawdata_sock}')
				try:
					data = json.loads(rawdata_sock)
					logger.debug(f'data: {data}')
				except json.decoder.JSONDecodeError as e:
					logger.error(f'{e}')
					logger.error(f'rawdata: {rawdata_sock}')
					data = {'msgtype': 'jsondecodeerror', 'rawdata': rawdata_sock}
				if data.get('msgtype') == 's_ping':
					logger.debug(f's_ping: {rawdata_sock}')
				elif data.get('msgtype') == 'bcsetclid':
					logger.debug(f'bcsetclid: data: {data} raw: {rawdata_sock}')
					self.client_id = data.get('client_id')
					self.sender.start()
					self.receiver.start()
					self.connected = True
					logger.debug(f'bcsetclid connected s:{self.sender} r:{self.receiver} rawdata: {rawdata_sock}')
					return True
				elif data.get('msgtype') == 'jsondecodeerror':
					pass
				elif data.get('msgtype') == 'msgokack':
					self.client_id = data.get('client_id')
					self.sender.client_id = self.client_id
					self.receiver.client_id = self.client_id
					self.sender.start()
					self.receiver.start()
					self.connected = True
					logger.debug(f'clidmsgokack: {self.client_id} s:{self.sender} r:{self.receiver} rawdata: {rawdata_sock}')
					return True
				else:
					logger.warning(f'raw: {rawdata_sock} {type(rawdata_sock)}\n{data}')

	def queue_monitor(self):
		payload = None
		while not self.kill:
			try:
				payload = self.queue.get()
				if payload:
					logger.debug(f'{self} payload: {payload}')
			except (TypeError, AttributeError) as e:
				logger.error(f'[prd] {e} {type(e)} ')
			except Exception as e:
				logger.error(f'[prd] unhandled {e} {type(e)}')

	def move(self, action):
		gpx, gpy = self.gridpos
		newgridpos = [gpx, gpy]
		if action == 'u':
			newgridpos = [gpx, gpy-1]
		elif action == 'd':
			newgridpos = [gpx, gpy+1]
		elif action == 'l':
			newgridpos = [gpx-1, gpy]
		elif action == 'r':
			newgridpos = [gpx+1, gpy]
		self.gridpos = newgridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		payload = {'msgtype' : 'cl_playermove', 'client_id': self.client_id, 'c_pktid': gen_randid(), 'pos': self.pos, 'gridpos': self.gridpos, 'action': action}
		data = json.dumps(payload).encode('utf-8')
		self.socket.send(data)

	def send_cl_message(self, clmsgtype, payload):
		if not self.connected:
			logger.warning(f'{self} not conncted')
			return
		if self.client_id == 'newplayer1':
			logger.warning(f'{self} need client_id from server!')
			return
		elif self.connected and self.client_id != 'newplayer1':
			pospayload = {
				'msgtype': clmsgtype,
				'client_id': self.client_id,
				'payload': payload,
				}
			self.sender.queue.put((self.socket, pospayload))

	def sendpos(self):
		if not self.connected:
			logger.warning(f'{self} not conncted')
			return
		if self.client_id == 'newplayer1':
			logger.warning(f'{self} need client_id from server!')
			return
		elif self.connected and self.client_id != 'newplayer1':
			pospayload = {
				'msgtype': 'cl_playerpos',
				'client_id': self.client_id,
				'pos': self.pos,
				}
			self.sender.queue.put((self.socket, pospayload))

class Player(BasicThing, Thread):
	def __init__(self, serverargs):
		Thread.__init__(self, daemon=True)
		self.pos = (0,0)
		self.gridpos = [0,0]
		super().__init__(gridpos=self.gridpos, image=None)
		self.serverargs = serverargs
		self.serveraddress = self.serverargs.server
		self.serverport = self.serverargs.port
		self.server = (self.serveraddress, self.serverport)
		self.vel = Vector2(0, 0)
		self.size = PLAYERSIZE
		self.client_id = None #gen_randid()
		self.image = pygame.transform.scale(pygame.image.load('data/playerone.png').convert(), self.size)
		self.rect = pygame.Surface.get_rect(self.image)
		self.surface = pygame.display.get_surface() # pygame.Surface(PLAYERSIZE)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.oldreceiver = Thread(target=self.oldreceive_data, daemon=True)
		self.sender = Sender(client_id=self.client_id, s_type='player')# Thread(target=self.send_updates,daemon=True)
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
		self.payloadcnt = 0
		self.mapreqcnt = 0
		self.cl_timer = 0
		self.status = 'idle'

	def __repr__(self):
		return f'playerone={self.client_id} pos={self.pos} {self.gridpos} hearts={self.hearts} gotmap ={self.gotmap} gotpos={self.gotpos} ready={self.ready} '

	def draw(self, screen):
		pygame.Surface.blit(screen, self.image, self.rect)

	def flame_hit(self, flame):
		self.hearts -= 1

	def oldreceive_data(self):
		while not self.kill:
			try:
				if self.connected:
					payloads = receive_data(conn=self.socket)
					if payloads:
						self.oldhandle_payloadq(payloads)
						self.payloadcnt += len(payloads)
					else:
						logger.warning(f'[prd] nopayload payloadcnt:{self.payloadcnt}')
			except (TypeError, AttributeError) as e:
				logger.error(f'[prd] {e} {type(e)} payloadcnt:{self.payloadcnt} ')
			except Exception as e:
				logger.error(f'[prd] unhandled {e} {type(e)}')


	def send_bomb(self):
		# send bomb to server
		# self.gamemap.grid[bx][by] = {'blktype':11, 'bomb':True}
		bombpos = self.rect.center
		bx,by = self.gridpos
		if self.bombs_left >= 0 and not self.gamemap.grid[bx][by].get('bomb'):
			self.gamemap.grid[bx][by] = {'blktype':11, 'bomb':True}
			payload = {'msgtype': 'cl_bombdrop', 'client_id':self.client_id, 'bombpos':bombpos,'bombgridpos':self.gridpos, 'bombs_left':self.bombs_left, 'bombpower':self.bombpower, 'c_pktid': gen_randid()}
			self.sender.queue.put((self.socket, payload))
			logger.debug(f'{self} send_bomb bombgridpos={payload.get("bombgridpos")} pos={payload.get("bombpos") } bombs_left={self.bombs_left} gridbomb={self.gamemap.grid[bx][by].get("bomb")} sender: {self.sender}')
		elif self.gamemap.grid[bx][by].get('bomb'):
			logger.warning(f'bomb on gridspot {bx},{by} sgb={self.gamemap.grid[bx][by].get("bomb")}')

	def send_requestpos(self):
		# get initial position from server
		payload = {'msgtype': 'cl_reqpos', 'client_id': self.client_id, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'c_pktid': gen_randid()}
		self.sender.queue.put((self.socket, payload))
		if not self.gotpos:
			logger.debug(f'sending cl_reqpos payload={payload}')
		else:
			logger.warning(f'cl_reqpos already gotpos={self.gotpos} pos={self.pos} {self.gridpos}')

	def send_maprequest(self, gridsize):
		# request map from server
		logger.debug(f'send_maprequest gridsize={gridsize} / p1gz={self.gamemap.gridsize}')
		payload = {'client_id':self.client_id, 'msgtype':'maprequest', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'gridsize':gridsize, 'c_pktid': gen_randid()}
		self.sender.queue.put((self.socket, payload))

	def send_refreshgrid(self):
		# request map from server
		payload = {'client_id':self.client_id, 'msgtype':'refreshsgrid', 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'gridpos':self.gridpos, 'c_pktid': gen_randid()}
		self.sender.queue.put((self.socket, payload))

	def send_gridupdate(self, gridpos=None, blktype=None, grid_data=None, bomb=False):
		# inform server about grid update
		# called after bomb explodes and kills block
		self.gamemap.grid[gridpos[0]][gridpos[1]] = {'blktype':blktype, 'bomb':False}
		payload = {'msgtype':'cl_gridupdate', 'client_id': self.client_id, 'blkgridpos': gridpos, 'blktype': blktype, 'pos': self.pos, 'griddata':grid_data, 'gridpos':self.gridpos, 'c_pktid': gen_randid()}
		if self.ready:

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

		payload = {'msgtype': 'clientquit', 'client_id': self.client_id, 'payload': 'quit', 'c_pktid': gen_randid()}
		logger.info(f'sending quitmsg payload={payload}')

		self.sender.queue.put((self.socket, payload))
		#send_data(conn=self.socket, payload=quitmsg)

		self.kill = True
		self.connected = False
		if self.socket:
			self.socket.close()

	def connect_to_server(self) -> bool:
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
				return False
		self.connected = True
		self.oldreceiver.start()
		self.oldsender.start()
		# if not self.gotmap:
		self.send_maprequest(gridsize=15)
		return self.connected

	def move(self, direction):
		#gpx = int(self.rect.x // BLOCK)
		#gpy = int(self.rect.y // BLOCK)
		oldgridpos = self.gridpos
		gpx, gpy = self.gridpos
		newgridpos = [gpx, gpy]
		moved = False
		# logger.debug(f'{self} move {direction} {self.gridpos}')
		# = {'blktype':blktype, 'bomb':False}
		if direction == 'up':
			newgridpos = [gpx, gpy-1]
		elif direction == 'down':
			newgridpos = [gpx, gpy+1]
		elif direction == 'left':
			newgridpos = [gpx-1, gpy]
		elif direction == 'right':
			newgridpos = [gpx+1, gpy]
		try:
			if self.gamemap.get_block(gridpos=newgridpos).get('blktype', 0) > 10:
				moved = True
		except BlockNotFoundError as e:
			logger.warning(f'[move] {e}')
			moved = False
		if moved:
			self.gridpos = newgridpos
			self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
			self.rect.x = self.pos[0]
			self.rect.y = self.pos[1]
			#send_data(self.socket, payload)
			#logger.info(f'move {direction} from {oldgridpos} to {newgridpos} g:{self.gamemap.grid[gpx][gpy]} selfgridpos={self.gridpos} rect={self.rect} pos={self.pos}')
		#else:
			#gx,gy = newgridpos
			# gtemp = self.gamemap.grid[gx][gy].get('blk')
			#logger.warning(f'cant move {direction} from {oldgridpos} to {newgridpos} g:{self.gamemap.grid[gx][gy]} selfgridpos={self.gridpos} rect={self.rect} pos={self.pos}')
			#logger.warning(f'selfgp={self.gamemap.get_block(gridpos=self.gridpos)} ngp={self.gamemap.get_block(gridpos=newgridpos)}')
			# logger.warning(f'')


	def oldhandle_payloadq(self, payloads):
		if not payloads:
			return
		for payload in payloads:
			msgtype = payload.get('msgtype')
			in_pktid = payload.get('pktid')
			if msgtype == 'oldbcsetclid':
				clid = payload.get('client_id')
				self.set_clientid(clid)
			if msgtype == 's_netplayers':
				# logger.debug(f'netplayers payload={payload}')
				netplayers = payload.get('netplayers', None)
				if netplayers:
					self.netplayers = netplayers
			if msgtype == 'olds_ping':
				#logger.debug(f'{self} s_ping payload={payload}')
				bchtimer = payload.get('bchtimer')
				pktid = payload.get('pktid')
				#logger.debug(f's_ping payload={payload} bchtimer={bchtimer} cl_timer={self.cl_timer} sendq={self.sender.queue.qsize()}')
				clpongpayload = {
					'msgtype': 'cl_pong',
					'client_id': self.client_id,
					'cl_timer': self.cl_timer,
					'in_pktid': pktid,
					'c_pktid': gen_randid(),
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
				# logger.debug(f'{msgtype} g={gridpos} b={blktype} bclid={bclid} client_id={self.client_id}')
				pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'c_ngu', 'client_id':self.client_id, 'blkgridpos':gridpos, 'blktype':blktype, 'bclid':bclid}))
				# send grid update to bdude

			if msgtype == 'bc_netbomb':
				# received bomb from server
				if payload.get('client_id') == self.client_id:
					self.bombs_left -= 1
				pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'bc_netbomb', 'bombdata':payload}))
				logger.info(f'{msgtype} eventpost bl={self.bombs_left} payload={payload}')

			if msgtype == 's_posupdate':
				# received posupdate from server
				logger.info(f'posupdate payload={payload}')
				pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos}))
				#pygame.event.post(posmsg)

			if msgtype == 's_pos':
				# received playerpos from server
				self.pos = payload.get('pos')
				self.rect.x = self.pos[0]
				self.rect.y = self.pos[1]
				self.gridpos = payload.get('gridpos')
				self.gamemap.grid = payload.get('grid')
				self.gotpos = True
				self.gotmap = True
				pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'gridpos':self.gridpos, 'grid':self.gamemap.grid}))

			if msgtype == 's_grid':
				# complete grid from server
				self.gamemap.grid = payload.get('grid')
				self.gridpos = payload.get('gridpos')
				self.pos = payload.get('pos')
				self.rect.x = self.pos[0]
				self.rect.y = self.pos[1]
				self.gotmap = True
				self.gotpos = True
				self.ready = True
				pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'s_gamemapgrid', 'client_id':self.client_id, 'grid':self.gamemap.grid, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'gridpos':self.gridpos}))
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
			'c_pktid': gen_randid(),
			}
		if self.ready:
			self.sender.queue.put((self.socket, pospayload))
