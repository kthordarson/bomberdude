#!/usr/bin/python
import asyncio
from typing import Dict, Tuple
from contextlib import suppress
import sys
import json
from argparse import ArgumentParser
from threading import Thread, current_thread, Timer, active_count, _enumerate, Event
from queue import Queue, Empty
from loguru import logger
from constants import *
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
		logger.info(f'players={len(self.server.gs.players)} t:{active_count()}')
		for t in _enumerate():
			print(f'\t{t} {t.name} alive: {t.is_alive()}')
		# print(f'gamestate: {self.server.gs}')
		# print(f'gamestateplayers: {self.server.gs.players}')
		for p in self.server.gs.players:
			print(f'\tp={p} {self.server.gs.players[p]}')

	def dump_playerlist(self):
		logger.info(f'players: {len(self.server.gs.players)} ')
		for p in self.server.gs.players:
			print(f'\tplayer: {p} pos: {self.server.gs.players[p].get("position")}  b: {self.server.gs.players[p].get("bombsleft")} h: {self.server.gs.players[p].get("health")}  counter: {self.server.gs.players[p].get("counter")} ')

	def run(self):
		while not self.stopped():
			try:
				cmd = input(':> ')
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'd':
					self.server.debugmode = not self.server.debugmode
				if cmd[:1] == 'p':
					self.dump_playerlist()
				elif cmd[:1] == 'q':
					logger.warning(f'{self} {self.server} tuiquit')
					self.stop()
				else:
					logger.info(f'[tui] cmds: s=serverinfo, d=debugmode, p=playerlist, q=quit')
			except KeyboardInterrupt:
				self.stop()
				break

class BombServer():
	def __init__(self):
		self.ctx = Context()
		self.sock_push_gamestate: Socket = self.ctx.socket(zmq.PUB)
		self.sock_push_gamestate.bind('tcp://127.0.0.1:9696')

		self.sock_recv_player_evts: Socket = self.ctx.socket(zmq.PULL)
		self.sock_recv_player_evts.bind('tcp://127.0.0.1:9697')
		self.ticker_task = asyncio.create_task(self.ticker(self.sock_push_gamestate, self.sock_recv_player_evts),)
		self.debugmode = False
		self.gs = GameState(player_states=[], game_seconds=1, debugmode=self.debugmode)

	async def update_from_client(self, sockrecv):
		ufcl_cnt = 0
		game_events = None
		try:
			while True:
				msg = await sockrecv.recv_json()
				clid = msg['client_id']
				game_events = msg.get('game_events', None)
				events = msg.get('events', None)
				ufcl_cnt += 1
				event_dict = msg['event']
				event_dict['counter'] = msg['counter']
				event_dict['client_id'] = clid
				event_dict['ufcl_cnt'] = ufcl_cnt
				event_dict['game_events'] = game_events
				event_dict['events'] = events
				player_event = PlayerEvent(**event_dict)
				player_event.set_client_id(clid)
				self.gs.update_game_state(player_event, clid, msg)
				# if game_events:
				# 	logger.debug(f'playerevent={player_event} game_events:{game_events} msg:{msg}')
				#if events:
				#	logger.info(f'events:{events} msg:{msg}')
				# logger.info(f'msg={msg}')
		except asyncio.CancelledError as e:
			logger.error(f'{e} {type(e)}')


	async def ticker(self, sockpush, sockrecv):
		t = create_task(self.update_from_client(sockrecv))
		logger.debug(f'tickertask: {t}')
		# Send out the game state to all players 60 times per second.
		try:
			while True:
				self.gs.check_players()
				await sockpush.send_json(self.gs.to_json(self.debugmode))
				self.gs.game_events = []
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
	tui = ServerTUI(server, debugmode=args.debug)
	tui.start()
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
