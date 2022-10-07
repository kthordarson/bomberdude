from types import NoneType
from pygame.math import Vector2
import random
import pygame
import struct
import socket
import sys,os
from loguru import logger
from threading import Thread

# from things import Block
from constants import FPS, DEFAULTFONT, BLOCK,SQUARESIZE
from map import Gamemap
from globals import gen_randid
from network import receive_data, send_data, dataid

from queue import Queue

class ServerGUI(Thread):
	def __init__(self):
		super().__init__()
		self.screen =  pygame.display.set_mode((800,600), 0, 8)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.menusize = (250, 180)
		self.image = pygame.Surface(self.menusize)
		self.pos = Vector2(self.screenw // 2 - self.menusize[0] // 2, self.screenh // 2 - self.menusize[1] // 2)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.bg_color = pygame.Color("black")
		self.bombclients = []
		self.netplayers = {}
		self.serverclock = pygame.time.Clock()
		self.gamemapgrid = []

	def renderinfo(self):
			try:
				pygame.display.flip()
			except:
				self.screen = pygame.display.set_mode((800,600), 0, 8)
			self.screen.fill(self.bg_color)
			ctextpos = [10, 10]
			try:
				fps = self.serverclock.get_fps()
				msgtxt = f'fps={fps} clients:{len(self.bombclients)} np:{len(self.netplayers)} '
			except TypeError as e:
				logger.warning(f'[ {self} ] TypeError:{e}')
				msgtxt = ''
			self.font.render_to(self.screen, ctextpos, msgtxt, (150,150,150))
			ctextpos = [15, 25]
			npidx = 1
			#netplrs = [self.netplayers[k] for k in self.netplayers if not self.netplayers[k]['kill']]
			#self.netplayers = netplrs
			for np in self.netplayers:
				snp = self.netplayers[np]
				spos = snp["pos"]
				sgpos = snp["gridpos"]
				ngx = (int(spos[0]//BLOCK),int(spos[1]//BLOCK))
				msgtxt = f'[{npidx}/{len(self.netplayers)}] servernp:{snp["client_id"]} pos={snp["pos"]} {snp["gridpos"]} snpkill={snp["kill"]}'
				if snp['client_id'] != '0':
					self.font.render_to(self.screen, (ctextpos[0]+13, ctextpos[1] ), msgtxt, (130,30,130))
					ctextpos[1] += 20
				if snp['client_id'] == '0':
					self.font.render_to(self.screen, (ctextpos[0]+13, ctextpos[1] ), msgtxt, (190,80,230))
					ctextpos[1] += 20
			bidx = 1
			plcolor = [255,0,0]
			for bc in self.bombclients:
				bctimer = pygame.time.get_ticks()-bc.lastupdate
				self.gamemapgrid = bc.gamemap.grid
				bcgridpos = (bc.gridpos[0], bc.gridpos[1])
				if bcgridpos[0] > 100 or bcgridpos[1] > 100:
					logger.error(f'{bc} gridpos out of range bcgridpos:{bcgridpos}')
					break
				np = {'client_id':bc.client_id, 'pos':bc.pos, 'centerpos':bc.centerpos,'kill':int(bc.kill), 'gridpos':bcgridpos}
				self.netplayers[bc.client_id] = np
				bc.netplayers[bc.client_id] = np
				textmsg = f'[{bidx}/{len(self.bombclients)}] bc={bc.client_id} pos={bc.pos} np:{len(bc.netplayers)} t:{bctimer}'
				self.font.render_to(self.screen, ctextpos, textmsg, (130,130,130))
				ctextpos[1] += 20
				bidx += 1
				#self.font.render_to(self.screen, (ctextpos[0]+10, ctextpos[1]), f'np={np}', (140,140,140))
				#ctextpos[1] += 20
				npidx = 1
				for npitem in bc.netplayers:
					bcnp = bc.netplayers[npitem]
					msgstring = f'[{npidx}/{len(bc.netplayers)}] bcnp={bcnp["client_id"]} pos={bcnp["pos"]} {bcnp["gridpos"]} kill={bcnp["kill"]} t:{bctimer}'
					if npitem != '0':
						self.font.render_to(self.screen, (ctextpos[0]+15, ctextpos[1]), msgstring, (145,245,145))
						npidx += 1
						ctextpos[1] += 20
					if npitem == '0':
						self.font.render_to(self.screen, (ctextpos[0]+15, ctextpos[1]), msgstring, (145,145,145))
						npidx += 1
						ctextpos[1] += 20
				pygame.draw.circle(self.screen, plcolor, center=bc.pos, radius=5)
				plcolor[1] += 60
				plcolor[2] += 60

class Sender(Thread):
	def __init__(self, client_id):
		Thread.__init__(self)
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
		while True:
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
				self.queue.task_done()
				# self.queue.task_done()

class Servercomm(Thread):
	def __init__(self, serverqueue=None):
		Thread.__init__(self)
		self.kill = False
		self.serverqueue = serverqueue
		self.queue = Queue()
		#np = {'client_id':'0', 'pos':(0,0), 'centerpos':(0,0),'kill':0}
		self.netplayers = {}
		#self.netplayers[np['client_id']] = np
		self.srvcount = 0
		logger.info(f'[BC] {self} server_comm init')

	def __str__(self):
		return f'[scomm] count={self.srvcount} np={len(self.netplayers)} sq:{self.queue.qsize()}'

	def run(self):
		logger.info(f'[ {self} ] server_comm run')
		while True:
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
						#logger.debug(f'[ {self} ] bomb payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'netgrid':
						#logger.debug(f'[ {self} ] bomb payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'clientquit':
						logger.debug(f'[ {self} ] quit payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'reqpos':
						logger.debug(f'[ {self} ] reqpos payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'resetmap':
						logger.debug(f'[ {self} ] resetmaps payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'netgridupdate':
						# logger.debug(f'[ {self} ] netgridupdate payload:{len(payload)}')
						self.serverqueue.put(payload)
					self.queue.task_done()

				#logger.debug(f'[ {self} ] payload:{payload}')


class BombClientHandler(Thread):
	def __init__(self, conn=None,  addr=None, gamemap=None, servercomm=None, npos=None, ngpos=None):
		Thread.__init__(self)
		self.queue = Queue()
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = '0'
		self.kill = 0
		self.conn = conn
		self.addr = addr
		np = {'client_id':'0', 'pos':(0,0), 'centerpos':(0,0),'kill':0, 'gridpos':[0,0]}
		self.netplayers = {}
		self.netplayers[np['client_id']] = np
		self.pos = npos
		self.gridpos = ngpos
		self.gotpos = False
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
		
		#if not newgridpos:
		#	ngx = int(newpos[0]//BLOCK)
		#	ngy = int(newpos[1]//BLOCK)
		#	newgridpos = (ngx,ngy)
		
		if self.gridpos[0] > 100 or self.gridpos[1] > 100 or gridpos[0] > 100 or gridpos[1] > 100:
			logger.error(f'{self} gridpos out of range {self.gridpos} g={gridpos} p={pos}')
		else:
			self.pos = pos
			self.gridpos = gridpos
			posmsg = {'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos, 'newpos':pos, 'newgridpos':gridpos}
			self.sender.queue.put((self.conn, posmsg))
			logger.info(f'[ {self} ] set_pos newpos={pos} ngp={gridpos}')

	def posupdate(self, data):
		logger.error(f'[ {self} ] posupdate data={data}  mypos={self.pos}')
		# # when server sends new player position
		# if not self.gotpos:
		# 	logger.debug(f'[ {self} ] posupdate data={data}  mypos={self.pos}')
		# 	newgrid = self.gamemap.placeplayer(self.gamemap.grid, self.pos)
		# 	self.gamemap.grid = newgrid
		# 	payload = {'msgtype':dataid["posupdate"], 'client_id':self.client_id, 'pos':self.pos, 'newpos':self.pos, 'newgrid':newgrid, 'data_id':dataid["posupdate"]}
		# 	self.sender.queue.put((self.conn, payload))
		# 	self.gotpos = True
		# else:
		# 	logger.warning(f'[ {self} ] dupeposupdate data={data}  mypos={self.pos}')

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
		

	def send_map(self, newgrid=None, randpos=False, refresh=False):
		# send mapgrid to player
		# todo fix player pos on grid
		if not refresh:
			ng, newpos, newgridpos = self.gamemap.placeplayer(grid=newgrid, pos=self.pos, randpos=randpos)
		else:
			ng = self.gamemap.grid
			newpos = self.pos
			newgridpos = self.gridpos
		#newpos = (nx,ny)
		if newgridpos[0] > 100 or newgridpos[1] > 100 or self.gridpos[0]>1000 or self.gridpos[1]>1000:
			logger.error(f'{self} gridpos out of range {newgridpos} self.gridpos={self.gridpos}')
		oldpos = self.pos
		oldgridpos = self.gridpos
		if randpos:
			self.set_pos(pos=newpos, gridpos=newgridpos)
			self.pos = newpos
			self.gridpos = newgridpos
		logger.info(f'send_map newgrid:{len(newgrid)} self.pos:{self.pos} newpos={newpos} oldpos={oldpos} ng={self.gridpos} og={oldgridpos} randpos={randpos}')
		self.gamemap.grid = ng
		payload = {'msgtype':'mapfromserver', 'gamemapgrid':self.gamemap.grid, 'data_id':dataid['gamegrid'], 'newpos': self.pos, 'newgridpos':self.gridpos, 'oldgridpos':oldgridpos}
		# logger.debug(f'[ {self} ] send_map payload={len(payload)} randpos={randpos}')
		self.sender.queue.put((self.conn, payload))

	def gridupdate(self, data):
		# when client send update after bomb explosion
		logger.debug(f'griddata:{len(data)}')
		self.sender.queue.put((self.conn, data))

	def bombevent(self, data):
		# when client sends bomb
		logger.debug(f'{self.client_id} bombevent bomber:{data.get("client_id")} pos:{data.get("bombpos")}')
		self.sender.queue.put((self.conn, data))

	def get_client_id(self):
		# get real client id from remote client
		payload = {'msgtype':'bcgetid', 'payload':'sendclientid', 'data_id':dataid['getid']}
		self.sender.queue.put((self.conn, payload))
		logger.debug(f'[ {self} ] sent payload:{payload}')
		# #self.sender.send(self.conn, payload)
		# rid, resp = None, None
		# try:
		# 	resp = receive_data(self.conn)
		# 	rid = resp.get('data_id')
		# 	if resp or rid:
		# 		clid = resp.get('client_id', None)
		# 		self.client_id = clid
		# 		self.sender.set_clid(clid)
		# 		#logger.info(f'[ {self} ] rid:{rid} resp:{resp}')
		# 		if resp == 'reqmap':
		# 			logger.debug(f'[ {self} ] rid:{rid} resp:{resp}')
		# 			self.send_map(newgrid=self.gamemap.grid, randpos=True)
		# except (ConnectionResetError, BrokenPipeError, struct.error, EOFError) as e:
		# 	logger.error(f'[ {self} ] receive_data error:{e}')
		# #self.sendq.put(payload)

	def run(self):
		self.get_client_id()
		logger.debug(f'[ {self} ]  run ')
		#st = Thread(target=self.sender, daemon=False)
		#st.run()
		#srvcomm = Thread(target=self.server_comms, daemon=False)
		#srvcomm.run()
		self.sender.start()
		#self.servercomm.run()
		#self.set_pos(self.pos)
		while True:
			self.netplayers = self.servercomm.netplayers
			# logger.debug(f'[ {self} ] np={self.netplayers}')
			if self.client_id is None or self.client_id == '0':
				self.get_client_id()
			if self.kill or self.sender.kill:
				logger.debug(f'{self} killed')
				self.sender.kill = True
				self.kill = True
				self.conn.close()
				break
			#if len(self.netplayers) >= 1:
			npayload = {'msgtype':dataid['netplayers'], 'client_id':self.client_id, 'netplayers':self.netplayers, 'data_id':dataid['netplayers']}
			self.sender.queue.put((self.conn, npayload))

			rid, rtype = None, None
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
					try:
						if isinstance(resp, int):
							rid = resp
						else:
							rid = resp.get('data_id')
						rtype = dataid.get(rid, None)
					except AttributeError as e:
						logger.warning(f'[ {self} ] AttributeError:{e}  self.lastupdate={self.lastupdate} resp={resp}')
					if rid == dataid.get('info') or rid == 0:
						self.servercomm.queue.put({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos})
					elif rtype == dataid.get('playerpos') or rid == 3:
						#logger.debug(f'[ {self} ] {rtype} {rid} {resp}')
						s_clid = resp.get('client_id', None)
						if not self.client_id or self.client_id == '0':
							self.client_id = s_clid
							logger.debug(f'r:{len(resps)} setclientid {rtype} {rid} {resp}')
						s_pos = resp.get('pos', None)
						c_pos = resp.get('centerpos', None)
						g_pos = resp.get('gridpos', None)
						if g_pos[0] > 100 or g_pos[1] > 100:
							logger.error(f"[BC] {self} g_pos={g_pos} out of range {s_clid} {s_pos} {self.pos}")
						self.pos = s_pos
						self.centerpos = c_pos
						self.gridpos = g_pos
						posmsg = {'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos, 'centerpos':c_pos, 'gridpos':g_pos}
						self.servercomm.queue.put(posmsg)

					elif rtype == dataid.get('update') or rid == 4:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'r:{len(resps)} update {rtype} {rid} {resp}')
						# logger.debug(f'[ {self} ] received id:{rid} resp={resp}')

					elif rtype == dataid['reqmap'] or rid == 7:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'r:{len(resps)} reqmap {rtype} {rid} {resp}')
						self.send_map(newgrid=self.gamemap.grid, randpos=True, refresh=False)

					elif rtype == dataid.get('gameevent') or rid == 9:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'r:{len(resps)} gameevent {rtype} {rid} {resp}')
						else:
							logger.debug(f'gamevent received id:{rid} resp={resp}')

					elif rtype == dataid['gridupdate'] or rid == 12:
						# new grid and send update to clients
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} gridupdate {rtype} {rid} {resp}')
						senderid = resp.get('client_id', None)
						blkgridpos = resp.get('blkgridpos', None)
						blktype = resp.get('blktype', None)
						# if not blktype:
						# 	logger.error(f'gridupdate missing blktype rt={rtype} rid={rid}  r:{len(resps)} resp={resp}')
						# 	blktype = 0
						griddata = resp.get('griddata')
						self.gamemap.grid[blkgridpos[0]][blkgridpos[1]] = blktype
						gridmsg = {'msgtype': 'netgridupdate', 'client_id': senderid, 'blkgridpos': blkgridpos, 'blktype':blktype, 'data_id': dataid['gridupdate'], 'griddata':griddata}
						self.servercomm.queue.put(gridmsg)
						#self.gamemap.grid = newgrid
						#self.send_map()
						# logger.debug(f'gridupdate senderid:{senderid} blkgridpos={blkgridpos} blktype={blktype}')

					elif rtype == dataid.get('netbomb') or rid == 14:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} netbomb {rtype} {rid} {resp}')
						updatemsg = {'msgtype':'netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'data_id':dataid['netbomb']}
						self.servercomm.queue.put(updatemsg)

					elif rtype == dataid.get('clientquit') or rid == 16:
						qmsg = {'msgtype':'clientquit', 'client_id':self.client_id}
						self.servercomm.queue.put(qmsg)

					elif rtype == dataid.get('reqpos') or rid == 17:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} reqpos {rtype} {rid} {resp}')
						msg = {'msgtype':'reqpos', 'client_id':self.client_id}
						self.servercomm.queue.put(msg)

					elif rtype == dataid.get('posupdate') or rid == 19:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} posupdate {rtype} {rid} {resp}')
						# client sent posupdate
						msg = {'msgtype':'posupdate', 'client_id':self.client_id, 'posupdata':resp}
						self.servercomm.queue.put(msg)

					elif rtype == dataid.get('resetmap') or rid == 20:
						# make new mapgrid and send to all clients
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} resetmap {rtype} {rid} {resp}')
						msg = {'msgtype':'resetmap', 'client_id':self.client_id}
						self.servercomm.queue.put(msg)

					elif rtype == dataid['refreshsgrid'] or rid == 21:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'r:{len(resps)} refreshsgrid {rtype} {rid} {resp}')
						self.send_map(newgrid=self.gamemap.grid, randpos=False, refresh=True)

					elif rtype == dataid['auth'] or rid == 101:
						logger.debug(f'[ {self} ] r:{len(resps)} auth received id:{rid} resp={resp}')
						clid = resp.get('client_id', None)
						if not self.client_id or self.client_id == '0':
							logger.debug(f'[ {self} ] r:{len(resps)} auth {rtype} {rid} {resp}')
						self.client_id = clid

					elif rtype == dataid['UnpicklingError'] or rid == 1002:
						logger.warning(f'[ {self} ] r:{len(resps)} UnpicklingError rid:{rid}')
					else:
						if resp:
							logger.warning(f'[ {self} ] r:{len(resps)} unknownevent rid:{rid} rtype:{rtype}  resp={resp}')
						else:
							pass
						#logger.error(f'[ {self} ] unknownevent noresp rid:{rid} rtype:{rtype}  resp={type(resp)}')

class BombServer(Thread):
	def __init__(self, gui):
		Thread.__init__(self, daemon=False)
		self.bombclients  = []
		self.gamemap = Gamemap()
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		np = {'client_id':'0', 'pos':(0,0), 'centerpos':(0,0),'kill':0, 'gridpos':[0,0]}
		self.netplayers = {}
		self.netplayers[np['client_id']] = np
		self.gui = gui # ServerGUI()
		self.servercomm = Servercomm(serverqueue=self.queue)
		self.serverclock = pygame.time.Clock()

	def __str__(self):
		return f'[S] k:{self.kill} bc:{len(self.bombclients)} np:{len(self.netplayers)}'

	def serverevents(self):
		events = pygame.event.get()
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_q:
					self.kill = True

	def run(self):
		logger.debug(f'[ {self} ] run')
		#self.servercomm.run()
		self.gui.start()
		self.gamemap.generate_custom(gridsize=SQUARESIZE)
		self.servercomm.start()
		fps = -1
		while not self.kill:
			events = pygame.event.get()
			for event in events:
				if event.type == pygame.KEYDOWN:
					if event.key == pygame.K_q:
						self.kill = True
						self.conn.close()
						break
			self.serverclock.tick(30)

			# refresh gui data
			self.gui.bombclients = self.bombclients
			for np in self.netplayers:
				self.gui.netplayers[np] = self.netplayers[np]
				for bc in self.bombclients:
					for npbc in bc.netplayers:
						self.gui.netplayers[npbc] = bc.netplayers[npbc]
			self.gui.renderinfo()
			kp = False
			try:
				# remove killed players
				self.netplayers.pop([self.netplayers.get(k) for k in self.netplayers if self.netplayers[k]['kill']][0].get('client_id'))
				kp = True
			except IndexError:
				pass
			for bc in self.bombclients:
				bc.netplayers = self.netplayers
				if bc.gridpos[0] > 100 or bc.gridpos[1] > 100:
					logger.error(f'gridpos out of range for bc={bc}')
				for bcnp in bc.netplayers:
					if bc.netplayers[bcnp]['gridpos'][0] > 100 or bc.netplayers[bcnp]['gridpos'][0] > 100:
						logger.error(f'gridpos out of range for bc={bc} bcnp={bcnp}')
					self.netplayers[bcnp] = bc.netplayers[bcnp]
				for np in self.netplayers:
					try:
						if bc.netplayers[np]['gridpos'][0] > 100 or bc.netplayers[np]['gridpos'][0] > 100:
							logger.error(f'gridpos out of range for bc={bc} np={np}')
					except KeyError as e: 
						logger.error(f'{self} KeyError:{e} bc={bc} np={np}')
					bc.netplayers[np] = self.netplayers[np]
				payload = {'msgtype':'netplayers', 'netplayers':self.netplayers}
				bc.servercomm.queue.put(payload)
				if pygame.time.get_ticks()-bc.lastupdate > 10000:
					bc.kill = True					
					try:
						bc.netplayers[bc.client_id]['kill'] = 1
						self.netplayers[bc.client_id]['kill'] = 1
					except KeyError as e:
						logger.error(f'err e:{e} bc:{bc}')
					logger.warning(f'[ {self} ] {bc} timeout')
					self.bombclients.pop(self.bombclients.index(bc))
			if self.kill:
				for c in self.bombclients:
					logger.debug(f'[ {self} ] killing {c}')
					c.kill = True
				logger.debug(f'[ {self} ] killed')
				self.conn.close()
				os._exit(0)
			if not self.queue.empty():
				data = self.queue.get()
				# logger.debug(f'[ {self} ] getq data:{data}')
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
						if bc.gridpos[0] > 100 or bc.gridpos[1] > 100:
							logger.error(f'{bc} gridpos out of range')
						elif bc.client_id != '0':
							self.gamemap.grid, bnewpos, bcgridpos = self.gamemap.placeplayer(grid=self.gamemap.grid, randpos=False, pos=bc.pos)
							if bcgridpos[0] > 100 or bcgridpos[1] > 100:
								logger.error(f'bcgridpos:{bcgridpos}')
								break
							#bc.pos = bnewpos
							#bc.gridpos = bcgridpos
							#bc.set_pos(pos=bc.pos, gridpos=bc.gridpos)
							#bc.gamemap.grid = bcg
							bc.send_map(newgrid=self.gamemap.grid, randpos=False, refresh=True)
							#self.gamemap.grid = bcg#
							for np in self.netplayers:
								if bc.netplayers[np]["gridpos"][0] > 100 or bc.netplayers[np]['gridpos'][1] > 100:
									logger.warning(f'gridpos out of range bc={bc} np={np}')
								bc.netplayers[np] = self.netplayers[np]
							for np in bc.netplayers:
								self.netplayers[np] = bc.netplayers[np]
					logger.debug(f'[ {self} ] new player:{newbc} cl:{len(self.bombclients)}')
				elif smsgtype == 'playerpos':
					for bc in self.bombclients:
						clid = data.get('client_id', None)
						#if clid != '0':
						pos = data.get('pos', None)
						gridpos = data.get('gridpos', None)
						if gridpos[0] > 100 or gridpos[1] > 100 or bc.gridpos[0] > 100 or bc.gridpos[1] > 100:
							logger.error(f'{self} gridpos out of range {gridpos}')
						centerpos = data.get('centerpos')
						ckill = data.get('kill')
						#if clid != bc.client_id:
						np = {'pos':pos, 'centerpos':centerpos, 'kill':ckill, 'gridpos':gridpos}
						bc.netplayers[clid] = np
						self.netplayers[clid] = np
						#elif clid == bc.client_id:
						#	logger.warning(f'[ {self} ] clid={clid} bc={bc} skipping')
						if ckill:
							# client kill flag set, kill bombclient and remove from list
							bc.kill = True
							logger.warning(f'[ {self} ] {bc} kill')
							bc.netplayers[clid]['kill'] = 1
							self.netplayers[clid]['kill'] = 1
				elif smsgtype == 'netplayers':
					# unused
					logger.debug(f'netplayersmsg data={data}')
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
					basegrid = self.gamemap.generate_custom(gridsize=SQUARESIZE)
					#self.gamemap.grid = basegrid
					for bc in self.bombclients:
						bcg, bnewpos, newgridpos = self.gamemap.placeplayer(basegrid, bc.pos)
						bc.pos = bnewpos
						bc.gridpos = newgridpos
						bc.set_pos(pos=bc.pos, gridpos=bc.gridpos)
						bc.gamemap.grid = bcg
						bc.send_map(newgrid=bcg, randpos=True, refresh=False)
						self.gamemap.grid = bcg

				else:
					logger.warning(f'[ {self} ] data={data}')
				self.queue.task_done()
			# if self.gamemap.is_empty():
			# 	# all blocks cleared from map, make and send new grid to all clients
			# 	logger.info(f'[ {self} ] map is empty')
			# 	newgrid = self.gamemap.generate_custom(squaresize=15, players=self.netplayers)
			# 	self.gamemap.grid = newgrid
			# 	for bc in self.bombclients:
			# 		bcg = self.gamemap.placeplayer(self.gamemap.grid, bc.pos)
			# 		bc.gamemap.grid = bcg
			# 		bc.send_map(newgrid=bcg)
			# 		self.gamemap.grid = bcg


def main():
	pygame.init()
	pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])
	mainthreads = []
	key_message = 'bomberdude'
	logger.debug(f'[bombserver] started')
	clients = 0
	# serverq = Queue()
	gui = ServerGUI()
	server = BombServer(gui)
	server.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.conn.bind(('0.0.0.0', 9696))
	server.conn.listen()
	server.start()
	while True:
		logger.debug(f'[bombserver] {server} waiting for connection clients:{clients}')
		try:
			if server.kill:
				logger.warning(f'[bombserver] {server} server killed')
				server.conn.close()
				break
			conn, addr = server.conn.accept()
			server.queue.put({'msgtype':'newclient', 'conn':conn, 'addr':addr})
		except KeyboardInterrupt as e:
			server.conn.close()
			logger.warning(f'KeyboardInterrupt:{e} serverq:{server.queue} server:{server}')
			for bc in server.bombclients:
				logger.warning(f'kill bc:{bc}')
				bc.kill = True
				bc.join()
			server.kill = True
			server.join()
			logger.warning(f'kill server:{server}')
			return



if __name__ == '__main__':
	logger.info('start')
	main()
	logger.info('done')
	sys.exit(0)
