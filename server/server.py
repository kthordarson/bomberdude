#!/usr/bin/python
import time
import asyncio
import json
from threading import Event
from loguru import logger
import random
from constants import BLOCK
from aiohttp import web
from game.gamestate import GameState
from server.api import ApiServer
from utils import gen_randid
from constants import UPDATE_TICK

class BombServer:
	def __init__(self, args):
		self.args = args
		self.server_game_state = GameState(args=self.args, mapname=args.mapname, client_id='theserver')
		self.apiserver = ApiServer(name="bombapi", server=self, game_state=self.server_game_state)
		self.connections = set()  # Track active connections
		self.client_tasks = set()  # Track active client tasks
		self.connection_to_client_id = {}  # Map connections to client IDs
		self.process_task = None
		self.loop = asyncio.get_event_loop()
		# self.ticker_broadcast = asyncio.create_task(self.ticker_broadcast(),)
		self._stop = Event()
		# self.discovery_service = ServerDiscovery(self)
		# asyncio.create_task(self.discovery_service.start_discovery_service())

	async def process_messages(self):
		"""Process messages from client queue"""
		logger.debug(f"{self} message processing starting")
		while not self.stopped():
			try:
				msg = await self.server_game_state.client_queue.get()
			except asyncio.QueueEmpty:
				continue
			self.server_game_state.client_queue.task_done()
			client_id = msg.get('client_id')
			if client_id in ('gamestatenotset', 'bdudenotset', 'missingclientid'):
				logger.error(f"client_id not set: {msg}")
				continue
			try:
				self.server_game_state.update_game_state(client_id, msg)
			except (TypeError, UnboundLocalError) as e:
				logger.warning(f"{e} {type(e)} {msg}")
			except asyncio.CancelledError as e:
				logger.info(f"CancelledError {e}")
				await self.stop()
				break
			except Exception as e:
				logger.error(f"Message processing error: {e} {type(e)} {msg}")
				await self.stop()
				break
			if msg.get('game_event'):
				game_event = msg.get('game_event')
				try:
					await self.server_game_state.update_game_event(game_event)
				except Exception as e:
					logger.error(f'{e} {type(e)} msg={msg}')

	async def client_connected_cb(self, reader, writer):
		"""Handle new client connections using StreamReader/StreamWriter"""
		addr = writer.get_extra_info('peername')
		# sock = writer.get_extra_info('socket')

		logger.info(f"New connection from {addr[0]} ")

		try:
			# Add to connection tracking
			# sock.setblocking(False)
			self.connections.add(writer)
			self.server_game_state.add_connection(writer)
			# Process first message to get client ID
			data = await asyncio.wait_for(reader.readline(), timeout=1.0)
			if not data:
				return
			message = data.decode('utf-8').strip()
			msg = json.loads(message)
			client_id = msg.get('client_id') or msg.get('game_event', {}).get('client_id')

			if client_id:
				ack_event = {
							"event_type": "acknewplayer",
							"client_id": client_id,
							"handled": False,
							"handledby": "server.client_connected",
							"event_time": time.time()
						}
				await self.server_game_state.broadcast_event(ack_event)
				# Store client ID
				self.connection_to_client_id[writer] = client_id

				# Create player_joined event
				player_joined = {
					"event_time": time.time(),
					"event_type": "player_joined",
					"client_id": client_id,
					"position": msg.get('position') or msg.get('game_event', {}).get('position', [100, 100]),
					"handled": False,
					"handledby": "client_connected_cb",
					"eventid": gen_randid()
				}

				# Broadcast to all clients
				await self.server_game_state.broadcast_event(player_joined)

				modified_tiles = {}
				for pos, gid in self.server_game_state.modified_tiles.items():
					modified_tiles[str(pos)] = gid

				# Send initial map info
				map_info = {
					"event_time": time.time(),
					"event_type": "map_info",
					"mapname": self.server_game_state.mapname,
					"modified_tiles": modified_tiles,
					"client_id": client_id,
					"handled": False,
				}
				if len(modified_tiles) > 0:
					logger.debug(f'modified_tiles: {len(modified_tiles)}')
					# Broadcast to all clients
					await self.server_game_state.broadcast_event(map_info)

			# Broadcast updated game state to all clients
			game_state = self.server_game_state.to_json()
			await self.server_broadcast_state(game_state)

			# Process client messages
			while not self.stopped():
				try:
					# Read one line (JSON message ending with newline)
					data = await asyncio.wait_for(reader.readline(), timeout=0.2)
					if not data:  # Connection closed
						break
					message = data.decode('utf-8').strip()
					if not message:  # Skip empty messages
						logger.warning(f'empty message from {addr[0]}')
						continue
					try:
						msg = json.loads(message)
						# Store client ID for this connection when we get it
						if 'client_id' in msg:
							self.connection_to_client_id[writer] = msg['client_id']
						elif msg.get('game_event', {}).get('client_id'):
							self.connection_to_client_id[writer] = msg['game_event']['client_id']
						await self.server_game_state.client_queue.put(msg)
					except json.JSONDecodeError as e:
						try:
							writer.close()
							# await writer.wait_closed()
							await asyncio.wait_for(writer.wait_closed(), timeout=0.1)
						except (ConnectionResetError, asyncio.TimeoutError, Exception) as e:
							# Already closed or timed out, just log and continue
							logger.error(f"Error during connection cleanup: {e} {addr}")
						client_id = self.connection_to_client_id.get(writer)
						logger.warning(f"Error decoding json: {e} from: {client_id} data: {message} fromaddr: {addr}")
						try:
							del self.connection_to_client_id[writer]
							del self.server_game_state.playerlist[client_id]
						except KeyError as e:
							logger.warning(f"{e} removing client_id: {client_id} addr: {addr} writer: {writer}")
						except Exception as e:
							logger.error(f"Error removing client_id: {e} {addr}")
						try:
							self.server_game_state.remove_connection(writer)
						except Exception as e:
							logger.error(f"Error removing client_id: {e} {addr}")
						try:
							self.connections.remove(writer)
						except Exception as e:
							logger.error(f"Error removing client_id: {e} {addr}")
				except asyncio.TimeoutError:
					# This is normal, just continue
					continue
				except ConnectionError as e:
					logger.info(f"Connection {e} {addr}")
					break
				except Exception as e:
					logger.error(f"Unexpected {e} {type(e)} in client handler {addr}")
					break
		finally:
			client_id = self.connection_to_client_id.get(writer)
			# Clean up connection
			if writer in self.connections:
				self.connections.remove(writer)
			if writer in self.server_game_state.connections:
				self.server_game_state.connections.remove(writer)
			if writer in self.connection_to_client_id:
				del self.connection_to_client_id[writer]

			# Remove player from playerlist if we have their client ID
			if client_id and client_id in self.server_game_state.playerlist:
				logger.info(f"Removing {addr} player {client_id} from game")
				del self.server_game_state.playerlist[client_id]

				# Create player quit event
				quit_event = {
					"event_time": time.time(),
					"event_type": "playerquit",
					"client_id": client_id,
					"handled": False,
					"handledby": "server_disconnect",
				}
				# Broadcast player disconnect to remaining clients
				await self.server_game_state.broadcast_event(quit_event)

		try:
			writer.close()
			# await writer.wait_closed()
			await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
		except Exception as e:
			# Already closed or timed out, just log and continue
			logger.debug(f"connection cleanup: {e} {addr}")

	async def get_tile_map(self, request):
		position = self.get_position()

		modified_tiles = {}
		for pos, gid in self.server_game_state.modified_tiles.items():
			modified_tiles[str(pos)] = gid

		map_data = {
			"mapname": str(self.args.mapname),
			"position": position,
			"modified_tiles": modified_tiles,
			"client_id": str(gen_randid())}
		if self.args.debug:
			logger.debug(f'get_tile_map request: {request} mapname: {self.args.mapname} {position} Sending {len(modified_tiles)} modified')
		return web.json_response(map_data)

	async def new_start_server(self):
		"""Start the game server using asyncio's high-level server API"""
		# Create the server
		server = await asyncio.start_server(lambda r, w: self.client_connected_cb(r, w), host=self.args.host, port=9696, reuse_address=True,)

		addr = server.sockets[0].getsockname()

		# Create the HTTP server for map requests
		app = web.Application()
		app.router.add_get('/get_tile_map', self.get_tile_map)
		runner = web.AppRunner(app)
		await runner.setup()
		site = web.TCPSite(runner, self.args.host, 9699)
		await site.start()
		logger.info(f'HTTPapi server started on {self.args.host}:9699 addr: {addr}')

		# Start processing messages
		self.process_task = self.loop.create_task(self.process_messages())

		# Ticker task to broadcast game state
		ticker_task = self.loop.create_task(self.ticker_broadcast())

		try:
			# Run the server
			async with server:
				await server.serve_forever()
		finally:
			# Clean up
			if self.process_task:
				self.process_task.cancel()
			ticker_task.cancel()
			await runner.cleanup()

	async def ticker_broadcast(self):
		"""Broadcast game state at regular intervals"""
		last_broadcast = time.time()
		try:
			while not self.stopped():
				# Broadcast player states (at a sensible rate)
				if time.time() - last_broadcast > 0.05:  # 20 updates per second
					game_state = self.server_game_state.to_json()
					await self.server_broadcast_state(game_state)
					last_broadcast = time.time()
				await asyncio.sleep(1 / UPDATE_TICK)
		except asyncio.CancelledError:
			logger.info("Ticker broadcast task cancelled")
		except Exception as e:
			logger.error(f"Error in ticker broadcast: {e} {type(e)}")

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

		position = random.choice(valid_positions)

		if self.args.debug:
			logger.debug(f'Generated valid position: {position}')

		return {'position': position}

	async def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	async def server_broadcast_state(self, state):
		data = json.dumps(state).encode('utf-8') + b'\n'

		# Use gather for concurrent sending
		send_tasks = []

		for writer in self.connections:
			send_tasks.append(self._send_to_client(writer, data))
			# send_tasks.append(self.loop.sock_sendall(conn, data))

		# Wait for all sends to complete
		if send_tasks:
			try:
				await asyncio.gather(*send_tasks, return_exceptions=True)
			except Exception as e:
				logger.error(f"Error during broadcast: {e}")

	async def _send_to_client(self, writer, data):
		"""Helper method to send data to a client with error handling"""
		try:
			writer.write(data)
			await writer.drain()
			return True
		except (ConnectionResetError, BrokenPipeError) as e:
			logger.warning(f"Connection error while sending: {e}")
			# Connection is dead, remove it
			if writer in self.connections:
				self.connections.remove(writer)
			return False
		except Exception as e:
			logger.error(f"Error sending to client: {e}")
			return False
