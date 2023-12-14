#!/usr/bin/python
import os
import socket
import select
import struct
import sys
import json
from threading import Thread, current_thread
from queue import Queue
import pygame
from loguru import logger
from pygame.event import Event
import re
from constants import (BLOCK, DEFAULTFONT, FPS, SENDUPDATEEVENT, SERVEREVENT, SQUARESIZE,NEWCLIENTEVENT,NEWCONNECTIONEVENT,PKTLEN)
from globals import gen_randid
from map import Gamemap,generate_grid
from network import Sender, send_data, Receiver

from socketserver import ThreadingMixIn, TCPServer, BaseRequestHandler, StreamRequestHandler

HEADER = 64
FORMAT = 'utf8'
DISCONNECT_MESSAGE = 'disconnect'


def testclient(ip, port, message):
    with socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
        response = str(sock.recv(1024), 'ascii')
        print("Received: {}".format(response))

class TestHandler(BaseRequestHandler):
	class Disconnect(BaseException):
		pass
	def __init__(self, request, client_address, server):
		self.user = None
		self.host = client_address
		self.realname = None
		self.nick = None
		self.send_queue = []
		self.channels = {}
		self.hicounter = 0
		self.client_id = gen_randid()
		super().__init__(request, client_address, server)
		logger.debug(f'[h] {self} {request}')

	def handle(self):
		logger.debug(f'[h] {self} handle')
		try:
			while True:
				self._handle_one()
		except self.Disconnect as e:
			logger.warning(f'{self} {e}')
			self.request.close()
		# data = str(self.request.recv(1024), 'ascii')
		# cur_thread = current_thread()
		# response = f'testok'.encode('utf8') # bytes("{}: {}".format(cur_thread.name, data), 'ascii')
		# rawdata_sock = re.sub('^0+','',str(data))
		# logger.debug(f'[H] t: {cur_thread.name} raw: {rawdata_sock}')
		# self.request.sendall(response)
	def _handle_one(self):
		"""
		Handle one read/write cycle.
		"""
		# logger.debug(f'[h1] {self} handle_one')
		ready_to_read, ready_to_write, in_error = select.select([self.request], [self.request], [self.request], 0.1)
		# logger.debug(f'[h1] {self} rtr: {ready_to_read} rtw: {ready_to_write} ie: {in_error}')
		if in_error:
			logger.warning(f'{self} in_error: {in_error}')
			raise self.Disconnect()

		# Write any commands to the client
		while self.send_queue and ready_to_write:
			msg = self.send_queue.pop(0)
			# logger.debug(f'sqmsg: {msg}')
			self._send(msg)

		# See if the client has any commands for us.
		if ready_to_read:
			self._handle_incoming()

	def _handle_incoming(self):
		self.hicounter += 1
		#payload = json.dumps({'msgtype' : 'cl_test', 'c_pktid': gen_randid()})
		# self.sender.queue.put((self.socket, cl_newplayerpayload))
		#data = json.dumps(payload).encode('utf-8')
		#data = data.zfill(PKTLEN)
		try:
			rawdata = self.request.recv(PKTLEN)
		except Exception as e:
			raise e

		if not rawdata:
			logger.warning(f'[hi] {self} nodata')
			raise self.Disconnect()
		# logger.debug(f'[hi] {self} data: {data}')
		# payload = json.dumps({'msgtype' : 'cl_test', 'hicounter':self.hicounter, 'c_pktid': gen_randid()}).encode('utf8')
		# data = json.dumps(payload).encode('utf-8')
		# self.send_queue.append(payload)
		jresp = None
		# data = re.sub('^0+','',str(rawdata))
		data = re.sub('^0+','',rawdata.decode('utf8'))
		try:
			jresp = json.loads(data)
		except Exception as e:
			logger.error(f'{e} {type(e)} {type(data)} data:\n{data}\nrawdata: {rawdata}')
			data = json.dumps({'msgtype' : 'error', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
			self.send_queue.append(data)
		# if not jresp:
		# 	logger.warning(f'no jresp from data: {data}')
			# data = json.dumps(payload)
		if jresp:
			msgtype = jresp.get('msgtype')
			data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
			match msgtype:
				case 'cl_test':
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					# self.send_queue.append(data)
				case 'cltestnoerror':
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					# self.send_queue.append(data)
				case 'noerror':
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					# self.send_queue.append(data)
				case 'error':
					data = json.dumps({'msgtype' : 'ackerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					# self.send_queue.append(data)
				case 'ackerror':
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					# self.send_queue.append(data)
				case 'missingmsgtype':
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					# self.send_queue.append(data)
				case 'cl_newplayer':
					data = json.dumps({'msgtype' : 'ackcl_newplayer', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					self.send_queue.append(data)
				case 'ackcl_newplayer':
					data = json.dumps({'msgtype' : 'ackcl_newplayer', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					self.send_queue.append(data)
				case 'cl_playermove':
					data = json.dumps({'msgtype' : 'noerror', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					self.send_queue.append(data)
				case _:
					logger.info(f'jresp: {jresp} resp: {data}')
					data = json.dumps({'msgtype' : 'missingmsgtype', 'client_id': self.client_id, 'hicounter': self.hicounter, 'c_pktid': gen_randid()}).encode('utf-8')
					#self.send_queue.append(data)

		# logger.debug(f'{self} test sent: {len(payload)} {type(payload)} {payload}')
		# for line in self.buffer:
		# 	line = line.decode('utf-8')
		# 	self._handle_line(line)
	def _handle_line(self, line):
		try:
			logger.debug(f'l: {line}') # %s: %s' % (self.client_ident(), line))
		except AttributeError as e:
			logger.error(f'{e} {type(e)}')
			raise
		except Exception as e:
			logger.error(f'{e} {type(e)}')
			raise

		if response:
			self._send(response)

	def _send(self, msg):
		# logger.debug(f'sendtomsg: {msg}')
		self.request.send(msg)



class TestThreadedTCPServer(ThreadingMixIn, TCPServer):
	allow_reuse_address = True
	daemon_threads = True
	def __enter__(self):
		print('entering')
		return self

	def __exit__(self, exc_t, exc_v, trace):
		print('exiting')

	def __init__(self, *args, **kwargs):
			self.servername = 'localhost'
			self.channels = {}
			self.clients = {}
			super().__init__(*args, **kwargs)


class NewBombSever(ThreadingMixIn, TCPServer):
	allow_reuse_address = True
	# def __init__(self):
	# 	# Thread.__init__(self, daemon=True)
	# 	self.kill = False
	# 	self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	# 	self.bindaddress = '127.0.0.1'
	# 	self.clients = []
	# 	self.grid = generate_grid()
	# 	self.connectionq = Queue()
	# 	self.clientq = Queue()
	# 	self.ch = NewConnectionHandler(bindaddress=self.bindaddress, connectionq=self.connectionq)
	def __enter__(self):
		print('entering')
		return self

	def __exit__(self, exc_t, exc_v, trace):
		print('exiting')
	# main server thread
	# get new bomb clients from newconnectionhandler

#	def __repr__(self) -> str:
#		return f'[s] c:{len(self.clients)} ch: {self.ch}'

	def send_pings(self):
		for idx,client in enumerate(self.clients):
			payload = {
				'msgtype' : 's_ping',
				'client_id' : client.client_id,
				'clientbchtimer' : client.bchtimer,
				'cl_sq' : client.sender.queue.qsize(),
				'cl_rq' : client.receiver.queue.qsize(),
				'cl_sent' : client.sender.sendcount,
				'cl_recv' : client.receiver.receivecount,
				'clients' : len(self.clients),
				'chconnections' : self.ch.connections,
				'clidx' : idx,
			}
			if client.kill:
				logger.warning(f'{self} client: {client} killed')
				self.clients.pop(self.clients.index(client))
			elif client.client_id == 'newplayer1':
				logger.warning(f'{self} newplayer1client: {client} ')
			else:
				try:
					client.sender.queue.put((client.socket,payload))
				except BrokenPipeError as e:
					logger.error(f'{self} send_pings {e} ')

	def run(self):
		self.ch.start()
		while not self.kill:
			if self.kill:
				self.ch.kill = True
				logger.debug(f'{self} killed')
				break
			else:
				# self.send_pings()
				for idx,client in enumerate(self.clients):
					infopayload = {
						'msgtype' : 'serverinfo',
						'client_id' : client.client_id,
						'clientbchtimer' : client.bchtimer,
						'cl_sq' : client.sender.queue.qsize(),
						'cl_rq' : client.receiver.queue.qsize(),
						'cl_sent' : client.sender.sendcount,
						'cl_recv' : client.receiver.receivecount,
						'clients' : len(self.clients),
						'chconnections' : self.ch.connections,
						'clidx' : idx,
					}
					client.send_ping_info(infopayload)
				if not self.ch.connectionq.empty():
					payload = self.ch.connectionq.get()
					self.new_connection(payload)
					self.ch.connectionq.task_done()
				if not self.clientq.empty():
					payload = self.clientq.get()
					self.handle_client_payload(payload)
					self.clientq.task_done()

	def handle_client_payload(self, payload):
		# logger.info(f'{self} handle_client_payload {payload}')
		msgtype = payload.get('msgtype')
		match msgtype:
			case 'cl_newplayer':
				pass
			case 'cl_playerpos':
				pass
			case 'cl_playermove':
				logger.info(f'{msgtype} from {payload.get("client_id")} {payload.get("pos")} ')
			case 's_ping':
				pass
			case 'msgok':
				pass
			case 'gamemsg':
				pass
			case 'error1':
				pass
			case 'cl_pong':
				pass
			case _:
				logger.warning(f'{self} unhandled msgtype: {msgtype} payload: {payload}')

	def new_connection(self, payload):
		# new connection from newconnectionhandler
		# create new client and send grid
		conn = payload.get('conn')
		newclient = NewClientHandler(socket=conn,clientq=self.clientq)
		logger.info(f'{self} new_connection: {newclient} payload: {type(payload)} {payload}')
		newclient.start()
		# newclient.socket.connect((self.bindaddress, 9696))
		self.clients.append(newclient)

	def sendgrid(self):
		pass
		# jgrid = json.loads(str(grid.tolist()), parse_float=True)

	def get_players(self):
		pass

	def get_player(self, playerid):
		pass

class NewConnectionHandler(Thread, BaseRequestHandler):
	# handles new connections
	# create new client handler and passes to newbombserver
	def __init__(self, bindaddress, connectionq):
		Thread.__init__(self, daemon=True)
		self.kill = False
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.bindaddress = bindaddress
		self.connections = 0
		self.connectionq = connectionq

	def __repr__(self) -> str:
		return f'[ch] c:{self.connections} q:{self.connectionq.qsize()}'

	def run(self):
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind((self.bindaddress, 9696))
		self.socket.listen()
		while not self.kill:
			if self.kill:
				logger.debug(f'{self} killed')
				self.socket.close()
				break
			try:
				conn, addr = self.socket.accept()
				payload={'conn':conn, 'addr':addr, 'bindaddress': self.bindaddress}
				self.connectionq.put(payload)
				self.connections += 1
			except Exception as e:
				logger.error(f'{self} [!] unhandled exception:{e} {type(e)}')
				self.kill = True
				break

class NewClientHandler(Thread):
	# handles client and server communications
	# server creates new clienthandler for each player
	def __init__(self, socket, clientq):
		Thread.__init__(self, daemon=True)
		self.client_id = gen_randid()
		self.kill = False
		self.socket = socket
		self.bchtimer = pygame.time.get_ticks()
		self.sender = Sender(client_id=self.client_id, s_type=f'snch:{self.client_id}', socket=self.socket)
		# sender thread, put data in client sender queue and sender thread sends data to client
		self.receiver = Receiver(socket=self.socket, client_id=self.client_id, s_type=f'rnch:{self.client_id}')
		# receiver thread, receives data from server and puts data in receiver queue
		self.bcsetclidpayload = {'msgtype':'bcsetclid', 'client_id':self.client_id}
		self.clientq = clientq

	def __repr__(self):
		return f'NBCH( id:{self.client_id} s:{self.sender} r:{self.receiver} )'

	def send_ping_info(self, payload):
		self.sender.queue.put((self.sender.socket,payload))

	def handle_payloadq(self, payloads):
		logger.debug(f'{self} handle_payloadq {payloads}')

	def send_payload(self, payload):
		pass
		# try:
		# 	# self.socket.sendall(payload)
		# 	self.sender.queue.put((self.socket, payload))
		# except BrokenPipeError as e:
		# 	logger.error(f'{self} send_payload {e} payload: {payload}')
		# 	raise(e)

	def run(self):
		self.receiver.start()
		self.sender.start()

		self.sender.queue.put((self.socket, self.bcsetclidpayload))
		logger.debug(f'{self} run')
		while not self.kill:
			self.bchtimer = pygame.time.get_ticks()
			if self.kill:
				self.socket.close()
				logger.warning(f'{self} killed sender={self.sender} socket: {self.socket} closed')
				break
			msgtype = None
			rawsockd = []
			try:
				# incoming_data = receive_data(self.conn)
				if not self.receiver.queue.empty():
					rawsockd = self.receiver.queue.get()
					self.receiver.queue.task_done()
					# logger.debug(f'{self} gotincomingdata: {incoming_data}')
			except (ConnectionResetError, BrokenPipeError, struct.error, EOFError, OSError) as e:
				logger.error(f'{self} receive_data error:{e}')
				self.kill = True
				break
			if len(rawsockd) > 1:
				msgtype = None
				jmsg = None
				# if not isinstance(rawsockd, str) or not isinstance(rawsockd, dict):
				# 	try:
				# 		incoming_data = rawsockd[rawsockd.index('{'):]
				# 	except AttributeError as ae:
				# 		logger.error(f'{ae} {type(rawsockd)}\n{rawsockd}\n')
				# else:
				# 	incoming_data = rawsockd
				incoming_data = rawsockd
				if isinstance(incoming_data, str):
					try:
						jmsg = json.loads(incoming_data)
						# logger.debug(f'{self} gotincomingdata:\n{incoming_data}\n\njmsg:{jmsg}')
					except (json.decoder.JSONDecodeError) as e:
						logger.error(f'incoming_data error:{e} {type(e)} type: {type(incoming_data)} len: {len(incoming_data)}')
						logger.error(f'\nincoming_data: {incoming_data}\n')
						continue
					except TypeError as e:
						logger.error(f'incoming_data error:{e} {type(e)} type: {type(incoming_data)} len: {len(incoming_data)}')
						logger.error(f'\nincoming_data: {incoming_data}\n')
						continue
				elif isinstance(incoming_data, dict):
					jmsg = incoming_data
				if jmsg:
					self.clientq.put(jmsg)
					# msgtype = jmsg.get('msgtype')
					# if msgtype == 'cl_newplayer':# or jmsg.get('client_id') == 'newplayer1':
					# 	# logger.info(f'{msgtype} jmsg: {jmsg}')
					# 	# payload = {'msgtype':'bcsetclid', 'client_id':self.client_id}
					# 	# send_data(self.socket, payload=payload, pktid=gen_randid())
					# 	self.sender.queue.put((self.socket, self.bcsetclidpayload))
					# 	logger.info(f'{self} sending bcsetclid')

					# elif jmsg.get('client_id') == 'newplayer1':
					# 	logger.warning(f'{self} need client_id! jmsg: {jmsg}')
					# 	# payload = {'msgtype':'bcsetclid', 'client_id':self.client_id}
					# 	# send_data(self.socket, payload=payload, pktid=gen_randid())
					# 	self.sender.queue.put((self.socket, self.bcsetclidpayload))
					# elif msgtype == 's_ping':
					# 	logger.info(f'{msgtype} jmsg: {jmsg}')
					# elif msgtype == 'cl_pong':
					# 	self.sender.queue.put((self.socket, {'msgtype':'ch_ping', 'client_id':self.client_id}))
					# 	# logger.info(f'{msgtype} jmsg: {jmsg}')
					# elif msgtype == 'msgok':
					# 	logger.info(f'{msgtype} jmsg: {jmsg}')
					# elif msgtype == 'msgokack':
					# 	pass
					# 	# logger.info(f'{msgtype} jmsg: {jmsg}')
					# elif msgtype == 'cl_playerpos':
					# 	pass
					# 	# logger.info(f'{msgtype} jmsg: {jmsg}')
					# elif msgtype == 'gamemsg': # game ping
					# 	pass
					# elif msgtype == 'cl_playermove': # sent when player moves
					# 	pass
					# 	# logger.info(f'{msgtype} from {jmsg.get("client_id")} {jmsg.get("pos")} sqs: {self.sender} rqs: {self.receiver} ')
					# elif msgtype == 'error1':
					# 	logger.warning(f'{msgtype} jmsg: {jmsg}')
					# else:
					# 	logger.warning(f'unhandledmsgtype {msgtype} data: {incoming_data} jmsg={jmsg}')



def servermain():
	server = TestThreadedTCPServer(('127.0.0.1', 9696), TestHandler)
	# server = NewBombSever(('127.0.0.1', 9696), ThreadedTCPRequestHandler)
	#server = ThreadedTCPServer(('127.0.0.1', 9696), ThreadedTCPRequestHandler)
	server.serve_forever()
	# with server:
	# 	serverthread = Thread(target=server.serve_forever, daemon=True)
	# 	serverthread.start()
	# 	logger.debug(f'[S] {server} started')
		# while not server.kill:
		# 	if server.kill:
		# 		logger.warning(f'[S] {server} server killed')
		# 		server.socket.close()
		# 		return
def do_send(socket, serveraddress, payload):
	# payload = payload.zfill(PKTLEN)

	if isinstance(payload, str):
		payload = payload.encode('utf8')
	if isinstance(payload, dict):
		payload = json.dumps(payload).encode('utf8')
	payload = payload.zfill(PKTLEN)
	msglen = str(len(payload)).encode('utf8')
	msglen = msglen.zfill(PKTLEN)
	#msglen = msglen.zfill(4)
	#msglen += b' ' * (PKTLEN - len(payload))
	# logger.info(f'sending: {type(msglen)} {type(payload)}\n{payload}\n')
	try:
		socket.sendto(msglen,serveraddress )
	except TypeError as e:
		logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
	try:
		socket.sendto(payload,serveraddress)
	except TypeError as e:
		logger.error(f'{e} payloaderror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')

def newhandler(conn, addr):
	connected = True
	while connected:
		rawmsglen = conn.recv(PKTLEN).decode(FORMAT)
		msglen = int(re.sub('^0+','',rawmsglen))
		# logger.debug(f"raw: {type(rawmsglen)} {rawmsglen}  {msglen} ")
		try:
			datalen = msglen
			logger.debug(f"datalenmsglen: {datalen} {type(msglen)} {msglen} ")
		except ValueError as e:
			logger.warning(f'{e} {type(e)} msglen: {type(msglen)} {msglen}')
		except Exception as e:
			logger.error(f'{e} {type(e)} msglen: {type(msglen)} {msglen}')
		# datalen = int(re.sub('^0+','',msglen))
		if datalen:
			logger.debug(f"datalen: {type(datalen)} {datalen}")
			msg = conn.recv(datalen).decode(FORMAT)
			if msg == DISCONNECT_MESSAGE:
				connected = False
			logger.info(f"[{addr}] msg: {msg}")
			# msg = "Msg received".encode(FORMAT)
			msg = {'msgtype': 'servermsgresponse'}
			do_send(conn, addr, msg)

if __name__ == '__main__':
	socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	socket.bind(('127.0.0.1',9696))
	while True:
		socket.listen()
		conn, addr = socket.accept()
		thread = Thread(target=newhandler, args=(conn,addr))
		thread.start()
