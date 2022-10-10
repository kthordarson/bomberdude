import time
from pygame.math import Vector2
from pygame.event import Event
from pygame import USEREVENT
import pygame
import struct
import socket
import sys,os
from loguru import logger
from threading import Thread
from queue import Queue
# from things import Block
from constants import FPS, DEFAULTFONT, BLOCK,SQUARESIZE,DEFAULTGRID, DEFAULTGRID4
from map import Gamemap
from globals import gen_randid
from network import receive_data, send_data


class Sender(Thread):
	def __init__(self, client_id):
		Thread.__init__(self, daemon=True)
		self.kill = False
		self.queue = Queue()
		self.sendcount = 0
		self.client_id = client_id
		logger.info(f'{self} senderthread init')

	def __str__(self):
		return f'[sender] clid={self.client_id} count={self.sendcount} sq:{self.queue.qsize()}'

	def set_clid(self, clid):
		self.client_id = clid
		logger.info(f'[ {self} ] set_clid {clid}')

	def run(self):
		logger.info(f'[ {self} ] run')
		while not self.kill:
			if self.kill:
				logger.warning(f'[ {self} ] killed')
				break
			if not self.queue.empty():
				conn, payload = self.queue.get()
				# logger.debug(f'[ {self} ] senderthread sending payload:{payload}')
				try:
					# send_data(conn, payload={'msgtype':'bcnetupdate', 'payload':payload})
					send_data(conn, payload)
				except (BrokenPipeError, ConnectionResetError) as e:
					logger.error(f'[ {self} ] senderr {e}')
					self.kill = True
					break
				self.sendcount += 1
				try:
					self.queue.task_done()
				except ValueError as e:
					logger.warning(f'{self} queue.task_done err {e}')
				# self.queue.task_done()

class Servercomm(Thread):
	def __init__(self):
		Thread.__init__(self, daemon=True)
		self.kill = False
		self.queue = Queue()
		self.netplayers = {}
		self.srvcount = 0
		logger.info(f'[BC] {self} server_comm init')

	def __str__(self):
		return f'[scomm] count={self.srvcount} np={len(self.netplayers)} sq:{self.queue.qsize()}'

	def run(self):
		logger.info(f'[ {self} ] server_comm run')
		while not self.kill:
			if self.kill:
				logger.warning(f'[ {self} ] server_comm killed')
				break
			payload = None
			if not self.queue.empty():
				payload = self.queue.get()
				self.srvcount += 1
				if payload:
					if payload.get('msgtype') == 'netplayers':
						netplayers = payload.get('netplayers')
						for np in netplayers:
							self.netplayers[np] = netplayers[np]
					elif payload.get('msgtype') == 'netbomb':
						#logger.debug(f'bomb payload:{payload}')
						nb = Event(USEREVENT, payload=payload)
						pygame.event.post(nb)
					elif payload.get('msgtype') == 'netgrid':
						#logger.debug(f'bomb payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'clientquit':
						logger.debug(f'quit payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'reqpos':
						logger.debug(f'reqpos payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'resetmap':
						logger.debug(f'resetmaps payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'netgridupdate':
						# logger.debug(f'netgridupdate payload:{len(payload)}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					try:
						self.queue.task_done()
					except ValueError as e:
						logger.warning(f'{self} queue.task_done err {e}')

				#logger.debug(f'[ {self} ] payload:{payload}')


class BombClientHandler(Thread):
	def __init__(self, conn=None,  addr=None, gamemap=None, servercomm=None, npos=None, ngpos=None):
		Thread.__init__(self, daemon=True)
		self.queue = Queue()
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = gen_randid()
		self.kill = False
		self.conn = conn
		self.addr = addr
		self.pos = npos
		self.gridpos = ngpos
		self.gotpos = False
		self.gotmap = False
		self.clidset = False
		self.centerpos = (0,0)
		self.gamemap = gamemap
		self.sender = Sender(client_id=self.client_id)
		self.servercomm = servercomm # Servercomm(self.queue)
		self.start_time = pygame.time.get_ticks()
		self.lastupdate = self.start_time
		self.maxtimeout = 9000
		logger.info(f'[BC] BombClientHandler init addr:{self.addr} client_id:{self.client_id}')

	def __str__(self):
		return f'[BCH] {self.client_id} t:{pygame.time.get_ticks()-self.start_time} l:{self.lastupdate} sq:{self.queue.qsize()} sqs:{self.sendq.qsize()} {self.sender} {self.servercomm}'

	def set_pos(self, pos=None, gridpos=None):
		# called when server generates new map and new player position
		self.pos = pos
		self.gridpos = gridpos
		posmsg = {'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos, 'newpos':pos, 'newgridpos':gridpos}
		self.sender.queue.put((self.conn, posmsg))
		logger.info(f'[ {self} ] set_pos newpos={pos} ngp={gridpos}')

	def posupdate(self, data):
		logger.error(f'[ {self} ] posupdate data={data}  mypos={self.pos}')

	def quitplayer(self, quitter):
		# when player quits or times out
		logger.info(f'[ {self} ] quitplayer quitter:{quitter}')
		if quitter == self.client_id:
			self.kill = True
			self.sender.kill = True
			self.conn.close()

	def send_gridupdate(self, blkpos, blktype, bclid):
		payload = {'msgtype': 'netgridupdate', 'client_id':self.client_id, 'blkgridpos':blkpos, 'blktype':blktype, 'bclid':bclid}
		if bclid != self.client_id:
			logger.info(f'{self.client_id} bclid={bclid} sending gridupdate blkpos={blkpos} blktype={blktype}')
		elif bclid == self.client_id:
			pass
			#logger.warning(f'{self.client_id} bclid={bclid} sending gridupdate to self blkpos={blkpos} blktype={blktype}')
		self.sender.queue.put((self.conn, payload))


	def send_map(self):
		# send mapgrid to player
		# todo fix player pos on grid
		if not self.gotmap:
			logger.info(f'{self} sending map to {self.client_id} sendq={self.sendq.qsize()} ')
		else:
			logger.warning(f'{self} already gotmap sendq={self.sendq.qsize()} ')
		payload = {'msgtype':'mapfromserver', 'gamemapgrid':self.gamemap.grid, 'newpos': self.pos, 'newgridpos':self.gridpos}
		# logger.debug(f'[ {self} ] send_map payload={len(payload)} randpos={randpos}')
		self.sender.queue.put((self.conn, payload))

	def gridupdate(self, data):
		# when client send update after bomb explosion
		logger.debug(f'griddata:{len(data)}')
		self.sender.queue.put((self.conn, data))

	def bombevent(self, data):
		# when client sends bomb
		logger.debug(f'{self.client_id} bombevent bomber:{data.get("client_id")} pos:{data.get("bombpos")} {data.get("bombgridpos")}')
		self.sender.queue.put((self.conn, data))

	def set_client_id(self):
		# send client id to remote client
		if not self.clidset:
			payload = {'msgtype':'bcsetclid', 'client_id':self.client_id}
			self.sender.queue.put((self.conn, payload))
			logger.debug(f'sent payload:{payload}')
			self.clidset = True
		else:
			logger.warning(f'clid already set:{self.client_id}')

	def run(self):
		self.set_client_id()
		logger.debug(f'[ {self} ]  run ')
		self.sender.start()
		while not self.kill:
			#self.netplayers = self.servercomm.netplayers
			# logger.debug(f'[ {self} ] np={self.netplayers}')
			if self.kill or self.sender.kill:
				logger.debug(f'{self} killed sender={self.sender}')
				self.sender.kill = True
				self.sender.join(timeout=1)
				logger.debug(f'{self} killed sender={self.sender} killed')
				self.kill = True
				self.conn.close()
				logger.debug(f'{self} killed sender={self.sender} {self.conn} closed')
				break
			if len(self.servercomm.netplayers) >= 1:
				npayload = {'msgtype':'netplayers', 'client_id':self.client_id, 'netplayers':self.servercomm.netplayers}
				self.sender.queue.put((self.conn, npayload))

			rid = None
			resps = []
			try:
				resps = receive_data(self.conn)
				# logger.debug(f'[ {self} ] rid:{rid} resp:{resp}')
			except (ConnectionResetError, BrokenPipeError, struct.error, EOFError, OSError) as e:
				logger.error(f'[ {self} ] receive_data error:{e}')
				self.conn.close()
				self.kill = True
				break
			if resps:
				for resp in resps:
					self.lastupdate = pygame.time.get_ticks()
					rid = resp.get('msgtype')
					# logger.debug(f'resps={len(resps)} rid={rid} resp={resp}')

					if rid == 'info':
						ev = Event(USEREVENT, payload={'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos})
						pygame.event.post(ev)
						# self.servercomm.queue.put({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos})

					elif rid == 'playerpos':
						#logger.debug(f'[ {self} ] {rid} {resp}')
						s_clid = resp.get('client_id', None)
						s_pos = resp.get('pos', None)
						c_pos = resp.get('centerpos', None)
						g_pos = resp.get('gridpos', None)
						s_gotmap = resp.get('gotmap', None)
						s_gotpos = resp.get('gotpos', None)
						#logger.debug(f'resp={resp}')
						self.pos = s_pos
						self.centerpos = c_pos
						self.gridpos = g_pos
						ev = Event(USEREVENT, payload={'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos, 'centerpos':c_pos, 'gridpos':g_pos})
						pygame.event.post(ev)
						#posmsg = {'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos, 'centerpos':c_pos, 'gridpos':g_pos}
						#self.servercomm.queue.put(posmsg)

					elif rid == 'update':
						logger.warning(f'r:{len(resps)} update {rid} {resp}')
						# logger.debug(f'[ {self} ] received id:{rid} resp={resp}')

					elif rid == 'requestclid':
						self.set_client_id()

					elif rid == 'gameevent':
						logger.warning(f'gamevent received id:{rid} resp={resp}')

					elif rid == 'gridupdate':
						# new grid and send update to clients
						senderid = resp.get('client_id', None)
						blkgridpos = resp.get('blkgridpos', None)
						blktype = resp.get('blktype', None)
						griddata = resp.get('griddata')
						self.gamemap.grid[blkgridpos[0]][blkgridpos[1]] = blktype
						ev = Event(USEREVENT, payload={'msgtype': 'netgridupdate', 'client_id': senderid, 'blkgridpos': blkgridpos, 'blktype':blktype, 'griddata':griddata})
						pygame.event.post(ev)

					elif rid == 'netbomb' or rid == 'bombdrop':
						bx,by = resp.get('bombgridpos', None)
						self.gamemap.grid[bx][by] = 11
						ev = Event(USEREVENT, payload={'msgtype':'netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'bombgridpos':resp.get('bombgridpos'), 'bombpower':resp.get('bombpower')})
						pygame.event.post(ev)

					elif rid == 'clientquit':
						ev = Event(USEREVENT, payload={'msgtype':'clientquit', 'client_id':self.client_id})
						pygame.event.post(ev)

					elif rid == 'reqpos':
						ev = Event(USEREVENT, payload={'msgtype':'reqpos', 'client_id':self.client_id})
						pygame.event.post(ev)

					elif rid == 'posupdate':
						# client sent posupdate
						ev = Event(USEREVENT, payload={'msgtype':'posupdate', 'client_id':self.client_id, 'posupdata':resp})
						pygame.event.post(ev)

					elif rid == 'resetmap':
						# make new mapgrid and send to all clients
						pygame.event.post(Event(USEREVENT, payload={'msgtype':'resetmap', 'client_id':self.client_id}))

					elif rid == 'maprequest':
						pygame.event.post(Event(USEREVENT, payload={'msgtype':'maprequest', 'client_id':self.client_id, 'gridsize':resp.get('gridsize')}))
						#self.send_map()


					elif rid == 'refreshsgrid':
						logger.warning(f'refreshsgrid rid={rid} resp={resp}')
						# self.send_map()

					elif rid == 'auth':
						logger.debug(f'[ {self} ] r:{len(resps)} auth received id:{rid} resp={resp}')
						clid = resp.get('client_id', None)
						self.client_id = clid

					elif rid == 'UnpicklingError':
						logger.warning(f'[ {self} ] r:{len(resps)} UnpicklingError rid:{rid}')
					else:
						if resp:
							logger.warning(f'[ {self} ] r:{len(resps)} unknownevent rid:{rid} resp={resp}')
						else:
							pass


class BombServer(Thread):
	def __init__(self, gui=None):
		Thread.__init__(self, daemon=False)
		self.bombclients  = []
		self.gamemap = Gamemap()
		self.gamemap.grid = self.gamemap.generate_custom(gridsize=15)
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.netplayers = {}
		#self.gui = gui # ServerGUI()
		self.servercomm = Servercomm()
		self.serverclock = pygame.time.Clock()

	def __str__(self):
		return f'[S] k:{self.kill} bc:{len(self.bombclients)} np:{len(self.netplayers)} scomnp:{len(self.servercomm.netplayers)}'

	def eventhandler(self, serverevents):
		for data in serverevents:
			smsgtype = data.get('msgtype')
			if smsgtype == 'newclient':
				# logger.debug(f'[ {self} ] q: {data}')
				conn = data.get('conn')
				addr = data.get('addr')
				# clid = data.get('clid')
				#srvcomm = Servercomm(serverqueue=self.queue)
				basegrid, npos, ngpos = self.gamemap.placeplayer(grid=self.gamemap.grid, randpos=True)
				self.gamemap.grid = basegrid
				newbc = BombClientHandler(conn=conn, addr=addr, gamemap=self.gamemap, servercomm=self.servercomm, npos=npos, ngpos=ngpos)
				newbc.gamemap.grid = self.gamemap.grid
				newbc.start()
				self.bombclients.append(newbc)
				for bc in self.bombclients:
					if bc.client_id:
						#self.gamemap.grid, bnewpos, bcgridpos = self.gamemap.placeplayer(grid=self.gamemap.grid, randpos=False, pos=bc.pos)
						#bc.send_map(randpos=False, refresh=False)
						for np in self.netplayers:
							bc.servercomm.netplayers[np] = self.netplayers[np]
						for np in bc.servercomm.netplayers:
							self.netplayers[np] = bc.servercomm.netplayers[np]
				logger.debug(f'[ {self} ] new player:{newbc} cl:{len(self.bombclients)}')
			elif smsgtype == 'playerpos':
				for bc in self.bombclients:
					clid = data.get('client_id', None)
					if not clid:
						logger.warning(f'[ {self} ] no client_id in data:{data}')
					pos = data.get('pos', None)
					gridpos = data.get('gridpos', None)
					centerpos = data.get('centerpos')
					ckill = data.get('kill')
					#if clid != bc.client_id:
					np = {'client_id':clid, 'pos':pos, 'centerpos':centerpos, 'kill':ckill, 'gridpos':gridpos}
					bc.servercomm.netplayers[clid] = np
					self.netplayers[clid] = np
					#elif clid == bc.client_id:
					#	logger.warning(f'[ {self} ] clid={clid} bc={bc} skipping')
					if ckill:
						# client kill flag set, kill bombclient and remove from list
						bc.kill = True
						logger.warning(f'[ {self} ] {bc} kill')
						bc.servercomm.netplayers[clid]['kill'] = True
						self.netplayers[clid]['kill'] = True
			elif smsgtype == 'netplayers':
				# unused
				netplrs = data.get('netplayers')
				for np in netplrs:
					self.netplayers[np] = netplrs[np]
					# if np != '0':
					# 	self.netplayers[np] = netplrs[np]
					# else:
					# 	logger.warning(f'netplayersmsg data={len(data)} netplrs={len(netplrs)} np={np} netp={netplrs[np]}')

			elif smsgtype == 'netbomb':
				# logger.debug(f'[ {self} ] netbomb from {data.get("client_id")} pos={data.get("bombpos")}')
				for bc in self.bombclients:
					# inform all clients about bomb
					bc.bombevent(data)
			elif smsgtype == 'netgrid':
				self.gamemap.grid = data.get('gamemapgrid')
				# logger.debug(f'[ {self} ] netgrid {len(data)}')
				for bc in self.bombclients:
					bc.gridupdate(data)
			elif smsgtype == 'clientquit':
				# inform all clients about client quit
				logger.debug(f'[ {self} ] quit {data}')
				quitter = data.get('client_id')
				for bc in self.bombclients:
					bc.quitplayer(quitter)
			elif smsgtype == 'reqpos':
				clid = data.get('client_id')
				logger.debug(f'[ {self} ] reqpos from {clid} {data}')
				for bc in self.bombclients:
					if bc.client_id == clid:
						bc.posupdate(data)
			elif smsgtype == 'netgridupdate':
				blkpos = data.get('blkgridpos')
				blktype = data.get('blktype')
				bclid = data.get('client_id')
				self.gamemap.grid[blkpos[0]][blkpos[1]] = blktype
				# logger.info(f'netgridupdate data={len(data)} blkpos={blkpos} blktype={blktype} grid={self.gamemap.grid[blkpos[0]][blkpos[1]]}')
				for bc in self.bombclients:
					bc.gamemap.grid = self.gamemap.grid
					bc.send_gridupdate(blkpos=blkpos, blktype=blktype, bclid=bclid)

			elif smsgtype == 'resetmap' or self.gamemap.is_empty():
				# todo fix player pos on new grid
				if self.gamemap.is_empty():
					logger.info(f'self.gamemap.is_empty() = {self.gamemap.is_empty()}')
				else:
					clid = data.get('client_id')
					logger.info(f'[ {self} ] resetmap from {clid} {data}')
				basegrid = self.gamemap.generate_custom(gridsize=10)
				#self.gamemap.grid = basegrid
				for bc in self.bombclients:
					bcg, bnewpos, newgridpos = self.gamemap.placeplayer(basegrid, bc.pos)
					bc.pos = bnewpos
					bc.gridpos = newgridpos
					bc.set_pos(pos=bc.pos, gridpos=bc.gridpos)
					bc.gamemap.grid = bcg
					bc.send_map()
					self.gamemap.grid = bcg

			elif smsgtype == 'maprequest':
				# todo fix player pos on new grid
				clid = data.get('client_id')
				gz = data.get('gridsize')
				if not gz:
					logger.error(f'{self} no gz data={data}')
					return
				logger.info(f'[ {self} ] resetmap from gz={gz} {clid} {data}')
				basegrid = self.gamemap.generate_custom(gridsize=gz)
				#self.gamemap.grid = basegrid
				for bc in self.bombclients:
					bcg, bnewpos, newgridpos = self.gamemap.placeplayer(basegrid, bc.pos)
					bc.pos = bnewpos
					bc.gridpos = newgridpos
					bc.set_pos(pos=bc.pos, gridpos=bc.gridpos)
					bc.gamemap.grid = bcg
					bc.send_map()
					self.gamemap.grid = bcg


			else:
				logger.warning(f'[ {self} ] data={data}')

	def gui_refresh(self):
		# refresh gui data
		self.gui.bombclients = self.bombclients		
		try:
			for np in self.netplayers:
				if not self.netplayers[np]['kill']:
					self.gui.netplayers[np] = self.netplayers[np]
					for bc in self.bombclients:
						if bc.client_id:
							for npbc in bc.servercomm.netplayers:
								self.gui.netplayers[npbc] = bc.servercomm.netplayers[npbc]
		except RuntimeError as e:
			logger.warning(f'{e}')
		try:
			self.gui.renderinfo()
		except Exception as e:
			logger.error(f'gui error {e}')

	def run(self):
		logger.debug(f'[ {self} ] run')
		# self.gui.start()
		self.servercomm.start()
		while not self.kill:
			serverevents = []
			if not self.queue.empty():
				serverevents.append(self.queue.get())
				try:
					self.queue.task_done()
				except ValueError as e:
					logger.warning(f'{self} queue.task_done err {e}')
			events = pygame.event.get()
			for event in events:
				if event.type == pygame.KEYDOWN:
					logger.info(f'[{len(serverevents)} {len(events)}] event={event}')
					if event.key == pygame.K_q:
						[logger.info(f'[{len(serverevents)} {len(events)}] pgevent={ev}') for ev in events]
						self.kill = True
						logger.info(f'{self} quitting')
						for bc in self.bombclients:
							logger.info(f'{self} killing {bc} ')
							bc.sender.kill = True
							bc.kill = True
							logger.info(f'{self} killing {bc} sender {bc.sender}')
						self.conn.close()
						logger.info(f'{self.conn} close')
						#self.gui.join(timeout=1)
						#logger.info(f'{self.gui} kill')
						self.servercomm.join(timeout=1)
						logger.info(f'{self.servercomm} kill')
						os._exit(0)

				elif event.type == pygame.USEREVENT:
					#logger.info(f'[{len(serverevents)}] event={event}')
					serverevents.append(event.payload)
				elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, 32786, 32777, 772, 32768, 1027, 32775, 32774, 32770, 32785, 4352,32776, 32788,32783,32784,32788]:
					pass
				else:
					logger.warning(f'[{len(serverevents)}] event={event}')
			#self.netplayers.pop([self.netplayers.get(k) for k in self.netplayers if self.netplayers[k]['kill']][0].get('client_id'))
			self.eventhandler(serverevents)
			self.serverclock.tick(FPS)
			#self.gui_refresh()
			# kp = False
			# try:
			# 	self.netplayers.pop([self.netplayers.get(k) for k in self.netplayers if self.netplayers[k]['kill']][0].get('client_id'))
			# 	kp = True
			# except (KeyError, IndexError) as e:
			# 	logger.warning(f'{e}')
			for bc in self.bombclients:
				if bc.client_id:
					if pygame.time.get_ticks()-bc.lastupdate > 10000:
						bc.kill = True
						logger.warning(f'{bc} killtimeout')
						for bc in self.bombclients:
							try:
								bc.servercomm.netplayers[bc.client_id]['kill'] = True
								bc.servercomm.netplayers[bc.client_id]['kill'] = True
								self.netplayers[bc.client_id]['kill'] = True
							except KeyError as e:
								logger.warning(f'KeyError e:{e} bc:{bc}')
						self.bombclients.pop(self.bombclients.index(bc))
						# remove killed players
			deadnps = [self.netplayers.get(k) for k in self.netplayers if self.netplayers.get(k).get('kill')]
			if len(deadnps) > 0:
				killednp = [self.netplayers.pop(k.get('client_id')) for k in deadnps]
				for k in killednp:					
					for bc in self.bombclients:
						try:
							bc.servercomm.netplayers.pop(k.get('client_id'))
						except KeyError as e:
							pass
							#logger.warning(f'KeyError e:{e} bc:{bc} k:{k}')
							#break
						# logger.debug(f'dnp={len(deadnps)} {bc} popped {k}')
			for bc in self.bombclients:
				if bc.client_id:
					bc.servercomm.netplayers = self.netplayers
					for np in self.netplayers:
						if not self.netplayers[np]['kill']:
							bc.servercomm.netplayers[np] = self.netplayers[np]
					# for bcnp in bc.servercomm.netplayers:
					# 	if bcnp != '0' and not bc.servercomm.netplayers[bcnp]['kill']:
					# 		self.netplayers[bcnp] = bc.servercomm.netplayers[bcnp]
			ev = Event(USEREVENT, payload={'msgtype':'netplayers', 'netplayers':self.netplayers})
			pygame.event.post(ev)

class ServerTUI(Thread):
	def __init__(self, server):
		Thread.__init__(self, daemon=False)
		self.server = server
		self.kill = False
	
	def get_serverinfo(self):
		print(self.server)
		for bc in self.server.bombclients:
			print(bc)
		
	def run(self):
		while not self.kill:
			if self.kill:
				break
			try:
				cmd = input(':> ')
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'q':
					self.kill = True
					self.server.conn.close()
					break
			except KeyboardInterrupt:
				self.kill = True
				break


def main():
	pygame.init()
	pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])
	mainthreads = []
	key_message = 'bomberdude'
	logger.debug(f'[bombserver] started')
	clients = 0
	#gui = ServerGUI()
	server = BombServer()
	tui = ServerTUI(server)
	server.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.conn.bind(('0.0.0.0', 9696))
	server.conn.listen()
	server.start()
	tui.start()
	while not server.kill:
		logger.debug(f'[bombserver] {server} waiting for connection clients:{clients}')
		if server.kill or tui.kill:
			logger.warning(f'[bombserver] {server} server killed')
			server.conn.close()
			return
		try:
			conn, addr = server.conn.accept()
			ncmsg=Event(USEREVENT, payload={'msgtype':'newclient', 'conn':conn, 'addr':addr})
			logger.info(f'ncmsg={ncmsg}')
			pygame.event.post(ncmsg)
		except KeyboardInterrupt as e:
			server.conn.close()
			tui.kill = True
			logger.warning(f'KeyboardInterrupt:{e} server:{server}')
			for bc in server.bombclients:
				logger.warning(f'kill bc:{bc}')
				bc.kill = True
				bc.join()
			tui.join()
			server.kill = True
			server.join()
			logger.warning(f'kill server:{server}')
			break



if __name__ == '__main__':
	logger.info('start')
	main()
	logger.info('done')
	sys.exit(0)
