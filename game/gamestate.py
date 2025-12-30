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
	def __init__(self, args, client_id, mapname):
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
		# Ensure static_map_surface always exists, even before load_tile_map is called
		self.static_map_surface = pygame.Surface((1, 1))
		# Use sets for O(1) add/remove; these are iterated frequently for collision checks.
		self.collidable_tiles = set()
		self.killable_tiles = set()
		self.upgrade_blocks = set()
		self._upgrade_spawned_tiles = set()
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
		self.broadcast_counter = 0
		# lots of if/elif event_type == ...
		self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
			"player_joined": self._on_player_joined,
			"player_left": self._on_player_left,
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
			"upgrade_pickup": self._on_upgrade_pickup,
			"upgrade_spawned": self._on_upgrade_spawned,
		}

	def __repr__(self):
		return f'Gamestate {self.client_id} ( event_queue:{self.event_queue.qsize()} client_queue:{self.client_queue.qsize()}  players:{len(self.playerlist)} players_sprites:{len(self.players_sprites)} broadcast_counter:{self.broadcast_counter} )'

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
			logger.error(f'{self} Error in _iter_tiles_from_index_in_rect: {e} {type(e)}')
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
			logger.error(f"{self} Error removing player from playerlist {cid}: {e} {type(e)}")
			pass

		# Remove any sprites for that player.
		try:
			for sprite in list(self.players_sprites):
				if str(getattr(sprite, "client_id", "")) == cid:
					sprite.kill()
					self.players_sprites.remove(sprite)
		except Exception as e:
			logger.error(f"{self} Error removing player sprite {cid}: {e} {type(e)}")

		# Clean up per-player bookkeeping if present.
		for d in (self.player_active_bombs, self.active_bombs_per_player, self.last_update_times):
			try:
				d.pop(cid, None)
			except Exception as e:
				logger.error(f"{self} Error cleaning up player data {cid} in {d}: {e} {type(e)}")
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
				sprite.health = state.health
				sprite.score = state.score
				sprite.bombs_left = state.bombs_left
				# Ensure the sprite image reflects killed/dead state.
				dead = state.killed or int(state.health) <= 0
				if sprite.set_dead:
					await sprite.set_dead(dead)
				break

	def to_json(self):
		"""Convert game state to JSON-serializable format"""
		modified_tiles = {str(pos): gid for pos, gid in self.modified_tiles.items()}
		return {
			'event_type': 'playerlistupdate',
			'playerlist': [k.to_dict() for k in self.playerlist.values()],
			'connections': len(self.connections),
			'mapname': self.mapname,
			'modified_tiles': modified_tiles,  # Include map modifications
		}

	async def destroy_block(self, block, create_upgrade: bool = False) -> None:
		"""
		Simplest possible version - just remove the block from collision group
		"""

		x, y = block.rect.topleft
		tile_x = x // self.tile_map.tilewidth
		tile_y = y // self.tile_map.tileheight
		new_gid = 1
		if create_upgrade and random.random() < 0.9:
			new_gid = 20
		tile = self.tile_cache.get(new_gid, None)
		if tile is None:
			self.tile_cache[new_gid] = self.tile_map.get_tile_image_by_gid(new_gid)

		map_update_event = {'event_type': "map_update_event", "position": (tile_x, tile_y), "new_gid": new_gid, "event_time": time.time(), "client_id": self.client_id, "handled": False,}
		# asyncio.create_task(self.broadcast_event(map_update_event))
		asyncio.create_task(self.event_queue.put(map_update_event))
		if self.args.debug_gamestate and new_gid == 20:
			logger.info(f'{self} new_gid: {new_gid} tile=({tile_x},{tile_y})')
		if self.args.debug_gamestate and new_gid == 1 and not create_upgrade:
			logger.debug(f'{self} new_gid: {new_gid} tile=({tile_x},{tile_y})')
			# map_update_event: {'event_type': 'map_update_event', 'position': (14, 53), 'new_gid': 20, 'event_time': 1767078826.0444207, 'client_id': '4093086018', 'handled': False}

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
			await asyncio.sleep(0.1)
			# do_send = False

		try:
			if do_send:
				await self.broadcast_state({'event_type': "broadcast_event", "event": event})
				self.broadcast_counter += 1
				# Track last time we sent an update for this specific client
				if event.get('event_type') == 'player_update':
					self.last_update_times[event.get('client_id')] = time.time()
		except Exception as e:
			logger.error(f"{self} Error in broadcast_event: {e} {type(e)}")

	async def broadcast_state(self, game_state):
		"""Broadcast game state to all connected clients"""
		try:
			# Convert modified_tiles once before serialization
			modified_tiles = {str(pos): gid for pos, gid in self.modified_tiles.items()}
			game_state['modified_tiles'] = modified_tiles
			data = json.dumps(game_state).encode('utf-8') + b'\n'
			# Broadcast in parallel using gather
			tasks = []
			for conn in list(self.connections):
				if not conn.is_closing():
					conn.write(data)
					tasks.append(conn.drain())
			if tasks:
				await asyncio.gather(*tasks, return_exceptions=True)

		except Exception as e:
			logger.error(f"{self} Error in broadcast_state: {e} {type(e)}")

	async def send_to_client(self, connection, data):
		"""Send data to specific client connection"""
		try:
			# loop = asyncio.get_event_loop()
			loop = asyncio.get_running_loop()
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
			logger.error(f"{self} Error sending to client: {e}")
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
		layer_names = ['Background', 'Blocks', 'Walls']
		for layername in layer_names:  # self.tile_map.visible_layers:
			layer = self.tile_map.get_layer_by_name(layername)
			collidable = layer.properties.get('collidable')  # type: ignore
			killable = layer.properties.get('killable')  # type: ignore
			for x, y, gid in layer:
				if gid == 0:
					continue
				tile = self.tile_cache.get(gid, None)
				if tile is None:
					self.tile_cache[gid] = self.tile_map.get_tile_image_by_gid(gid)
				self.static_map_surface.blit(self.tile_cache[gid], (x * tw, y * th))
				sprite: Any = pygame.sprite.Sprite()
				sprite.image = self.tile_cache[gid]
				sprite.rect = pygame.Rect(x * tw, y * th, tw, th)
				sprite.layer = layer.name  # type: ignore
				sprite.tile_pos = (x, y)
				sprite.id = gid
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
				logger.error(f'{self} Error parsing position key {key}: {e} {type(e)}')
				s = key.strip().strip('()')
				x_s, y_s = s.split(',')
				return (int(x_s), int(y_s))
		return key

	async def _apply_tile_change(self, x, y, new_gid):
		"""Apply a single tile change and update visuals/collisions/state."""
		tw, th = self.tile_map.tilewidth, self.tile_map.tileheight
		# self.tile_map.get_layer_by_name('Blocks').data[y][x] = new_gid  # type: ignore
		# self.modified_tiles[(x, y)] = new_gid
		if new_gid == 1:
			block = self.killable_by_tile.pop((x, y), None)
			if block:
				self.killable_tiles.discard(block)
				if self.args.debug_gamestate:
					logger.info(f"{self} Removed killable block at ({x},{y})")
			else:
				if self.args.debug_gamestate:
					logger.warning(f"{self} _apply_tile_change: No killable block found at ({x},{y}) to remove.")
			block = self.collidable_by_tile.pop((x, y), None)
			if block:
				self.collidable_tiles.discard(block)
				if self.args.debug_gamestate:
					logger.info(f"{self} Removed collidable block at ({x},{y})")
			else:
				if self.args.debug_gamestate:
					logger.warning(f"{self} _apply_tile_change: No collidable block found at ({x},{y}) to remove.")
		elif new_gid == 20:
			# Create and add an Upgrade object for this tile if not already present (for both server and clients)
			upgrade_tile = self.tile_cache.get(new_gid)
			self.tile_cache[new_gid] = upgrade_tile
			tile_pos = (x, y)
			if tile_pos not in self.upgrade_by_tile:
				# self.upgrade_by_tile[tile_pos] = new_gid
				# asyncio.create_task(self.broadcast_event(upgrade_event))
				upgrade_pos = (x * tw, y * th)
				upgrade_event = {'event_type': "upgrade_spawned", "client_id": self.client_id, "position": tile_pos, "upgradetype": new_gid, "handled": False, "handledby": "_apply_tile_change", "event_id": gen_randid(), "event_time": time.time(),}
				# asyncio.create_task(self.event_queue.put(upgrade_event))
				upgrade = Upgrade(position=upgrade_pos, upgrade_id=new_gid)
				await upgrade.async_init()
				self.upgrade_blocks.add(upgrade)
				self.upgrade_by_tile[tile_pos] = upgrade
				asyncio.create_task(self.broadcast_event(upgrade_event))
				if self.args.debug_gamestate:
					logger.info(f"{self} {upgrade} GID {new_gid} at ({x},{y}) self.upgrade_blocks: {len(self.upgrade_blocks)} self.upgrade_by_tile: {len(self.upgrade_by_tile)}")
			else:
				if self.args.debug_gamestate:
					logger.warning(f"{self} _apply_tile_change: Upgrade already exists at ({x},{y}), skipping creation.")
		else:
			if self.args.debug_gamestate:
				logger.warning(f"{self} _apply_tile_change: Unhandled new_gid {new_gid} at ({x},{y})")

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
			self.playerlist[client_id] = playerdict
		else:
			logger.warning(f'no client_id in msg: {msg}')

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
						"client_id": flame.client_id,
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
					# asyncio.create_task(self.broadcast_event(hit_event))
					try:
						flame.kill()
					except Exception as e:
						logger.error(f"{self} Error killing flame after hit: {e} {type(e)}")
					return

	async def check_upgrade_collisions(self):
		"""Detect players picking up upgrade blocks.

		Checks both local Bomberplayer sprites and replicated PlayerState entries
		(servers usually only have PlayerState entries). Skips upgrades that
		have no rect yet (async_init not completed) or are still within a small
		spawn grace period to avoid immediate pickup on spawn.
		"""
		# Collect both sprite objects (client local sprites) and authoritative PlayerState entries
		sprite_players = list(self.players_sprites)
		ps_players = [p for p in self.playerlist.values() if isinstance(p, PlayerState)]

		SPAWN_GRACE = 0.0  # seconds
		picked_up_blocks = set()

		for upgrade_block in list(self.upgrade_blocks):
			# Skip recently spawned upgrades during a short grace period
			elapsed = pygame.time.get_ticks() / 1000 - getattr(upgrade_block, "born_time", 0)
			if elapsed < SPAWN_GRACE:
				continue

			# Check sprite players first (local client sprites)
			for player in sprite_players:
				if player.rect.colliderect(upgrade_block.rect):
					picked_up_blocks.add((upgrade_block, player.client_id))
					if self.args.debug_gamestate:
						logger.info(f"{self} {upgrade_block} picked by sprite player {player.client_id} picked_up_blocks: {len(picked_up_blocks)}")
					break

			# If already picked by a sprite, skip checking PlayerState entries
			# if any(upgrade_block is ub for ub, _ in picked_up_blocks):
			# 	continue

			# Check PlayerState entries (server authoritative state)
			for ps in ps_players:
				if ps.rect.colliderect(upgrade_block.rect):
					picked_up_blocks.add((upgrade_block, ps.client_id))
					if self.args.debug_gamestate:
						logger.info(f"{self} {upgrade_block} picked by PlayerState {ps.client_id} picked_up_blocks: {len(picked_up_blocks)}")
					break

		# Process pickups
		for upgrade_block, picker_id in picked_up_blocks:
			# Remove from local indices first to avoid processing the same pickup repeatedly
			tile_x = upgrade_block.rect.x // self.tile_map.tilewidth
			tile_y = upgrade_block.rect.y // self.tile_map.tileheight
			self.upgrade_blocks.discard(upgrade_block)
			self.upgrade_by_tile.pop((tile_x, tile_y), None)

			# Emit upgrade collected event and enqueue a map update so the networking task sends it to the server.
			current_time = time.time()
			upgrade_event = {'event_type': "upgrade_pickup", "client_id": picker_id, "position": upgrade_block.position, "upgradetype": getattr(upgrade_block, "upgradetype", "unknown"), "handled": False, "handledby": picker_id, "event_id": gen_randid(), "event_time": current_time,}
			# enqueue only; server will authoritatively remove the tile and broadcast map update
			asyncio.create_task(self.event_queue.put(upgrade_event))
			# map_update_event = {'event_type': "map_update_event", "position": (tile_x, tile_y), "new_gid": 1, "event_time": time.time(), "client_id": self.client_id, "handled": False,}
			# asyncio.create_task(self.event_queue.put(map_update_event))
			if self.args.debug_gamestate:
				logger.info(f'{self} upgrade_pickup event for {upgrade_block} picked by {picker_id} at ({tile_x},{tile_y}) self.upgrade_blocks: {len(self.upgrade_blocks)} self.upgrade_by_tile: {len(self.upgrade_by_tile)}')

			# Kill local sprite
			# try:
			# 	upgrade_block.kill()
			# except Exception as e:
			# 	if self.args.debug_gamestate:
			# 		logger.error(f"{self} Error killing upgrade block after pickup: {e} {type(e)}")

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
					# asyncio.create_task(self.broadcast_event(hit_event))
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
		if self.args.debug_gamestate:
			logger.info(f"Player joined: {event}")
		player_state = {
			"client_id": event.get("client_id"),
			"client_name": event.get("client_name"),
			"position": self._to_pos_tuple(event.get("position")),
			"health": DEFAULT_HEALTH,
			"bombs_left": 3,
			"score": 0,
		}
		self.playerlist[event.get("client_id",'x')] = player_state
		await asyncio.sleep(0)
		return event.get("client_name")

	async def _on_player_left(self, event: dict[str, Any]) -> str | None:
		client_id = event.get("client_id", 'unknown')
		self.remove_player(client_id, remove_local=False)
		event["handled"] = True
		event["handledby"] = "_on_player_left"
		if self.args.debug:
			logger.info(f"Player left: {client_id} {event.get('client_name')}")
		await asyncio.sleep(0)
		return client_id

	async def _on_acknewplayer(self, event: dict) -> str:
		# Mark client as ready upon ack from server
		self._ready = True
		event["handled"] = True
		# Optionally ensure local player is present
		client_id = event.get("client_id")
		if client_id not in self.playerlist:
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
		if client_id not in self.playerlist:
			self.playerlist[client_id] = PlayerState(client_id=client_id, client_name=client_name, position=pos, health=DEFAULT_HEALTH, initial_bombs=3, score=0)  # type: ignore
		else:
			# If we already have a player entry, only set name if it's missing/unset.
			existing = self.playerlist.get(client_id)
			if existing.client_name in ('', 'client_namenotset') and client_name != 'client_namenotset':
				existing.client_name = client_name
			self.playerlist[client_id] = existing
		# Broadcast ack to the client
		ack_event = {
			'event_type': "acknewplayer",
			"client_id": client_id,
			"event": event
		}
		if self.args.debug_gamestate:
			logger.info(f"{self} _on_connection_event: Broadcasting acknewplayer for {client_id}")
		await self.broadcast_event(ack_event)
		return str(client_id)

	async def _on_map_update(self, event: dict[str, Any]) -> bool:
		pos_tuple = self._to_pos_tuple(event.get("position"))
		new_gid = event.get("new_gid")
		# If the map isn't fully loaded yet, skip applying.
		if not self.tile_map:
			logger.error(f"{self} Skipping _on_map_update: tile_map not ready. event: {event}")
			return False

		# Map updates are expressed in tile coords (x, y)
		x, y = pos_tuple
		await self._apply_tile_change(x, y, new_gid)
		return True

	async def _on_bullet_fired(self, event: dict) -> bool:
		# De-dupe bullet events so we don't spawn multiple bullets from repeated broadcasts.
		bid = event.get("event_id")
		client_id = event.get("client_id")

		if bid in self.processed_bullets:
			if self.args.debug_gamestate:
				logger.warning(f"{self} _on_bullet_fired: Duplicate bullet event_id {bid}, ignoring. self.processed_bullets: {len(self.processed_bullets)}")
			await asyncio.sleep(0)
			return False
		self.processed_bullets.add(bid)

		# Gate firing by the shooter's authoritative state (NOT the local player).
		shooter_entry = self.playerlist.get(client_id)
		dead = bool(getattr(shooter_entry, 'killed', False)) or int(getattr(shooter_entry, 'health', 0) or 0) <= 0
		if dead:
			if self.args.debug_gamestate:
				logger.warning(f"{self} _on_bullet_fired: Shooter {client_id} is dead/killed, ignoring bullet fire.")
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
		event["handledby"] = "_on_bullet_fired"
		# Server should rebroadcast bullet events so other clients can spawn the bullet.
		asyncio.create_task(self.broadcast_event(event))
		# asyncio.create_task(self.event_queue.put(event))
		if self.client_id == "theserver":
			pass  # asyncio.create_task(self.broadcast_event(event))
		else:
			if self.args.debug_gamestate:
				pass  # logger.warning(f"{self} skipping broadcast_event bullet event from {client_id}: {event}")
		await asyncio.sleep(0)
		return True

	async def _on_player_drop_bomb(self, event: dict[str, Any]) -> bool:
		client_id = event.get("client_id")
		pos = self._to_pos_tuple(event.get("position"))
		# Keep replicated state in sync with the event
		player_entry = self.playerlist.get(client_id)
		player_entry.bombs_left -= 1
		if self.args.debug_gamestate:
			pass  # logger.debug(f"{self} Updated PlayerState bombs_left for {client_id} to {player_entry.bombs_left}")
		# Also update local sprite if this is us
		for sprite in self.players_sprites:
			if sprite.client_id == client_id:
				sprite.bombs_left = player_entry.bombs_left
				break
		# Create a bomb sprite locally. Server does not simulate bombs but should broadcast.
		bomb = Bomb(position=pos, client_id=client_id)
		await bomb.async_init()
		self.bombs.add(bomb)

		event["handled"] = True
		event["handledby"] = "_on_player_drop_bomb"
		asyncio.create_task(self.broadcast_event(event))
		if self.client_id == "theserver":
			pass  # asyncio.create_task(self.broadcast_event(event))
		else:
			if self.args.debug_gamestate:
				pass  # logger.warning(f"{self} skipping broadcast_event bomb drop event from {client_id}: {event}")
		return True

	async def _on_bomb_exploded(self, event: dict[str, Any]) -> bool:
		# De-dupe explosions so the originating client doesn't double-credit bombs_left
		explosion_id = event.get("event_id")
		if event.get("handled"):
			self.processed_explosions.add(explosion_id)
			if self.args.debug_gamestate:
				logger.warning(f"{self} _on_bomb_exploded: explosion_id {explosion_id}, already handled ignoring. self.processed_explosions: {len(self.processed_explosions)} event: {event}")
			await asyncio.sleep(0)
			return False
		if explosion_id in self.processed_explosions:
			if self.args.debug_gamestate:
				logger.warning(f"{self} _on_bomb_exploded: Duplicate explosion_id {explosion_id}, ignoring. self.processed_explosions: {len(self.processed_explosions)} event: {event}")
			await asyncio.sleep(0)
			return False
		self.processed_explosions.add(explosion_id)
		owner_raw = event.get("owner_id") or event.get("client_id")
		player_entry = self.playerlist.get(owner_raw)
		if player_entry:
			player_entry.bombs_left = min(3, player_entry.bombs_left + 1)
			# Also update local sprite if present
			for sprite in self.players_sprites:
				if sprite.client_id == owner_raw:
					sprite.bombs_left = min(3, sprite.bombs_left + 1)
					break

			event["handled"] = True
			event["handledby"] = "_on_bomb_exploded"
			asyncio.create_task(self.broadcast_event(event))
			if self.client_id == "theserver":
				pass  # asyncio.create_task(self.broadcast_event(event))
				if self.args.debug_gamestate:
					logger.debug(f"{self} _on_bomb_exploded: event: {event}")
			await asyncio.sleep(0)
		else:
			if self.args.debug_gamestate:
				pass  # logger.warning(f"{self} _on_bomb_exploded: No player entry for owner_id/client_id: {owner_raw} event: {event}")
			await asyncio.sleep(0)
		return True

	async def _on_noop_event(self, event: dict[str, Any]) -> bool:
		# Intentionally ignore (used for client-side feedback events)
		event["handled"] = True
		event["handledby"] = "_on_noop_event"
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
			ps = existing
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
		event["handledby"] = "_on_player_update"
		if self.client_id == "theserver":
			# IMPORTANT: clients can have stale health; broadcast server-authoritative state.
			out_event = dict(event)
			out_event["handled"] = False
			out_event["handledby"] = "server.authoritative_player_update"
			out_event["position"] = ps.position
			out_event["score"] = ps.score
			out_event["bombs_left"] = ps.bombs_left
			out_event["health"] = ps.health
			out_event["client_name"] = ps.client_name
			# asyncio.create_task(self.broadcast_event(out_event))
		else:
			if self.args.debug_gamestate:
				pass  # logger.warning(f"{self} skipping broadcast_event for player_update on client.")
			# asyncio.create_task(self.broadcast_event(event))
		out_event = dict(event)
		out_event["handled"] = False
		out_event["handledby"] = "server.authoritative_player_update"
		out_event["position"] = ps.position
		out_event["score"] = ps.score
		out_event["bombs_left"] = ps.bombs_left
		out_event["health"] = ps.health
		out_event["client_name"] = ps.client_name
		asyncio.create_task(self.broadcast_event(out_event))
		await asyncio.sleep(0)
		return True

	async def _on_player_hit(self, event: dict) -> bool:
		# De-dupe by event id when available
		hit_id = event.get('event_id') or event.get('event_id')
		if hit_id is not None and hit_id in self.processed_hits or event.get('handled'):
			if self.args.debug_gamestate:
				logger.warning(f"{self} Duplicate player_hit event ignored: {event} self.processed_hits: {len(self.processed_hits)}")
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
			allowed_reporters = {"theserver"}
			allowed_reporters.add(shooter)
			allowed_reporters.add(target_id)
			if reported_by not in allowed_reporters:
				if self.args.debug_gamestate:
					logger.warning(f"{self} Rejected unauthorized player_hit report: {event} reported_by: {reported_by} allowed_reporters: {allowed_reporters}")
				await asyncio.sleep(0)
				return False

		target = event.get("target_id", "")
		target_player_entry = self.playerlist.get(target)
		old_health = target_player_entry.health
		# Keep event_type as 'player_hit' so receivers handle it consistently.
		event["handledby"] = "_on_player_hit"
		damage = event.get('damage', 0)
		# If server attached an authoritative target_health, apply it directly on clients.
		auth_health = int(event.get("target_health",0))
		if self.client_id != "theserver":
			target_player_entry.health = max(0, auth_health)
			if target_player_entry.health <= 0:
				target_player_entry.killed = True
			if self.args.debug_gamestate:
				pass  # logger.debug(f"{self} target {target}: {old_health} -> {target_player_entry.health} damage: {damage}")
		if self.client_id == "theserver":
			target_player_entry.take_damage(damage, attacker_id=event.get("client_id"))
			if self.args.debug_gamestate:
				logger.info(f"{self} _on_player_hit for {target}: {old_health} -> {target_player_entry.health} damage: {damage} from attacker: {event.get('client_id')} {event.get('client_name')}")
		else:
			if self.args.debug_gamestate:
				logger.debug(f"{self} _on_player_hit for {target}: {old_health} -> {target_player_entry.health} damage: {damage} from attacker: {event.get('client_id')} {event.get('client_name')}")
		self.playerlist[target] = target_player_entry
		# If we are the target, also sync the local sprite so HUD/debug reflects correct health.
		# if isinstance(target_player_entry, PlayerState):
		await self._sync_local_sprite_from_state(target_player_entry)

		# Mark handled locally so we don't reapply if this event loops back.
		event['handled'] = True
		event["handledby"] = "_on_player_hit"
		# if hit_id is not None:
		self.processed_hits.add(hit_id)

		# Only the server should broadcast hit events.
		if self.client_id == "theserver":
			# Broadcast a fresh copy that clients will actually apply.
			out_event = dict(event)
			out_event["handled"] = False
			out_event["handledby"] = "server.broadcast_player_hit"
			out_event["target_health"] = getattr(target_player_entry, 'health', None)
			# asyncio.create_task(self.broadcast_event(out_event))
		else:
			if self.args.debug_gamestate:
				pass  # logger.warning(f"{self} skipping broadcast_event for player_hit on client.")
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
				logger.warning(f"{self} Duplicate upgrade pickup event ignored: {event} self.processed_upgrades: {len(self.processed_upgrades)}")
			return False
		self.processed_upgrades.add(event_id)
		# logger.debug(f"{self} _on_upgrade_pickup event: {event}")
		# event: {'event_type': 'upgrade_pickup', 'client_id': '731614597', 'position': [768, 1088], 'upgradetype': 'range', 'handled': False, 'handledby': '731614597', 'event_id': 5857889296, 'event_time': 1767046605.908763}
		pos = event.get('position')
		tile_x = int(pos[0]) // self.tile_map.tilewidth
		tile_y = int(pos[1]) // self.tile_map.tileheight
		# Remove the Upgrade block locally
		# self.modified_tiles[(tile_x, tile_y)] = 1
		# self.tile_map.get_layer_by_name('Blocks').data[tile_y][tile_x] = 1  # type: ignore
		# self.upgrade_by_tile[(tile_x, tile_y)] = None
		upgrade_object = self.upgrade_by_tile.pop((tile_x, tile_y), None)
		if upgrade_object:
			if self.args.debug_gamestate:
				logger.debug(f"{self} Removed {upgrade_object} at tile {(tile_x, tile_y)} pos: {pos} upgrade: {upgrade_object} self.upgrade_blocks: {len(self.upgrade_blocks)} self.upgrade_by_tile: {len(self.upgrade_by_tile)}")
			await self.destroy_block(upgrade_object, create_upgrade=False)
			upgrade_object.kill()
			self.upgrade_blocks.discard(upgrade_object)
		else:
			if self.args.debug_gamestate:
				logger.warning(f"{self} No upgrade found at tile {(tile_x, tile_y)} pos: {pos} to remove. self.upgrade_blocks: {len(self.upgrade_blocks)} self.upgrade_by_tile: {len(self.upgrade_by_tile)}")
		event['handled'] = True
		event['handledby'] = '_on_upgrade_pickup'
		await asyncio.sleep(0)

		return True

	async def _on_upgrade_spawned(self, event: dict) -> bool:
		# Create an Upgrade locally from a server announcement
		pos = event.get('position')
		tw, th = self.tile_map.tilewidth, self.tile_map.tileheight
		upgrade_pos = (pos[0] * tw, pos[1] * th)
		tile_x = int(pos[0])
		tile_y = int(pos[1])
		# Avoid duplicate spawns
		if (tile_x, tile_y) in self.upgrade_by_tile:
			if self.args.debug_gamestate:
				logger.warning(f'{self} Upgrade already exists at {(tile_x, tile_y)}, pos: {pos} upgrade_pos: {upgrade_pos} ignoring upgrade_by_tile: {self.upgrade_by_tile[(tile_x, tile_y)]} event: {event}')
			await asyncio.sleep(0)
			return False
		upgradetype = event.get('upgradetype',0)
		upgrade = Upgrade(position=upgrade_pos, upgrade_id=upgradetype)
		await upgrade.async_init()
		self.upgrade_blocks.add(upgrade)
		self.upgrade_by_tile[(tile_x, tile_y)] = upgrade

		block = self.collidable_by_tile.pop((tile_x, tile_y), None)
		self.collidable_tiles.discard(block)
		block = self.killable_by_tile.pop((tile_x, tile_y), None)
		self.killable_tiles.discard(block)

		# self.modified_tiles[(tile_x, tile_y)] = upgradetype
		# self.tile_map.get_layer_by_name('Blocks').data[tile_y][tile_x] = upgradetype  # type: ignore

		if self.args.debug_gamestate:
			logger.debug(f"{self} {upgrade} self.upgrade_blocks: {len(self.upgrade_blocks)} at {(tile_x, tile_y)}, pos: {pos} upgrade_pos: {upgrade_pos} upgradetype: {upgradetype} popped block: {block} ")
			# event: {'event_type': 'upgrade_spawned', 'client_id': 'theserver', 'position': [16, 53], 'upgradetype': 20, 'handled': False, 'handledby': '_apply_tile_change', 'event_id': 9882611095, 'event_time': 1767078826.0457697}
		await asyncio.sleep(0)
		return True

	async def _on_unknown_event(self, event: dict) -> bool:
		logger.warning(f"{self} Unknown event_type: {event.get('event_type')} event: {event}")
		await asyncio.sleep(0)
		return False
