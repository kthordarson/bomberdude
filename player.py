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
		self.client_id = f'np:{gen_randid()}'
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
		self.sendcounter = 0
		self.recvcounter = 0
		self.runcounter = 0
		self.lastpktid = ''

	def __repr__(self) -> str:
		if self.testmode:
			return f'NPTest({self.client_id} pos:{self.pos} s:{self.sendcounter} r:{self.recvcounter})'
		else:
			return f'NP({self.client_id} pos:{self.pos})'

	def do_testing(self):
		pass

	def do_send(self, payload):
		self.lastpktid = gen_randid()
		payload['c_pktid'] = self.lastpktid
		if isinstance(payload, dict):
			msgtype = payload.get('msgtype')
			payload = json.dumps(payload).encode('utf8').zfill(PKTLEN)
		if isinstance(payload, str):
			msgtype = 'xxx'
			logger.warning(f'dosend str {type(payload)} payload: {payload} ')
			payload = payload.encode('utf8').zfill(PKTLEN)
		# msglen += b' ' * (PKTLEN - len(payload))
		msglen = str(len(payload)).encode('utf8').zfill(PKTLEN)
		logger.debug(f'dosend {msgtype} c_pktid: {self.lastpktid}')
		self.socket.sendto(msglen,(self.serveraddress, 9696))
		self.socket.sendto(payload,(self.serveraddress, 9696))

	def run(self):
		try:
			self.socket.connect((self.serveraddress, 9696))
		except OSError as e:
			pass
		# self.sender.start()
		# self.receiver.run()

		data = {'msgtype' : 'cl_newplayer', 'client_id': self.client_id, 'runcounter': self.runcounter}
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
					self.runcounter += 1
					logger.debug(f'sendqdata: {data}')
			except BrokenPipeError as e:
				logger.error(e)
			replen = self.socket.recv(PKTLEN).decode('utf8')
			datalen = int(re.sub('^0+','',replen))
			jresp = None
			response = self.socket.recv(datalen).decode('utf8')
			response = re.sub('^0+','', response)
			try:
				jresp = json.loads(response)
			except json.decoder.JSONDecodeError as e:
				logger.warning(f'{e} {type(e)} {type(response)}\nresp: {response}')
			except TypeError as e:
				logger.warning(f'{e} {type(e)} {type(response)}\nresp: {response}')
			except Exception as e:
				logger.error(f'{e} {type(e)} {type(response)}\nresp: {response}')
			if jresp:
				# logger.debug(f'jresp: {jresp}')
				try:
					msgtype = jresp.get('msgtype')
				except AttributeError as e:
					logger.error(f'{e} jr: {jresp}')
					msgtype = 'error'

				try:
					data = json.loads(jresp.get('data'))
				except TypeError as ee:
					# logger.warning(f'{ee} jresp: {type(jresp)}\njresp: {jresp}\n')
					data = jresp.get('data')
				pktidchk = data.get('c_pktid')
				idchk = data.get('client_id')
				if self.lastpktid != pktidchk:
					logger.warning(f'{self} {msgtype} pktidchk {self.lastpktid} != {pktidchk} from {idchk}')
				if self.lastpktid == pktidchk:
					pass
					# logger.debug(f'pktidchkok {self.lastpktid} = {pktidchk} from {idchk}')
				match msgtype:
					case 'cl_test':
						data = {'msgtype' : 'cl_test', 'client_id': self.client_id, 'runcounter': self.runcounter}
						self.do_send(data)
					case 'servermsgresponse':
						pass
					case 'server_playermove':
						#logger.debug(f'jresp: {type(jresp)}\njresp: {jresp}\n')
						pos = data.get('pos')
						action = data.get('action')
						if self.client_id != idchk:
							logger.info(f'{msgtype} from {idchk} {pos}')
						if action == 'bomb':
							logger.info(f'BOMB! {msgtype} from {idchk} {pos}')
					case 'msgresponse':
						pass
					case 'ackmissingmsgtype':
						pass
					case 'cltestnoerror':
						pass
					case 'gameserverresponse':
						pass
					case 'noerror':
						pass
					case 'missingmsgtype':
						pass
					case 'error':
						pass
					case 'ackerror':
						pass
					case 'serverack':
						pass
					case 'ackcl_newplayer':
						self.client_id = jresp.get('client_id')
						self.sender.s_type = f'snch:{self.client_id}'
						self.receiver.s_type = f'rnp:{self.client_id}'
						self.sender.client_id = self.client_id
						self.receiver.client_id = self.client_id
						logger.info(f'{self} ackcl_newplayer {jresp}')
						data = {'msgtype' : 'noerror', 'client_id': self.client_id, 'runcounter': self.runcounter}
						self.do_send(data)
						# data = json.dumps(resp).encode('utf8')
					case _:
						logger.warning(f'missingmsgtype jresp: {jresp} resp: {response}')
						data = {'msgtype' : 'missingmsgtype', 'client_id': self.client_id, 'runcounter': self.runcounter}
						self.do_send(data)
				# self.socket.sendto(data.zfill(PKTLEN),(self.serveraddress, 9696))

				# data = json.dumps(payload)



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
		elif action == 'bomb':
			# todo placebomb
			pass
		else:
			logger.warning(f'{self} move {action} not implemented')
		self.gridpos = newgridpos
		self.pos = (self.gridpos[0] * BLOCK, self.gridpos[1] * BLOCK)
		payload = {'msgtype' : 'cl_playermove', 'client_id': self.client_id, 'pos': self.pos, 'action': action}
		self.do_send(payload)
		# logger.debug(f'sent {payload}  ')

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

