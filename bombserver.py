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
from aiohttp import web
import socket
import pytiled_parser
import pytmx

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
		# self.server.stop()
		logger.warning(f"{self} stop {self.stopped()} server: {self.server.stopped()}")

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
		help = """
		cmds:
		s = show server info
		l = dump player list
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
					...
				elif cmd[:2] == "ds":
					...
				elif cmd[:3] == "dst":
					...
				elif cmd[:2] == "pd":
					...
				elif cmd[:1] == "q":
					logger.warning(f"{self} {self.server} tuiquit")
					# self.stop()
					asyncio.run_coroutine_threadsafe(self.server.stop(), self.server.loop)
					break
					# asyncio.run(self.server.stop())
					# asyncio.run_coroutine_threadsafe(self.server.stop(), self.server.loop)
					# self.server.sub_sock.close()
					# self.server.push_sock.close()
				else:
					pass  # logger.info(f'[tui] cmds: s=serverinfo, d=debug, p=playerlist, q=quit')
			except (EOFError, KeyboardInterrupt) as e:
				logger.warning(f"{type(e)} {e}")
				self.stop()
				asyncio.run_coroutine_threadsafe(self.server.stop(), self.server.loop)
				# self.server.stop()
				break


class BombServer:
	def __init__(self, args):
		self.args = args
		self.debug = self.args.debug
		self.server_game_state = GameState(args=self.args, mapname=args.mapname, name='server')
		self.client_queue = asyncio.Queue()  # Add queue for client messages
		self.connections = set()  # Track active connections
		self.client_tasks = set()  # Track active client tasks
		self.process_task = None

		# self.server_game_state.load_tile_map(args.mapname)
		# tmxdata = pytmx.TiledMap(args.mapname)

		# self.ctx = Context()
		# self.pushsock = self.ctx.socket(zmq.PUB)  # : Socket
		# self.pushsock.bind(f"tcp://{args.listen}:9696")
		# self.recvsock = self.ctx.socket(zmq.PULL)  # : Socket
		# self.recvsock.bind(f"tcp://{args.listen}:9697")
		self.sub_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.push_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		# Set socket options to allow port reuse
		self.sub_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.push_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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
		self._stop = Event()
		# debugstuff
		# self.app = Flask(import_name='bombserver')
		# self.app.run(host=args.listen, port=args.port)

	def __repr__(self):
		return 'BomberServer()'

	async def handle_connections(self):
		logger.debug(f"{self} starting handle_connections {self.loop}")
		try:
			conn, addr = await self.loop.sock_accept(self.sub_sock)
			self.connections.add(conn)
			logger.debug(f"Accepted connection {len(self.connections)} from {addr}")
			# self.loop.create_task(self.handle_client(conn))
			task = self.loop.create_task(self.handle_client(conn))
			self.client_tasks.add(task)
			task.add_done_callback(lambda t: self.connections.remove(conn))
			logger.debug(f"Task {len(self.client_tasks)} {task} created for {addr} ")
		except Exception as e:
			logger.error(f'Error in handle_connections: {e} {type(e)}')

	async def handle_client(self, conn):
		logger.info(f"handle_client: starting for conn: {conn}")
		try:
			while not self.stopped():
				try:
					data = await self.loop.sock_recv(conn, 4096)
					if not data:
						break
					msg = json.loads(data.decode('utf-8'))
					logger.info(f"msg: {msg}")
					await self.client_queue.put(msg)  # Put message in queue instead of processing directly
				except Exception as e:
					logger.error(f"Socket error: {e} {type(e)}")
		except Exception as e:
			logger.error(f"handle_client: {e} {type(e)}")
		finally:
			logger.debug(f"{self} Socket closing")
			conn.close()

	def cleanup_client(self, task, conn):
		"""Clean up client connection and task"""
		try:
			self.connections.remove(conn)
			self.client_tasks.remove(task)
		except (KeyError, ValueError):
			pass
		finally:
			if not conn.closed:
				conn.close()

	async def process_messages(self):
		"""Process messages from client queue"""
		while not self.stopped():
			try:
				msg = await self.client_queue.get()
				try:
					clid = str(msg["client_id"])
					self.server_game_state.update_game_state(clid, msg)
					if evts := msg.get("game_events", []):
						await self.process_game_events(msg)
				except Exception as e:
					logger.error(f"Error processing message: {e}")
				finally:
					self.client_queue.task_done()
			except asyncio.CancelledError:
				break
			except Exception as e:
				logger.error(f"Message processing error: {e}")

	async def get_game_state(self):
		return await self.server_game_state.to_json()

	async def get_tile_map(self, request):
		position = self.get_position()
		if self.args.debug:
			logger.debug(f'get_tile_map request: {request}  {self.args.mapname} {position}')
		return web.json_response({"mapname": str(self.args.mapname), "position": position})

	async def remove_timedout_players(self):
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
		# Get map dimensions in tiles
		map_width = self.server_game_state.tile_map.width
		map_height = self.server_game_state.tile_map.height

		# Get all collidable tiles
		collidable_positions = set()
		layer = self.server_game_state.tile_map.get_layer_by_name('Walls')
		for x, y, gid in layer:
			if gid != 0:
				collidable_positions.add((x, y))
		# for layer in self.server_game_state.tile_map.visible_layers:
		# 	if isinstance(layer, pytmx.TiledTileLayer) and layer.properties.get('collidable'):
		# 		for x, y, _ in layer:
		# 			collidable_positions.add((x, y))

		# Generate list of all possible positions excluding collidable tiles
		valid_positions = []
		for x in range(map_width):
			for y in range(map_height):
				if (x, y) not in collidable_positions:
					valid_positions.append((x, y))

		if not valid_positions:
			logger.error("No valid spawn positions found!")
			return {'position': (BLOCK, BLOCK)}  # fallback position

		# Choose random valid position
		pos = random.choice(valid_positions)
		position = (pos[0] * BLOCK, pos[1] * BLOCK)

		if self.args.debug:
			logger.debug(f'Generated valid position: {position}')

		return {'position': position}

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

	async def send_data(self, data):
		try:
			# Accept a single connection
			conn, addr = await self.loop.sock_accept(self.push_sock)
			try:
				# Use asyncio's sock_sendall
				await self.loop.sock_sendall(conn, json.dumps(await data).encode('utf-8'))
			except Exception as e:
				logger.warning(f"{type(e)} {e} in send_data {conn} {addr}")
			finally:
				conn.close()
		except Exception as e:
			logger.error(f"{type(e)} {e} in send_data {data}")

	async def oldsend_data(self, data):
		try:
			for conn, addr in self.push_sock.accept():
				try:
					# await conn.sendall(json.dumps(data).encode('utf-8'))
					await self.loop.sock_sendall(conn, json.dumps(data).encode('utf-8'))
					conn.close()
				except Exception as e:
					logger.warning(f"{type(e)} {e} in send_data {conn} {addr}")
		except Exception as e:
			logger.error(f"{type(e)} {e} in send_data {data}")

	async def stop(self):
		self._stop.set()
		logger.warning(f"{self} stopping {self.stopped()} tui: {self.tui} {self.tui.stopped()}")
		self.sub_sock.close()
		logger.warning(f"{self} {self.sub_sock} closed")
		self.push_sock.close()
		logger.warning(f"{self} {self.push_sock} closed")

		# Cancel ticker task
		if not self.ticker_task.done():
			self.ticker_task.cancel()
			logger.warning(f"{self} {self.ticker_task} cancelled")
			try:
				await self.ticker_task
			except asyncio.CancelledError:
				pass
		logger.warning(f"{self} stop {self.stopped()}")

	def stopped(self):
		return self._stop.is_set()

	async def ticker(self) -> None:
		# tt_updatefromclient = create_task(self.update_from_client(sockrecv))
		# apitsk =  create_task(self.apiserver._run(host=self.args.listen, port=9699),)
		logger.debug(f"tickertask: {self.push_sock=}\n{self.sub_sock=}")
		self.process_task = self.loop.create_task(self.process_messages())
		# Send out the game state to all players 60 times per second.
		try:
			while not self.stopped():
				await self.handle_connections()
				try:
					# self.server_game_state.check_players()
					# await self.remove_timedout_players()
					game_state = await self.server_game_state.to_json()
					await self.send_data(game_state)
					# await self.send_data(self.server_game_state.to_json())  # Send updated game state to clients
				except Exception as e:
					logger.error(f"{type(e)} {e} ")
				await asyncio.sleep(1 / UPDATE_TICK)  # SERVER_UPDATE_TICK_HZ
		except asyncio.CancelledError as e:
			logger.warning(f"tickertask CancelledError {e}")
		except Exception as e:
			logger.error(f"tickertask {e} {type(e)}")
		finally:
			logger.debug("Ticker task exiting")
			# Cancel message processing task
			if self.process_task:
				self.process_task.cancel()
				try:
					await self.process_task
				except asyncio.CancelledError:
					pass

			# Cancel all client tasks
			for task in self.client_tasks:
				task.cancel()
			if self.client_tasks:
				await asyncio.gather(*self.client_tasks, return_exceptions=True)


async def main(args) -> None:
	fut = asyncio.Future()
	# app = App(signal=fut)
	# ctx = Context()
	server = BombServer(args)
	# tui = ServerTUI(server, debug=args.debug)
	server.tui.start()
	apiserver = ApiServer("bombapi")
	apiserver.add_url_rule("/get_game_state", view_func=server.get_game_state, methods=["GET"])
	apiserver.add_url_rule("/get_tile_map", view_func=server.get_tile_map, methods=["GET"])
	apiserver.add_url_rule("/get_position", view_func=server.get_position, methods=["GET"])
	# apithread = Thread(target=apiserver.run, name=apiserver._import_name, args=(args.listen, 9699), daemon=True)
	api_task = asyncio.create_task(apiserver.run(args.listen, 9699))
	try:
		await asyncio.wait_for(apiserver.wait_until_ready(), timeout=5.0)
		# apithread.start()
		logger.debug(f'{server=} {server.tui=} {apiserver=}')
		# await asyncio.wait([server.ticker_task, fut], return_when=asyncio.FIRST_COMPLETED)
		await asyncio.wait([api_task, server.ticker_task, fut], return_when=asyncio.FIRST_COMPLETED)
	except CancelledError as e:
		logger.warning(f"main Cancelled {e}")
	finally:
		logger.info(f"main exit {server}")
		# server.tui.stop()
		# server.stop()
		# await server.ticker_task
		# server.loop.stop()
		# server.push_sock.close(1)
		# server.sub_sock.close(1)
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
	parser.add_argument("--map", action="store", dest="mapname", default="data/map3.tmx")
	args = parser.parse_args()
	run(main(args))
