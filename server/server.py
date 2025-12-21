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
# from .discovery import ServerDiscovery

class BombServer:
	def __init__(self, args):
		self.args = args
		self.server_game_state = GameState(args=self.args, mapname=args.mapname, client_id='theserver')
		self.apiserver = ApiServer(name="bombapi", server=self, game_state=self.server_game_state)
		self.connections = set()  # Track active connections
		self.client_tasks = set()  # Track active client tasks
		self.connection_to_client_id = {}  # Map connections to client IDs
		self.loop = asyncio.get_event_loop()
		self._stop = Event()
		# self.discovery_service = ServerDiscovery(self)
		# asyncio.create_task(self.discovery_service.start_discovery_service())

	async def client_connected_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		logger.info(f"New connection from {writer.get_extra_info('peername')[0]} ")
		self.server_game_state.add_connection(writer)
		# Start a per-connection message loop
		asyncio.create_task(self.process_messages(reader, writer))

	async def process_messages(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		try:
			while not writer.is_closing():
				data = await reader.readuntil(b'\n')
				if not data:
					await asyncio.sleep(0.01)
					continue
				msg = json.loads(data.decode('utf-8'))
				game_event = msg.get('game_event')
				if isinstance(game_event, dict):
					await self.server_game_state.update_game_event(game_event)
				# Optionally broadcast the current state
				await self.server_broadcast_state(self.server_game_state.to_json())
		except (asyncio.IncompleteReadError, ConnectionResetError) as e:
			logger.warning(f'{e} {type(e)} Connection closed by client')
		except pygame.error as e:
			logger.error(f"{e} {type(e)} msg: {msg}")
			raise e
		except Exception as e:
			logger.error(f"{e} {type(e)} msg:{locals().get('msg')}")
			raise e
		finally:
			try:
				writer.close()
				await writer.wait_closed()
			except Exception as e:
				logger.error(f"Error closing connection: {e} {type(e)}")
			self.server_game_state.remove_connection(writer)

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
		server = await asyncio.start_server(lambda r, w: self.client_connected_callback(r, w), host=self.args.host, port=9696, reuse_address=True,)

		addr = server.sockets[0].getsockname()

		# Create the HTTP server for map requests
		app = web.Application()
		app.router.add_get('/get_tile_map', self.get_tile_map)
		runner = web.AppRunner(app)
		await runner.setup()
		site = web.TCPSite(runner, self.args.host, 9699)
		await site.start()
		logger.info(f'HTTPapi server started on {self.args.host}:9699 addr: {addr}')

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
					game_state = self.server_game_state.to_json()
					await self.server_broadcast_state(game_state)
					last_broadcast = time.time()
				await asyncio.sleep(1 / UPDATE_TICK)
		except asyncio.CancelledError as e:
			logger.warning(f"Ticker broadcast task cancelled: {e} {type(e)}")
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

	def _build_ack_event(self, client_id: str) -> dict:
		return {
			"event_type": "acknewplayer",
			"client_id": client_id,
			"handled": False,
			"handledby": "_build_ack_event",
			"event_time": time.time(),
		}

	def _build_player_joined(self, client_id: str, msg: dict) -> dict:
		pos = msg.get('position') or msg.get('game_event', {}).get('position', [100, 100])
		return {
			"event_time": time.time(),
			"event_type": "player_joined",
			"client_id": client_id,
			"position": pos,
			"handled": False,
			"handledby": "_build_player_joined",
			"eventid": gen_randid(),
		}

	def _build_map_info(self, client_id: str, modified_tiles: dict) -> dict:
		return {
			"event_time": time.time(),
			"event_type": "map_info",
			"mapname": self.server_game_state.mapname,
			"modified_tiles": modified_tiles,
			"client_id": client_id,
			"handled": False,
		}
