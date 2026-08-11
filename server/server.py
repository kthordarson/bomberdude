#!/usr/bin/python
import asyncio
import json
import os
import random
import time
from threading import Event

import pygame
import pytmx
from aiohttp import web
from loguru import logger

from game.gamestate import GameState
from utils import gen_randid

from .accounts import AccountStore
from .discovery import ServerDiscovery

# A connected client is expected to send state regularly; anything idle
# this long is treated as dead rather than left to hang forever.
CLIENT_IDLE_TIMEOUT = 30


class BombServer:
	def __init__(self, args):
		self.args = args
		self._ensure_headless_display()
		self.game_state = GameState(args=self.args, mapname=args.mapname, client_id='theserver')
		# The server is headless (no window), but still needs real tile
		# metadata (dimensions, layers, collision tiles) for map queries and
		# upgrade/block logic; without this the map stays an empty placeholder.
		self.game_state.load_tile_map(args.mapname)
		self.client_tasks = set()  # Track active client tasks
		self.connection_to_client_id = {}  # Map connections to client IDs
		self._stop = Event()
		self.discovery_service = ServerDiscovery(self)
		self.message_counter = 0
		self.accounts = AccountStore("data/players.db")

	@staticmethod
	def _ensure_headless_display():
		"""pytmx's pygame image loader calls Surface.convert(), which raises
		unless a display mode has been set. The server has no window, so set
		up a dummy SDL video driver and a minimal display surface."""
		if pygame.display.get_surface() is None:
			os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
			pygame.init()
			pygame.display.set_mode((1, 1))

	def __repr__(self):
		return f"<BombServer game_state connections={len(self.game_state.connections)} messages={self.message_counter} client_id={self.game_state.client_id}>"

	async def client_connected_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		logger.info(f"{self} New connection from {writer.get_extra_info('peername')[0]} ")
		self.game_state.add_connection(writer)
		# Start a per-connection message loop
		asyncio.create_task(self.process_messages(reader, writer))

	async def process_messages(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
		data = None
		msg = None
		try:
			while not writer.is_closing():
				try:
					data = await asyncio.wait_for(reader.readuntil(b'\n'), timeout=CLIENT_IDLE_TIMEOUT)
				except asyncio.TimeoutError:
					logger.warning(f"{self} Client {writer.get_extra_info('peername')} idle for {CLIENT_IDLE_TIMEOUT}s, disconnecting")
					break
				try:
					msg = json.loads(data.decode('utf-8'))
				except (UnicodeDecodeError, json.decoder.JSONDecodeError) as e:
					logger.error(f"error: {e} {type(e)} Data: {data}")
					await asyncio.sleep(1)
					continue
				msg_client_id = str(msg.get('client_id'))
				game_event = msg.get('game_event') or {}

				# Bind this connection to the identity it first claimed, and
				# reject anything that tries to act as a different one — a
				# client may only ever report events as itself.
				bound_client_id = self.connection_to_client_id.get(writer)
				if bound_client_id is None:
					self.connection_to_client_id[writer] = msg_client_id
					bound_client_id = msg_client_id
				elif msg_client_id != bound_client_id:
					logger.warning(f"{self} Rejected message: connection bound to {bound_client_id} but claimed {msg_client_id}")
					continue

				# For most event types `client_id` means "the actor reporting
				# this", so it must match the connection's bound identity.
				# `player_hit`/`upgrade_pickup` are witnessed-fact reports
				# where `client_id` names a *different* player (the attacker,
				# or the picker per replicated position) — those are instead
				# validated by `reported_by` (hits) or server-side proximity
				# against the claimed picker's own tracked position (pickups,
				# see `_on_upgrade_pickup`/`_is_near_tile`).
				event_type = game_event.get('event_type')
				if event_type not in ('player_hit', 'on_player_hit', 'upgrade_pickup'):
					event_actor = str(game_event.get('client_id', bound_client_id))
					if event_actor != bound_client_id:
						logger.warning(f"{self} Rejected forged event: connection {bound_client_id} tried to act as {event_actor}: {game_event}")
						continue
				reported_by = game_event.get('reported_by')
				if reported_by is not None and str(reported_by) != bound_client_id:
					logger.warning(f"{self} Rejected forged reported_by: connection {bound_client_id} claimed reported_by={reported_by}")
					continue

				await self.game_state.update_game_event(game_event)
				self.message_counter += 1
		except TypeError as e:
			logger.error(f"{e} {type(e)} in process_messages. data: {data} msg: {msg}")
		except (asyncio.IncompleteReadError, ConnectionResetError):
			pass  # logger.warning(f'{e} Connection closed by client')
		except pygame.error as e:
			logger.error(f"{e} {type(e)} ")
			# raise e
		except BrokenPipeError as e:
			logger.error(f"{e} {type(e)} in process_messages. data: {data} msg: {msg}")
		except Exception as e:
			logger.error(f"{e} {type(e)} ")
			# raise e
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
		try:
			position = self.get_position()
		except Exception as e:
			logger.error(f"Error getting position: {e} {type(e)}")
			position = {'position': (1, 1)}  # fallback position

		modified_tiles = {}
		for pos, gid in self.game_state.modified_tiles.items():
			modified_tiles[str(pos)] = gid

		map_data = {
			"mapname": str(self.args.mapname),
			"position": position,
			"modified_tiles": modified_tiles,
			"client_id": gen_randid()}
		if self.args.debug:
			logger.debug(f'{self} request: {request} mapname: {self.args.mapname} {position} Sending {len(modified_tiles)} modified_tiles')
		return web.json_response(map_data)

	async def get_client_id(self, request):
		client_id = gen_randid()
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

	async def register_player(self, request):
		body = await request.json()
		username = str(body.get("username", ""))
		password = str(body.get("password", ""))
		ok, reason = await asyncio.to_thread(self.accounts.create_player, username, password)
		if self.args.debug:
			logger.debug(f'{self} register_player username: {username} ok: {ok} reason: {reason}')
		return web.json_response({"ok": ok, "reason": reason})

	async def login_player(self, request):
		body = await request.json()
		username = str(body.get("username", ""))
		password = str(body.get("password", ""))
		ok, reason = await asyncio.to_thread(self.accounts.authenticate, username, password)
		if self.args.debug:
			logger.debug(f'{self} login_player username: {username} ok: {ok} reason: {reason}')
		return web.json_response({"ok": ok, "reason": reason})

	async def get_lobby_info(self, request):
		players = [{"client_name": p.client_name, "position": list(p.position)} for p in self.game_state.playerlist.values()]
		tile_map = self.game_state.tile_map
		resp = {
			"players": players,
			"mapname": str(self.args.mapname),
			"map_width": tile_map.width * tile_map.tilewidth,
			"map_height": tile_map.height * tile_map.tileheight,
		}
		if self.args.debug:
			logger.debug(f'{self} request: {request} get_lobby_info players: {len(players)}')
		return web.json_response(resp)

	async def new_start_server(self):
		"""Start the TCP game server and the LAN discovery service.

		HTTP routes (get_tile_map, get_client_id, etc.) are served by ApiServer,
		which callers create and run alongside this coroutine — see
		bdude.run_server_process() and bombserver.async_start_server().
		"""
		loop = asyncio.get_event_loop()
		discovery_task = loop.create_task(self.discovery_service.start_discovery_service())

		server = await asyncio.start_server(
			lambda r, w: self.client_connected_callback(r, w),
			host=self.args.listen,
			port=self.args.server_port,
			reuse_address=True,
		)
		addr = server.sockets[0].getsockname()
		if self.args.debug:
			logger.info(f'{self} TCP game server listening on {addr}')

		try:
			async with server:
				await server.serve_forever()
		except Exception as e:
			logger.error(f'{self} Server error: {e} {type(e)}')
		finally:
			discovery_task.cancel()
			try:
				await discovery_task
			except asyncio.CancelledError:
				pass

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
			if isinstance(layer, pytmx.TiledTileLayer):
				for x, y, gid in layer: # type: ignore
					if gid != 0:
						collidable_positions.add((x, y))
			else:
				logger.warning(f"Layer {layer} {type(layer)} is not a TiledTileLayer, skipping collision check.")

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
			if self.discovery_service.running:
				self.discovery_service.stop()
		except Exception as e:
			logger.error(f"{self} Error stopping discovery service: {e} {type(e)}")

