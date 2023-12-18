#!/usr/bin/python
from time import sleep
import os
import socket
import select
import struct
import sys
import json
from threading import Thread, current_thread, Timer
from queue import Queue
import pygame
from loguru import logger
from pygame.event import Event
import re
from constants import (BLOCK, DEFAULTFONT, FPS, SENDUPDATEEVENT, SERVEREVENT, SQUARESIZE,NEWCLIENTEVENT,NEWCONNECTIONEVENT,PKTLEN,PKTHEADER)
from globals import gen_randid, RepeatedTimer
from map import Gamemap,generate_grid
from network import Sender, send_data, Receiver# , do_send

from socketserver import ThreadingMixIn, TCPServer, BaseRequestHandler, StreamRequestHandler

HEADER = 64
FORMAT = 'utf8'
DISCONNECT_MESSAGE = 'disconnect'

class ServerSendException(Exception):
	pass

class NewHandler(Thread):
	def __init__(self, conn, addr, dataq, name):
		Thread.__init__(self,  daemon=True, name=name)
		self.conn = conn
		self.addr = addr
		self.connected = True
		self.dataq = dataq
		self.name = name
		self.client_id = None

	def __repr__(self) -> str:
		return f'[h] {self.client_id} {self.name} {self.connected} {self.dataq.qsize()}'
	
	def run(self):		
		while self.connected:
			try:
				rawmsglen = self.conn.recv(PKTHEADER).decode(FORMAT)
			except ConnectionResetError as e:
				logger.warning(f'{self} {e}')
				self.connected = False
				break
			try:
				msglen = int(re.sub('^0+','',rawmsglen))
			except ValueError as e:
				logger.error(f'{self} {e} {type(e)}\nrawmsglen: {type(rawmsglen)}\nrawm: {rawmsglen}')
				# connected = False
				# conn.close()
				break
				#connected = False
				#conn.close()
			# logger.debug(f"raw: {type(rawmsglen)} {rawmsglen}  {msglen} ")
			if msglen:
				# logger.debug(f"datalen: {type(datalen)} {datalen}")
				try:
					rawmsg = self.conn.recv(msglen).decode(FORMAT)
				except OSError as e:
					logger.error(f'{self} {e} {type(e)} m:{msglen} rawmsglen: {type(rawmsglen)}\raw: {rawmsglen}')
					self.connected = False
					self.conn.close()
					break
				msgdata = re.sub('^0+','', rawmsg)
				data = json.loads(msgdata)
				if not self.client_id:
					self.client_id = data.get('client_id', None)
					logger.info(f'{self} client_id: {self.client_id}')
				self.dataq.put(data)
				if self.dataq.qsize() > 5:
					logger.info(f"{self} dataq: {self.dataq.qsize()}")

class Gameserver(Thread):
	def __init__(self, connq):
		Thread.__init__(self,  daemon=True, name='gameserverthread')
		self.kill = False
		self.clients = []
		self.connq = connq
		self.dataq = Queue()
		self.grid = generate_grid()
		self.playerlist = {}
		self.updcntr = 0

	def __repr__(self):
		return f'[gs] c:{len(self.clients)}'

	def trigger_newplayer(self):
		self.updcntr += 1
		for client in self.clients:
			logger.debug(f'{self} {self.updcntr} {client.name}')
			msg = {'msgtype': 'trigger_newplayer', 'client': client.name} 
			try:
				# self.do_send(client._args[0], client._args[1], msg)
				self.do_send(client.conn, client.addr, msg)
			except ServerSendException as e:
				logger.warning(f'[!] {e} in {self} {client}')
				self.clients.pop(self.clients.index(client))
			except Exception as e:
				logger.error(f'[!] {e} in {self} {client}')
				self.clients.pop(self.clients.index(client))

	def refresh_clients(self):
		# logger.info(f'playerlist {self.playerlist}\nclients: {self.clients}\n' )
		for cl in self.clients:
			# logger.info(f'cl: {cl} ')
			if not cl.client_id:
				pass
				# logger.warning(f'needclientid {cl} {self.clients}')
				# continue
			else:
				try:
					if not cl.connected:
						self.playerlist[cl.client_id]['connected'] = False
						logger.warning(f'{self} {cl} disconnected playerlist: {self.playerlist}')
						self.clients.pop(self.clients.index(cl))
						# self.playerlist.pop(self.playerlist.index(cl))
					elif cl.connected:
						self.playerlist[cl.client_id]['connected'] = True
				except KeyError as e:
					logger.error(f'{e} {type(e)} {cl} {self.playerlist} {self.clients}')
					continue


	def refresh_playerlist(self, data):
		# logger.debug(f'refresh_playerlist {data}')
		clid = data.get('client_id')
		if clid:
			self.playerlist[clid] = data
		else:
			logger.error(f'clid not found in {data}')
		# if len(self.playerlist) >= 2:
		#	logger.debug(f'playerlist:\n{self.playerlist}\n')
		# logger.debug(f'playerlist: {self.playerlist}')

	def do_send(self, socket, serveraddress, payload):
		payload['playerlist'] = self.playerlist
		payload['grid'] = self.grid
		payload['updcntr'] = self.updcntr
		# pmsgtype = payload.get("msgtype")
		# logger.debug(f'do_send pmsgtype: {pmsgtype} {type(payload)}')
		try:
			# logger.debug(f'do_send {socket} {serveraddress} {payload}')
			# if isinstance(payload, str):
			# 	payload = payload.encode('utf8')
			# if isinstance(payload, dict):
			payload = json.dumps(payload).encode('utf8')
			# payload = payload # .zfill(PKTLEN)
			msglenx = str(len(payload)).encode('utf8')
			msglen = msglenx.zfill(PKTHEADER)
			try:
				socket.sendto(msglen,serveraddress )
				# logger.debug(f'do_send_msglen {pmsgtype} len: {msglenx}')
			except TypeError as e:
				logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
			except OSError as e:
				logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
			try:
				socket.sendto(payload,serveraddress)
				# logger.debug(f'do_send payload: {pmsgtype} {type(payload)}')
			except OSError as e:
				logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
			except TypeError as e:
				logger.error(f'{e} payloaderror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
				raise ServerSendException(e)
		except Exception as e:
			logger.error(f'[!] {e} {type(e)} {type(payload)} {payload}')
			raise ServerSendException(e)

	def msg_handler(self, data):
		msgtype = data.get('msgtype')
		if not msgtype:
			logger.error(f'[!] msgtype not found in {data}')
		self.refresh_playerlist(data) # todo check disconnected clients
		match msgtype:
			case 'playertimer' | 'ackserveracktimer' | 'cl_playermove':
				msg = {'msgtype': 'serveracktimer'}
				if not data.get('gotgrid'):
					logger.warning(f'need grid data: {data}')
				if not data.get('gotplayerlist'):
					logger.warning(f'need gotplayerlist data: {data}')
				for client in self.clients:
					msg['clientname'] = client.name
					# logger.debug(f'{self} {msgtype} from {data.get("client_id")} sendingto: {client.name} ')
					try:
						# self.do_send(client._args[0], client._args[1], msg)
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} {type(e)} in {self} {client}\ndata: {type(data)} {data}\nmsg: {type(msg)} {msg}\n')
						self.clients.pop(self.clients.index(client))
			case 'cl_playerbomb':
				# todo place bomb on grid
				if not data.get('gotgrid'):
					logger.warning(f'data: {data}')
				for client in self.clients:
					msg = {'msgtype': 'ackplrbmb', 'client': client.name, 'data': data}
					logger.info(f'{msgtype} to {client.name} dclid: {data.get("client_id")} clbombpos: {data.get("clbombpos")}')
					try:
						# self.do_send(client._args[0], client._args[1], msg)
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
			case _:
				logger.warning(f'unknown msgtype {msgtype} from {data.get("client_id")}\ndata: {data}')
				for client in self.clients:
					msg = {'msgtype': 'serveracktimer', 'client': client.name, 'data': data}
					try:
						# self.do_send(client._args[0], client._args[1], msg)
						self.do_send(client.conn, client.addr, msg)
					except ServerSendException as e:
						logger.warning(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))
					except Exception as e:
						logger.error(f'[!] {e} in {self} {client}')
						self.clients.pop(self.clients.index(client))

	def run(self):
		logger.info(f'{self} started')
		while True:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			try:
				self.refresh_clients()
			except Exception as e:
				logger.error(f'{self} {e} {type(e)}')
			if not self.dataq.empty():
				datafromq = self.dataq.get()
				self.dataq.task_done()
				try:
					# data = json.loads(datafromq)
					self.msg_handler(datafromq)
				except json.decoder.JSONDecodeError as e:
					logger.error(f'{e} {type(e)} {type(datafromq)} {datafromq}')
					continue
				# logger.debug(f'{self} msghanlder {data}')



if __name__ == '__main__':
	mainsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	mainsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	connq = Queue()
	server = Gameserver(connq)
	server.start()
	try:
		mainsocket.bind(('127.0.0.1',9696))
	except OSError as e:
		logger.error(e)
		sys.exit(1)
	conncounter = 0
	while True:
		mainsocket.listen()
		try:
			conn, addr = mainsocket.accept()
		except KeyboardInterrupt as e:
			logger.warning(f'{e}')
			break
		except Exception as e:
			logger.warning(f'{e} {type(e)}')
			break
		# thread = Thread(target=server.newhandler, args=(conn,addr), name=f'clthrd{conncounter}')
		thread = NewHandler(conn,addr, server.dataq, name=f'clthrd{conncounter}')
		server.clients.append(thread)
		thread.start()
		conncounter += 1
		logger.info(f'{server} started {thread} {conncounter}')
		server.trigger_newplayer()
