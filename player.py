import socket
import time
from threading import Thread
from queue import Queue
import re
import json
import pygame
from loguru import logger
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import spritecollide, Sprite, Group
from constants import BLOCK, USEREVENT, USEREVENT, PKTHEADER, FORMAT
from globals import gen_randid, BlockNotFoundError, RepeatedTimer
from map import Gamemap
from network import Sender,  send_data, Receiver


class ReceiverError(Exception):
	pass

class NewPlayer(Thread, Sprite):
	def __init__(self, image, serveraddress='127.0.0.1', testmode=False, rh=None):
		Thread.__init__(self, daemon=True, name='NewPlayerThread')
		Sprite.__init__(self)
		self.rh = rh
		self.gridpos = None # (0,0) #gridpos
		self.pos = None # (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		self.image = image
		self.rect = self.image.get_rect()
		self.client_id = f'np:{gen_randid()}'
		self.kill = False
		self.connected = False
		self.serveraddress = serveraddress
		self.receiver_t = Thread(target=self.receiver, daemon=True)
		self.receiverq = Queue()
		self.send_queue = Queue()
		self.msg_queue = Queue()
		self.grid = []
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.attempts = 0
		self.testmode = testmode
		self.sendcounter = 0
		self.recvcounter = 0
		self.runcounter = 0
		self.lastpktid = ''
		self.gotgrid = False
		self.gotpos = False # todo imkplement, get gridpos from server
		self.playerlist = {}
		self.cl_needgridcounter = 0
		self.bombsleft = 3
		self.health = 100
		self.updatetimer = RepeatedTimer(interval=1, function=self.playertimer)
		self.updcntr = 0
		self.score = 0
		# self.rect.x = self.pos[0]
		# self.rect.y = self.pos[1]


	def __repr__(self) -> str:
		return f'NewPlayer ({self.client_id} pos:{self.pos} b:{self.bombsleft} h:{self.health} upc: {self.updcntr} sq:{self.send_queue.qsize()} s:{self.sendcounter} r:{self.recvcounter} pl:{len(self.playerlist)}'

	def do_testing(self):
		pass

	def playertimer(self):
		if not self.connected:
			pass
			# logger.warning(f'{self} not connected')
		else:
			self.updcntr += 1
			payload = {'msgtype' : 'playertimer'}
			# self.do_send(payload)
			self.send_queue.put(payload)
			if not self.gotgrid:
				logger.warning(f'{self.client_id} playertimer needgrid ')
			if not self.gotpos:
				logger.warning(f'{self.client_id} playertimer needpos ')

	def do_send(self, payload):
		if not self.connected:
			logger.error(f'{self} notconnected p: {payload}')
			return
		payload['updcntr'] = self.updcntr
		payload['client_id'] = self.client_id
		payload['pos'] = self.pos
		payload['bombsleft'] = self.bombsleft
		payload['health'] = self.health
		payload['gridpos'] = self.gridpos
		payload['gotgrid'] = self.gotgrid
		payload['gotpos'] = self.gotpos
		payload['sendqsize'] = self.send_queue.qsize()
		self.lastpktid = gen_randid()
		payload['c_pktid'] = self.lastpktid
		payload['score'] = self.score
		payload = json.dumps(payload).encode('utf8')
		msglen = str(len(payload)).encode('utf8').zfill(PKTHEADER)
		self.socket.sendto(msglen,(self.serveraddress, 9696))
		# logger.debug(f'playerdosendpayload {outmsgtype} lenx:{msglenx} {len(payload)} c_pktid: {self.lastpktid}')
		self.socket.sendto(payload,(self.serveraddress, 9696))

	def receiver(self):
		if not self.connected:
			logger.warning(f'{self} not connected')
			# return
		logger.debug(f'[r] rqs:{self.receiverq.qsize()} waiting for packet on socket: {self.socket}')
		while True:
			if self.kill:
				logger.warning(f'{self} receiver kill')
				break
			while self.connected:
				try:
					replen = self.socket.recv(PKTHEADER).decode('utf8')
				except ConnectionAbortedError as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					break
				except Exception as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					raise ReceiverError(e)
				try:
					datalen = int(re.sub('^0+','',replen))
				except ValueError as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					# raise ReceiverError(e)
				except Exception as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					raise ReceiverError(e)
				# logger.debug(f'[r] datalen: {datalen}')
				try:
					response = self.socket.recv(datalen).decode('utf8')
				except ConnectionAbortedError as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					break
				except OSError as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					break
				except Exception as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					raise ReceiverError(e)
				try:
					response = re.sub('^0+','', response)
					jresp = json.loads(response)
					# logger.debug(f'[r] {jresp.get("msgtype")} rqs:{self.receiverq.qsize()} dl: {datalen} r: {len(response)} jr:{len(jresp)}')
					self.receiverq.put(jresp)
				except json.decoder.JSONDecodeError as e:
					logger.error(f'[r] {e} {type(e)} response: {response}')
					self.gotgrid = False
					self.gotpos = False
					# self.kill = True
					# raise ReceiverError(e)
				except Exception as e:
					logger.error(f'[r] {e} {type(e)}')
					self.kill = True
					raise ReceiverError(e)
	def doconnect(self):
		logger.info(f'doconnect ')
		c_cnt = 0
		while not self.connected:
			logger.info(f'doconnect c_cnt: {c_cnt}')
			if c_cnt >= 10:
				logger.error(f'{self} doconnect {c_cnt}')
				self.kill = True
				break
			try:
				self.socket.connect((self.serveraddress, 9696))
				self.connected = True
				logger.info(f'{self} connected c_cnt: {c_cnt}')
				break
			except Exception as e:
				logger.error(f'{self} doconnect {e} {type(e)} {c_cnt}')
				time.sleep(1)

	def run(self):
		logger.info(f'{self} run ')
		self.doconnect()
		# try:
		# 	self.socket.connect((self.serveraddress, 9696))
		# 	self.connected = True
		# 	logger.info(f'{self} connected maxretries: {maxretries}')
		# except Exception as e:
		# 	logger.error(f'{e} {type(e)} {maxretries}')
		# 	time.sleep(1)
		# 	self.connected = False
		self.receiver_t.start()
		logger.info(f'{self} receiver_t start ')
		while not self.kill:
			if not self.receiverq.empty():
				jresp = self.receiverq.get()
				self.receiverq.task_done()
				self.msg_handler(jresp)
			if not self.send_queue.empty():
				data = self.send_queue.get()
				self.send_queue.task_done()
				# self.socket.sendto(data,(self.serveraddress, 9696))
				try:
					self.do_send(data)
				except BrokenPipeError as e:
					logger.error(f'{self} senderror {e} data: {data}')
				self.runcounter += 1
				# logger.debug(f'sendqdata: {data}')

	def msg_handler(self, jresp):
		# logger.debug(f'jresp:\n {jresp}\n')
		msgtype = jresp.get('msgtype')
		match msgtype:
			case 'sv_playerlist': # server sent playerlist
				self.playerlist = jresp.get('playerlist')
				newscore = self.playerlist[self.client_id].get('score') # get our score
				if self.score != newscore:
					self.score = newscore
					logger.info(f'{msgtype} score:{self.score}')

			case 'sv_gridupdate': # todo do some checking here
				newgrid = jresp.get('grid')
				owngridchk = sum([sum(k) for k in self.grid])
				newgridchk = sum([sum(k) for k in newgrid])
				self.grid = newgrid
				pygame.event.post(pygame.event.Event(USEREVENT, payload={'msgtype': 'sv_gridupdate', 'grid':self.grid}))
				if newgridchk != owngridchk: # todo
					logger.warning(f'{msgtype} {owngridchk} {newgridchk}')
			case 'ackplrbmb':
				bomb_clid = jresp.get('data').get('client_id')
				clbombpos = jresp.get('data').get('clbombpos')
				if bomb_clid != self.client_id: # not a bomb from me...
					pass
					# logger.info(f'{self} otherplayerbomb {msgtype} from {bomb_clid} bombpos: {clbombpos}')
				elif bomb_clid == self.client_id: # my bomb
					# logger.info(f'{self} ownbomb {msgtype} bombpos: {clbombpos}')
					self.bombsleft -= 1
				else:
					logger.warning(f'{self} bomberclientid! {msgtype} jresp: {jresp}')
				pygame.event.post(pygame.event.Event(USEREVENT, payload={'msgtype': 'ackplrbmb', 'client_id': bomb_clid, 'clbombpos': clbombpos}))
			case 'newgridresponse':
				grid = jresp.get('grid')
				if grid:
					self.gotgrid = True
					self.grid = grid
					logger.info(f'gotgrid {self.gotgrid} {msgtype} ')
					pygame.event.post(pygame.event.Event(USEREVENT, payload={'msgtype': 'newgridfromserver', 'grid':self.grid}))
				else:
					logger.warning(f'nogrid in {jresp}')
				newpos = jresp.get('setpos')
				if newpos:
					self.gotpos = True
					self.gridpos = newpos
					self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
					self.rect.x = self.pos[0]
					self.rect.y = self.pos[1]
					logger.info(f'gotpos {msgtype} newpos: {newpos} {self.gridpos} {self.pos}')
				else:
					logger.warning(f'missing setpos from {jresp}')

			case 'serveracktimer' |  'trigger_newplayer':
				# logger.debug(f'{self} {msgtype} {jresp}')
				# playerlist = None
				# data = jresp.get('data')
				playerlist = jresp.get('playerlist', None)
				self.playerlist = playerlist
				if not self.gotgrid:
					grid = jresp.get('grid')
					if grid:
						self.gotgrid = True
						self.grid = grid
						logger.info(f'gotgrid {self.gotgrid} {msgtype} ')
						pygame.event.post(pygame.event.Event(USEREVENT, payload={'msgtype': 'newgridfromserver', 'grid':self.grid}))
					else:
						logger.warning(f'nogrid in {jresp}')
				if not self.gotpos:
					newpos = jresp.get('setpos')
					if newpos:
						self.gotpos = True
						self.gridpos = newpos
						self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
						self.rect.x = self.pos[0]
						self.rect.y = self.pos[1]
						logger.info(f'gotpos {msgtype} newpos: {newpos} {self.gridpos} {self.pos}')
					else:
						logger.warning(f'missing setpos from {jresp}')
			case _:
				logger.warning(f'missingmsgtype jresp: {jresp} ')

	def update(self):
		pass

	def draw(self, screen):
		if not self.gotpos:
			logger.warning(f'needposfromserver')
			return
		if not self.gotgrid:
			logger.warning(f'needgridfromserver')
			return
		screen.blit(self.image, self.rect)
		for player in self.playerlist:
			plconn = self.playerlist.get(player).get('connected')
			if player == 'null':
				logger.warning(f'player: {player} plconn: {plconn} \nplayerlist: {self.playerlist}')
				# break
			else:
				plid = self.playerlist.get(player).get('client_id')
				pos = self.playerlist.get(player).get('pos')
				gridpos = self.playerlist.get(player).get('gridpos')
				# gridpos = (pos[0] * BLOCK, pos[1] * BLOCK)
				if not pos:
					logger.warning(f'player: {player} plconn: {plconn}  playerlist: {self.playerlist}')
					break
				if pos:
					if self.client_id != plid:
						npimg = self.rh.get_image('data/netplayer.png')
						try:
							screen.blit(npimg, pos)
						except Exception as e:
							logger.error(f'{self} {e} {type(e)} pos: {pos} plconn: {plconn}  playerlist: {self.playerlist} player: {type(player)} {player}')
					elif self.client_id == plid:
						pass
					else:
						logger.warning(f'{self} pliderror! plconn: {plconn} ')
						npimg = self.rh.get_image('data/dummyplayer.png')
						screen.blit(npimg, pos)


	def sendbomb(self):
		payload = {'msgtype' : 'cl_playerbomb','action': 'playerbomb', 'clbombpos': self.gridpos}
		self.send_queue.put(payload)

	def move(self, action): # todo decide on to check grid or use spritecollide....
		if not self.gotgrid:
			logger.warning(f'{self} move {action} nogrid')
			return
		if not self.gotpos:
			logger.warning(f'{self} move {action} nopos')
			return
		gpx, gpy = self.gridpos
		newgridpos = [gpx, gpy]
		if action == 'u':
			if self.grid[gpx][gpy-1] in [2,40,44]:
				newgridpos = [gpx, gpy-1]
			else:
				logger.warning(f'cannot move {action} from {self.gridpos} to {[gpx, gpy-1]} gridval: {self.grid[gpx][gpy-1]}')
				newgridpos = [gpx, gpy]
				return
		elif action == 'd':
			if self.grid[gpx][gpy+1] in [2,40,44]:
				newgridpos = [gpx, gpy+1]
			else:
				logger.warning(f'cannot move {action} from {self.gridpos} to {[gpx, gpy+1]} gridval: {self.grid[gpx][gpy+1]}')
				newgridpos = [gpx, gpy]
				return
		elif action == 'l':
			if self.grid[gpx-1][gpy] in [2,40,44]:
				newgridpos = [gpx-1, gpy]
			else:
				logger.warning(f'cannot move {action} from {self.gridpos} to {[gpx-1, gpy]} gridval: {self.grid[gpx-1][gpy]}')
				newgridpos = [gpx, gpy]
				return
		elif action == 'r':
			if self.grid[gpx+1][gpy] in [2,40,44]: # else [gpx, gpy]
				newgridpos = [gpx+1, gpy]
			else:
				logger.warning(f'cannot move {action} from {self.gridpos} to {[gpx+1, gpy]} gridval: {self.grid[gpx+1][gpy]}')
				newgridpos = [gpx, gpy]
				return
		else:
			logger.warning(f'{self} move {action} not implemented')
		self.gridpos = newgridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		payload = {'msgtype' : 'cl_playermove', 'action': action}
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]
		self.send_queue.put(payload)
		# logger.info(f'{self} move {action} gridpos: {self.gridpos} pos: {self.pos}')

