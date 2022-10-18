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
from constants import FPS, DEFAULTFONT, BLOCK,SQUARESIZE
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
		logger.info(f'{self} init')

	def __str__(self):
		return f'[sender clid={self.client_id} count={self.sendcount} sq:{self.queue.qsize()}]'

	def run(self):
		logger.info(f'{self} run')
		while not self.kill:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			if not self.queue.empty():
				conn, payload = self.queue.get()
				self.queue.task_done()
				# logger.debug(f'{self} senderthread sending payload:{payload}')
				try:
					# send_data(conn, payload={'msgtype':'bcnetupdate', 'payload':payload})
					send_data(conn, payload)
					self.sendcount += 1
				except (BrokenPipeError, ConnectionResetError) as e:
					logger.error(f'{self} senderr {e}')
					self.kill = True
					break				

class Servercomm(Thread):
	# forward messages from clients to server
	def __init__(self):
		Thread.__init__(self, daemon=True)
		self.kill = False
		self.netplayers = {}
		self.srvcount = 0
		logger.debug(self)

	def __str__(self):
		return f'[scomm count={self.srvcount} np={len(self.netplayers)} ]'


class BombClientHandler(Thread):
	def __init__(self, conn=None, addr=None, gamemap=None, npos=None, ngpos=None):
		Thread.__init__(self, daemon=True)
		self.queue = Queue()
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = gen_randid()
		self.kill = False
		self.conn = conn
		self.addr = addr
		self.pos = npos
		self.gridpos = ngpos
		self.score = 0
		self.hearts = 0
		self.bombpower = 0
		self.gotpos = False
		self.gotmap = False
		self.clidset = False
		self.centerpos = (0,0)
		self.gamemap = gamemap
		self.start_time = pygame.time.get_ticks()
		self.lastupdate = self.start_time
		self.maxtimeout = 9000
		self.bchtimer = pygame.time.get_ticks()-self.start_time
		self.sender = Sender(client_id=self.client_id)
		self.netplayers = {}
		logger.debug(self)

	def __str__(self):
		return f'[BCH {self.client_id} t:{pygame.time.get_ticks()-self.start_time} l:{self.lastupdate} timer:{self.bchtimer} sq:{self.queue.qsize()} sqs:{self.sendq.qsize()} sender={self.sender}]'

	def set_pos(self, pos=None, gridpos=None):
		# called when server generates new map and new player position
		self.pos = pos
		self.gridpos = gridpos
		posmsg = {'msgtype':'s_pos', 'client_id':self.client_id, 'pos':self.pos, 'newpos':pos, 'newgridpos':gridpos, 'griddata':self.gamemap.grid, 'bchtimer':self.bchtimer}
		self.sender.queue.put((self.conn, posmsg))
		logger.info(f'{self} set_pos newpos={pos} ngp={gridpos}')

	def posupdate(self, data):
		logger.error(f'{self} posupdate data={data} mypos={self.pos}')

	def quitplayer(self, quitter):
		# when player quits or times out
		logger.info(f'{self} quitplayer quitter:{quitter}')
		if quitter == self.client_id:
			self.kill = True
			self.sender.kill = True
			self.conn.close()

	def send_gridupdate(self, blkpos, blktype, bclid):
		payload = {'msgtype': 's_netgridupdate', 'client_id':self.client_id, 'blkgridpos':blkpos, 'blktype':blktype, 'bclid':bclid, 'bchtimer':self.bchtimer}
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
			logger.info(f'sending map to {self.client_id} sendq={self.sendq.qsize()} ')
		else:
			logger.warning(f'already gotmap sendq={self.sendq.qsize()} ')
		payload = {'msgtype':'s_grid', 'gamemapgrid':self.gamemap.grid, 'newpos': self.pos, 'newgridpos':self.gridpos, 'bchtimer':self.bchtimer}
		# logger.debug(f'{self} send_map payload={len(payload)} randpos={randpos}')
		self.sender.queue.put((self.conn, payload))

	def gridupdate(self, data):
		# when client send update after bomb explosion
		logger.debug(f'griddata:{len(data)}')
		self.sender.queue.put((self.conn, data))

	def bombevent(self, data):
		# when client sends bomb
		logger.debug(f'sending bombevent bomber:{data.get("client_id")} pos:{data.get("bombpos")} {data.get("bombgridpos")} data={data}')
		self.sender.queue.put((self.conn, data))

	def set_client_id(self):
		# send client id to remote client
		if not self.clidset:
			payload = {'msgtype':'bcsetclid', 'client_id':self.client_id}
			self.sender.queue.put((self.conn, payload))
			logger.debug(f'{self} sent payload:{payload}')
			self.clidset = True
		else:
			logger.warning(f'{self} clid already set:{self.client_id}')

	def run(self):
		self.set_client_id()
		logger.debug(f'{self}  run ')
		# self.sender.start()
		while not self.kill:
			if self.kill or self.sender.kill:
				logger.debug(f'{self} killed sender={self.sender}')
				self.sender.kill = True
				self.sender.join(timeout=1)
				logger.debug(f'{self} killed sender={self.sender} killed')
				self.kill = True
				self.conn.close()
				logger.debug(f'{self} killed sender={self.sender} {self.conn} closed')
				break


			msgtype = None
			incoming_data = None
			try:
				incoming_data = receive_data(self.conn)
				# logger.debug(f'{self} rid:{rid} resp:{resp}')
			except (ConnectionResetError, BrokenPipeError, struct.error, EOFError, OSError) as e:
				logger.error(f'{self} receive_data error:{e}')
				self.conn.close()
				self.kill = True
				break
			if incoming_data:
				# if len(incoming_data) >= 5:
				# 	logger.warning(f'incoming_data oversize {len(incoming_data)} t={type(incoming_data)}')
				# 	logger.info(f'r0={incoming_data[0]}')
				# 	logger.info(f'r-1={incoming_data[:-1]}')
					#resps = resps[0]
				self.bchtimer = pygame.time.get_ticks()-self.start_time
				for resp in incoming_data:
					self.lastupdate = pygame.time.get_ticks()
					try:
						msgtype = resp.get('msgtype')
					except AttributeError as e: 
						logger.error(f'AttributeError {e} resp={resp}')
						break
					# logger.debug(f'resps={len(resps)} rid={rid} resp={resp}')
					#if msgtype == 'info':						
					#	pygame.event.post(Event(USEREVENT, payload={'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'gridpos':self.gridpos, 'score':self.score, 'hearts':self.hearts, 'bombpower': self.bombpower}))						
					if msgtype == 'cl_playerpos':
						# logger.debug(f'{self} {rid} {resp}')
						clid = resp.get('client_id', None)
						if clid:
							self.client_id = clid
						else:
							logger.warning(f'incomplete resp:{resp}')
							self.set_client_id()
							return
						pos = resp.get('pos')
						if pos:
							self.pos = pos
						else:
							logger.warning(f'incomplete resp:{resp}')
							return
						self.gotmap = resp.get('gotmap')
						self.gotpos = resp.get('gotpos')
						#logger.debug(f'resp={resp}')
						self.gridpos = resp.get('gridpos')
						if self.client_id:
							pygame.event.post(Event(USEREVENT, payload={'msgtype':'playerpos', 'client_id':self.client_id, 'posdata':resp, 'bchtimer':self.bchtimer}))
						else:
							logger.warning(f'no client_id in resp:{resp}')

					elif msgtype == 'gridupdate':
						# new grid and send update to clients
						#senderid = resp.get('client_id', None)
						blkgridpos = resp.get('blkgridpos', None)
						blktype = resp.get('blktype', None)
						#griddata = resp.get('griddata')
						self.gamemap.grid[blkgridpos[0]][blkgridpos[1]] = {'blktype':blktype, 'bomb':False}
						pygame.event.post(Event(USEREVENT, payload={'msgtype': 'netgridupdate', 'gridupdate': resp, 'bchtimer':self.bchtimer}))

					elif msgtype == 'cl_bombdrop':
						bx,by = resp.get('bombgridpos', None)
						self.gamemap.grid[bx][by] = {'blktype':11, 'bomb':True}
						pygame.event.post(Event(USEREVENT, payload={'msgtype':'bc_netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'bombgridpos':resp.get('bombgridpos'), 'bombpower':resp.get('bombpower'), 'bchtimer':self.bchtimer}))

					elif msgtype == 'clientquit':
						ev = Event(USEREVENT, payload={'msgtype':'clientquit', 'client_id':self.client_id, 'bchtimer':self.bchtimer})
						pygame.event.post(ev)

					elif msgtype == 'cl_reqpos':
						pygame.event.post(Event(USEREVENT, payload={'msgtype':'cl_reqpos', 'client_id':self.client_id, 'bchtimer':self.bchtimer}))

					elif msgtype == 'posupdate':
						# client sent posupdate
						ev = Event(USEREVENT, payload={'msgtype':'posupdate', 'client_id':self.client_id, 'posupdata':resp, 'bchtimer':self.bchtimer})
						pygame.event.post(ev)

					elif msgtype == 'resetmap':
						# make new mapgrid and send to all clients
						pygame.event.post(Event(USEREVENT, payload={'msgtype':'resetmap', 'client_id':self.client_id, 'bchtimer':self.bchtimer}))

					elif msgtype == 'maprequest':
						pygame.event.post(Event(USEREVENT, payload={'msgtype':'maprequest', 'client_id':self.client_id, 'gridsize':resp.get('gridsize'), 'bchtimer':self.bchtimer}))
						#self.send_map()

					elif msgtype == 'refreshsgrid':
						logger.warning(f'refreshsgrid rid={msgtype} resp={resp}')
						# self.send_map()

					elif msgtype == 'auth':
						logger.debug(f'{self} r:{len(incoming_data)} auth received id:{msgtype} resp={resp}')
						clid = resp.get('client_id', None)
						self.client_id = clid

					elif msgtype == 'UnpicklingError':
						logger.warning(f'{self} r:{len(incoming_data)} UnpicklingError rid:{msgtype}')
					else:
						if resp:
							logger.warning(f'{self} r:{len(incoming_data)} unknownevent rid:{msgtype} resp={resp}')
						else:
							pass


class BombServer(Thread):
	def __init__(self, gui=None):
		Thread.__init__(self, daemon=False)
		self.bombclients = []
		self.gamemap = Gamemap()
		self.gamemap.grid = self.gamemap.generate_custom(gridsize=15)
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.serverclock = pygame.time.Clock()
		self.netplayers = {}

	def __str__(self):
		return f'[S] k:{self.kill} bc:{len(self.bombclients)} '

	def eventhandler(self, serverevent):
		try:
			smsgtype = serverevent.get('msgtype')
		except AttributeError as e:
			logger.error(f'eventhandler AttributeError:{e} data:{serverevent}')
		if smsgtype == 'tuiquit':
			logger.info(f'tuiquit data={serverevent}')
			self.kill = True
			self.conn.close()
			pygame.quit()
		elif smsgtype == 'newclient':
			# logger.debug(f'{self} q: {data}')
			conn = serverevent.get('conn')
			addr = serverevent.get('addr')
			# clid = data.get('clid')
			#srvcomm = Servercomm(serverqueue=self.queue)
			basegrid, npos, ngpos = self.gamemap.placeplayer(grid=self.gamemap.grid, randpos=True)
			self.gamemap.grid = basegrid
			newbc = BombClientHandler(conn=conn, addr=addr, gamemap=self.gamemap, npos=npos, ngpos=ngpos)
			newbc.sender.start()
			newbc.start()
			#newbc.start()
			newbc.set_pos(pos=npos, gridpos=ngpos)
			newbc.gamemap.grid = self.gamemap.grid
			self.bombclients.append(newbc)
			for bc in self.bombclients:
				if bc.client_id:
					for np in self.netplayers:
						if self.netplayers[np]['client_id']:
							bc.netplayers[np] = self.netplayers[np]
							bc.netplayers[np]['src'] = 'scnp'
					for np in bc.netplayers:
						if bc.netplayers[np]['client_id']:
							self.netplayers[np] = bc.netplayers[np]
							bc.netplayers[np]['src'] = 'bcscnp'
			logger.debug(f'{self} new player:{newbc} cl:{len(self.bombclients)}')
		elif smsgtype == 'playerpos':
			for bc in self.bombclients:
				if not serverevent.get('client_id') or not serverevent.get('posdata'):
					logger.warning(f'incomplete data={serverevent}')
					return
				else:
					pdata = serverevent.get('posdata')
					clid = pdata.get('client_id')
					pos = pdata.get('pos')
					gridpos = pdata.get('gridpos')
					ckill = pdata.get('kill')
					hearts = pdata.get('hearts')
					bombpower = pdata.get('bombpower')
					score = pdata.get('score')
					cl_timer = pdata.get('cl_timer')
					#if clid != bc.client_id:
					np = {'src':'net','client_id':clid, 'pos':pos, 'kill':ckill, 'gridpos':gridpos, 'hearts':hearts, 'score':score,'bombpower':bombpower, 'cl_timer':cl_timer}
					bc.netplayers[clid] = np
					#self.netplayers[clid] = np
					#elif clid == bc.client_id:
					#	logger.warning(f'{self} clid={clid} bc={bc} skipping')
					if ckill:
						# client kill flag set, kill bombclient and remove from list
						bc.kill = True
						logger.warning(f'{self} {bc} kill')
						bc.netplayers[clid]['kill'] = True
						self.netplayers[clid]['kill'] = True
		elif smsgtype == 'netplayers':
			# unused
			netplrs = serverevent.get('netplayers')
			for np in netplrs:
				self.netplayers[np] = netplrs[np]
				# if np != '0':
				# 	self.netplayers[np] = netplrs[np]
				# else:
				# 	logger.warning(f'netplayersmsg data={len(data)} netplrs={len(netplrs)} np={np} netp={netplrs[np]}')
		elif smsgtype == 'bc_netbomb':
			logger.debug(f'netbomb serverevent={serverevent}')
			for bc in self.bombclients:
				# inform all clients about bomb
				bc.bombevent(serverevent)
		elif smsgtype == 'netgrid':
			self.gamemap.grid = serverevent.get('gamemapgrid')
			# logger.debug(f'{self} netgrid {len(data)}')
			for bc in self.bombclients:
				bc.gridupdate(serverevent)
		elif smsgtype == 'clientquit':
			# inform all clients about client quit
			logger.debug(f'{self} quit {serverevent}')
			quitter = serverevent.get('client_id')
			for bc in self.bombclients:
				bc.quitplayer(quitter)
		elif smsgtype == 'cl_reqpos':
			clid = serverevent.get('client_id')
			logger.debug(f'{self} smsgtype={smsgtype} from {clid} data={serverevent}')
			for bc in self.bombclients:
				if bc.client_id == clid:
					bc.posupdate(serverevent)
		elif smsgtype == 'netgridupdate':
			updated = serverevent.get('gridupdate')
			blkpos = updated.get('blkgridpos')
			blktype = updated.get("blktype")
			bclid = updated.get('client_id')
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
				clid = serverevent.get('client_id')
				logger.info(f'{self} resetmap from {clid} data={serverevent}')
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
			clid = serverevent.get('client_id')
			if not clid:
				logger.error(f'no client id data={serverevent}')
				return
			gz = serverevent.get('gridsize')
			if not gz:
				logger.error(f'{self} no gz data={serverevent}')
				return
			logger.info(f'{self} resetmap from {clid} gz={gz} data={serverevent}')
			basegrid = self.gamemap.generate_custom(gridsize=gz)
			#self.gamemap.grid = basegrid
			for bc in self.bombclients:
				# logger.debug(f'{self} sending newgrid to {bc}')
				bcg, bnewpos, newgridpos = self.gamemap.placeplayer(grid=basegrid, pos=bc.pos, randpos=True)
				bc.pos = bnewpos
				bc.gridpos = newgridpos
				bc.set_pos(pos=bc.pos, gridpos=bc.gridpos)
				bc.gamemap.grid = bcg
				bc.send_map()
				self.gamemap.grid = bcg
				logger.debug(f'{self} done sending newgrid to {bc}')
		else:
			logger.warning(f'{self} data={serverevent}')

	def run(self):
		logger.debug(f'{self} run')
		while not self.kill:
			if not self.queue.empty():
				self.eventhandler(self.queue.get())
				try:
					self.queue.task_done()
				except ValueError as e:
					logger.warning(f'{self} queue.task_done err {e}')
			events = pygame.event.get()
			for event in events:
				if event.type == pygame.KEYDOWN:
					logger.info(f'{len(events)} event={event}')
				if event.type == pygame.QUIT:
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
					os._exit(0)
				elif event.type == pygame.USEREVENT:
					self.eventhandler(event.payload)
				elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, 32786, 32777, 772, 32768, 1027, 32775, 32774, 32770, 32785, 4352,32776, 32788,32783,32784,32788]:
					pass
				else:
					logger.warning(f'event={event}')
			#self.netplayers.pop([self.netplayers.get(k) for k in self.netplayers if self.netplayers[k]['kill']][0].get('client_id'))
			
			self.serverclock.tick(FPS)
			# kp = False
			# try:
			# 	self.netplayers.pop([self.netplayers.get(k) for k in self.netplayers if self.netplayers[k]['kill']][0].get('client_id'))
			# 	kp = True
			# except (KeyError, IndexError) as e:
			# 	logger.warning(f'{e}')
			for bc in self.bombclients:
				if bc.client_id:
					if pygame.time.get_ticks()-bc.lastupdate > bc.maxtimeout:
						bc.kill = True
						logger.warning(f'{bc} killtimeout')
						for bc in self.bombclients:
							try:
								bc.netplayers[bc.client_id]['kill'] = True
								bc.netplayers[bc.client_id]['kill'] = True
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
							bc.netplayers.pop(k.get('client_id'))
						except KeyError as e:
							pass
							#logger.warning(f'KeyError e:{e} bc:{bc} k:{k}')
							#break
						# logger.debug(f'dnp={len(deadnps)} {bc} popped {k}')
			for bc in self.bombclients:
				if bc.client_id:
					bc.netplayers = self.netplayers
					for np in self.netplayers:
						if not self.netplayers[np]['kill']:
							bc.netplayers[np] = self.netplayers[np]
					# for bcnp in bc.netplayers:
					# 	if bcnp != '0' and not bc.netplayers[bcnp]['kill']:
					# 		self.netplayers[bcnp] = bc.netplayers[bcnp]
			
			pygame.event.post(Event(USEREVENT, payload={'msgtype':'netplayers', 'netplayers':self.netplayers}))

class ServerTUI(Thread):
	def __init__(self, server):
		Thread.__init__(self, daemon=False)
		self.server = server
		self.kill = False
	
	def get_serverinfo(self):
		logger.info(f'server={self.server} clients={len(self.server.bombclients)} ')
		logger.info(f'------bombclients------')
		for bc in self.server.bombclients:
			logger.debug(f'[bc] {bc}')
			for np in bc.netplayers:
				logger.info(f'\t[np] {np} {bc.netplayers[np]}')
		
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
					#quitevent=Event(USEREVENT, payload={'msgtype':'tuiquit'})
					pygame.event.post(Event(pygame.QUIT))
					break
			except KeyboardInterrupt:
				self.kill = True
				break


def main():
	pygame.init()
	pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])
	logger.debug(f'[bombserver] started')
	clients = 0
	server = BombServer()
	tui = ServerTUI(server)
	server.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.conn.bind(('0.0.0.0', 9696))
	server.conn.listen()
	tui.start()
	server.start()
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
