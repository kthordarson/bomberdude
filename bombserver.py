#!/usr/bin/python
import asyncio
from typing import Dict, Tuple
from contextlib import suppress
import sys
import json
from argparse import ArgumentParser
from threading import Thread, current_thread, Timer, active_count, Event
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

	def dump_players(self):
		for p in self.server.game_state.players:
			# print(f'p={p} pos = {self.server.game_state.players[p]["position"]} score: {self.server.game_state.players[p]["score"]} msgdt:{self.server.game_state.players[p]["msg_dt"]}')
			print(f'p={p} {self.server.game_state.players[p]}')

	def get_serverinfo(self):
		print(f'players={len(self.server.game_state.players)} threads:{active_count()}')
		print(f'{self.server.game_state}')
		# print(f'gamestate: {self.server.game_state}')
		# print(f'gamestateplayers: {self.server.game_state.players}')
		for p in self.server.game_state.players:
			print(f"p={p} pos = {self.server.game_state.players[p]['position']} score: {self.server.game_state.players[p]['score']} msgdt:{self.server.game_state.players[p]['msg_dt']} timeout:{self.server.game_state.players[p]['timeout']}")

	def dumpgameevents(self):
		print(f'gamestate: {self.server.game_state} events: {len(self.server.game_state.game_events)}')
		for e in self.server.game_state.game_events:
			print(f'event: {e}')

	def cleargameevents(self):
		print(f'clearevents gamestate: {self.server.game_state} events: {len(self.server.game_state.game_events)}')
		self.server.game_state.game_events = []

	def printhelp(self):
		help = f'''
		cmds:
		s = show server info
		d = toggle debugmode {self.server.debugmode}
		ds = toggle debugmode for gamestate {self.server.game_state.debugmode}
		dst = toggle debugmode for gamestate {self.server.game_state.debugmode_trace}
		pd = toggle packetdebugmode {self.server.packetdebugmode}
		e = dump game events {len(self.server.game_state.game_events)}
		ec = clear game events
		'''
		print(help)

	def run(self):
		while not self.stopped():
			try:
				cmd = input(':> ')
				if cmd[:1] == '?' or cmd[:1] == 'h':
					self.printhelp()
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'l':
					self.dump_players()
				if cmd[:1] == 'e':
					self.dumpgameevents()
				if cmd[:2] == 'ec':
					self.cleargameevents()
				if cmd[:1] == 'd':
					self.server.debugmode = not self.server.debugmode
					logger.debug(f'sdbg={self.server.debugmode} {self.server.game_state.debugmode}')
				if cmd[:2] == 'ds':
					self.server.game_state.debugmode = not self.server.game_state.debugmode
					logger.debug(f'sdbg={self.server.debugmode} {self.server.game_state.debugmode}')
				if cmd[:3] == 'dst':
					self.server.game_state.debugmode_trace = not self.server.game_state.debugmode_trace
					logger.debug(f'trace sdbg={self.server.debugmode} {self.server.game_state.debugmode} {self.server.game_state.debugmode_trace}')
				if cmd[:2] == 'pd':
					self.server.packetdebugmode = not self.server.packetdebugmode
				elif cmd[:1] == 'q':
					logger.warning(f'{self} {self.server} tuiquit')
					self.stop()
				else:
					pass # logger.info(f'[tui] cmds: s=serverinfo, d=debugmode, p=playerlist, q=quit')
			except KeyboardInterrupt:
				self.stop()
				break

class BombServer():
	def __init__(self, args):
		self.args = args
		self.ctx = Context()
		self.sock_push_gamestate: Socket = self.ctx.socket(zmq.PUB)
		self.sock_push_gamestate.bind(f'tcp://{args.listen}:9696')

		self.sock_recv_player_evts: Socket = self.ctx.socket(zmq.PULL)
		self.sock_recv_player_evts.bind(f'tcp://{args.listen}:9697')
		self.ticker_task = asyncio.create_task(self.ticker(self.sock_push_gamestate, self.sock_recv_player_evts),)
		self.debugmode = False
		self.packetdebugmode = False
		self.game_state = GameState(game_seconds=1, debugmode=self.debugmode)
		# debugstuff
		self.ufc_counter = 0
		self.tick_count = 0

	async def update_from_client(self, sockrecv):
		try:
			while True:
				self.ufc_counter += 1
				msg = await sockrecv.recv_json()
				if self.packetdebugmode:
					logger.info(f'msg: {msg}')
				clid = msg['client_id']
				# game_events = msg.get('game_events', [])
				# event_dict = msg['event']
				# event_dict['counter'] = msg['counter']
				# event_dict['client_id'] = clid
				# event_dict['ufcl_cnt'] = self.ufc_counter
				# event_dict['game_events'] = game_events
				# player_event = PlayerEvent(**event_dict)
				# player_event.set_client_id(clid)
				self.game_state.update_game_state(clid, msg)
				self.game_state.update_game_events(msg)
		except asyncio.CancelledError as e:
			logger.error(f'{e} {type(e)}')

	async def ticker(self, sockpush, sockrecv):
		t = create_task(self.update_from_client(sockrecv))
		logger.debug(f'tickertask: {t}')
		# Send out the game state to all players 60 times per second.
		try:
			while True:
				self.tick_count += 1
				self.game_state.check_players()
				await sockpush.send_json(self.game_state.to_json())
				await asyncio.sleep(1 / SERVER_UPDATE_TICK_HZ)
				# self.game_state.game_events = []
		except asyncio.CancelledError as e:
			logger.error(f'{e} {type(e)}')
			t.cancel()
			await t

async def main(args):
	fut = asyncio.Future()
	# app = App(signal=fut)
	ctx = Context()
	server = BombServer(args)
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
