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

def do_send(socket, serveraddress, payload):
	if isinstance(payload, str):
		payload = payload.encode('utf8')
	if isinstance(payload, dict):
		payload = json.dumps(payload).encode('utf8')
	payload = payload.zfill(PKTLEN)
	msglen = str(len(payload)).encode('utf8')
	msglen = msglen.zfill(PKTLEN)
	try:
		socket.sendto(msglen,serveraddress )
	except TypeError as e:
		logger.error(f'{e} msglenerror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')
	try:
		socket.sendto(payload,serveraddress)
	except TypeError as e:
		logger.error(f'{e} payloaderror = {type(msglen)} {msglen}\npayload = {type(payload)}\n{payload}\n')


class Gameserver(Thread):
	def __init__(self, connq):
		Thread.__init__(self,  daemon=True, name='gameserverthread')
		self.kill = False
		self.clients = []
		self.connq = connq
		self.dataq = Queue()

	def __repr__(self):
		return f'[gs] c:{len(self.clients)}'

	def newhandler(self, conn, addr):
		connected = True
		while connected:
			try:
				rawmsglen = conn.recv(PKTLEN).decode(FORMAT)
			except ConnectionResetError as e:
				logger.warning(f'{e}')
				connected = False
				break
			try:
				msglen = int(re.sub('^0+','',rawmsglen))
			except ValueError as e:
				logger.error(f'{e} {type(e)} rawmsglen: {type(rawmsglen)}\nrawm: {rawmsglen}')
				connected = False
				break
			# logger.debug(f"raw: {type(rawmsglen)} {rawmsglen}  {msglen} ")
			try:
				datalen = msglen
				# logger.debug(f"datalenmsglen: {datalen} {type(msglen)} {msglen} ")
			except ValueError as e:
				logger.warning(f'{e} {type(e)} msglen: {type(msglen)} {msglen}')
			except Exception as e:
				logger.error(f'{e} {type(e)} msglen: {type(msglen)} {msglen}')
			# datalen = int(re.sub('^0+','',msglen))
			if datalen:
				# logger.debug(f"datalen: {type(datalen)} {datalen}")
				rawmsg = conn.recv(datalen).decode(FORMAT)
				msgdata = re.sub('^0+','', rawmsg)
				# logger.info(f"[{addr}] msg: {msgdata}")
				self.dataq.put(msgdata)

	def run(self):
		logger.info(f'{self} started')
		while True:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			else:
				while not self.dataq.empty():
					data = self.dataq.get()
					self.dataq.task_done()
					data = json.loads(data)
					if 'error' in data:
						logger.warning(f'{self} serverdata:\n{data}\n')
					# logger.debug(f'data: {data}')
					msgtype = data.get('msgtype')
					match msgtype:
						case 'cl_newplayer':
							for client in self.clients:
								msg = {'msgtype': 'serverack', 'client': client.name, 'data': data}
								try:
									do_send(client._args[0], client._args[1], msg)
								except Exception as e:
									logger.error(f'[!] {e} in {self} {client}')
									self.clients.pop(self.clients.index(client))
						case 'cl_playermove':
							logger.debug(f'move {data.get("client_id")} c_pktid: {data.get("c_pktid")}')
							if data.get('action') == 'bomb':
								logger.debug(f'clientbomb from {data.get("client_id")}')
							for client in self.clients:
								msg = {'msgtype': 'server_playermove', 'client': client.name, 'data': data}
								try:
									do_send(client._args[0], client._args[1], msg)
								except Exception as e:
									logger.error(f'[!] {e} in {self} {client}')
									self.clients.pop(self.clients.index(client))

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
		conn, addr = mainsocket.accept()
		thread = Thread(target=server.newhandler, args=(conn,addr), name=f'clientthread{conncounter}')
		server.clients.append(thread)
		thread.start()
		conncounter += 1
		logger.info(f'started {thread} {conncounter}')
