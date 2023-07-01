#!/usr/bin/python
import os
import socket
import struct
import sys
from threading import Thread

import pygame
from loguru import logger
from pygame.event import Event

from constants import (BLOCK, DEFAULTFONT, FPS, SENDUPDATEEVENT, SERVEREVENT,
                       SQUARESIZE)
from globals import gen_randid
from map import Gamemap
from network import Sender, receive_data, send_data


class BombClientHandler(Thread):
	def __init__(self, conn=None, addr=None,  npos=None, ngpos=None):
		Thread.__init__(self, daemon=True)
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
		self.lastupdate = 0
		self.maxtimeout = 100
		self.bchtimer = pygame.time.get_ticks()
		self.sender = Sender(client_id=self.client_id, s_type='bch')
		logger.debug(self)

	def __str__(self):
		return f'[BCH {self.client_id} ]'

	def send_event(self, serverevent):
		self.sender.queue.put((self.conn, serverevent))

	def send_netupdate(self, netplayers, grid):
		self.sender.queue.put((self.conn, {'msgtype':'s_netplayers', 'netplayers':netplayers}))

	def set_pos(self, pos=None, gridpos=None, grid=None):
		# called when server generates new map and new player position
		self.pos = pos
		self.gridpos = gridpos
		posmsg = {'msgtype':'s_pos', 'client_id':self.client_id, 'pos':self.pos, 'gridpos':self.gridpos, 'bchtimer':self.bchtimer, 'grid':grid}
		self.sender.queue.put((self.conn, posmsg))
		logger.info(f'{self} set_pos {self.pos} g={self.gridpos}')


	def quitplayer(self, quitter):
		# when player quits or times out
		logger.info(f'{self} quitplayer quitter:{quitter}')
		if quitter == self.client_id:
			self.kill = True
			self.sender.kill = True
			self.conn.close()

	def send_gridupdate(self, blkpos, blktype, bclid):
		payload = {'msgtype': 's_netgridupdate', 'client_id':self.client_id, 'blkgridpos':blkpos, 'blktype':blktype, 'bclid':bclid, 'bchtimer':self.bchtimer}
		# if bclid != self.client_id:
		# 	logger.info(f'{self.client_id} bclid={bclid} sending gridupdate blkpos={blkpos} blktype={blktype}')
		# elif bclid == self.client_id:
		# 	pass
		# 	#logger.warning(f'{self.client_id} bclid={bclid} sending gridupdate to self blkpos={blkpos} blktype={blktype}')
		# logger.info(f'send_gridupdate {self.client_id} bclid={bclid} blkpos={blkpos} blktype={blktype}')
		self.sender.queue.put((self.conn, payload))

	def send_map(self, grid):
		# send mapgrid to player
		if not self.gotmap:
			logger.info(f'sending map to {self.client_id}')
		else:
			logger.warning(f'already gotmap')
		payload = {'msgtype':'s_grid', 'grid':grid, 'pos': self.pos, 'gridpos':self.gridpos, 'bchtimer':self.bchtimer}
		# logger.debug(f'{self} send_map payload={len(payload)}')
		self.sender.queue.put((self.conn, payload))

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
				for resp in incoming_data:
					try:
						msgtype = resp.get('msgtype')
						in_pktid = resp.get('pktid')
					except AttributeError as e: 
						logger.error(f'AttributeError {e} resp={resp}')
						break
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
							pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'playerpos', 'client_id':self.client_id, 'posdata':resp, 'bchtimer':self.bchtimer}))
						else:
							logger.warning(f'no client_id in resp:{resp}')

					elif msgtype == 'cl_gridupdate':
						# new grid and send update to clients
						pygame.event.post(Event(SERVEREVENT, payload={'msgtype': 'cl_gridupdate', 'cl_gridupdate': resp, 'bchtimer':self.bchtimer}))

					elif msgtype == 'cl_bombdrop':
						pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'bc_netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'bombgridpos':resp.get('bombgridpos'), 'bombpower':resp.get('bombpower'), 'bchtimer':self.bchtimer}))

					elif msgtype == 'clientquit':
						ev = Event(SERVEREVENT, payload={'msgtype':'clientquit', 'client_id':self.client_id, 'bchtimer':self.bchtimer})
						pygame.event.post(ev)

					elif msgtype == 'cl_reqpos':
						pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'cl_reqpos', 'client_id':self.client_id, 'bchtimer':self.bchtimer}))

					elif msgtype == 'cl_pong':
						self.bchtimer = 0
						self.lastupdate = 0
						pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'scl_pong', 'client_id':self.client_id, 'bchtimer':self.bchtimer}))

					elif msgtype == 'posupdate':
						logger.warning(f'msgtype={msgtype} resp={resp}')
						# client sent posupdate
						# ev = Event(SERVEREVENT, payload={'msgtype':'posupdate', 'client_id':self.client_id, 'posupdata':resp, 'bchtimer':self.bchtimer})
						#pygame.event.post(ev)

					elif msgtype == 'resetmap':
						# make new mapgrid and send to all clients
						logger.warning(f'msgtype={msgtype} resp={resp}')
						# pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'resetmap', 'client_id':self.client_id, 'bchtimer':self.bchtimer}))

					elif msgtype == 'maprequest':
						pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'maprequest', 'client_id':self.client_id, 'gridsize':resp.get('gridsize'), 'bchtimer':self.bchtimer}))
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
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.serverclock = pygame.time.Clock()
		self.netplayers = {}

	def __str__(self):
		return f'[S] k:{self.kill} bc:{len(self.bombclients)} '

	def eventhandler(self, serverevent):
		event_type = None
		try:
			event_type = serverevent.get('msgtype')
		except AttributeError as e:
			logger.error(f'eventhandler AttributeError:{e} data:{serverevent}')
		if event_type == 'tuiquit':
			logger.info(f'tuiquit data={serverevent}')
			self.kill = True
			self.conn.close()
			pygame.quit()
		elif event_type == 'newclient':
			# logger.debug(f'{self} q: {data}')
			conn = serverevent.get('conn')
			addr = serverevent.get('addr')
			# clid = data.get('clid')
			self.gamemap.grid, npos, ngpos = self.gamemap.placeplayer(grid=self.gamemap.grid)
			newbc = BombClientHandler(conn=conn, addr=addr,  npos=npos, ngpos=ngpos)
			newbc.sender.start()
			newbc.start()
			newbc.set_pos(pos=npos, gridpos=ngpos, grid=self.gamemap.grid)
			self.bombclients.append(newbc)
			logger.debug(f'{self} new player:{newbc} cl:{len(self.bombclients)}')

		elif event_type == 'playerpos':
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
				self.netplayers[clid] = np
		elif event_type == 's_netplayers':
			# unused
			netplrs = serverevent.get('netplayers')
			for np in netplrs:
				self.netplayers[np] = netplrs[np]
		elif event_type == 'scl_pong':
			for bc in self.bombclients:
				if bc.client_id == serverevent.get('client_id'):
					bc.lastupdate = 0
		elif event_type == 'bc_netbomb':
			for bc in self.bombclients:
				# inform all clients about bomb
				logger.debug(f'{event_type} sending to {bc.client_id}')
				bc.send_event(serverevent)

		elif event_type == 'netgrid':
			#self.gamemap.grid = serverevent.get('gamemapgrid')
			logger.warning(f'smsgtye={event_type} serverevent={serverevent}')

		elif event_type == 'clientquit':
			# inform all clients about client quit
			logger.debug(f'{self} quit {serverevent}')
			quitter = serverevent.get('client_id')
			for bc in self.bombclients:
				bc.quitplayer(quitter)

		elif event_type == 'cl_reqpos':
			clid = serverevent.get('client_id')
			logger.warning(f'{self} smsgtype={event_type} from {clid} data={serverevent}')

		elif event_type == 'cl_gridupdate':
			updated = serverevent.get('cl_gridupdate')
			blkpos = updated.get('blkgridpos')
			blktype = updated.get("blktype")
			bclid = updated.get('client_id')
			self.gamemap.grid[blkpos[0]][blkpos[1]] = blktype
			# logger.info(f'cl_gridupdate data={len(data)} blkpos={blkpos} blktype={blktype} grid={self.gamemap.grid[blkpos[0]][blkpos[1]]}')
			for bc in self.bombclients:
				bc.send_gridupdate(blkpos=blkpos, blktype=blktype, bclid=bclid)

		elif event_type == 'resetmap' or self.gamemap.is_empty():
			# todo fix player pos on new grid
			pass

		elif event_type == 'maprequest':
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
			for bc in self.bombclients:
				# logger.debug(f'{self} sending newgrid to {bc}')
				self.gamemap.grid, bnewpos, newgridpos = self.gamemap.placeplayer(grid=self.gamemap.grid, pos=bc.pos)
				bc.pos = bnewpos
				bc.gridpos = newgridpos
				bc.set_pos(pos=bc.pos, gridpos=bc.gridpos, grid=self.gamemap.grid)
				bc.send_map(self.gamemap.grid)
				logger.debug(f'{self} done sending newgrid to {bc}')
		else:
			logger.warning(f'{self} data={serverevent}')

	def send_update_event(self):
		for bc in self.bombclients:
			bc.sender.queue.put((bc.conn, {'msgtype':'s_ping', 'client_id':bc.client_id, 'bchtimer':bc.bchtimer}))
			if bc.client_id:
				bc.lastupdate += 1
				if bc.lastupdate > bc.maxtimeout:
					bc.kill = True
					logger.warning(f'{bc} killtimeout bc.lastupdate={bc.lastupdate} bc.maxtimeout={bc.maxtimeout}' )
					self.remove_dead_player(bc)
					self.bombclients.pop(self.bombclients.index(bc))

		for bc in self.bombclients:
			if bc.client_id:
				bc.send_netupdate(netplayers=self.netplayers, grid=self.gamemap.grid)
		# pygame.event.post(Event(SERVEREVENT, payload={'msgtype':'s_netplayers', 'netplayers':self.netplayers}))

	def remove_dead_player(self, bc):
		logger.warning(f'remove_dead_player {bc}')
		old_np = self.netplayers
		new_np = {}
		for np in self.netplayers:
			if np != bc.client_id:
				new_np[np] = old_np.get(np)
		self.netplayers = new_np

	def run(self):
		logger.debug(f'{self} run')
		
		pygame.time.set_timer(SENDUPDATEEVENT, 50)
		while not self.kill:
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
					os._exit(0)
				elif event.type == SERVEREVENT:
					self.eventhandler(event.payload)
				elif event.type == SENDUPDATEEVENT:
					self.send_update_event()
				elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, 32786, 32777, 772, 32768, 1027, 32775, 32774, 32770, 32785, 4352,32776, 32788,32783,32784,32788]:
					pass
				else:
					logger.warning(f'event={event}')
			
			self.serverclock.tick(FPS)

class ServerTUI(Thread):
	def __init__(self, server):
		Thread.__init__(self, daemon=False)
		self.server = server
		self.kill = False
	
	def get_serverinfo(self):
		logger.info(f'clients={len(self.server.bombclients)} ')
		logger.info(f'------netplayers------')
		for np in self.server.netplayers:
			logger.info(f'\t[np] {np} {self.server.netplayers[np].get("pos")}')
		logger.info(f'------bombclients------')
		for bc in self.server.bombclients:
			logger.info(f'\t[bc] {bc} sender queue = {bc.sender.queue.qsize()}')
		
	def run(self):
		while not self.kill:
			if self.kill:
				break
			try:
				cmd = input(':> ')
				if cmd[:1] == 's':
					self.get_serverinfo()
				elif cmd[:1] == 'q':
					self.kill = True
					pygame.event.post(Event(pygame.QUIT))
					break
				else:
					logger.info(f'[S] cmds: s serverinfo, q quit')
			except KeyboardInterrupt:
				self.kill = True
				break


def main():
	
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
			ncmsg=Event(SERVEREVENT, payload={'msgtype':'newclient', 'conn':conn, 'addr':addr})
			logger.info(f'ncmsg={ncmsg}')
			pygame.event.post(ncmsg)
		except (KeyboardInterrupt, OSError) as e:
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
	pygame.init()
	main()
