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
# import zmq
# from zmq.asyncio import Context
from aiohttp import web
import socket
from .tui import ServerTUI


class BombServer:
	def __init__(self, args):
		self.args = args
		self.debug = self.args.debug
		self.server_game_state = GameState(args=self.args, mapname=args.mapname, name='server')
		# self.client_queue = asyncio.Queue()  # Add queue for client messages
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
		self.playerindex = 0
		self._stop = Event()
		# debugstuff
		# self.app = Flask(import_name='bombserver')
		# self.app.run(host=args.listen, port=args.port)

	def __repr__(self):
		return 'BomberServer()'

	async def add_connection(self, conn, addr):
		"""Add a new client connection and set up handling"""
		try:
			# Add to server connections
			conn.setblocking(False)
			self.connections.add(conn)

			# Add to game state connections
			self.server_game_state.add_connection(conn)

			# Create and track client handling task
			task = self.loop.create_task(self.handle_client(conn))
			self.client_tasks.add(task)

			# Add cleanup callback when task is done
			task.add_done_callback(lambda t: self.cleanup_client(t, conn))

			logger.info(f"New connection added from {addr}. Total connections: {len(self.connections)} server_game_state: {len(self.server_game_state.connections)}")

			return task

		except Exception as e:
			logger.error(f"Error adding connection: {e}")
			if conn in self.connections:
				self.connections.remove(conn)
			if not conn._closed:
				conn.close()
			return None

	async def handle_connections(self):
		logger.debug(f"{self} starting handle_connections {self.loop}")
		try:
			self.sub_sock.setblocking(False)
			while not self.stopped():
				try:
					conn, addr = await self.loop.sock_accept(self.sub_sock)
					conn.setblocking(False)
					logger.debug(f"Accepted connection {len(self.connections)} from {addr}")
					await self.add_connection(conn, addr)
					# self.loop.create_task(self.handle_client(conn))
					# task = self.loop.create_task(self.handle_client(conn))
					# self.client_tasks.add(task)
					# task.add_done_callback(lambda t: self.connections.remove(conn))
					# logger.debug(f"Task {len(self.client_tasks)} {task} created for {addr} ")
				except (BlockingIOError, InterruptedError):
					await asyncio.sleep(0.01)
					continue
		except Exception as e:
			logger.error(f'Error in handle_connections: {e} {type(e)}')

	async def handle_client(self, conn):
		logger.info(f"handle_client: starting for conn: {conn} conns: {len(self.server_game_state.connections)}")
		try:
			while not self.stopped():
				try:
					# data = await self.loop.sock_recv(conn, 4096)
					data = await asyncio.wait_for(self.loop.sock_recv(conn, 4096),timeout=1.0)
					if not data:
						break
					msg = json.loads(data.decode('utf-8'))
					if self.args.debug:
						logger.info(f"msg: {msg}")
					await self.server_game_state.client_queue.put(msg)  # Put message in queue instead of processing directly
				except asyncio.TimeoutError:
					# Timeout is normal, just continue
					continue
				except json.JSONDecodeError as e:
					logger.error(f"Invalid JSON received: {e}")
					continue
				except ConnectionError as e:
					logger.error(f"Connection error: {e}")
					break
				except Exception as e:
					logger.error(f"Unexpected error in handle_client: {e}")
					break
		except Exception as e:
			logger.error(f"handle_client: {e} {type(e)}")
		finally:
			self.server_game_state.connections.remove(conn)
			logger.debug(f"{self} Socket closing")
			conn.close()

	def cleanup_client(self, task, conn):
		"""Clean up client connection and task"""
		logger.info(f'Cleaning up client {conn} task:{task}')
		try:
			self.connections.remove(conn)
			self.client_tasks.remove(task)
		except (KeyError, ValueError) as e:
			logger.warning(f'{e} {type(e)} while cleaning up client {conn} task:{task}')
		finally:
			if not conn._closed:
				conn.close()

	async def broadcast_state(self, state):
		"""Broadcast game state to all connected clients"""
		data = json.dumps(state).encode('utf-8')
		failed_conns = []

		for conn in self.connections:
			try:
				await self.loop.sock_sendall(conn, data)
			except (ConnectionError, BrokenPipeError) as e:
				logger.warning(f"Failed to send to client {conn}: {e}")
				failed_conns.append(conn)
			except Exception as e:
				logger.error(f"Unexpected error sending to client: {e}")
				failed_conns.append(conn)

		# Remove failed connections
		for conn in failed_conns:
			await self.cleanup_client(None, conn)

	async def process_messages(self):
		"""Process messages from client queue"""
		logger.debug(f"{self} message processing starting")
		while not self.stopped():
			try:
				msg = await self.server_game_state.client_queue.get()
				if self.args.debug:
					logger.debug(f"Processing message: {msg}")
				try:
					clid = str(msg["client_id"])
					self.server_game_state.update_game_state(clid, msg)
					if evts := msg.get("game_events", []):
						# await self.process_game_events(msg)
						await self.server_game_state.update_game_events(msg)
					game_state = self.server_game_state.to_json()
					await self.server_game_state.broadcast_state(game_state)
				except Exception as e:
					logger.error(f"Error processing message: {e}")
				finally:
					self.server_game_state.client_queue.task_done()
			except asyncio.CancelledError:
				break
			except Exception as e:
				logger.error(f"Message processing error: {e}")

	def get_game_state(self):
		return self.server_game_state.to_json()

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
					# if self.tui.stopped():
					# 	logger.warning(f"{self} update_from_clienttuistop {self.tui}")
					# 	break
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
		logger.warning(f"{self} stopping {self.stopped()} ")
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
		logger.debug(f"tickertask: {self.push_sock=}\n{self.sub_sock=}")
		self.process_task = self.loop.create_task(self.process_messages())
		# Send out the game state to all players 60 times per second.
		try:
			while not self.stopped():
				await self.handle_connections()
				try:
					# self.server_game_state.check_players()
					# await self.remove_timedout_players()
					game_state = self.server_game_state.to_json()
					# await self.send_data(game_state)
					await self.broadcast_state(game_state)  # Use new broadcast method
					# await self.server_game_state.broadcast_state(game_state)
					# await self.send_data(self.server_game_state.to_json())  # Send updated game state to clients
				except Exception as e:
					logger.error(f"{type(e)} {e} ")
				await asyncio.sleep(1 / UPDATE_TICK)
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
