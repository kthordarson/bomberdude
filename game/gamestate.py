import asyncio
import random
from typing import Any, Callable, cast, Optional
import ast
import pygame
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Group
from loguru import logger
import time
from dataclasses import dataclass
from game.playerstate import PlayerState
from utils import gen_randid
from objects.player import KeysPressed, Bomberplayer
from objects.bullets import Bullet
from objects.bombs import Bomb
from objects.explosionmanager import ExplosionManager
from objects.blocks import Upgrade
from constants import DEFAULT_HEALTH, UPDATE_TICK, GLOBAL_RATE_LIMIT, BLOCK
import pytmx
from pytmx import load_pygame
import json
import inspect  # <-- add

@dataclass
class GameState:
	def __init__(self, args, client_id='missingclientid', mapname=None):
		self.args = args
		self.players_sprites = Group()
		self.bullets = Group()
		self.bombs = Group()
		self.flames = Group()
		self.particles = Group()
		self.mapname = mapname
		self.event_queue = asyncio.Queue()
		self.keyspressed = KeysPressed('gamestate')
		self.tile_map = pytmx.TiledMap(mapname)
		# Use sets for O(1) add/remove; these are iterated frequently for collision checks.
		self.collidable_tiles = set()
		self.killable_tiles = set()
		self.upgrade_blocks = set()
		self._map_update_emitted = set()
		# Index tiles by (tile_x, tile_y) to avoid linear scans on removal.
		self.collidable_by_tile: dict[tuple[int, int], Any] = {}
		self.killable_by_tile: dict[tuple[int, int], Any] = {}
		self.upgrade_by_tile: dict[tuple[int, int], Any] = {}
		self.connections = set()
		self.client_queue = asyncio.Queue()
		self.playerlist = {}  # dict = field(default_factory=dict)
		self.last_pos_broadcast = 0
		self.explosion_manager = ExplosionManager()
		self._ready = False
		self.modified_tiles = {}  # Format: {(tile_x, tile_y): new_gid}
		self.tile_cache = {}
		self.last_update_times = {}
		self.client_id = client_id
		self.player_active_bombs = {}  # player_id -> active bomb count
		self.active_bombs_per_player = {}  # Track active bombs per player
		self.processed_explosions = set()  # Track processed explosions globally
		self.processed_hits = set()  # Track processed player_hit events (by event_id)
		self.processed_bullets = set()  # Track processed bullet_fired events (by event_id)
		self.processed_upgrades = set()  # Track processed upgrade pickups (by event_id)
		# lots of if/elif event_type == ...
		self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
			"player_joined": self._on_player_joined,
			"player_left": self._on_player_left,
			"map_info": self._on_map_info,
			"map_update_event": self._on_map_update,
			"on_bullet_fired": self._on_bullet_fired,
			"tile_changed": self._on_tile_changed,
			"acknewplayer": self._on_acknewplayer,
			"connection_event": self._on_connection_event,  # async
			"player_update": self._on_player_update,
			"player_drop_bomb": self._on_player_drop_bomb,
			"dropcooldown": self._on_noop_event,
			"nodropbomb": self._on_noop_event,
			"nodropbombkill": self._on_noop_event,
			"bomb_exploded": self._on_bomb_exploded,
			"player_hit": self._on_player_hit,
			"on_player_hit": self._on_player_hit,
			"upgrade_block_collected": self._on_upgrade_pickup,
			"upgrade_spawned": self._on_upgrade_spawned,
		}

	def _iter_tiles_from_index_in_rect(self, tile_index: dict[tuple[int, int], Any], rect: pygame.Rect, *, pad_pixels: int = 0):
		"""Yield tiles from a {(tile_x,tile_y)->tile} index intersecting rect.

		This avoids scanning every tile sprite for collision checks.
		"""
		try:
			tw = int(self.tile_map.tilewidth)
			th = int(self.tile_map.tileheight)
			map_w = int(getattr(self.tile_map, "width", 0))
			map_h = int(getattr(self.tile_map, "height", 0))
			if tw <= 0 or th <= 0 or map_w <= 0 or map_h <= 0:
				return
			x0 = int(rect.left) - int(pad_pixels)
			y0 = int(rect.top) - int(pad_pixels)
			x1 = int(rect.right) + int(pad_pixels) - 1
			y1 = int(rect.bottom) + int(pad_pixels) - 1
			# Convert pixel bounds -> tile bounds
			min_tx = max(0, min(map_w - 1, x0 // tw))
			min_ty = max(0, min(map_h - 1, y0 // th))
			max_tx = max(0, min(map_w - 1, x1 // tw))
			max_ty = max(0, min(map_h - 1, y1 // th))
		except Exception as e:
			logger.error(f'Error in _iter_tiles_from_index_in_rect: {e} {type(e)}')
			return

		for ty in range(min_ty, max_ty + 1):
			for tx in range(min_tx, max_tx + 1):
				tile = tile_index.get((tx, ty))
				if tile is not None:
					yield tile

	def iter_collidable_in_rect(self, rect: pygame.Rect, *, pad_pixels: int = 0):
		return self._iter_tiles_from_index_in_rect(self.collidable_by_tile, rect, pad_pixels=pad_pixels)

	def iter_killable_in_rect(self, rect: pygame.Rect, *, pad_pixels: int = 0):
		return self._iter_tiles_from_index_in_rect(self.killable_by_tile, rect, pad_pixels=pad_pixels)

	def remove_player(self, client_id: str, *, remove_local: bool = False) -> None:
		"""Remove a player from replicated state and any associated sprites.

		On the server this is used to clean up after a disconnect.
		On clients it's used by the `player_left` event handler.
		"""
		cid = str(client_id)
		if not remove_local and cid == str(self.client_id):
			return

		# Remove from replicated player state.
		self.playerlist.pop(cid, None)
		# Be defensive: some older code paths may have inserted non-str keys.
		try:
			self.playerlist.pop(int(cid), None)
		except Exception as e:
			logger.error(f"Error removing player from playerlist {cid}: {e} {type(e)}")
			pass

		# Remove any sprites for that player.
		try:
			for sprite in list(self.players_sprites):
				if str(getattr(sprite, "client_id", "")) == cid:
					sprite.kill()
					self.players_sprites.remove(sprite)
		except Exception as e:
			logger.error(f"Error removing player sprite {cid}: {e} {type(e)}")

		# Clean up per-player bookkeeping if present.
		for d in (self.player_active_bombs, self.active_bombs_per_player, self.last_update_times):
			try:
				d.pop(cid, None)
			except Exception as e:
				logger.error(f"Error cleaning up player data {cid} in {d}: {e} {type(e)}")
				pass

	async def _sync_local_sprite_from_state(self, state: Optional[PlayerState]) -> None:
		"""Keep the local Bomberplayer sprite in sync with authoritative state."""
		if not isinstance(state, PlayerState):
			return
		if state.client_id != self.client_id:
			return
		for sprite in self.players_sprites:
			if sprite.client_id == self.client_id:
				# Only sync non-positional fields; movement is client-driven.
				# if hasattr(sprite, "health"):
				sprite.health = state.health
				# if hasattr(sprite, "score"):
				sprite.score = state.score
				# if hasattr(sprite, "bombs_left"):
				sprite.bombs_left = state.bombs_left
				# Ensure the sprite image reflects killed/dead state.
				dead = bool(getattr(state, 'killed', False)) or int(getattr(state, 'health', 0) or 0) <= 0
				if sprite.set_dead:
					await sprite.set_dead(dead)
				break

	def __repr__(self):
		return f'Gamestate ( event_queue:{self.event_queue.qsize()} client_queue:{self.client_queue.qsize()}  players:{len(self.playerlist)} players_sprites:{len(self.players_sprites)})'

	def to_json(self):
		"""Convert game state to JSON-serializable format"""
		playerlist = []
		for player in self.playerlist.values():
			if player:
				if hasattr(player, 'to_dict'):
					if player.client_id != 'bomberserver':
						playerlist.append(player.to_dict())
				else:
					if player['client_id'] != 'bomberserver':
						playerlist.append(player)
		modified_tiles = {str(pos): gid for pos, gid in self.modified_tiles.items()}
		return {
			'event_type': 'playerlistupdate',
			'playerlist': playerlist,
			'connections': len(self.connections),
			'mapname': self.mapname,
			'modified_tiles': modified_tiles,  # Include map modifications
		}

	async def destroy_block(self, block):
		"""
		Simplest possible version - just remove the block from collision group
		"""
		x, y = block.rect.topleft
		tile_x = x // self.tile_map.tilewidth
		tile_y = y // self.tile_map.tileheight
		layer_names = ('Blocks', 'UpgradeBlocks')
		for layer_name in layer_names:
			layer = self.tile_map.get_layer_by_name(layer_name)

			self.collidable_tiles.discard(block)
			self.killable_tiles.discard(block)
			self.collidable_by_tile.pop((tile_x, tile_y), None)
			self.killable_by_tile.pop((tile_x, tile_y), None)
			layer.data[tile_y][tile_x] = 0  # type: ignore
			self.modified_tiles[(tile_x, tile_y)] = 0
			# Update visual representation
			self.static_map_surface.blit(self.tile_cache.get(1), (tile_x * self.tile_map.tilewidth, tile_y * self.tile_map.tileheight))  # type: ignore

			# Spawn an upgrade once per destroyed tile (avoid duplicate spawns)
			# Only the server should decide and announce upgrades
			if not hasattr(self, '_upgrade_spawned_tiles'):
				self._upgrade_spawned_tiles = set()
			if (tile_x, tile_y) not in self._upgrade_spawned_tiles and layer_name in ('UpgradeBlocks'):
				self._upgrade_spawned_tiles.add((tile_x, tile_y))
				upgradetype = random.choice(['default', 'speed', 'power', 'range'])
				upgrade_id = gen_randid()
				upgrade_pos = (tile_x * self.tile_map.tilewidth, tile_y * self.tile_map.tileheight)
				event_upgrade = {
					"event_type": "upgrade_spawned",
					"position": upgrade_pos,
					"upgradetype": upgradetype,
					"client_id": upgrade_id,
					"event_time": time.time(),
					"handled": False,
					"event_id": gen_randid(),
				}
				# Spawn upgrade block locally on the server too
				upgrade = Upgrade(upgrade_pos, upgradetype=upgradetype, client_id=str(upgrade_id))
				self.upgrade_blocks.add(upgrade)
				await upgrade.async_init()
				self.upgrade_by_tile[(tile_x, tile_y)] = upgrade
				# Server should immediately broadcast upgrade spawns to all clients; clients enqueue for server if they generate one
				if self.client_id == 'theserver':
					asyncio.create_task(self.broadcast_event(event_upgrade))
				else:
					await self.event_queue.put(event_upgrade)
				if self.args.debug_gamestate:
					logger.info(f'upgrade_spawned: {event_upgrade} layer: {layer_name} upgrade: {upgrade} self.upgrade_blocks: {len(self.upgrade_blocks)}')
				return

			# Emit only a single map_update_event per destroyed tile

			if (tile_x, tile_y) not in self._map_update_emitted:
				self._map_update_emitted.add((tile_x, tile_y))
				map_update_event = {'event_type': "map_update_event", "position": (tile_x, tile_y), "new_gid": 0, "event_time": time.time(), "client_id": self.client_id, "handled": False,}
				if self.client_id == 'theserver':
					asyncio.create_task(self.broadcast_event(map_update_event))
				else:
					await self.event_queue.put(map_update_event)
				if self.args.debug_gamestate:
					logger.debug(f'map_update_event: {map_update_event} layer: {layer_name}')

	def ready(self):
		return self._ready

	def add_connection(self, connection):
		"""Add a new client connection"""
		self.connections.add(connection)
		if self.args.debug:
			logger.info(f"New connection added. Total connections: {len(self.connections)}")

	def remove_connection(self, connection):
		"""Remove a client connection"""
		if connection in self.connections:
			self.connections.remove(connection)
			if self.args.debug:
				logger.info(f"Connection removed. Total connections: {len(self.connections)}")

	async def broadcast_event(self, event):
		# Only broadcast player_update events at a reduced rate
		do_send = True
		client_id = event.get('client_id')
		current_time = time.time()
		# Use per-client rate limiting
		# Get last update time for this client (default to 0)
		last_time = self.last_update_times.get(client_id, 0)
		timediff = current_time - last_time

		# Rate limit
		if timediff < GLOBAL_RATE_LIMIT and last_time > 0:
			# Use debug level instead of warning for rate limiting
			if self.args.debug:
				logger.warning(f'Rate limiting {client_id}: {timediff:.5f}s GLOBAL_RATE_LIMIT: {GLOBAL_RATE_LIMIT} last_time: {last_time}')
			do_send = False

		try:
			if do_send:
				await self.broadcast_state({'event_type': "broadcast_event", "event": event})
				# Track last time we sent an update for this specific client
				if event.get('event_type') == 'player_update':
					self.last_update_times[event.get('client_id')] = time.time()
		except Exception as e:
			logger.error(f"Error in broadcast_event: {e} {type(e)}")

	async def broadcast_state(self, game_state):
		"""Broadcast game state to all connected clients"""
		try:
			data = json.dumps(game_state).encode('utf-8') + b'\n'

			# Convert modified_tiles once before serialization
			modified_tiles = {str(pos): gid for pos, gid in self.modified_tiles.items()}
			game_state['modified_tiles'] = modified_tiles

			# Broadcast in parallel using gather
			tasks = []
			for conn in list(self.connections):
				if not conn.is_closing():
					conn.write(data)
					tasks.append(conn.drain())
			if tasks:
				await asyncio.gather(*tasks, return_exceptions=True)

		except Exception as e:
			logger.error(f"Error in broadcast_state: {e} {type(e)}")

	async def send_to_client(self, connection, data):
		"""Send data to specific client connection"""
		try:
			loop = asyncio.get_event_loop()
			if isinstance(data, dict):
				data_out = json.dumps(data).encode('utf-8') + b'\n'
			elif isinstance(data, bytes):
				data_out = data + b'\n'
			else:
				data_out = str(data).encode('utf-8') + b'\n'

			if hasattr(connection, 'write'):  # StreamWriter
				connection.write(data_out)
				await connection.drain()
			else:  # Socket
				await loop.sock_sendall(connection, data_out)
		except Exception as e:
			logger.error(f"Error sending to client: {e}")
			self.remove_connection(connection)

	def get_playerone(self) -> Bomberplayer | None:
		"""Always return a Bomberplayer instance"""
		for player in self.players_sprites:
			if player.client_id == self.client_id:
				return player
		if self.args.debug:
			logger.warning(f'get_playerone: No local player found for client_id: {self.client_id}')
		return None

	def load_tile_map(self, mapname):
		self.mapname = mapname
		self.tile_map = load_pygame(self.mapname)
		# Create a cache for tile images
		tw, th = self.tile_map.tilewidth, self.tile_map.tileheight
		self.static_map_surface = pygame.Surface((self.tile_map.width * tw, self.tile_map.height * th))

		# Reset caches and indexes when loading a new map
		self.collidable_tiles.clear()
		self.killable_tiles.clear()
		self.collidable_by_tile.clear()
		self.killable_by_tile.clear()
		self.upgrade_by_tile.clear()

		for layer in self.tile_map.visible_layers:
			collidable = bool(layer.properties.get('collidable'))
			# if not collidable:
			# 	continue
			killable = bool(layer.properties.get('killable'))
			for x, y, gid in layer:
				# Skip empty tiles (gid = 0)
				if gid == 0:
					continue
				# Cache the tile image if not already cached
				tile = self.tile_cache.get(gid, None)
				if tile is None:
					self.tile_cache[gid] = self.tile_map.get_tile_image_by_gid(gid)
				self.static_map_surface.blit(self.tile_cache[gid], (x * tw, y * th))
				sprite = pygame.sprite.Sprite()
				sprite: Any = sprite  # or use a Protocol class
				sprite.image = self.tile_cache[gid]
				sprite.rect = pygame.Rect(x * tw, y * th, tw, th)
				sprite.layer = layer.name
				sprite.tile_pos = (x, y)
				if killable:
					self.killable_tiles.add(sprite)
					self.killable_by_tile[(x, y)] = sprite
				if collidable:
					self.collidable_tiles.add(sprite)
					self.collidable_by_tile[(x, y)] = sprite

	# ---------- Helpers for map updates ----------
	def _parse_pos_key(self, key):
		"""Safely parse a position key that may be a tuple or a string like '(x, y)'"""
		if isinstance(key, tuple):
			return key
		if isinstance(key, str):
			try:
				return tuple(ast.literal_eval(key))  # type: ignore
			except Exception as e:
				logger.error(f'Error parsing position key {key}: {e} {type(e)}')
				s = key.strip().strip('()')
				x_s, y_s = s.split(',')
				return (int(x_s), int(y_s))
		return key

	async def _apply_tile_change(self, x, y, new_gid):
		"""Apply a single tile change and update visuals/collisions/state."""
		layers_names = ('Blocks', 'UpgradeBlocks')
		for layer_name in layers_names:
			layer = self.tile_map.get_layer_by_name(layer_name)
			tw, th = self.tile_map.tilewidth, self.tile_map.tileheight
			if 0 <= y < len(layer.data) and 0 <= x < len(layer.data[0]):  # type: ignore
				layer.data[y][x] = new_gid  # type: ignore
				self.modified_tiles[(x, y)] = new_gid
				if new_gid == 0:
					floor_tile = self.tile_cache.get(1)
					if floor_tile:
						self.static_map_surface.blit(floor_tile, (x * tw, y * th))
					# O(1) removals using indexes (no scanning)
					block = self.killable_by_tile.pop((x, y), None)
					if block is None:
						block = self.collidable_by_tile.pop((x, y), None)
					else:
						self.collidable_by_tile.pop((x, y), None)
					if block is not None:
						self.killable_tiles.discard(block)
						self.collidable_tiles.discard(block)
					# Remove upgrade block if present
					upgrade_block = self.upgrade_by_tile.pop((x, y), None)
					if upgrade_block is not None:
						self.upgrade_blocks.discard(upgrade_block)
						upgrade_block.kill()
		await asyncio.sleep(0)

	def _apply_modifications_dict(self, modified_tiles: dict):
		"""Batch-apply many tile modifications efficiently."""
		layers_names = ('Blocks', 'UpgradeBlocks')
		for layer_name in layers_names:
			layer = self.tile_map.get_layer_by_name(layer_name)
			tw, th = self.tile_map.tilewidth, self.tile_map.tileheight
			floor_tile = self.tile_cache.get(1)
			positions_to_clear = set()

			for pos_key, new_gid in modified_tiles.items():
				x, y = self._parse_pos_key(pos_key)
				if 0 <= y < len(layer.data) and 0 <= x < len(layer.data[0]):  # type: ignore
					layer.data[y][x] = new_gid  # type: ignore
					self.modified_tiles[(x, y)] = new_gid
					if new_gid == 0:
						positions_to_clear.add((x, y))

			if positions_to_clear and floor_tile:
				for (x, y) in positions_to_clear:
					self.static_map_surface.blit(floor_tile, (x * tw, y * th))
			# Remove cleared positions from collision sets and indexes in O(k)
			for (x, y) in positions_to_clear:
				block = self.killable_by_tile.pop((x, y), None)
				if block is None:
					block = self.collidable_by_tile.pop((x, y), None)
				else:
					self.collidable_by_tile.pop((x, y), None)
				if block:
					self.killable_tiles.discard(block)
					self.collidable_tiles.discard(block)
				# Remove upgrade block if present
				upgrade_block = self.upgrade_by_tile.pop((x, y), None)
				if upgrade_block is not None:
					self.upgrade_blocks.discard(upgrade_block)
					upgrade_block.kill()

	def update_game_state(self, client_id, msg):
		msg_event = msg.get('game_event')
		msg_client_id = msg_event.get('client_id')
		if msg_client_id:
			playerdict = {
				'client_id': msg_client_id,
				'position': msg_event.get('position'),
				'score': msg_event.get('score'),
				'health': msg_event.get('health'),
				'msg_dt': msg_event.get('msg_dt'),
				'timeout': msg_event.get('timeout'),
				'killed': msg_event.get('killed'),
				'event_type': 'update_game_state',
				'bombs_left': msg_event.get('bombs_left'),
			}
			self.playerlist[client_id] = self.ensure_player_state(playerdict)
			# self.playerlist[client_id] = playerdict
		else:
			logger.warning(f'no client_id in msg: {msg}')

	def ensure_player_state(self, player_data):
		"""Convert dictionary player data to PlayerState with guaranteed defaults"""
		if isinstance(player_data, dict):
			# Create PlayerState with explicit defaults for None values
			return PlayerState(
				position=player_data.get('position', [0, 0]),
				client_id=player_data.get('client_id', 'unknown'),
				client_name=player_data.get('client_name', 'client_namenotset') or 'client_namenotset',
				score=player_data.get('score', 0) or 0,  # Convert None to 0
				initial_bombs=player_data.get('bombs_left', 3) or 3,  # Convert None to 3
				health=player_data.get('health', 100) or 100,  # Convert None to 100
				killed=player_data.get('killed', False) or False,
				timeout=player_data.get('timeout', False) or False
			)
		elif isinstance(player_data, PlayerState):
			# Ensure PlayerState has non-None values for critical attributes
			if not getattr(player_data, 'client_name', None):
				player_data.client_name = 'client_namenotset'
			if player_data.bombs_left is None:
				player_data.bombs_left = 3
			if player_data.health is None:
				player_data.health = 100
			if player_data.score is None:
				player_data.score = 0
			return player_data
		else:
			# For unexpected types, create a safe default PlayerState
			logger.warning(f"Converting unexpected type {type(player_data)} to PlayerState")
			return PlayerState(
				position=(0, 0),
				client_id=int(getattr(player_data, 'client_id', 0)),
				health=100,
				score=0
			)

	def cleanup_playerlist(self):
		"""Remove players with None positions from playerlist"""
		for client_id, player in list(self.playerlist.items()):
			if (isinstance(player, PlayerState) and player.position is None) or (isinstance(player, dict) and player.get('position') is None):
				logger.info(f"Removing player with None position: {client_id}")
				del self.playerlist[client_id]

	def check_flame_collisions(self) -> None:
		"""Check for collisions between bomb flames and players.

		Notes:
		- In the current client simulation, clients usually only have *their own* sprite in `players_sprites`, so this primarily detects hits on the local player and reports them (similar to bullets).
		- If a player is touched by a flame, we emit a `player_hit` event and kill the flame.
		"""
		players = list(self.players_sprites)
		# Flames live under the ExplosionManager in this codebase.
		flames = list(self.explosion_manager.flames)

		for flame in flames:
			flame_rect = getattr(flame, "rect", None)

			for player in players:
				player_id = player.client_id
				player_rect = player.rect

				# Don't re-hit already-dead players.
				if player.killed or player.health <= 0:
					continue

				if flame_rect.colliderect(player_rect):
					hit_event = {
						"event_time": time.time(),
						'event_type': "player_hit",
						"client_id": getattr(flame, "client_id", None),  # flame owner (bomb owner)
						"reported_by": self.client_id,  # victim/self report (server allows this)
						"target_id": player_id,
						"damage": 10,
						"position": (int(flame_rect.centerx), int(flame_rect.centery)),
						"handled": False,
						"handledby": "check_flame_collisions",
						"event_id": gen_randid(),
					}
					# Queue the hit event and remove the flame so it only damages once.
					asyncio.create_task(self.event_queue.put(hit_event))
					try:
						flame.kill()
					except Exception as e:
						logger.error(f"Error killing flame after hit: {e} {type(e)}")
					return

	async def check_upgrade_collisions(self):
		players = list(self.players_sprites)
		for upgrade_block in list(self.upgrade_blocks):
			for player in players:
				if player.rect.colliderect(upgrade_block.rect):
					# Apply upgrade effect based on type
					current_time = time.time()
					upgrade_event = {"event_time": current_time, 'event_type': "upgrade_block_collected", "client_id": player.client_id, "position": upgrade_block.position, "handled": False, "handledby": player.client_id, "event_id": gen_randid(),}
					# asyncio.create_task(self.event_queue.put(upgrade_event))

					# # If this is the server, broadcast to all clients
					# if self.client_id == "theserver":
					# 	asyncio.create_task(self.broadcast_event(upgrade_event))
					# else:
					# 	asyncio.create_task(self.event_queue.put(upgrade_event))

					tile_x = upgrade_block.rect.x // self.tile_map.tilewidth
					tile_y = upgrade_block.rect.y // self.tile_map.tileheight
					upgrade_block.kill()
					self.upgrade_blocks.discard(upgrade_block)
					self.upgrade_by_tile.pop((tile_x, tile_y), None)
					# Broadcast the map modification to all clients
					map_update_event = {'event_type': "map_update_event", "position": (tile_x, tile_y), "new_gid": 0, "event_time": time.time(), "client_id": self.client_id, "handled": False,}
					# asyncio.create_task(self.event_queue.put(map_update_event))

					# Only the server should broadcast these events
					if self.client_id == "theserver":
						logger.debug(f'{player} picked up: {upgrade_block}')
						asyncio.create_task(self.broadcast_event(upgrade_event))
						asyncio.create_task(self.broadcast_event(map_update_event))
					else:
						# Clients just update local state, do not broadcast
						logger.info(f'{player} picked up: {upgrade_block}')
						asyncio.create_task(self.event_queue.put(upgrade_event))
						asyncio.create_task(self.event_queue.put(map_update_event))

					# if self.client_id == "theserver":
					# 	asyncio.create_task(self.broadcast_event(map_update_event))
					# else:
					# 	asyncio.create_task(self.event_queue.put(map_update_event))

		await asyncio.sleep(0)

	async def check_bullet_collisions(self):
		"""Check for collisions between bullets and players"""
		players = list(self.players_sprites)
		for bullet in self.bullets:
			for player in players:
				if player.client_id == bullet.owner_id:
					continue
				if bullet.rect.colliderect(player.rect):
					hit_event = {"event_time": time.time(), 'event_type': "player_hit", "client_id": bullet.owner_id, "reported_by": self.client_id, "target_id": player.client_id, "damage": 10, "position": (bullet.position.x, bullet.position.y), "handled": False, "handledby": "check_bullet_collisions", "event_id": gen_randid()}
					asyncio.create_task(self.event_queue.put(hit_event))
					bullet.kill()
		await asyncio.sleep(0)

	async def update_game_event(self, event: dict[str, Any]) -> None:
		event_type = event.get('event_type', 'unknown_event')
		handler = self.handlers.get(event_type, self._on_unknown_event)
		_ = await handler(event)

	def _to_pos_tuple(self, pos: Any) -> tuple[int, int]:
		if isinstance(pos, (list, tuple)) and len(pos) == 2:
			x, y = pos
			if isinstance(x, (int, float)) and isinstance(y, (int, float)):
				return (int(x), int(y))
		return (100, 100)  # default as tuple

	async def _on_player_joined(self, event: dict[str, Any]) -> str | None:
		client_id = event.get("client_id")
		pos_tuple = self._to_pos_tuple(event.get("position"))
		client_name = event.get("client_name")
		player_state = self.ensure_player_state({
			"client_id": client_id,
			"client_name": client_name,
			"position": pos_tuple,
			"health": DEFAULT_HEALTH,
			"bombs_left": 3,
			"score": 0,
		})
		self.playerlist[client_id] = player_state
		await asyncio.sleep(0)
		return client_name

	async def _on_player_left(self, event: dict[str, Any]) -> str | None:
		client_id = event.get("client_id", 'unknown')
		self.remove_player(client_id, remove_local=False)
		event["handled"] = True
		event["handledby"] = "gamestate._on_player_left"
		if self.args.debug:
			logger.info(f"Player left: {client_id}")
		await asyncio.sleep(0)
		return client_id

	async def _on_acknewplayer(self, event: dict) -> str:
		# Mark client as ready upon ack from server
		self._ready = True
		event["handled"] = True
		# Optionally ensure local player is present
		client_id = event.get("client_id")
		if isinstance(client_id, str) and client_id not in self.playerlist:
			self.playerlist[client_id] = PlayerState(client_id=client_id, position=(100, 100), health=DEFAULT_HEALTH, initial_bombs=3, score=0)  # type: ignore
		await asyncio.sleep(0)
		return str(client_id)

	async def _on_connection_event(self, event: dict) -> str:
		# Treat connection_event similarly to ack for clients
		self._ready = True
		event["handled"] = True
		client_id = event.get("client_id")
		pos = self._to_pos_tuple(event.get("position", (100, 100)))
		client_name = event.get("client_name", "client_namenotset")
		if isinstance(client_id, str) and client_id not in self.playerlist:
			self.playerlist[client_id] = PlayerState(client_id=client_id, client_name=client_name, position=pos, health=DEFAULT_HEALTH, initial_bombs=3, score=0)  # type: ignore
		elif isinstance(client_id, str):
			# If we already have a player entry, only set name if it's missing/unset.
			existing = self.playerlist.get(client_id)
			ps = self.ensure_player_state(existing)
			if getattr(ps, 'client_name', 'client_namenotset') in ('', 'client_namenotset') and client_name != 'client_namenotset':
				ps.client_name = client_name
			self.playerlist[client_id] = ps
		# Broadcast ack to the client
		ack_event = {
			'event_type': "acknewplayer",
			"client_id": client_id,
			"event": event
		}
		await self.broadcast_event(ack_event)
		return str(client_id)

	async def _on_map_info(self, event: dict) -> bool:
		mods = event.get("modified_tiles") or {}
		self._apply_modifications_dict(mods)
		await asyncio.sleep(0)
		return True

	async def _on_map_update(self, event: dict[str, Any]) -> bool:
		pos_tuple = self._to_pos_tuple(event.get("position"))
		new_gid = event.get("new_gid")
		if not isinstance(new_gid, int):
			logger.warning(f"Bad map_update event (new_gid): {event}")
			return False
		# If the map isn't fully loaded yet, skip applying.
		if not hasattr(self, "tile_map"):
			if self.args.debug:
				logger.warning(f"{self} Skipping _on_map_update: tile_map not ready. event: {event}")
			return False

		# Map updates are expressed in tile coords (x, y)
		x, y = pos_tuple
		# Do not spawn upgrades on the client; only the server broadcasts upgrade_spawned events.
		await self._apply_tile_change(x, y, new_gid)
		event["handled"] = True
		event["handledby"] = "gamestate._on_map_update"

		asyncio.create_task(self.broadcast_event(event))

		# Server should rebroadcast map changes; clients typically have no connections.
		# if self.client_id == "theserver":
		# 	asyncio.create_task(self.broadcast_event(event))
		# else:
		# 	if self.args.debug_gamestate:
		# 		logger.warning(f"{self} Skipping _on_map_update broadcast: not server.. self.client_id: {self.client_id}")
		await asyncio.sleep(0)
		return True

	async def _on_bullet_fired(self, event: dict) -> bool:
		# De-dupe bullet events so we don't spawn multiple bullets from repeated broadcasts.
		bid = event.get("event_id")
		client_id = event.get("client_id")

		if bid in self.processed_bullets:
			if self.args.debug_gamestate:
				logger.warning(f"_on_bullet_fired: Duplicate bullet event_id {bid}, ignoring.")
			await asyncio.sleep(0)
			return False
		self.processed_bullets.add(bid)

		# Gate firing by the shooter's authoritative state (NOT the local player).
		shooter_entry = self.playerlist.get(client_id)
		shooter_state = self.ensure_player_state(shooter_entry)
		dead = bool(getattr(shooter_state, 'killed', False)) or int(getattr(shooter_state, 'health', 0) or 0) <= 0
		if dead:
			if self.args.debug_gamestate:
				logger.warning(f"_on_bullet_fired: Shooter {client_id} is dead/killed, ignoring bullet fire.")
			await asyncio.sleep(0)
			return False

		pos_tuple = self._to_pos_tuple(event.get("position"))
		dir_raw = event.get("direction")
		if isinstance(dir_raw, (list, tuple)) and len(dir_raw) == 2:
			dx, dy = dir_raw
			if isinstance(dx, (int, float)) and isinstance(dy, (int, float)):
				direction = (float(dx), float(dy))
			else:
				direction = (1.0, 0.0)
		else:
			direction = (1.0, 0.0)

		# Bullet stores screen_rect but doesn't currently use it for update; provide a sane default.
		screen_rect = pygame.Rect(0, 0, 0, 0)
		bullet = Bullet(position=pos_tuple, direction=direction, screen_rect=screen_rect, owner_id=client_id)
		self.bullets.add(bullet)

		event["handled"] = True
		event["handledby"] = "gamestate._on_bullet_fired"
		# Server should rebroadcast bullet events so other clients can spawn the bullet.
		if self.client_id == "theserver":
			asyncio.create_task(self.broadcast_event(event))
		await asyncio.sleep(0)
		return True

	async def _on_player_drop_bomb(self, event: dict[str, Any]) -> bool:
		client_id = event.get("client_id")
		if not isinstance(client_id, str):
			logger.debug(f"Bad player_drop_bomb event client_id: {event}")
			return False
		pos = self._to_pos_tuple(event.get("position"))
		bombs_left = int(event.get("bombs_left",0))
		# Keep replicated state in sync with the event
		player_entry = self.playerlist.get(client_id)
		if isinstance(player_entry, dict):
			player_entry["bombs_left"] = bombs_left
		elif isinstance(player_entry, PlayerState):
			player_entry.bombs_left = bombs_left
		# Also update local sprite if this is us
		for sprite in self.players_sprites:
			if getattr(sprite, "client_id", None) == client_id:
				sprite.bombs_left = bombs_left
				break
		# Create a bomb sprite locally. Server does not simulate bombs but should broadcast.
		bomb = Bomb(position=pos, client_id=client_id)
		await bomb.async_init()
		self.bombs.add(bomb)

		event["handled"] = True
		event["handledby"] = "gamestate._on_player_drop_bomb"
		if self.client_id == "theserver":
			asyncio.create_task(self.broadcast_event(event))
		return True

	async def _on_bomb_exploded(self, event: dict[str, Any]) -> bool:
		# De-dupe explosions so the originating client doesn't double-credit bombs_left
		explosion_id = event.get("event_id") or event.get("event_id")
		# if isinstance(explosion_id, str):
		if explosion_id in self.processed_explosions:
			if self.args.debug_gamestate:
				logger.warning(f"_on_bomb_exploded: Duplicate explosion_id {explosion_id}, ignoring. self.processed_explosions: {len(self.processed_explosions)}")
			await asyncio.sleep(0)
			return False
		self.processed_explosions.add(explosion_id)

		owner_raw = event.get("owner_id") or event.get("client_id")
		# if not isinstance(owner_raw, str):
		# 	return

		# Restore one bomb to the owner (capped by Bomberplayer property setter at 3)
		# for sprite in self.players_sprites:
		# 	if sprite.client_id == owner_raw:
		# 		sprite.bombs_left = sprite.bombs_left + 1
		# 		if self.args.debug_gamestate:
		# 			logger.debug(f"_on_bomb_exploded: Restored bomb to {owner_raw}, now has {sprite.bombs_left} bombs left.")
		# 		break

		player_entry = self.playerlist.get(owner_raw)
		if isinstance(player_entry, PlayerState):
			player_entry.bombs_left = min(3, player_entry.bombs_left + 1)
			if self.args.debug_gamestate:
				logger.info(f"_on_bomb_exploded: Restored bomb to {owner_raw}, now has {player_entry.bombs_left} bombs left.")
		# Also update local sprite if present
		for sprite in self.players_sprites:
			if getattr(sprite, "client_id", None) == owner_raw:
				sprite.bombs_left = min(3, getattr(sprite, "bombs_left", 0) + 1)
				break

		event["handled"] = True
		event["handledby"] = "gamestate._on_bomb_exploded"
		if self.client_id == "theserver":
			asyncio.create_task(self.broadcast_event(event))
		await asyncio.sleep(0)
		return True

	async def _on_noop_event(self, event: dict[str, Any]) -> bool:
		# Intentionally ignore (used for client-side feedback events)
		event["handled"] = True
		event["handledby"] = "gamestate._on_noop_event"
		await asyncio.sleep(0)
		return True

	async def _on_tile_changed(self, event: dict) -> bool:
		pos_key = event.get("pos")
		gid = event.get("gid")
		pos = self._parse_pos_key(pos_key)
		x, y = pos
		await self._apply_tile_change(x, y, gid)
		await asyncio.sleep(0)
		return True

	async def _on_player_update(self, event: dict[str, Any]) -> bool:
		# Normalize and update remote/local player state then broadcast
		client_id = event.get("client_id")
		pos_tuple = self._to_pos_tuple(event.get("position"))

		pos = event.get("position")
		health = int(event.get("health", 0))
		client_name = event.get("client_name", "None")
		score = int(event.get("score", 0))
		bombs_left = event.get("bombs_left")

		# Server is authoritative for health; clients may have stale state.
		# Keep accepting health updates on clients so they reflect server state.
		accept_health_update = self.client_id != "theserver"
		# Client name is set by the client once; server keeps the first non-default.
		accept_name_update = True

		existing = self.playerlist.get(client_id)
		if existing is None:
			ps = PlayerState(
				client_id=client_id,  # type: ignore
				client_name=client_name or 'client_namenotset',
				position=pos_tuple,
				# position=pos if isinstance(pos, (list, tuple)) else [100, 100],
				health=health,
				initial_bombs=bombs_left if isinstance(bombs_left, int) else 3,
				score=score if isinstance(score, int) else 0,
			)
			self.playerlist[client_id] = ps
			# Keep local sprite in sync (health/score/bombs) with authoritative data.
			await self._sync_local_sprite_from_state(ps)
		else:
			ps = self.ensure_player_state(existing)
			# if isinstance(pos, (list, tuple)):
			ps.position = pos_tuple
			ps.position_updated = True  # helps interpolation
			if accept_health_update:
				ps.health = int(health)
			ps.score = score
			ps.bombs_left = bombs_left
			ps.client_name = client_name
			self.playerlist[client_id] = ps
			await self._sync_local_sprite_from_state(ps)

		# Mark handled and schedule broadcast without blocking
		event["handled"] = True
		event["handledby"] = "gamestate._on_player_update"
		if self.client_id == "theserver":
			# IMPORTANT: clients can have stale health; broadcast server-authoritative state.
			out_event = dict(event)
			out_event["handled"] = False
			out_event["handledby"] = "server.authoritative_player_update"
			out_event["position"] = ps.position
			out_event["score"] = ps.score
			out_event["bombs_left"] = ps.bombs_left
			out_event["health"] = ps.health
			out_event["client_name"] = getattr(ps, 'client_name', 'client_namenotset')
			asyncio.create_task(self.broadcast_event(out_event))
		else:
			asyncio.create_task(self.broadcast_event(event))
		await asyncio.sleep(0)
		return True

	async def _on_player_hit(self, event: dict) -> bool:
		# De-dupe by event id when available
		hit_id = event.get('event_id') or event.get('event_id')
		if hit_id is not None and hit_id in self.processed_hits or event.get('handled'):
			if self.args.debug_gamestate:
				logger.warning(f"Duplicate player_hit event ignored: {event} self.processed_hits: {len(self.processed_hits)}")
			await asyncio.sleep(0)
			return False

		# If this is the authoritative server, restrict who can report a hit.
		# In the current client simulation, only the *victim* reliably has collision geometry
		# (clients typically only have their own sprite in players_sprites), so accept reports
		# from the victim (reported_by == target_id), and also allow shooter/server for future.
		if self.client_id == "theserver":
			shooter = event.get("client_id", "")
			reported_by = event.get("reported_by")
			target_id = event.get("target_id", "")
			# if isinstance(reported_by, str):
			allowed_reporters = {"theserver"}
			# if isinstance(shooter, str):
			allowed_reporters.add(shooter)
			# if isinstance(target_id, str):
			allowed_reporters.add(target_id)
			if reported_by not in allowed_reporters:
				if self.args.debug_gamestate:
					logger.warning(f"Rejected unauthorized player_hit report: {event} reported_by: {reported_by} allowed_reporters: {allowed_reporters}")
				await asyncio.sleep(0)
				return False

		target = event.get("target_id", "")
		target_player_entry = self.playerlist.get(target)
		old_health = target_player_entry.health
		# Keep event_type as 'player_hit' so receivers handle it consistently.
		event["handledby"] = "gamestate._on_player_hit"
		damage = event.get('damage', 0)
		# If server attached an authoritative target_health, apply it directly on clients.
		auth_health = int(event.get("target_health",0))
		if self.client_id != "theserver":
			target_player_entry.health = max(0, auth_health)
			if target_player_entry.health <= 0:
				target_player_entry.killed = True
		else:
			target_player_entry.take_damage(damage, attacker_id=event.get("client_id"))
		self.playerlist[target] = target_player_entry
		# If we are the target, also sync the local sprite so HUD/debug reflects correct health.
		# if isinstance(target_player_entry, PlayerState):
		await self._sync_local_sprite_from_state(target_player_entry)

		# Mark handled locally so we don't reapply if this event loops back.
		event['handled'] = True
		event["handledby"] = "gamestate._on_player_hit"
		# if hit_id is not None:
		self.processed_hits.add(hit_id)

		# Only the server should broadcast hit events.
		if self.client_id == "theserver":
			# Broadcast a fresh copy that clients will actually apply.
			out_event = dict(event)
			out_event["handled"] = False
			out_event["handledby"] = "server.broadcast_player_hit"
			out_event["target_health"] = getattr(target_player_entry, 'health', None)
			asyncio.create_task(self.broadcast_event(out_event))
		await asyncio.sleep(0)
		return True

	async def _on_upgrade_pickup(self, event: dict) -> bool:
		# Handle upgrade pickup events
		event_id = event.get("event_id")
		if event_id in self.processed_upgrades:
			if self.args.debug_gamestate:
				logger.warning(f"Duplicate upgrade pickup event ignored: {event} self.processed_upgrades: {len(self.processed_upgrades)}")
			return False
		self.processed_upgrades.add(event_id)
		position = event.get('position')
		# Find and remove the upgrade at this position
		for upgrade in list(self.upgrade_blocks):
			if upgrade.rect.topleft == position:
				self.upgrade_blocks.discard(upgrade)
				tile_x = position[0] // self.tile_map.tilewidth
				tile_y = position[1] // self.tile_map.tileheight
				self.upgrade_by_tile.pop((tile_x, tile_y), None)
				if self.args.debug_gamestate:
					logger.debug(f'Upgrade block picked up: {upgrade} at {position} type: {upgrade.upgradetype} self.upgrade_blocks: {len(self.upgrade_blocks)}')
				break
		event["handled"] = True
		event["handledby"] = "gamestate._on_upgrade_pickup"
		return True

	async def _on_upgrade_spawned(self, event: dict) -> bool:
		# Create an Upgrade locally from a server announcement
		pos = event.get('position')
		tile_x = int(pos[0]) // self.tile_map.tilewidth
		tile_y = int(pos[1]) // self.tile_map.tileheight
		# Avoid duplicate spawns
		if (tile_x, tile_y) in self.upgrade_by_tile:
			if self.args.debug_gamestate:
				logger.warning(f'Upgrade already exists at {(tile_x, tile_y)}, ignoring spawn: {event}')
			await asyncio.sleep(0)
			return False
		upgrade = Upgrade(pos, upgradetype=event.get('upgradetype'), client_id=str(event.get('client_id')))
		await upgrade.async_init()
		self.upgrade_blocks.add(upgrade)
		self.upgrade_by_tile[(tile_x, tile_y)] = upgrade
		event['handled'] = True
		event['handledby'] = 'gamestate._on_upgrade_spawned'
		if self.args.debug_gamestate:
			logger.debug(f"_on_upgrade_spawned created {upgrade} self.upgrade_blocks: {len(self.upgrade_blocks)}")
		await asyncio.sleep(0)
		return True

	async def _on_unknown_event(self, event: dict) -> bool:
		logger.warning(f"Unknown event_type: {event.get('event_type')} event: {event}")
		await asyncio.sleep(0)
		return False
