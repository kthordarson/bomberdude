import socket
from threading import Thread
from queue import Queue
import re
import json
import pygame
from loguru import logger
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import spritecollide

from constants import BLOCK, PLAYEREVENT, PLAYERSIZE, PKTLEN
from globals import BasicThing, gen_randid, BlockNotFoundError
from map import Gamemap
from network import Sender,  send_data, Receiver
HEADER = 64
FORMAT = 'utf8'
DISCONNECT_MESSAGE = 'disconnect'

class NewPlayer(Thread):
	def __init__(self, serveraddress='127.0.0.1', testmode=False):
		Thread.__init__(self, daemon=True)
		self.client_id = 'newplayer1'
		self.kill = False
		self.connected = False
		self.serveraddress = serveraddress
		self.queue_monitor_t = Thread(target=self.queue_monitor, daemon=True)
		self.send_queue = Queue()
		self.msg_queue = Queue()
		self.pos = [0,0]
		self.gridpos = [0,0]
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# self.sender = Sender(client_id=self.client_id, s_type=f'snp:{self.client_id}', socket=self.socket)
		# sender thread, put data in client sender queue and sender thread sends data to client
		# self.receiver = Thread(target=self.receive_data, daemon=True)
		# self.receiver = Receiver(socket=self.socket, client_id=self.client_id, s_type=f'rnp:{self.client_id}')
		# receiver thread, receives data from server and puts data in receiver queue
		self.attempts = 0
		self.testmode = testmode

	def __repr__(self) -> str:
		if self.testmode:
			return f'NPTest({self.client_id} pos:{self.pos})'
		else:
			return f'NP({self.client_id} pos:{self.pos})'

	def do_testing(self):
		pass
		# testcounter = 0
		# self.socket.connect((self.serveraddress, 9696))
		# self.sender.start()
		# self.receiver.run()
		# data = {'msgtype' : 'cl_newplayer', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}
		# self.sender.queue.put((self.socket, cl_newplayerpayload))
		# data = json.dumps(payload)
		# data = data.zfill(PKTLEN
		# self.do_send(data)
		# msglen = str(len(data)).encode('utf8')
		# msglen += b' ' * (PKTLEN - len(data))
		# self.socket.sendto(msglen,(self.serveraddress, 9696))
		# self.socket.sendto(data,(self.serveraddress, 9696))

	def do_send(self, payload):

		if isinstance(payload, dict):
			payload = json.dumps(payload).encode('utf8').zfill(PKTLEN)
		if isinstance(payload, str):
			payload = payload.encode('utf8').zfill(PKTLEN)
		# msglen += b' ' * (PKTLEN - len(payload))
		msglen = str(len(payload)).encode('utf8').zfill(PKTLEN)
		logger.debug(f'dosend msglen: {len(payload)} payload: {type(payload)}')
		self.socket.sendto(msglen,(self.serveraddress, 9696))
		self.socket.sendto(payload,(self.serveraddress, 9696))

	def run(self):
		testcounter = 0
		try:
			self.socket.connect((self.serveraddress, 9696))
		except OSError as e:
			pass
		# self.sender.start()
		# self.receiver.run()
		data = {'msgtype' : 'cl_newplayer', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}
		self.do_send(data)
		# self.sender.queue.put((self.socket, cl_newplayerpayload))
		# data = json.dumps(payload)
		logger.debug(f'{self} run cl_newplayerpayload sent: {data}')
		# data = data.zfill(PKTLEN)
		#self.socket.sendto(data,(self.serveraddress, 9696))

		while not self.kill:
			try:
				if not self.send_queue.empty():
					data = self.send_queue.get()# .zfill(PKTLEN)
					self.send_queue.task_done()
					# self.socket.sendto(data,(self.serveraddress, 9696))
					#self.do_send(data)
					testcounter += 1
					logger.debug(f'sendqdata: {data}')
			except BrokenPipeError as e:
				logger.error(e)
			replen = self.socket.recv(PKTLEN).decode('utf8')
			datalen = int(re.sub('^0+','',replen))
			jresp = None
			response = self.socket.recv(datalen).decode('utf8')
			response = re.sub('^0+','', response)
			if 'Msg received' in response:
				# print(data)
				jresp = {'msgtype': 'msgresponse'}
			else:
				try:
					jresp = json.loads(response)
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8') # .zfill(PKTLEN)
				except json.decoder.JSONDecodeError as e:
					logger.warning(f'{e} {type(e)} {type(response)}\nresp: {response}')
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8') # .zfill(PKTLEN)
					# self.socket.sendto(data,(self.serveraddress, 9696))
					self.do_send(data)
					jresp = None
				except TypeError as e:
					logger.warning(f'{e} {type(e)} {type(response)}\nresp: {response}')
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8') # .zfill(PKTLEN)
					# self.socket.sendto(data,(self.serveraddress, 9696))
					self.do_send(data)
					jresp = None
					# data = json.dumps({'msgtype' : 'error', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					# break
				except Exception as e:
					logger.error(f'{e} {type(e)} {type(response)}\nresp: {response}')
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8') # .zfill(PKTLEN)
					# self.socket.sendto(data,(self.serveraddress, 9696))
					self.do_send(data)
					jresp = None
				#data = json.dumps({'msgtype' : 'error', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
				#break
			#if not jresp:
			#	logger.warning(f'resp: {response}')
			#	data = json.dumps({'msgtype' : 'error', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf-8')
			#	self.send
				# self.sender.queue.put((self.socket, cl_newplayerpayload))
				# data = json.dumps(payload)
			if jresp:
				msgtype = jresp.get('msgtype')
				data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
				match msgtype:
					case 'cl_test':
						data = json.dumps({'msgtype' : 'cltestnoerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'servermsgresponse':
						data = json.dumps({'msgtype' : 'cltestnoerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'msgresponse':
						data = json.dumps({'msgtype' : 'cltestnoerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'ackmissingmsgtype':
						data = json.dumps({'msgtype' : 'cltestnoerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'cltestnoerror':
						data = json.dumps({'msgtype' : 'cltestnoerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'noerror':
						data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'missingmsgtype':
						data = json.dumps({'msgtype' : 'cltestnoerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'error':
						data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'ackerror':
						data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
					case 'ackcl_newplayer':
						self.client_id = jresp.get('client_id')
						self.sender.s_type = f'snch:{self.client_id}'
						self.receiver.s_type = f'rnp:{self.client_id}'
						self.sender.client_id = self.client_id
						self.receiver.client_id = self.client_id
						logger.info(f'{self} ackcl_newplayer {jresp}')
						resp = {'msgtype' : 'noerror', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}
						data = json.dumps(resp).encode('utf8')
					case _:
						logger.warning(f'missingmsgtype jresp: {jresp} resp: {response}')
						data = json.dumps({'msgtype' : 'missingmsgtype', 'client_id': self.client_id, 'testcounter': testcounter, 'c_pktid': gen_randid()}).encode('utf8')
				# self.socket.sendto(data.zfill(PKTLEN),(self.serveraddress, 9696))

				# data = json.dumps(payload)

	def oldrun(self):
		if self.connect():
			self.sender.start()
			self.receiver.start()
			cl_newplayerpayload = {'msgtype' : 'cl_newplayer', 'client_id': self.client_id, 'c_pktid': gen_randid()}
			self.sender.queue.put((self.socket, cl_newplayerpayload))
			# data = json.dumps(payload).encode('utf-8')
			# send_data(conn=self.socket, payload=cl_newplayerpayload, pktid=gen_randid())
			logger.debug(f'{self} runcl_newplayerpayload sent: {len(cl_newplayerpayload)} {type(cl_newplayerpayload)} {cl_newplayerpayload}')
		else:
			logger.warning(f'{self} not connected')
			self.kill = True
			return None
		while not self.kill:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			# if self.client_id == 'newplayer1':
			#	self.sender.queue.put((self.socket, cl_newplayerpayload))
			payload = None
			if not self.receiver.queue.empty():
				payload = self.receiver.queue.get()
				self.receiver.queue.task_done()
				# logger.debug(f'sq: {self.sender} rq: {self.receiver} got receiver payload {len(payload)} {type(payload)}\n{payload}')
				if payload:
					if 'bcsetclid' in payload:
						logger.debug(f'{self} payload:{payload}')
					self.handle_payloadq(payload)


	def handle_payloadq(self, rawpayload):
		# logger.debug(f'rawpayload {len(rawpayload)} {type(rawpayload)}\n{rawpayload}')
		if isinstance(rawpayload, dict):
			payload = json.loads(json.dumps(rawpayload))
		elif isinstance(rawpayload, str):
			payload = json.loads(rawpayload)
		else:
			logger.warning(f'unknown payloadtype {type(rawpayload)}\nr:\n{rawpayload}')
			return
		# logger.debug(f'payload:\n{payload}\n')
		try:
			msgtype = payload.get('msgtype')
			in_pktid = payload.get('pktid')
		except AttributeError as e:
			logger.error(f'{e} payload: {type(payload)}\n{payload}')
			return
		if msgtype == 'bcsetclid':
			self.client_id = payload.get('client_id')
			self.sender.s_type = f'snch:{self.client_id}'
			self.receiver.s_type = f'rnp:{self.client_id}'
			self.sender.client_id = self.client_id
			self.receiver.client_id = self.client_id
			logger.info(f'{self} bcsetclid payload={payload}')
			# clid = payload.get('client_id')
			# self.set_clientid(clid)
		elif msgtype == 's_netplayers':
			# logger.debug(f'netplayers payload={payload}')
			netplayers = payload.get('netplayers', None)
			# if netplayers:
			# 	self.netplayers = netplayers
		elif msgtype == 's_ping':
			if self.client_id == 'newplayer1':
				self.client_id = payload.get('client_id')
				self.sender.s_type = f'snch:{self.client_id}'
				self.receiver.s_type = f'rnp:{self.client_id}'
				self.sender.client_id = self.client_id
				self.receiver.client_id = self.client_id
				logger.info(f'{self} spingbcsetclid payload={payload}')
			if payload.get('clients') > 1 or payload.get('chconnections') > 1:
				if payload.get('client_id') != self.client_id:
					logger.debug(f'spinginfo payload={payload}')
		elif msgtype == 'serverinfo':
			if self.client_id == 'newplayer1':
				self.client_id = payload.get('client_id')
				self.sender.s_type = f'snch:{self.client_id}'
				self.receiver.s_type = f'rnp:{self.client_id}'
				self.sender.client_id = self.client_id
				self.receiver.client_id = self.client_id
				logger.info(f'{self} spingbcsetclid payload={payload}')
			if payload.get('clients') > 1 or payload.get('chconnections') > 1:
				if payload.get('client_id') != self.client_id:
					logger.debug(f'spinginfo payload={payload}')
			# pongpayload = {'msgtype' : 'cl_pong', 'client_id': self.client_id, 'c_pktid': gen_randid()}
			# self.sender.queue.put((self.socket, pongpayload))
			# pass
		elif msgtype == 's_netgridupdate':
			# received gridupdate from server
			gridpos = payload.get('blkgridpos')
			blktype = payload.get("blktype")
			bclid = payload.get('bclid')

		elif msgtype == 'bc_netbomb':
			# received bomb from server
			logger.info(f'{msgtype} payload={payload}')

		elif msgtype == 's_posupdate':
			# received posupdate from server
			logger.info(f'posupdate payload={payload}')

		elif msgtype == 's_pos':
			# received playerpos from server
			self.pos = payload.get('pos')
			self.rect.x = self.pos[0]
			self.rect.y = self.pos[1]
			self.gridpos = payload.get('gridpos')
			self.gamemap.grid = payload.get('grid')
			self.gotpos = True
			self.gotmap = True
			# pygame.event.post(Event(PLAYEREVENT, payload={'msgtype':'newnetpos', 'posdata':payload, 'pos':self.pos,'gotmap':self.gotmap,'gotpos':self.gotpos, 'newpos':self.pos, 'gridpos':self.gridpos, 'grid':self.gamemap.grid}))

		elif msgtype == 's_grid':
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
			logger.debug(f's_grid g={len(self.gamemap.grid)} newpos={self.pos} {self.gridpos} p1={self}')
		else:
			logger.warning(f'{self} unknown msgtype: {msgtype}\npayload: {payload}\n')


	def connect(self):
		logger.info(f'{self} connecting to {self.serveraddress}')
		try:
			self.socket.connect((self.serveraddress, 9696))
		except ConnectionRefusedError as e:
			logger.error(f'{self} {e}')
			return False
		except OSError as e:
			if e.errno == 106:
				self.connected = True
				logger.info(f'{self} {e}')
				return True
			else:
				logger.error(f'{self} {e}')
				return False
		self.connected = True
		logger.info(f'{self} connected to {self.serveraddress}')
		return True


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
		payload = {'msgtype' : 'cl_playermove', 'client_id': self.client_id, 'c_pktid': gen_randid(), 'pos': self.pos, 'action': action}
		# data = json.dumps(payload).encode('utf-8')
		# self.socket.send(data)
		#self.sender.queue.put((self.socket, payload))
		self.do_send(payload)
		# logger.debug(f'sent movepayload sq: {self.sender} rq: {self.receiver}  ')

	def send_cl_message(self, clmsgtype, payload):
		if not self.connected:
			logger.warning(f'{self} not conncted')
			return
		elif self.client_id == 'newplayer1':
			logger.warning(f'{self} need client_id from server!')
			return
		elif self.connected and self.client_id != 'newplayer1':
			pospayload = {
				'msgtype': clmsgtype,
				'client_id': self.client_id,
				'payload': payload,
				}
			self.sender.queue.put((self.socket, pospayload))
		else:
			logger.warning(f'{self} send_cl_message failed...')

	def sendpos(self):
		if not self.connected:
			logger.warning(f'{self} not conncted')
			return
		elif self.client_id == 'newplayer1':
			logger.warning(f'{self} need client_id from server!')
			return
		elif self.connected and self.client_id != 'newplayer1':
			pospayload = {
				'msgtype': 'cl_playerpos',
				'client_id': self.client_id,
				'pos': self.pos,
				}
			# self.sender.queue.put((self.socket, pospayload))
			# data = json.dumps({'msgtype':'cl_playerpos', 'client_id':self.client_id,'pos': self.pos,}).encode('utf-8')
			payload = {'msgtype':'cl_playerpos', 'client_id':self.client_id,'pos': self.pos}
			# send_data(self.socket, payload=payload, pktid=gen_randid())
			self.sender.queue.put((self.socket, payload))
		else:
			logger.warning(f'{self} sendpos failed...')
