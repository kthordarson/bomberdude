#!/usr/bin/python
import pygame
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
from .discovery import ServerDiscovery

class BombServer:
	def __init__(self, args):
		self.args = args
		self.game_state = GameState(args=self.args, mapname=args.mapname, client_id='theserver')
		self.apiserver = ApiServer(name="bombapi", server=self, game_state=self.game_state)
		self.connections = set()  # Track active connections
		self.client_tasks = set()  # Track active client tasks
		self.connection_to_client_id = {}  # Map connections to client IDs
		self.loop = asyncio.get_event_loop()
		self._stop = Event()
		self.discovery_service = ServerDiscovery(self)
		self.message_counter = 0
		asyncio.create_task(self.discovery_service.start_discovery_service())

	def __repr__(self):
		return f"<BombServer clients={len(self.connections)} messages={self.message_counter} client_id={self.game_state.client_id}>"

	async def client_connected_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		logger.info(f"{self} New connection from {writer.get_extra_info('peername')[0]} ")
		self.game_state.add_connection(writer)
		# Start a per-connection message loop
		asyncio.create_task(self.process_messages(reader, writer))

	async def process_messages(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		data = None
		try:
			while not writer.is_closing():
				data = await reader.readuntil(b'\n')
				try:
					msg = json.loads(data.decode('utf-8'))
				except (UnicodeDecodeError, json.decoder.JSONDecodeError) as e:
					logger.error(f"error: {e} {type(e)} Data: {data}")
					await asyncio.sleep(1)
					continue
				# Track which client_id is associated with this connection so we can
				# clean up player state on disconnect.
				msg_client_id = msg.get('client_id')
				self.connection_to_client_id[writer] = str(msg_client_id)
				game_event = msg.get('game_event')
				await self.game_state.update_game_event(game_event)
				await self.server_broadcast_state(self.game_state.to_json())
				self.message_counter += 1
		except (asyncio.IncompleteReadError, ConnectionResetError) as e:
			pass  # logger.warning(f'{e} Connection closed by client')
		except pygame.error as e:
			logger.error(f"{e} {type(e)} ")
			raise e
		except Exception as e:
			logger.error(f"{e} {type(e)} ")
			raise e
		finally:
			# Best-effort disconnect cleanup: remove player entry from server state
			# and notify any remaining clients.
			disconnected_client_id = self.connection_to_client_id.pop(writer, None)
			try:
				writer.close()
				await writer.wait_closed()
			except (asyncio.IncompleteReadError, ConnectionResetError) as e:
				logger.warning(f'{e} Connection closed by client')
			except Exception as e:
				logger.error(f"Error closing connection: {e} {type(e)}")
			self.game_state.remove_connection(writer)
			if disconnected_client_id:
				try:
					self.game_state.remove_player(disconnected_client_id)
					left_event = {
						'event_type': "player_left",
						"client_id": disconnected_client_id,
						"event_time": time.time(),
						"handled": False,
						"handledby": "server.disconnect",
						"event_id": gen_randid(),
					}
					await self.game_state.broadcast_event(left_event)
				except Exception as e:
					logger.error(f"Error during disconnect cleanup for {disconnected_client_id}: {e} {type(e)}")

	async def get_tile_map(self, request):
		position = self.get_position()

		modified_tiles = {}
		for pos, gid in self.game_state.modified_tiles.items():
			modified_tiles[str(pos)] = gid

		map_data = {
			"mapname": str(self.args.mapname),
			"position": position,
			"modified_tiles": modified_tiles,
			"client_id": str(gen_randid())}
		if self.args.debug:
			logger.debug(f'{self} request: {request} mapname: {self.args.mapname} {position} Sending {len(modified_tiles)} modified_tiles')
		return web.json_response(map_data)

	async def get_client_id(self, request):
		client_id = str(gen_randid())
		if self.args.debug:
			logger.debug(f'{self} request: {request} Assigning client_id: {client_id}')
		resp = {"client_id": client_id}
		return web.json_response(resp)

	async def get_map_name(self, request):
		mapname = str(self.args.mapname)
		if self.args.debug:
			logger.debug(f'{self} request: {request} mapname: {mapname}')
		resp = {"mapname": mapname}
		return web.json_response(resp)

	async def new_start_server(self):
		"""Start the game server using asyncio's high-level server API"""
		# Create the server
		server = await asyncio.start_server(lambda r, w: self.client_connected_callback(r, w), host=self.args.listen, port=self.args.server_port, reuse_address=True,)

		addr = server.sockets[0].getsockname()

		# Create the HTTP server for map requests
		app = web.Application()
		app.router.add_get('/get_tile_map', self.get_tile_map)
		app.router.add_get('/get_client_id', self.get_client_id)
		app.router.add_get('/get_map_name', self.get_map_name)

		runner = web.AppRunner(app)
		await runner.setup()
		if self.args.debug:
			logger.debug(f'{self}  {app} {runner} API server runner host {self.args.listen} port {self.args.api_port}')
		tcp_port = self.args.server_port+1
		site = web.TCPSite(runner, self.args.listen, tcp_port)
		try:
			await site.start()
			if self.args.debug:
				logger.info(f'{self} TCPSite started on {self.args.listen}:{tcp_port} serveraddr: {addr}')
		except Exception as e:
			logger.error(f'{self} Error starting API server on {self.args.listen}:{tcp_port}: {e} {type(e)}')
			return
		# Ticker task to broadcast game state
		ticker_task = self.loop.create_task(self.ticker_broadcast())

		try:
			# Run the server
			async with server:
				await server.serve_forever()
		finally:
			# Clean up
			ticker_task.cancel()
			await runner.cleanup()

	async def ticker_broadcast(self):
		"""Broadcast game state at regular intervals"""
		last_broadcast = time.time()
		try:
			while not self.stopped():
				# Broadcast player states (at a sensible rate)
				if time.time() - last_broadcast > 0.05:  # 20 updates per second
					game_state = self.game_state.to_json()
					await self.server_broadcast_state(game_state)
					last_broadcast = time.time()
				await asyncio.sleep(1 / UPDATE_TICK)
		except asyncio.CancelledError as e:
			logger.info(f"Ticker broadcast task cancelled {e}")
		except Exception as e:
			logger.error(f"Error in ticker broadcast: {e} {type(e)}")

	def get_position(self, retas="int"):
		# Get map dimensions in tiles
		map_width = self.game_state.tile_map.width
		map_height = self.game_state.tile_map.height

		# Get all collidable tiles
		collidable_positions = set()
		layers = []
		wall_layer = self.game_state.tile_map.get_layer_by_name('Walls')
		block_layer = self.game_state.tile_map.get_layer_by_name('Blocks')
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
			return {'position': (1, 1)}  # fallback position

		position = random.choice(valid_positions)
		return {'position': position}

	async def stop(self):
		self._stop.set()
		try:
			if self.discovery_service:
				self.discovery_service.stop()
		except Exception as e:
			logger.error(f"{self} Error stopping discovery service: {e} {type(e)}")

	def stopped(self):
		return self._stop.is_set()

	async def server_broadcast_state(self, state):
		data = json.dumps(state).encode('utf-8') + b'\n'
		# Use gather for concurrent sending
		send_tasks = []
		for writer in self.connections:
			send_tasks.append(self._send_to_client(writer, data))
		# Wait for all sends to complete
		if send_tasks:
			try:
				await asyncio.gather(*send_tasks, return_exceptions=True)
			except Exception as e:
				logger.error(f"{self} Error during broadcast: {e}")

	async def _send_to_client(self, writer, data):
		"""Helper method to send data to a client with error handling"""
		try:
			writer.write(data)
			await writer.drain()
			return True
		except (ConnectionResetError, BrokenPipeError) as e:
			logger.warning(f"{self} Connection error while sending: {e}")
			# Connection is dead, remove it
			if writer in self.connections:
				self.connections.remove(writer)
			return False
		except Exception as e:
			logger.error(f"{self} Error sending to client: {e}")
			return False

	def _build_ack_event(self, client_id: str) -> dict:
		return {
			'event_type': "acknewplayer",
			"client_id": client_id,
			"handled": False,
			"handledby": "_build_ack_event",
			"event_time": time.time(),
		}

	def _build_player_joined(self, client_id: str, msg: dict) -> dict:
		pos = msg.get('position') or msg.get('game_event', {}).get('position', [100, 100])
		return {
			"event_time": time.time(),
			'event_type': "player_joined",
			"client_id": client_id,
			"position": pos,
			"handled": False,
			"handledby": "_build_player_joined",
			"event_id": gen_randid(),
		}
