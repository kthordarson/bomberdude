#!/usr/bin/python
import copy
import asyncio
import sys
import json
from argparse import ArgumentParser
from threading import Thread, Timer, active_count, Event
from loguru import logger
import random
from constants import BLOCK, GRIDSIZE, UPDATE_TICK
from gamestate import GameState
from asyncio import run, create_task, CancelledError
from api import ApiServer
# import zmq
# from zmq.asyncio import Context
import socket
import pytiled_parser


SERVER_UPDATE_TICK_HZ = 10


def generate_grid(gsz=GRIDSIZE):
	return json.loads(open("data/map.json", "r").read())


class ServerSendException(Exception):
	pass


class HandlerException(Exception):
	pass


class TuiException(Exception):
	pass


class RepeatedTimer:
	def __init__(self, interval, function, *args, **kwargs):
		self._timer = None
		self.interval = interval
		self.function = function
		self.args = args
		self.kwargs = kwargs
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
		logger.warning(f"{self} stop")


class ServerTUI(Thread):
	def __init__(self, server, debug=False, gq=None):
		Thread.__init__(self, daemon=True, name="tui")
		self.gq = gq
		self.server = server
		self.debug = debug
		self._stop = Event()

	def __repr__(self):
		return f"ServerTUI (s:{self.stopped()})"

	def stop(self):
		self._stop.set()
		logger.warning(f"{self} stop")

	def stopped(self):
		return self._stop.is_set()

	def dump_players(self):
		for p in self.server.server_game_state.players:
			# print(f'p={p} pos = {self.server.server_game_state.players[p]["position"]} score: {self.server.server_game_state.players[p]["score"]} msgdt:{self.server.server_game_state.players[p]["msg_dt"]}')
			logger.debug(f"p={p} {self.server.server_game_state.players[p]}")

	def get_serverinfo(self):
		logger.debug(f"players={len(self.server.server_game_state.players)} threads:{active_count()}")
		logger.debug(f"{self.server.server_game_state}")
		# print(f'gamestate: {self.server.server_game_state}')
		# print(f'gamestateplayers: {self.server.server_game_state.players}')
		for p in self.server.server_game_state.players:
			logger.debug(f"p={p} pos = {self.server.server_game_state.players[p]['position']} score: {self.server.server_game_state.players[p]['score']} msgdt:{self.server.server_game_state.players[p]['msg_dt']:.2f} timeout:{self.server.server_game_state.players[p]['timeout']}")

	def dumpgameevents(self):
		logger.debug(f"gamestate: {self.server.server_game_state} events: {len(self.server.server_game_state.game_events)}")
		for e in self.server.server_game_state.game_events:
			logger.debug(f"event: {e}")

	def cleargameevents(self):
		logger.debug(f"clearevents gamestate: {self.server.server_game_state} events: {len(self.server.server_game_state.game_events)}")
		self.server.server_game_state.game_events = []

	def printhelp(self):
		help = f"""
		cmds:
		s = show server info
		l = dump player list
		r = remove timedout players
		d = toggle debug {self.server.debug}
		ds = toggle debug for gamestate {self.server.server_game_state.debug}
		dst = toggle debug for gamestate {self.server.server_game_state.debugmode_trace}
		pd = toggle packetdebugmode {self.server.packetdebugmode}
		e = dump game events {len(self.server.server_game_state.game_events)}
		ec = clear game events
		"""
		print(help)

	def run(self) -> None:
		while not self.stopped():
			try:
				cmd = input(":> ")
				if cmd[:1] == "?" or cmd[:1] == "h":
					self.printhelp()
				elif cmd[:1] == "s":
					self.get_serverinfo()
				elif cmd[:1] == "r":
					self.server.remove_timedout_players()
				elif cmd[:1] == "l":
					self.dump_players()
				elif cmd[:1] == "e":
					self.dumpgameevents()
				elif cmd[:2] == "ec":
					self.cleargameevents()
				elif cmd[:1] == "d":
					self.server.debug = not self.server.debug
					logger.debug(f"sdbg={self.server.debug} {self.server.server_game_state.debug}")
				elif cmd[:2] == "ds":
					self.server.server_game_state.debug = (
						not self.server.server_game_state.debug
					)
					logger.debug(f"sdbg={self.server.debug} {self.server.server_game_state.debug}")
				elif cmd[:3] == "dst":
					self.server.server_game_state.debugmode_trace = (
						not self.server.server_game_state.debugmode_trace
					)
					logger.debug(f"trace sdbg={self.server.debug} {self.server.server_game_state.debug} {self.server.server_game_state.debugmode_trace}")
				elif cmd[:2] == "pd":
					self.server.packetdebugmode = not self.server.packetdebugmode
				elif cmd[:1] == "q":
					logger.warning(f"{self} {self.server} tuiquit")
					self.stop()
					self.server.sub_sock.close()
					self.server.push_sock.close()
				else:
					pass  # logger.info(f'[tui] cmds: s=serverinfo, d=debug, p=playerlist, q=quit')
			except (EOFError, KeyboardInterrupt) as e:
				logger.warning(f"{type(e)} {e}")
				self.stop()
				break


class BombServer:
	def __init__(self, args):
		self.args = args
		self.debug = self.args.debug
		self.server_game_state = GameState(args=self.args, mapname=args.mapname, name='server')
		self.server_game_state.load_tile_map(args.mapname)
		# self.ctx = Context()
		# self.pushsock = self.ctx.socket(zmq.PUB)  # : Socket
		# self.pushsock.bind(f"tcp://{args.listen}:9696")
		# self.recvsock = self.ctx.socket(zmq.PULL)  # : Socket
		# self.recvsock.bind(f"tcp://{args.listen}:9697")
		self.sub_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.push_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sub_sock.bind((self.args.host, 9696))
		self.push_sock.bind((self.args.host, 9697))
		self.sub_sock.listen(5)
		self.push_sock.listen(5)
		self.loop = asyncio.get_event_loop()
		# self.ticker_task = asyncio.create_task(self.ticker(self.pushsock, self.recvsock,),)
		self.ticker_task = asyncio.create_task(self.ticker(),)
		self.packetdebugmode = self.args.packetdebugmode
		self.tui = ServerTUI(self, debug=args.debug)
		self.playerindex = 0
		# debugstuff
		# self.app = Flask(import_name='bombserver')
		# self.app.run(host=args.listen, port=args.port)

	def __repr__(self):
		return 'BomberServer()'

	async def handle_connections(self):
		logger.debug(f"{self} starting handle_connections {self.loop}")
		while True:
			conn, addr = await self.loop.sock_accept(self.sub_sock)
			logger.debug(f"Accepted connection from {addr}")
			self.loop.create_task(self.handle_client(conn))
			logger.debug(f"Task created for {addr}")

	async def handle_client(self, conn):
		try:
			data = await self.loop.sock_recv(conn, 4096)
			if not data:
				return
			msg = json.loads(data.decode('utf-8'))
			logger.info(f"msg: {msg}")
			clid = str(msg["client_id"])
			try:
				self.server_game_state.update_game_state(clid, msg)
			except KeyError as e:
				logger.warning(f"{type(e)} {e} {msg=}")
			except Exception as e:
				logger.error(f"{type(e)} {e} {msg=}")
			evkeycnt = len(msg.get("game_events", []))
			if evkeycnt > 0:
				logger.debug(f"evk: {evkeycnt} gameevent: {msg.get('game_events', [])}")
				try:
					self.server_game_state.update_game_events(msg)
				except AttributeError as e:
					logger.warning(f"{type(e)} {e} {msg=}")
				except KeyError as e:
					logger.warning(f"{type(e)} {e} {msg=}")
				except TypeError as e:
					logger.warning(f"{type(e)} {e} {msg=}")
				except Exception as e:
					logger.error(f"{type(e)} {e} {msg=}")
		except socket.error as e:
			logger.error(f"Socket error: {e}")
		finally:
			logger.debug(f"{self} Socket closing")
			conn.close()

	def oldhandle_connections(self):
		logger.debug(f"{self} starting handle_connections")
		while True:
			conn, addr = self.sub_sock.accept()
			logger.debug(f"Accepted connection from {addr}")
			try:
				data = conn.recv(4096)
				if not data:
					break
				msg = json.loads(data.decode('utf-8'))
				# if self.packetdebugmode and len(msg.get('game_events')) > 0:
				logger.info(f"msg: {msg}")
				clid = str(msg["client_id"])
				try:
					self.server_game_state.update_game_state(clid, msg)
				except KeyError as e:
					logger.warning(f"{type(e)} {e} {msg=}")
				except Exception as e:
					logger.error(f"{type(e)} {e} {msg=}")
				evkeycnt = len(msg.get("game_events", []))
				if evkeycnt > 0:
					logger.debug(f"evk: {evkeycnt} gameevent: {msg.get('game_events', [])}")
					try:
						self.server_game_state.update_game_events(msg)
					except AttributeError as e:
						logger.warning(f"{type(e)} {e} {msg=}")
					except KeyError as e:
						logger.warning(f"{type(e)} {e} {msg=}")
					except TypeError as e:
						logger.warning(f"{type(e)} {e} {msg=}")
					except Exception as e:
						logger.error(f"{type(e)} {e} {msg=}")
			except socket.error as e:
				logger.error(f"Socket error: {e}")
			finally:
				logger.debug(f"{self} Socket closing")
				conn.close()

	async def get_game_state(self):
		return self.server_game_state.to_json()

	async def get_tile_map(self):
		mapname = str(self.server_game_state.tile_map.tiled_map.map_file)
		if "maptest2" in mapname:
			map4pos = [
				(2, 2),
				(3, 25),
				(27, 2),
				(25, 25),
			]
			position = (
				map4pos[self.playerindex][0] * 64,
				map4pos[self.playerindex][1] * 64,
			)
			self.playerindex = len(self.server_game_state.players)
		elif "maptest5" in mapname:
			map4pos = [
				(2, 2),
				(2, 38),
				(58, 2),
				(58, 38),
			]
			position = (
				map4pos[self.playerindex][0] * 32,
				map4pos[self.playerindex][1] * 32,
			)
			self.playerindex = len(self.server_game_state.players)
		elif "maptest4" in mapname:
			map4pos = [
				(2, 2),
				(25, 27),
				(27, 2),
				(2, 22),
			]
			position = (
				map4pos[self.playerindex][0] * 32,
				map4pos[self.playerindex][1] * 32,
			)
			self.playerindex = len(self.server_game_state.players)
		else:
			position = self.get_position()
		if self.debug:
			logger.debug(f'get_tile_map {mapname} {position}')
		return {"mapname": str(mapname), "position": position}

	def remove_timedout_players(self):
		pcopy = copy.copy(self.server_game_state.players)
		len0 = len(self.server_game_state.players)
		for p in pcopy:
			try:
				if self.server_game_state.players[p].get("timeout", False):
					self.server_game_state.players.pop(p)
					logger.warning(f"remove_timedout_players {p} {len0}->{len(self.server_game_state.players)} {self.server_game_state.players[p]}")
				elif self.server_game_state.players[p].get("playerquit", False):
					self.server_game_state.players.pop(p)
					logger.debug(f"playerquit {p} {len0}->{len(self.server_game_state.players)}")
			except KeyError as e:
				logger.warning(f"keyerror in remove_timedout_players {e} {self.server_game_state.players[p]} {self.server_game_state.players}")

	def get_position(self, retas="int"):
		foundpos = False
		walls: pytiled_parser.Layer = self.server_game_state.tile_map.get_tilemap_layer("Walls")
		blocks: pytiled_parser.Layer = self.server_game_state.tile_map.get_tilemap_layer("Blocks")
		x = 0
		y = 0
		while not foundpos:
			x = random.randint(2, int(self.server_game_state.tile_map.width) - 2)
			y = random.randint(2, int(self.server_game_state.tile_map.height) - 2)
			if walls.data[x][y] == 0 and blocks.data[x][y] == 0:
				foundpos = True
				x1 = x * BLOCK  # self.server_game_state.tile_map.width
				y1 = y * BLOCK  # self.server_game_state.tile_map.width
				logger.debug(f"foundpos {x}/{x1} {y}/{y1}")
				return {'position': (x1, y1)}

	async def update_from_client(self, sockrecv) -> None:
		logger.debug(f"{self} starting update_from_client {sockrecv=}")
		try:
			while True:
				msg = await sockrecv.recv_json()
				if self.packetdebugmode and len(msg.get('game_events')) > 0:  # and msg['msgsource'] != "pushermsgdict":
					logger.info(f"msg: {msg}")
				clid = str(msg["client_id"])
				try:
					self.server_game_state.update_game_state(clid, msg)
				except KeyError as e:
					logger.warning(f"{type(e)} {e} {msg=}")
				except Exception as e:
					logger.error(f"{type(e)} {e} {msg=}")
				evkeycnt = len(msg.get("game_events", []))
				if evkeycnt > 0:
					logger.debug(f"evk: {evkeycnt} gameevent: {msg.get('game_events', [])}")
					try:
						self.server_game_state.update_game_events(msg)
					except AttributeError as e:
						logger.warning(f"{type(e)} {e} {msg=}")
					except KeyError as e:
						logger.warning(f"{type(e)} {e} {msg=}")
					except TypeError as e:
						logger.warning(f"{type(e)} {e} {msg=}")
					except Exception as e:
						logger.error(f"{type(e)} {e} {msg=}")
					if self.tui.stopped():
						logger.warning(f"{self} update_from_clienttuistop {self.tui}")
						break
		except asyncio.CancelledError as e:
			logger.warning(f"update_from_client CancelledError {e} ")

	def send_data(self, data):
		try:
			for conn, addr in self.push_sock.accept():
				try:
					conn.sendall(json.dumps(data).encode('utf-8'))
					conn.close()
				except Exception as e:
					logger.warning(f"{type(e)} {e} in send_data {conn} {addr}")
		except Exception as e:
			logger.error(f"{type(e)} {e} in send_data {data}")

	async def ticker(self) -> None:
		# tt_updatefromclient = create_task(self.update_from_client(sockrecv))
		# apitsk =  create_task(self.apiserver._run(host=self.args.listen, port=9699),)
		logger.debug(f"tickertask: {self.push_sock=}\n{self.sub_sock=}")
		# Send out the game state to all players 60 times per second.
		try:
			while True:
				await self.handle_connections()
				try:
					self.server_game_state.check_players()
				except TypeError as e:
					logger.warning(f"self.server_game_state.check_players() {e}")
				try:
					self.remove_timedout_players()
				except Exception as e:
					logger.warning(f"{type(e)} {e} in remove_timedout_players ")
				self.send_data(self.server_game_state.to_json())  # Send updated game state to clients
				await asyncio.sleep(1 / UPDATE_TICK)  # SERVER_UPDATE_TICK_HZ
				if self.tui.stopped():
					logger.warning(f"{self} tickertuistop tui: {self.tui}\n")
					break
				if self.tui.stopped():
					logger.warning(f"{self} tickertuistop tui: {self.tui}\n")
					break
		except asyncio.CancelledError as e:
			logger.warning(f"tickertask CancelledError {e}")
		except Exception as e:
			logger.error(f"tickertask {e} {type(e)}")


async def main(args) -> None:
	fut = asyncio.Future()
	# app = App(signal=fut)
	# ctx = Context()
	server = BombServer(args)
	logger.debug(f'{server=} {server.tui=}')
	# tui = ServerTUI(server, debug=args.debug)
	server.tui.start()
	apiserver = ApiServer("bombapi")
	logger.debug(f'{apiserver=}')
	apiserver.add_url_rule("/get_game_state", view_func=server.get_game_state, methods=["GET"])
	apiserver.add_url_rule("/get_tile_map", view_func=server.get_tile_map, methods=["GET"])
	apiserver.add_url_rule("/get_position", view_func=server.get_position, methods=["GET"])
	apithread = Thread(target=apiserver.run, name=apiserver._import_name, args=(args.listen, 9699), daemon=True)
	logger.info(f"ticker_task:{server.ticker_task} starting {apithread=}")
	apithread.start()
	logger.info(f"started {apithread=}")

	try:
		await asyncio.wait([server.ticker_task, fut], return_when=asyncio.FIRST_COMPLETED)
	except CancelledError as e:
		logger.warning(f"main Cancelled {e}")
	finally:
		server.ticker_task.cancel()
		await server.ticker_task
		server.push_sock.close(1)
		server.sub_sock.close(1)
		# ctx.destroy(linger=1000)


if __name__ == "__main__":
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	parser = ArgumentParser(description="server")
	parser.add_argument("--host", action="store", dest="host", default="127.0.0.1")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
	parser.add_argument("--port", action="store", dest="port", default=9696, type=int)
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-dp", "--debugpacket", action="store_true", dest="packetdebugmode", default=False,)
	parser.add_argument("--map", action="store", dest="mapname", default="data/maptest2.json")
	args = parser.parse_args()
	run(main(args))
