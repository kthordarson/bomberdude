import socket
from threading import Thread
from queue import Queue
import re
import json
import pygame
from loguru import logger
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import spritecollide, Sprite, Group
from time import sleep
from constants import BLOCK, PLAYEREVENT, PLAYERSIZE, PKTLEN, NEWGRIDEVENT,NETPLAYEREVENT, PKTHEADER
from globals import gen_randid, BlockNotFoundError, RepeatedTimer
from map import Gamemap
from network import Sender,  send_data, Receiver
HEADER = 64
FORMAT = 'utf8'
DISCONNECT_MESSAGE = 'disconnect'

class ReceiverError(Exception):
	pass

class NewPlayer(Thread, Sprite):
	def __init__(self, gridpos, image, serveraddress='127.0.0.1', testmode=False, rh=None):
		Thread.__init__(self, daemon=True)
		Sprite.__init__(self)
		self.rh = rh
		self.gridpos = gridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		self.image = image # self.rh.get_image('data/playerone.png')
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
		self.playerlist = {}
		self.cl_needgridcounter = 0
		self.updatetimer = RepeatedTimer(interval=1, function=self.playertimer)
		self.updcntr = 0
		self.gotplayerlist = False
		self.rect.x = self.pos[0]
		self.rect.y = self.pos[1]

	def __repr__(self) -> str:
		return f'NP({self.client_id} pos:{self.pos} upc: {self.updcntr} sq:{self.send_queue.qsize()} s:{self.sendcounter} r:{self.recvcounter}) pl:{len(self.playerlist)}'

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
			if not self.gotplayerlist:
				logger.warning(f'{self.client_id} playertimer needplayerlist ')

	def do_send(self, payload):
		outmsgtype = payload.get('msgtype')
		payload['updcntr'] = self.updcntr
		payload['client_id'] = self.client_id
		payload['pos'] = self.pos
		payload['gridpos'] = self.gridpos
		payload['gotgrid'] = self.gotgrid
		payload['gotplayerlist'] = self.gotplayerlist
		payload['sendqsize'] = self.send_queue.qsize()
		self.lastpktid = gen_randid()
		payload['c_pktid'] = self.lastpktid
		payload = json.dumps(payload).encode('utf8')# .zfill(PKTLEN)
		# msglen += b' ' * (PKTLEN - len(payload))
		msglen = str(len(payload)).encode('utf8').zfill(PKTHEADER)
		msglenx = str(len(payload)).encode('utf8')
		# logger.debug(f'playerdosendmsglen lenx:{msglenx} c_pktid: {self.lastpktid}')
		self.socket.sendto(msglen,(self.serveraddress, 9696))
		# logger.debug(f'playerdosendpayload {outmsgtype} lenx:{msglenx} {len(payload)} c_pktid: {self.lastpktid}')
		self.socket.sendto(payload,(self.serveraddress, 9696))

	def receiver(self):
		logger.debug(f'[r] rqs:{self.receiverq.qsize()} waiting for packet on socket: {self.socket}')
		while True:
			if self.kill:
				logger.warning(f'{self} receiver kill')
				break
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
				raise ReceiverError(e)
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
			except Exception as e:
				logger.error(f'[r] {e} {type(e)}')
				self.kill = True
				raise ReceiverError(e)
			try:
				response = re.sub('^0+','', response)
				jresp = json.loads(response)
				# logger.debug(f'[r] {jresp.get("msgtype")} rqs:{self.receiverq.qsize()} dl: {datalen} r: {len(response)} jr:{len(jresp)}')
				self.receiverq.put(jresp)
			except Exception as e:
				logger.error(f'[r] {e} {type(e)}')
				self.kill = True
				raise ReceiverError(e)
			# self.msg_handler(jresp)
		# try:
		# 	jresp = json.loads(response)
		# except json.decoder.JSONDecodeError as e:
		# 	logger.warning(f'{e} {type(e)} {type(response)}\nresp: {response}')
		# except TypeError as e:
		# 	logger.warning(f'{e} {type(e)} {type(response)}\nresp: {response}')
		# except Exception as e:
		# 	logger.error(f'{e} {type(e)} {type(response)}\nresp: {response}')
		# if jresp:
		# 	self.msg_handler(jresp)
		# 	# logger.debug(f'\n{self} resp:\n{response}\n')
		# 	# logger.debug(f'\n{self} jresp:\n{jresp}\n')
		# else:
		# 	logger.error(f'no jresp from {response}')

	def run(self):
		try:
			self.socket.connect((self.serveraddress, 9696))
		except OSError as e:
			raise e
		self.receiver_t.start()
		self.connected = True
		while not self.kill:
			if not self.receiverq.empty():
				jresp = self.receiverq.get()
				self.receiverq.task_done()
				self.msg_handler(jresp)
			if not self.send_queue.empty():
				data = self.send_queue.get()# .zfill(PKTLEN)
				self.send_queue.task_done()
				# self.socket.sendto(data,(self.serveraddress, 9696))
				self.do_send(data)
				self.runcounter += 1
				# logger.debug(f'sendqdata: {data}')

	def msg_handler(self, jresp):
		# logger.debug(f'jresp:\n {jresp}\n')
		msgtype = jresp.get('msgtype')
		payload = {'msgtype' : 'ackserveracktimer', 'msgacktype': msgtype}
		# try:
		# 	msgtype = jresp.get('msgtype')
		# except AttributeError as e:
		# 	logger.error(f'{e} jr: {jresp}')
		# 	#break
		# if not msgtype:
		# 	logger.warning(f'{self} msgtype not found in jresp: {jresp}')
		# 	raise Exception(f'{self} msgtype not found in jresp: {jresp}')
		# # logger.debug(f'{msgtype} jresp:\n {jresp}\n')
		match msgtype:
			case 'ackplrbmb':
				bomb_clid = jresp.get('data').get('client_id')
				clbombpos = jresp.get('data').get('clbombpos')
				pygame.event.post(pygame.event.Event(PLAYEREVENT, payload={'msgtype': 'ackplrbmb', 'client_id': bomb_clid, 'clbombpos': clbombpos}))
				if bomb_clid != self.client_id:
					logger.info(f'{self} otherplayerbomb {msgtype} from {bomb_clid} bombpos: {clbombpos}')
				elif bomb_clid == self.client_id:
					# logger.info(f'{self} ownbomb {msgtype} bombpos: {clbombpos}')
					pass
				else:
					logger.warning(f'{self} bomberclientid! {msgtype} jresp: {jresp}')
			case 'serveracktimer' | 'ackclplrmv' | 'trigger_newplayer':
				# logger.debug(f'{self} {msgtype} {jresp}')
				# playerlist = None
				# data = jresp.get('data')
				playerlist = jresp.get('playerlist', None)
				if len(playerlist) > 0 and not self.gotplayerlist:
					self.playerlist = playerlist
					self.gotplayerlist = True
					logger.info(f'{msgtype} firstsetplayerlistok {self.playerlist}')
				if len(playerlist) > 0 and self.gotplayerlist:
					self.playerlist = playerlist
					self.gotplayerlist = True
					# logger.info(f'playerlistupdate {self.playerlist}')
				elif len(playerlist) == 0:
					self.gotplayerlist = False
					if msgtype != 'trigger_newplayer':
						logger.warning(f'{self} empty playerlist in jresp\n{jresp}')
				if not playerlist:
					if msgtype != 'trigger_newplayer':
						self.gotplayerlist = False
						logger.warning(f'{self} no playerlist in jresp\n{jresp}')
				if not self.gotgrid:
					grid = jresp.get('grid')
					self.gotgrid = True
					self.grid = grid
					# logger.info(f'{self} gotgrid {self.gotgrid} {msgtype} ')
					pygame.event.post(pygame.event.Event(NEWGRIDEVENT, payload={'msgtype': 'newgridfromserver', 'grid':self.grid}))
			case _:
				logger.warning(f'missingmsgtype jresp: {jresp} ')
				# data = {'msgtype' : 'missingmsgtype', 'client_id': self.client_id, 'runcounter': self.runcounter}
				payload = {'msgtype' : 'missingmsgtype'}
		# logger.info(f'sendqput {self.send_queue.qsize()} msgtype={msgtype} payloadmsgt:={payload.get("msgtype")}') # \nmsgtype={msgtype}\njresp:\n{jresp}\n')
		# self.send_queue.put(payload)
				# self.send_queue.put(data)
	def update(self):
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		# logger.info(f'{self}')

	def draw(self, screen):
		screen.blit(self.image, self.rect)
		for player in self.playerlist:
			# logger.debug(f'{player} {self.player.playerlist.get(player)}')
			plid = self.playerlist.get(player).get('client_id')
			pos = self.playerlist.get(player).get('pos')
			gridpos = self.playerlist.get(player).get('gridpos')
			# gridpos = (pos[0] * BLOCK, pos[1] * BLOCK)
			if self.client_id != plid:
				npimg = self.rh.get_image('data/netplayer.png')
				screen.blit(npimg, pos)
				# blk = NewBlock(gridpos=gridpos, image=self.rh.get_image('data/netplayer.png'))
			elif self.client_id == plid:
				pass
				# blk = NewBlock(gridpos=gridpos, image=self.rh.get_image('data/playerone.png'))
				# blks.add(BasicBlock(gridpos=gridpos, image=self.rh.get_image('data/playerone.png'))
			else:
				logger.warning(f'{self} pliderror!')
				npimg = self.rh.get_image('data/dummyplayer.png')
				screen.blit(npimg, pos)
				# blk = NewBlock(gridpos=gridpos, image=self.rh.get_image('data/dummyplayer.png'))


	def sendbomb(self):
		payload = {'msgtype' : 'cl_playerbomb','action': 'playerbomb', 'clbombpos': self.gridpos}
		self.send_queue.put(payload)

	def move(self, action):
		if not self.gotgrid:
			logger.warning(f'{self} move {action} nogrid')
			return
		gpx, gpy = self.gridpos
		newgridpos = [gpx, gpy]
		if action == 'u':
			if self.grid[gpx][gpy-1] == 2:
				newgridpos = [gpx, gpy-1]
			else:
				logger.warning(f'{self} cannot move {action} from {self.gridpos} to {[gpx, gpy-1]} gridval: {self.grid[gpx][gpy-1]}')
				newgridpos = [gpx, gpy]
				return
		elif action == 'd':
			if self.grid[gpx][gpy+1] == 2:			 
				newgridpos = [gpx, gpy+1]
			else:
				logger.warning(f'{self} cannot move {action} from {self.gridpos} to {[gpx, gpy+1]} gridval: {self.grid[gpx][gpy+1]}')
				newgridpos = [gpx, gpy]
				return
		elif action == 'l':
			if self.grid[gpx-1][gpy] == 2:
				newgridpos = [gpx-1, gpy]
			else:
				logger.warning(f'{self} cannot move {action} from {self.gridpos} to {[gpx-1, gpy]} gridval: {self.grid[gpx-1][gpy]}')
				newgridpos = [gpx, gpy]
				return
		elif action == 'r':
			if self.grid[gpx+1][gpy] == 2: # else [gpx, gpy]
				newgridpos = [gpx+1, gpy] 
			else:
				logger.warning(f'{self} cannot move {action} from {self.gridpos} to {[gpx+1, gpy]} gridval: {self.grid[gpx+1][gpy]}')
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
		logger.info(f'{self} move {action} gridpos: {self.gridpos} pos: {self.pos}')

