#!/usr/bin/python
import enum
import struct
import asyncio
from typing import Dict, Tuple
from contextlib import suppress
import time
import os
import random
import socket
import sys
import json
from argparse import ArgumentParser
import threading
from threading import Thread, current_thread, Timer, active_count, _enumerate, Event
from queue import Queue, Empty
from loguru import logger
import re
import pickle
import arcade
from constants import *
from exceptions import *
from objects import gen_randid
from objects import PlayerEvent, PlayerState, GameState,KeysPressed
from asyncio import run, create_task, CancelledError

import zmq
from zmq.asyncio import Context, Socket
SERVER_UPDATE_TICK_HZ = 10
def generate_grid(gsz=GRIDSIZE):
	return json.loads(open('data/map.json','r').read())

class ServerSendException(Exception):
	pass

class HandlerException(Exception):
	pass

class TuiException(Exception):
	pass

_MAX_DATAGRAM_BODY = 32000


class _NetFlags(enum.IntFlag):
	DATA = 0x1
	ACK = 0x2
	NAK = 0x4
	EOM = 0x8
	UNRELIABLE = 0x10
	CTL = 0x8000


_SUPPORTED_FLAG_COMBINATIONS = (
	_NetFlags.DATA,    # Should work but I don't think it's been seen in the wild
	_NetFlags.DATA | _NetFlags.EOM,
	_NetFlags.UNRELIABLE,
	_NetFlags.ACK,
)

class DatagramError(Exception):
	pass


class RepeatedTimer():
	def __init__(self, interval, function, *args, **kwargs):
		self._timer     = None
		self.interval   = interval
		self.function   = function
		self.args       = args
		self.kwargs     = kwargs
		self.is_running = False
		self.start()

	def _run(self):
		self.is_running = False
		self.start()
		self.function(*self.args, **self.kwargs)

	def start(self):
		if not self.is_running:
			self._timer = Timer(self.interval, self._run)
			self._timer.start()
			self.is_running = True

	def stop(self):
		self._timer.cancel()
		self.is_running = False
		logger.warning(f'{self} stop')


class ServerTUI(Thread):
	def __init__(self, server, debugmode=False, gq=None):
		Thread.__init__(self, daemon=True, name='tui')
		self.gq = gq
		self.server = server
		self.debugmode = debugmode
		self._stop = Event()

	def __repr__(self):
		return f'ServerTUI (s:{self.stopped()})'

	def stop(self):
		self._stop.set()
		logger.warning(f'{self} stop')

	def stopped(self):
		return self._stop.is_set()

	def get_serverinfo(self):
		logger.info(f'players={len(self.server.players)} t:{active_count()}')
		for t in _enumerate():
			print(f'\t{t} {t.name} alive: {t.is_alive()}')

	def dump_playerlist(self):
		logger.info(f'players: {len(self.server.players)} clientlist: {len(self.server.clients)}')
		for p in self.server.players:
			print(f'\tplayer: {p} pos: {self.server.players[p].get("pos")} gp: {self.server.players[p].get("gridpos")} b: {self.server.players[p].get("bombsleft")} h: {self.server.players[p].get("health")} uc: {self.server.players[p].get("runcounter")} ')
		for c in self.server.clients:
			print(f'\tclient: {c.name} id: {c.client_id} connected: {c.connected} hqs: {c.handlerq.qsize()}')
			c.send_ping()

	def run(self):
		while not self.stopped():
			try:
				cmd = input(':> ')
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'p':
					self.dump_playerlist()
				elif cmd[:1] == 'q':
					logger.warning(f'{self} {self.server} tuiquit')
					self.gq.put({'msgtype':'quit'})
					# raise TuiException('tui killed')
					self.stop()
				# else:
				#	logger.info(f'[tui] {self} server: {self.server}')
			except KeyboardInterrupt:
				self.stop()
				break

def apply_movement(speed, dt, curpos , key: KeysPressed):
	cx = 0
	cy = 0
	oldpos = [curpos[0], curpos[1]]
	newpos = [curpos[0], curpos[1]]
	# logger.info(f'curpos: {curpos} {type(curpos)} k:{key}')
	if key == arcade.key.UP or key == arcade.key.W or key == 119  or key.keys[119]:
		newpos[1] += PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.DOWN or key == arcade.key.S or key == 115  or key.keys[115]:
		newpos[1] -= PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.LEFT or key == arcade.key.A or key == 97 or key.keys[97]:
		newpos[0] -= PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.RIGHT or key == arcade.key.D or key == 100  or key.keys[100]:
		newpos[0] += PLAYER_MOVEMENT_SPEED
		# logger.debug(f'movement k: {key} op: {oldpos} cp:{curpos} np:{newpos}')
	elif key == arcade.key.SPACE:
		pass
	# logger.info(f'curpos: {curpos} np:{newpos} k:{key} ')
	return newpos
	# delta_position = (sum([k for k in kp.keys]),sum([k for k in kp.keys]))
	#return current_position + delta_position * speed * dt


class BombServer():
	def __init__(self):
		self.ctx = Context()
		self.sock_push_gamestate: Socket = self.ctx.socket(zmq.PUB)
		self.sock_push_gamestate.bind('tcp://127.0.0.1:9696')

		self.sock_recv_player_evts: Socket = self.ctx.socket(zmq.PULL)
		self.sock_recv_player_evts.bind('tcp://127.0.0.1:9697')
		self.gs = GameState(player_states=[], game_seconds=1)
		self.ticker_task = asyncio.create_task(self.ticker(self.sock_push_gamestate, self.sock_recv_player_evts),)
		self.players = {}

	def update_game_state(self, event: PlayerEvent, clid, msg):
		# logger.debug(f'gs: {gs} event:{event} from: {clid}')
		# logger.info(f'msg={msg}')
		plrs = msg.get('players', [])
		for p in plrs:
			pos = plrs.get(p).get('position')
			self.players[p] = {'position' : pos }
		for ps in self.gs.player_states:
			if ps.client_id == 'bstmissing':
				ps.client_id = clid
				logger.debug(f'bstmissing ps:{ps} setting clid to {clid} gs: {self.gs} event:{event}')
			dt = time.time() # - (player_state.updated)
			oldpspos = ps.position
			# current_position = apply_movement(player_state.speed, dt, current_position, event)
			current_position = apply_movement(PLAYER_MOVEMENT_SPEED, dt, oldpspos, event)
			ps.position = current_position # = current_position[0]
			#ps.y = current_position[1]
			ps.updated = time.time()
			self.players[clid] = {'position': ps.position}
			#if len(self.players) > 1:
			#	logger.info(f'clid:{clid} oldpspos={oldpspos} pspos={ps.position} players: {len(self.players)}')# ps={ps}  gs: {self.gs} event={event}')
				# logger.debug(f'players={self.players}')

	async def update_from_client(self, sockrecv):
		ufcl_cnt = 0
		try:
			while True:
				msg = await sockrecv.recv_json()
				# msg={'counter': 1445, 'event': {'keys': {'65362': False, '119': False, '65364': False, '115': False, '65361': False, '97': False, '65363': False, '100': False, '113': False}, 'client_id': '3187165f87', 'ufcl_cnt': 2286}, 'client_id': '3187165f87', 'position': [111.0, 133]}
				ufcl_cnt += 1
				self.gs.game_seconds += 1
				counter = msg['counter']
				event_dict = msg['event']
				clid = msg['client_id']
				event_dict['client_id'] = clid
				event_dict['ufcl_cnt'] = ufcl_cnt
				# event_dict = await sock.recv_json()
				event = PlayerEvent(**event_dict)
				event.set_client_id(clid)
				self.update_game_state(event, clid, msg)
				# logger.info(f'msg={msg}')
		except asyncio.CancelledError as e:
			logger.error(f'{e} {type(e)}')


	async def ticker(self, sockpush, sockrecv):
		logger.debug(f'tickerstart')
		# s = gs.to_json()
		# print(f's:{s}')

		# A task to receive keyboard and mouse inputs from players.
		# This will also update the game state, gs.
		t = create_task(self.update_from_client(sockrecv))
		logger.debug(f'gs: {self.gs}  t:{t}')

		# Send out the game state to all players 60 times per second.
		try:
			while True:
				await sockpush.send_string(self.gs.to_json(self.players))
				# print('.', end='', flush=True)
				await asyncio.sleep(1 / SERVER_UPDATE_TICK_HZ)
		except asyncio.CancelledError as e:
			logger.error(f'{e} {type(e)}')
			t.cancel()
			await t



async def main(args):
	fut = asyncio.Future()
	# app = App(signal=fut)
	ctx = Context()
	server = BombServer()
	logger.info(f'ticker_task:{server.ticker_task}')
	try:
		await asyncio.wait([server.ticker_task, fut],return_when=asyncio.FIRST_COMPLETED)
	except CancelledError as e:
		logger.error(f'{e} {type(e)} cancel')
	finally:
		server.ticker_task.cancel()
		await server.ticker_task
		server.sock_push_gamestate.close(1)
		server.sock_recv_player_evts.close(1)
		ctx.destroy(linger=1000)


if __name__ == '__main__':
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	parser = ArgumentParser(description='server')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696, type=int)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()
	run(main(args))
	# loop = asyncio.get_event_loop()
	# loop.create_task(main(args, loop))
	# loop.run_forever()
	# loop.close()
