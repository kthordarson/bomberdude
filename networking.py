import socket
import time
from threading import Thread
from threading import Event as TEvent
from queue import Queue
import re
import json
from loguru import logger

from constants import *
from exceptions import *
from objects import gen_randid, Bomberplayer

class Client(Thread):
	def __init__(self, serveraddress=None, eventq=None):
		super().__init__(daemon=True, name='BombClientThread')
		self._stop = TEvent()
		self.client_id = None#  gen_randid()
		self.serveraddress = serveraddress
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connected = False
		self.eventq = eventq
		self.receiverq = Queue()
		self.send_queue = Queue()
		self.receiver = ReceiverThread(receiverq=self.receiverq, socket=self.socket)
		self.sendcounter = 0
		self.runcounter = 0
		self.pos = (0,0)
		self.health = 100
		self.gridpos = (0,0)
		self.bombsleft = 33
		self.gotgrid = False
		self.gotpos = False
		self.sendqsize = self.send_queue.qsize()
		self.runcounter = 0
		self.playerlist = {}
		# self.player = Bomberplayer("data/playerone.png",scale=0.9) # arcade.Sprite("data/playerone.png",scale=1)

	def __repr__(self):
		return f'Client(id: {self.client_id} conn:{self.connected} stop:{self.stopped()} sqs:{self.send_queue.qsize()} rqs:{self.receiverq.qsize()} rr:{self.receiver.recvcounter} rc:{self.runcounter} uc:{self.runcounter})'

	def stop(self):
		self._stop.set()
		logger.info(f'STOP {self} {self._stop.is_set()} socket:{self.socket}')

	def stopped(self):
		return self._stop.is_set()

	def do_connect(self, reconnect=False):
		c_cnt = 0
		if reconnect:
			self.stop()
			self.receiver.stop()
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.receiver.socket = self.socket
			self.connected = False
			logger.warning(f'{self} reconnecting...')
		while not self.connected:
			c_cnt += 1
			logger.info(f'do_connect c_cnt: {c_cnt}')
			if c_cnt >= 10:
				logger.error(f'{self} do_connect {c_cnt}')
				return False
			try:
				self.socket.connect(self.serveraddress)
				self.connected = True
				self.receiver.connected = True
				logger.info(f'{self} connected c_cnt: {c_cnt} r:{self.receiver}')
				if not reconnect:
					self.receiver._stop.clear()
					self._stop.clear()
				return True
			except Exception as e:
				logger.error(f'{self} doconnect {e} {type(e)} {c_cnt}')
				return False

	def get_servermap(self):
		c_cnt = 0
		gotservermap = False
		while not gotservermap:
			c_cnt += 1
			logger.info(f'get_servermap c_cnt: {c_cnt}')
			if gotservermap:
				logger.debug(f'{self} get_servermap c_cnt: {c_cnt}')
				return True
			if c_cnt >= 10:
				logger.error(f'get_servermap error {c_cnt}')
				return False
			try:
				self.send_queue.put({'msgtype': 'getservermap'})
				time.sleep(1)
			except Exception as e:
				logger.error(f'{self} get_servermap {e} {type(e)} {c_cnt}')
				return False

	def do_send(self, payload):
		if not self.connected:
			logger.warning(f'{self} notconnected p: {payload}')
			return
		payload['runcounter'] = self.runcounter
		payload['runcounter_r'] = self.receiver.runcounter
		payload['client_id'] = self.client_id
		#payload['pos'] = (self.pos[0],self.pos[1])
		#payload['bombsleft'] = self.bombsleft
		#payload['health'] = self.health
		#payload['gridpos'] = self.gridpos
		#payload['gotgrid'] = self.gotgrid
		#payload['gotpos'] = self.gotpos
		#payload['sendqsize'] = self.send_queue.qsize()
		#payload['connected'] = self.connected
		try:
			payload = json.dumps(payload).encode('utf8')
		except Exception as e:
			logger.error(f'{self} jsondumps {e} {type(e)} payload:\n{payload}')
			return
		msglen = str(len(payload)).encode('utf8').zfill(PKTHEADER)
		try:
			self.socket.sendto(msglen,self.serveraddress)
			self.socket.sendto(payload,self.serveraddress)
			self.sendcounter += 1
		except Exception as e:
			logger.error(f'{self} sendto {e} {type(e)} msglen:{msglen} payload:\n{payload}')
		# logger.debug(f'playerdosendpayload {outmsgtype} lenx:{msglenx} {len(payload)} c_pktid: {self.lastpktid}')

	def msg_handler(self, jresp):
		# logger.debug(f'jresp:\n {jresp}\n')
		try:
			msgtype = jresp.get('msgtype')
			# logger.debug(f'msgtype: {msgtype}')
		except AttributeError as e:
			logger.error(f'{e} {type(e)} jresp: {jresp}')
			msgtype = ''
		match msgtype:
			case 'bombdrop':
				# logger.info(f'{msgtype} {jresp}') # todo makebombs
				self.eventq.put(jresp)
			case 'playermove':
				# logger.info(f'{msgtype} {jresp}') # todo makebombs
				self.eventq.put(jresp)
			case 'ping':
				logger.debug(f'got ping from {jresp.get("client_id")} griddatalen: {len(jresp.get("grid"))}') # serverdebugping
			case 'ackplrbmb':
				bomb_client_id = jresp.get('data').get('client_id')
				clbombpos = jresp.get('data').get('clbombpos')
				if bomb_client_id != self.client_id: # not a bomb from me...
					# pass
					logger.info(f'{self} otherplayerbomb {msgtype} from {bomb_client_id} bombpos: {clbombpos}')
				elif bomb_client_id == self.client_id: # my bomb
					logger.info(f'{self} ownbomb {msgtype} bombpos: {clbombpos}')
					self.bombsleft -= 1
				else:
					logger.warning(f'{self} bomberclientid! {msgtype} jresp: {jresp}')
			case 'newgridresponse':
				grid = jresp.get('grid')
				if grid:
					self.gotgrid = True
					self.grid = grid
					logger.info(f'gotgrid {self.gotgrid} {msgtype} ')
				else:
					logger.warning(f'nogrid in {jresp}')
				newpos = jresp.get('setpos')
				if newpos:
					self.gotpos = True
					self.gridpos = newpos
					self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
					logger.info(f'gotpos {msgtype} newpos: {newpos} {self.gridpos} {self.pos}')
			case 'trigger_netplayers':
				self.eventq.put(jresp)
			case 'trigger_newplayer': # when new player joins
				client_id = jresp.get('client_id')
				# logger.info(f'{msgtype} {jresp}')
				if not self.client_id: # set client_id if not set
					self.client_id = client_id
					self.pos = jresp.get('setpos')
					self.grid = jresp.get('grid')
					self.gotgrid = True
					self.gotpos = True
					self.playerlist[jresp.get('client_id')] = {'setpos':jresp.get('setpos')}
					logger.info(f'{self} {msgtype} name: {jresp.get("clientname")} client_id: {jresp.get("client_id")} setpos: {jresp.get("setpos")} ')
					self.eventq.put(jresp)
					return
			case 'serveracktimer':
				# logger.debug(f'{self} {msgtype} {jresp}')
				# playerlist = None
				# data = jresp.get('data')
				playerlist = jresp.get('playerlist', None)
				self.playerlist = playerlist

				grid = jresp.get('grid', None)
				self.grid = grid
				self.gotgrid = True
				self.gotpos = True
				# self.update_run()
			case 'sv_serverdebug': # got debuginfo from server
				self.debuginfo['server'] = jresp.get('dbginfo')
			case 'error': # got debuginfo from server
				logger.error(jresp)
				conn = self.do_connect(reconnect=True)
				if conn:
					logger.info(f'{self} reconnected')
				else:
					logger.error(f'{self} not reconnected')
					self.stop()
			case _:
				logger.warning(f'missingmsgtype jresp: {jresp} ')

	def update_run(self):
		if not self.send_queue.empty():
			sqdata = self.send_queue.get()
			if sqdata:
				# logger.debug(f'{sqdata.get("msgtype")} rqs: {self.receiverq.qsize()} recvrc:{self.receiver.runcounter} sqs: {self.send_queue.qsize()} runc:{self.runcounter} sendc:{self.sendcounter} ')
				# logger.info(f'rqs: {self.receiverq.qsize()} sqs: {self.send_queue.qsize()} data:\n {sqdata}')
				try:
					self.do_send(sqdata)
				except OSError as e:
					logger.error(f'senderror {e} data: {sqdata}')
					if e.errno == 32:
						# logger.error(f'errno32 {e} data: {sqdata}')
						self.connected = False
						self.receiver.connected = False
						self.receiver.join(timeout=0)
						self.stop()
						return
				self.send_queue.task_done()

	def update_run_recv(self):
		if not self.receiverq.empty():
			rqdata = self.receiverq.get()
			if rqdata:
				# logger.info(f'{rqdata.get("msgtype")} rqs: {self.receiverq.qsize()} sqs: {self.send_queue.qsize()} ')
				self.msg_handler(rqdata)
				self.receiverq.task_done()


class ReceiverThread(Thread):
	def __init__(self, receiverq=None, socket=None):
		super().__init__(daemon=True, name='ReceiverThread')
		self.receiverq = receiverq
		self.socket = socket
		self.name = 'ReceiverThread'
		self.connected = False
		self.recvcounter = 0
		self._stop = TEvent()
		self.runcounter = 0

	def __repr__(self):
		return f'{self.name} ( rqs:{self.receiverq.qsize()} {self.recvcounter} runc:{self.runcounter})'

	def stop(self):
		self.connected = False
		self._stop.set()
		logger.info(f'STOP {self} {self._stop.is_set()} socket:{self.socket}')

	def stopped(self):
		return self._stop.is_set()

	def run(self):
		while True:
			self.runcounter += 1
			if self.stopped():
				return
			else:
				try:
					replen = self.socket.recv(PKTHEADER).decode('utf8')
					datalen = int(re.sub('^0+','',replen))
					response = self.socket.recv(datalen).decode('utf8')
					jresp = json.loads(response)
					self.receiverq.put(jresp)
					self.recvcounter += 1
				except Exception as e:
					# logger.error(f'{self} get_jresp {e} {type(e)} response: {response}')
					errmsg = f'get_jresp {e} {type(e)} response: {response}'
					logger.error(errmsg)
					msg = {'msgtype': 'error', 'errmsg':errmsg}
					self.receiverq.put(msg)
