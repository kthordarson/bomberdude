#!/usr/bin/python
import time
import asyncio
import json
from threading import Event
from loguru import logger
import random
from constants import BLOCK
from gamestate import GameState
# import zmq
# from zmq.asyncio import Context
from aiohttp import web
import socket


class BombServer:
	def __init__(self, args):
		self.args = args
		self.server_game_state = GameState(args=self.args, mapname=args.mapname)
		self.connections = set()  # Track active connections
		self.client_tasks = set()  # Track active client tasks
		self.process_task = None
		self.loop = asyncio.get_event_loop()
		self.ticker_task = asyncio.create_task(self.ticker(),)
		self.playerindex = 0
		self._stop = Event()

	def __repr__(self):
		return 'BomberServer()'

	async def new_connection(self, conn, addr):
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

			# Broadcast the updated game state to all clients
			game_state = self.server_game_state.to_json()
			await self.server_broadcast_state(game_state)
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
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		s.bind((self.args.host, 9696))
		s.listen(5)
		s.setblocking(False)
		try:
			# self.sock.setblocking(False)
			while not self.stopped():
				try:
					conn, addr = await self.loop.sock_accept(s)
					conn.setblocking(False)
					logger.debug(f"Accepted connection {len(self.connections)} from {addr}")
					await self.new_connection(conn, addr)
				except (BlockingIOError, InterruptedError) as e:
					logger.error(f'{e} {type(e)} in handle_connections')
					continue
		except Exception as e:
			logger.error(f'Error in handle_connections: {e} {type(e)}')

	async def handle_client(self, conn):
		logger.info(f"handle_client: starting for conn: {conn} conns: {len(self.server_game_state.connections)}")
		try:
			while True:
				try:
					# data = await self.loop.sock_recv(conn, 4096)
					data = await asyncio.wait_for(self.loop.sock_recv(conn, 4096),timeout=0.2)
					if not data:
						break
					# logger.debug(f'data={data}')
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
				messages = data.decode('utf-8').split('\n')
				for message in messages:
					if message.strip():  # Ignore empty messages
						try:
							msg = json.loads(message)
							if self.args.debugpacket:
								if msg.get('game_event').get('event_type') != 'player_update':
									logger.debug(f"Received message: {msg.get('game_event').get('event_type')}")
							await self.server_game_state.client_queue.put(msg)  # Put message in queue instead of processing directly
						except json.JSONDecodeError as e:
							logger.warning(f"Error decoding json: {e} data: {data}")
							continue
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

	async def server_broadcast_state(self, state):
		# Don't send full game state every time
		if state.get('msgtype') == 'playerlist':
			# Strip unnecessary data to reduce packet size
			for player in state.get('playerlist', []):
				keys_to_keep = ['client_id', 'position', 'angle', 'health']
				for key in list(player.keys()):
					if key not in keys_to_keep:
						del player[key]

		data = json.dumps(state).encode('utf-8') + b'\n'

		# Use gather for concurrent sending
		send_tasks = []

		for conn in self.connections:
			send_tasks.append(self.loop.sock_sendall(conn, data))

		# Wait for all sends to complete
		try:
			await asyncio.gather(*send_tasks)
		except Exception as e:
			logger.error(f"Error during broadcast: {e}")

	def get_game_state(self):
		return self.server_game_state.to_json()

	async def get_tile_map(self, request):
		position = self.get_position()
		if self.args.debug:
			logger.debug(f'get_tile_map request: {request}  {self.args.mapname} {position}')
		return web.json_response({"mapname": str(self.args.mapname), "position": position})

	def get_position(self, retas="int"):
		# Get map dimensions in tiles
		map_width = self.server_game_state.tile_map.width
		map_height = self.server_game_state.tile_map.height

		# Get all collidable tiles
		collidable_positions = set()
		layers = []
		wall_layer = self.server_game_state.tile_map.get_layer_by_name('Walls')
		block_layer = self.server_game_state.tile_map.get_layer_by_name('Blocks')
		layers.append(wall_layer)
		layers.append(block_layer)
		for layer in layers:
			for x, y, gid in layer:
				if gid != 0:
					collidable_positions.add((x, y))

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
		# pos = random.choice(valid_positions)
		# position = (pos[0] * BLOCK, pos[1] * BLOCK)
		position = random.choice(valid_positions)

		if self.args.debug:
			logger.debug(f'Generated valid position: {position}')

		return {'position': position}

	async def stop(self):
		self._stop.set()
		# Cancel ticker task
		if not self.ticker_task.done():
			self.ticker_task.cancel()
			# logger.warning(f"{self} {self.ticker_task} cancelled")
			try:
				await self.ticker_task
			except asyncio.CancelledError:
				pass
		logger.info(f"{self} stop {self.stopped()}")

	def stopped(self):
		return self._stop.is_set()

	async def process_messages(self):
		"""Process messages from client queue"""
		logger.debug(f"{self} message processing starting")
		while not self.stopped():
			try:
				msg = await self.server_game_state.client_queue.get()
			except asyncio.QueueEmpty:
				continue
			self.server_game_state.client_queue.task_done()
			try:
				clid = msg.get('game_event').get('client_id')
			except Exception as e:
				logger.error(f"Error processing message: {e} {type(e)}	{msg}")
				break
			self.server_game_state.update_game_state(clid, msg)
			try:
				if evts := msg.get("game_event"):
					# await self.process_game_events(msg)
					game_event = msg.get('game_event')
					if self.args.debug:
						if evts.get('event_type') != 'player_update':
							logger.debug(f"{game_event.get('event_type')} event_queue: {self.server_game_state.event_queue.qsize()} client_queue: {self.server_game_state.client_queue.qsize()}")
					await self.server_game_state.update_game_event(game_event)
			except UnboundLocalError as e:
				logger.warning(f"UnboundLocalError: {e} {type(e)} {msg}")
			except asyncio.CancelledError as e:
				logger.info(f"CancelledError {e}")
				await self.stop()
				break
			except Exception as e:
				logger.error(f"Message processing error: {e} {type(e)} {msg}")
				await self.stop()
				break

	async def ticker(self) -> None:
		logger.debug(f"tickertask start")  # noqa: F541
		self.process_task = self.loop.create_task(self.process_messages())
		# Send out the game state to all players 60 times per second.
		last_broadcast = time.time()
		try:
			while not self.stopped():
				await self.handle_connections()
				try:
					# Broadcast player states to all clients (but at a sensible rate - not every frame)
					if time.time() - last_broadcast > 0.05:  # 20 updates per second instead of 60
						game_state = self.server_game_state.to_json()
						await self.server_broadcast_state(game_state)
				except Exception as e:
					logger.error(f"{type(e)} {e} ")
		except asyncio.CancelledError as e:
			logger.info(f"tickertask CancelledError {e}")
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
