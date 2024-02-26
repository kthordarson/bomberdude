#!/usr/bin/python
import copy
from flask import Flask
import asyncio
from typing import Dict, Tuple
from contextlib import suppress
import sys
import json
from argparse import ArgumentParser
from threading import Thread, current_thread, Timer, active_count, Event
from queue import Queue, Empty
from loguru import logger
import random
from constants import *
from objects import gen_randid
from gamestate import GameState
from asyncio import run, create_task, CancelledError
from api import ApiServer
import zmq
from zmq.asyncio import Context, Socket
import pytiled_parser


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
		r = remove timedout players
		d = toggle debugmode {self.server.debugmode}
		ds = toggle debugmode for gamestate {self.server.game_state.debugmode}
		dst = toggle debugmode for gamestate {self.server.game_state.debugmode_trace}
		pd = toggle packetdebugmode {self.server.packetdebugmode}
		e = dump game events {len(self.server.game_state.game_events)}
		ec = clear game events
		'''
		print(help)

	def run(self) -> None:
		while not self.stopped():
			try:
				cmd = input(':> ')
				if cmd[:1] == '?' or cmd[:1] == 'h':
					self.printhelp()
				if cmd[:1] == 's':
					self.get_serverinfo()
				if cmd[:1] == 'r':
					self.server.remove_timedout_players()
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
		self.ufc_counter = 0
		self.tick_count = 0
		self.debugmode = self.args.debugmode
		self.game_state = GameState(game_seconds=1, debugmode=self.debugmode)


		self.ctx = Context()
		self.pushsock = self.ctx.socket(zmq.PUB) # : Socket
		self.pushsock.bind(f'tcp://{args.listen}:9696')

		# self.datasock: Socket = self.ctx.socket(zmq.PUB)
		# self.datasock.bind(f'tcp://{args.listen}:9699')

		self.recvsock = self.ctx.socket(zmq.PULL) # : Socket
		self.recvsock.bind(f'tcp://{args.listen}:9697')
		self.ticker_task = asyncio.create_task(self.ticker(self.pushsock, self.recvsock, ),)
		self.packetdebugmode = self.args.packetdebugmode
		# debugstuff
		# self.app = Flask(import_name='bombserver')
		# self.app.run(host=args.listen, port=args.port)

	async def get_game_state(self):
		return self.game_state.to_json()

	async def get_tile_map(self):
		mapname = self.game_state.tile_map.tiled_map.map_file
		#tile_map = arcade.load_tilemap('data/map3.json', layer_options={"Blocks": {"use_spatial_hash": True},}, scaling=1)
		#tm = pickle.dumps(self.game_state.tile_map)
		position = self.get_position()
		return {'mapname': str(mapname), 'position': position}

	def remove_timedout_players(self):
		pcopy = copy.copy(self.game_state.players)
		for p in pcopy:
			if self.game_state.players[p]['timeout']:
				logger.warning(f'remove_timedout_players {p} {self.game_state.players[p]}')
				self.game_state.players.pop(p)

	def get_position(self, retas='int'):
		foundpos = False
		walls:pytiled_parser.Layer = self.game_state.tile_map.get_tilemap_layer('Walls')
		blocks:pytiled_parser.Layer = self.game_state.tile_map.get_tilemap_layer('Blocks')
		x = 0
		y = 0
		while not foundpos:
			x = random.randint(1, int(self.game_state.tile_map.width)-1)
			y = random.randint(1, int(self.game_state.tile_map.height)-1)
			# print(f'checking {x} {y}')
			if walls.data[x][y] == 0 and blocks.data[x][y] == 0:
				foundpos = True
				x1 = x * BLOCK # self.game_state.tile_map.width
				y1 = y * BLOCK # self.game_state.tile_map.width
				logger.debug(f'foundpos {x}/{x1} {y}/{y1}')
				if retas == 'int':
					return (x1,y1)
				else:
					return str(f'{x1},{y1}')


	async def update_from_client(self, sockrecv) -> None:
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

	async def ticker(self, sockpush, sockrecv) -> None:
		t = create_task(self.update_from_client(sockrecv))
		# apitsk =  create_task(self.apiserver._run(host=self.args.listen, port=9699),)
		logger.debug(f'tickertask: {t} ')
		# Send out the game state to all players 60 times per second.
		try:
			while True:
				self.tick_count += 1
				if self.packetdebugmode:
					logger.info(f'tick_count: {self.tick_count}')
				self.game_state.check_players()
				self.remove_timedout_players()
				await sockpush.send_json(self.game_state.to_json())
				await asyncio.sleep(1 / SERVER_UPDATE_TICK_HZ)
				# self.game_state.game_events = []
		except asyncio.CancelledError as e:
			logger.error(f'{e} {type(e)}')
			t.cancel()
			await t

async def main(args) -> None:
	fut = asyncio.Future()
	# app = App(signal=fut)
	ctx = Context()
	server = BombServer(args)
	tui = ServerTUI(server, debugmode=args.debugmode)
	tui.start()
	logger.info(f'ticker_task:{server.ticker_task}')
	apiserver = ApiServer('bombserver')
	apiserver.add_url_rule('/get_game_state', view_func=server.get_game_state, methods=['GET'])
	apiserver.add_url_rule('/get_tile_map', view_func=server.get_tile_map, methods=['GET'])
	apiserver.add_url_rule('/get_position', view_func=server.get_position, methods=['GET'])
	apithread = Thread(target=apiserver.run, args=(args.listen, 9699), daemon=True)
	apithread.start()

	try:
		await asyncio.wait([server.ticker_task, fut],return_when=asyncio.FIRST_COMPLETED)
	except CancelledError as e:
		logger.error(f'{e} {type(e)} cancel')
	finally:
		server.ticker_task.cancel()
		await server.ticker_task
		server.pushsock.close(1)
		server.recvsock.close(1)
		ctx.destroy(linger=1000)


if __name__ == '__main__':
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	parser = ArgumentParser(description='server')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696, type=int)
	parser.add_argument('-d','--debug', action='store_true', dest='debugmode', default=False)
	parser.add_argument('-dp','--debugpacket', action='store_true', dest='packetdebugmode', default=False)
	args = parser.parse_args()
	run(main(args))
