from types import NoneType
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
from constants import FPS, DEFAULTFONT, BLOCK,SQUARESIZE,DEFAULTGRID
from map import Gamemap
from globals import gen_randid
from network import receive_data, send_data, dataid

class ServerGUI(Thread):
	def __init__(self):
		super().__init__(daemon=True)
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
		self.guiclock = pygame.time.Clock()
		self.gamemapgrid = []

	def renderinfo(self):
			self.guiclock.tick(30)
			try:
				pygame.display.flip()
			except:
				self.screen = pygame.display.set_mode((800,600), 0, 8)
			self.screen.fill(self.bg_color)
			ctextpos = [10, 10]
			try:
				
				msgtxt = f'fps={self.guiclock.get_fps():2f} clients:{len(self.bombclients)} np:{len(self.netplayers)} '
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
				spos = snp.get('pos')
				sgpos = snp.get('gridpos')
				msgtxt = f'[{npidx}/{len(self.netplayers)}] servernp:{snp} pos={spos} {sgpos}'
				self.font.render_to(self.screen, (ctextpos[0]+13, ctextpos[1] ), msgtxt, (130,30,130))
				ctextpos[1] += 20
				npidx += 1
#				if sid == '0':
#					self.font.render_to(self.screen, (ctextpos[0]+13, ctextpos[1] ), msgtxt, (190,80,230))
#					ctextpos[1] += 20
			bidx = 1
			plcolor = [255,0,0]
			for bc in self.bombclients:
				if bc.client_id:
					bctimer = pygame.time.get_ticks()-bc.lastupdate
					self.gamemapgrid = bc.gamemap.grid
					bcgridpos = (bc.gridpos[0], bc.gridpos[1])
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
				self.queue.task_done()
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
						#logger.debug(f'[ {self} ] bomb payload:{payload}')
						nb = Event(USEREVENT, payload=payload)
						pygame.event.post(nb)
					elif payload.get('msgtype') == 'netgrid':
						#logger.debug(f'[ {self} ] bomb payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'clientquit':
						logger.debug(f'[ {self} ] quit payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'reqpos':
						logger.debug(f'[ {self} ] reqpos payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'resetmap':
						logger.debug(f'[ {self} ] resetmaps payload:{payload}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					elif payload.get('msgtype') == 'netgridupdate':
						# logger.debug(f'[ {self} ] netgridupdate payload:{len(payload)}')
						pygame.event.post(Event(USEREVENT, payload=payload))
					self.queue.task_done()

				#logger.debug(f'[ {self} ] payload:{payload}')


class BombClientHandler(Thread):
	def __init__(self, conn=None,  addr=None, gamemap=None, servercomm=None, npos=None, ngpos=None):
		Thread.__init__(self, daemon=True)
		self.queue = Queue()
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = None
		self.kill = False
		self.conn = conn
		self.addr = addr
		self.netplayers = {}
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
		

	def send_map(self, newgrid=None, randpos=False, refresh=False):
		# send mapgrid to player
		# todo fix player pos on grid
		if not newgrid:
			logger.warning(f'{self} no newgrid...')
			newgrid = DEFAULTGRID
		if not refresh:
			ng, newpos, newgridpos = self.gamemap.placeplayer(grid=newgrid, pos=self.pos, randpos=randpos)
		else:
			ng = self.gamemap.grid
			newpos = self.pos
			newgridpos = self.gridpos
		#newpos = (nx,ny)
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

	def run(self):
		self.get_client_id()
		logger.debug(f'[ {self} ]  run ')
		self.sender.start()
		while not self.kill:
			self.netplayers = self.servercomm.netplayers
			# logger.debug(f'[ {self} ] np={self.netplayers}')
			if self.client_id is None or self.client_id == '0':
				self.get_client_id()
			if self.kill or self.sender.kill:
				logger.debug(f'{self} killed sender={self.sender}')
				self.sender.kill = True
				self.sender.join(timeout=1)
				logger.debug(f'{self} killed sender={self.sender} killed')
				self.kill = True
				self.conn.close()
				logger.debug(f'{self} killed sender={self.sender} {self.conn} closed')
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
						ev = Event(USEREVENT, payload={'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos})
						pygame.event.pos(ev)
						# self.servercomm.queue.put({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos})
					elif rtype == dataid.get('playerpos') or rid == 3:
						#logger.debug(f'[ {self} ] {rtype} {rid} {resp}')
						s_clid = resp.get('client_id', None)
						if not self.client_id or self.client_id == '0':
							self.client_id = s_clid
							logger.debug(f'r:{len(resps)} setclientid {rtype} {rid} {resp}')
						s_pos = resp.get('pos', None)
						c_pos = resp.get('centerpos', None)
						g_pos = resp.get('gridpos', None)
						self.pos = s_pos
						self.centerpos = c_pos
						self.gridpos = g_pos
						ev = Event(USEREVENT, payload={'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos, 'centerpos':c_pos, 'gridpos':g_pos})
						pygame.event.post(ev)
						#posmsg = {'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos, 'centerpos':c_pos, 'gridpos':g_pos}
						#self.servercomm.queue.put(posmsg)

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
						ev = Event(USEREVENT, payload={'msgtype': 'netgridupdate', 'client_id': senderid, 'blkgridpos': blkgridpos, 'blktype':blktype, 'data_id': dataid['gridupdate'], 'griddata':griddata})
						pygame.event.post(ev)
						#gridmsg = {'msgtype': 'netgridupdate', 'client_id': senderid, 'blkgridpos': blkgridpos, 'blktype':blktype, 'data_id': dataid['gridupdate'], 'griddata':griddata}
						#self.servercomm.queue.put(gridmsg)
						#self.gamemap.grid = newgrid
						#self.send_map()
						# logger.debug(f'gridupdate senderid:{senderid} blkgridpos={blkgridpos} blktype={blktype}')

					elif rtype == dataid.get('netbomb') or rid == 14:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} netbomb {rtype} {rid} {resp}')
						ev = Event(USEREVENT, payload={'msgtype':'netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'data_id':dataid['netbomb']})
						pygame.event.post(ev)
						#updatemsg = {'msgtype':'netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'data_id':dataid['netbomb']}
						#self.servercomm.queue.put(updatemsg)

					elif rtype == dataid.get('clientquit') or rid == 16:
						ev = Event(USEREVENT, payload={'msgtype':'clientquit', 'client_id':self.client_id})
						pygame.event.post(ev)
						#qmsg = {'msgtype':'clientquit', 'client_id':self.client_id}
						#self.servercomm.queue.put(qmsg)

					elif rtype == dataid.get('reqpos') or rid == 17:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} reqpos {rtype} {rid} {resp}')
						ev = Event(USEREVENT, payload={'msgtype':'reqpos', 'client_id':self.client_id})
						pygame.event.post(ev)
						#msg = {'msgtype':'reqpos', 'client_id':self.client_id}
						#self.servercomm.queue.put(msg)

					elif rtype == dataid.get('posupdate') or rid == 19:
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} posupdate {rtype} {rid} {resp}')
						# client sent posupdate
						ev = Event(USEREVENT, payload={'msgtype':'posupdate', 'client_id':self.client_id, 'posupdata':resp})
						pygame.event.post(ev)
						#self.servercomm.queue.put(msg)

					elif rtype == dataid.get('resetmap') or rid == 20:
						# make new mapgrid and send to all clients
						if not self.client_id or self.client_id == '0':
							s_clid = resp.get('client_id', None)
							self.client_id = s_clid
							logger.debug(f'[ {self} ] r:{len(resps)} resetmap {rtype} {rid} {resp}')
						ev = Event(USEREVENT, payload={'msgtype':'resetmap', 'client_id':self.client_id})
						pygame.event.post(ev)
						#self.servercomm.queue.put(msg)

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
		self.gamemap.grid = self.gamemap.generate_custom(gridsize=10)
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.netplayers = {}
		self.gui = gui # ServerGUI()
		self.servercomm = Servercomm()
		self.serverclock = pygame.time.Clock()

	def __str__(self):
		return f'[S] k:{self.kill} bc:{len(self.bombclients)} np:{len(self.netplayers)}'

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
					if bc.client_id != '0':
						self.gamemap.grid, bnewpos, bcgridpos = self.gamemap.placeplayer(grid=self.gamemap.grid, randpos=False, pos=bc.pos)
						bc.send_map(newgrid=self.gamemap.grid, randpos=False, refresh=True)
						for np in self.netplayers:
							if np == '0':
								break
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
					centerpos = data.get('centerpos')
					ckill = data.get('kill')
					#if clid != bc.client_id:
					np = {'client_id':clid, 'pos':pos, 'centerpos':centerpos, 'kill':ckill, 'gridpos':gridpos}
					bc.netplayers[clid] = np
					self.netplayers[clid] = np
					#elif clid == bc.client_id:
					#	logger.warning(f'[ {self} ] clid={clid} bc={bc} skipping')
					if ckill:
						# client kill flag set, kill bombclient and remove from list
						bc.kill = True
						logger.warning(f'[ {self} ] {bc} kill')
						bc.netplayers[clid]['kill'] = True
						self.netplayers[clid]['kill'] = True
			elif smsgtype == 'netplayers':
				# unused
				netplrs = data.get('netplayers')
				for np in netplrs:
					if np != '0':
						self.netplayers[np] = netplrs[np]
					else:
						logger.warning(f'netplayersmsg data={len(data)} netplrs={len(netplrs)} np={np} netp={netplrs[np]}')

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
				basegrid = self.gamemap.grid # self.gamemap.generate_custom(gridsize=SQUARESIZE)
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

	def gui_refresh(self):
		# refresh gui data
		self.gui.bombclients = self.bombclients
		for np in self.netplayers:
			if np != '0' or not self.netplayers[np]['kill']:
				self.gui.netplayers[np] = self.netplayers[np]
				for bc in self.bombclients:
					if bc.client_id != '0':
						for npbc in bc.netplayers:
							self.gui.netplayers[npbc] = bc.netplayers[npbc]
		try:
			self.gui.renderinfo()
		except Exception as e:
			logger.error(f'gui error {e}')

	def run(self):
		logger.debug(f'[ {self} ] run')
		#self.servercomm.run()
		self.gui.start()
		#self.gamemap.generate_custom(gridsize=SQUARESIZE)
		self.servercomm.start()
		fps = -1
		while not self.kill:
			serverevents = []
			if not self.queue.empty():
				serverevents.append(self.queue.get())
				self.queue.task_done()
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
						self.gui.join(timeout=1)
						logger.info(f'{self.gui} kill')
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
			self.eventhandler(serverevents)
			self.serverclock.tick(30)
			self.gui_refresh()
			# kp = False
			# # remove killed players
			# try:
			# 	self.netplayers.pop([self.netplayers.get(k) for k in self.netplayers if self.netplayers[k]['kill']][0].get('client_id'))
			# 	kp = True
			# except (KeyError, IndexError) as e:
			# 	logger.warning(f'{e}')
			for bc in self.bombclients:
				if bc.client_id != '0':
					bc.netplayers = self.netplayers
					for bcnp in bc.netplayers:
						if bcnp != '0':
							self.netplayers[bcnp] = bc.netplayers[bcnp]
					for np in self.netplayers:
						if np != '0':
							bc.netplayers[np] = self.netplayers[np]
					ev = Event(USEREVENT, payload={'msgtype':'netplayers', 'netplayers':self.netplayers})
					pygame.event.post(ev)
					#bc.servercomm.queue.put(payload)
					if pygame.time.get_ticks()-bc.lastupdate > 10000:
						bc.kill = True					
						try:
							bc.netplayers[bc.client_id]['kill'] = True
							self.netplayers[bc.client_id]['kill'] = True
						except KeyError as e:
							logger.error(f'err e:{e} bc:{bc}')
						logger.warning(f'[ {self} ] {bc} timeout')
						self.bombclients.pop(self.bombclients.index(bc))


def main():
	pygame.init()
	pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])
	mainthreads = []
	key_message = 'bomberdude'
	logger.debug(f'[bombserver] started')
	clients = 0
	gui = ServerGUI()
	server = BombServer(gui)
	server.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.conn.bind(('0.0.0.0', 9696))
	server.conn.listen()
	server.start()
	while not server.kill:
		logger.debug(f'[bombserver] {server} waiting for connection clients:{clients}')
		try:
			if server.kill:
				logger.warning(f'[bombserver] {server} server killed')
				server.conn.close()
				return
			conn, addr = server.conn.accept()
			ncmsg=Event(USEREVENT, payload={'msgtype':'newclient', 'conn':conn, 'addr':addr})
			logger.info(f'ncmsg={ncmsg}')			
			pygame.event.post(ncmsg)
		except KeyboardInterrupt as e:
			server.conn.close()
			logger.warning(f'KeyboardInterrupt:{e} server:{server}')
			for bc in server.bombclients:
				logger.warning(f'kill bc:{bc}')
				bc.kill = True
				bc.join()
			server.kill = True
			server.join()
			logger.warning(f'kill server:{server}')
			break



if __name__ == '__main__':
	logger.info('start')
	main()
	logger.info('done')
	sys.exit(0)
