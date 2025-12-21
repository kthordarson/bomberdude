import asyncio
from typing import Any, Callable, cast
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
		self.collidable_tiles = []
		self.killable_tiles = []
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
		layer = self.tile_map.get_layer_by_name('Blocks')

		self.collidable_tiles.remove(block)
		self.killable_tiles.remove(block)
		layer.data[tile_y][tile_x] = 0  # Set to empty tile  # type: ignore
		self.modified_tiles[(tile_x, tile_y)] = 0
		# Update visual representation
		self.static_map_surface.blit(self.tile_cache.get(1), (tile_x * self.tile_map.tilewidth, tile_y * self.tile_map.tileheight))  # type: ignore

		# Broadcast the map modification to all clients
		map_update_event = {
			"event_type": "map_update",
			"position": (tile_x, tile_y),
			"new_gid": 0,  # 0 = removed
			"event_time": time.time(),
			"client_id": self.client_id,
			"handled": False,
		}
		await self.event_queue.put(map_update_event)

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
		# event_type = event.get('event_type')

		client_id = event.get('client_id')
		current_time = time.time()
		# Use per-client rate limiting
		# Get last update time for this client (default to 0)
		last_time = self.last_update_times.get(client_id, 0)
		timediff = current_time - last_time

		# Rate limit
		if timediff < GLOBAL_RATE_LIMIT and last_time > 0:
			# Use debug level instead of warning for rate limiting
			if self.args and hasattr(self.args, 'debug') and self.args.debug:
				logger.debug(f'Rate limiting {client_id}: {timediff:.5f}s GLOBAL_RATE_LIMIT: {GLOBAL_RATE_LIMIT}')
			do_send = False

		try:
			if do_send:
				await self.broadcast_state({"event_type": "broadcast_event", "event": event})
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
				# if hasattr(conn, 'write'):
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

	def get_playerone(self) -> Bomberplayer:
		"""Always return a Bomberplayer instance"""
		if self.client_id == 'theserver':
			player = Bomberplayer(texture="data/playerone.png", client_id=self.client_id)
			self.players_sprites.add(player)
			return player
		# Try to find player in sprites
		for player in self.players_sprites:
			if player.client_id == self.client_id:
				return player

		# If not found in sprites but in playerlist, create sprite from data
		target_id = self.client_id
		if target_id in self.playerlist:
			player_data = self.playerlist[target_id]
			# Convert to Bomberplayer
			pos = getattr(player_data, 'position', None)
			if isinstance(player_data, dict):
				pos = player_data.get('position')

			player = Bomberplayer(texture="data/playerone.png", client_id=self.client_id)
			if pos:
				player.position = Vec2d(pos)
				player.rect.topleft = (int(player.position.x), int(player.position.y))

			# Add to sprites collection
			self.players_sprites.add(player)
			return player

		# Create default player as last resort
		logger.warning(f"Creating default player - no player found! target_id: {target_id} playerlist keys: {list(self.playerlist.keys())}")
		player = Bomberplayer(texture="data/playerone.png", client_id=self.client_id)
		self.players_sprites.add(player)
		return player

	def load_tile_map(self, mapname):
		self.mapname = mapname
		self.tile_map = load_pygame(self.mapname)
		# Create a cache for tile images
		tmap = self.tile_map
		tw, th = tmap.tilewidth, tmap.tileheight
		self.static_map_surface = pygame.Surface((tmap.width * tw, tmap.height * th))

		for layer in tmap.visible_layers:
			collidable = bool(layer.properties.get('collidable'))
			killable = bool(layer.properties.get('killable'))
			for x, y, gid in layer:
				# Skip empty tiles (gid = 0)
				if gid == 0:
					continue
				# Cache the tile image if not already cached
				if gid not in self.tile_cache:
					self.tile_cache[gid] = tmap.get_tile_image_by_gid(gid)

				tile = self.tile_cache[gid]
				if tile:
					self.static_map_surface.blit(tile, (x * tw, y * th))
					if collidable:
						sprite = pygame.sprite.Sprite()
						sprite: Any = sprite  # or use a Protocol class
						sprite.image = tile
						sprite.rect = pygame.Rect(x * tw, y * th, tw, th)
						sprite.layer = layer.name
						self.collidable_tiles.append(sprite)
						if killable:
							self.killable_tiles.append(sprite)
		if self.args.debug:
			logger.debug(f'loading {self.mapname} done. Cached {len(self.tile_cache)} unique tiles.')

	def render_map(self, screen, camera):
		"""Render the map using cached tile images"""
		self.explosion_manager.draw(screen, camera)
		screen.blit(self.static_map_surface, camera.apply(pygame.Rect(0, 0, self.static_map_surface.get_width(), self.static_map_surface.get_height())))

	# ---------- Helpers for map updates ----------
	def _parse_pos_key(self, key):
		"""Safely parse a position key that may be a tuple or a string like '(x, y)'"""
		if isinstance(key, tuple):
			return key
		if isinstance(key, str):
			try:
				return tuple(ast.literal_eval(key))  # type: ignore
			except Exception:
				s = key.strip().strip('()')
				x_s, y_s = s.split(',')
				return (int(x_s), int(y_s))
		return key

	def _apply_tile_change(self, x, y, new_gid):
		"""Apply a single tile change and update visuals/collisions/state."""
		layer = self.tile_map.get_layer_by_name('Blocks')
		if not layer:
			return
		tw, th = self.tile_map.tilewidth, self.tile_map.tileheight
		if 0 <= y < len(layer.data) and 0 <= x < len(layer.data[0]):  # type: ignore
			layer.data[y][x] = new_gid  # type: ignore
			self.modified_tiles[(x, y)] = new_gid
			if new_gid == 0:
				floor_tile = self.tile_cache.get(1)
				if floor_tile:
					self.static_map_surface.blit(floor_tile, (x * tw, y * th))
				# Remove from collision lists if applicable (scan until found)
				removed = False
				for block in self.killable_tiles:
					bx = block.rect.x // tw
					by = block.rect.y // th
					if bx == x and by == y:
						self.killable_tiles.remove(block)
						if block in self.collidable_tiles:
							self.collidable_tiles.remove(block)
						removed = True
						break

	def _apply_modifications_dict(self, modified_tiles: dict):
		"""Batch-apply many tile modifications efficiently."""
		layer = self.tile_map.get_layer_by_name('Blocks')
		if not layer:
			return
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

		if positions_to_clear and floor_tile is not None:
			for (x, y) in positions_to_clear:
				self.static_map_surface.blit(floor_tile, (x * tw, y * th))

		if positions_to_clear:
			def pos_of(block):
				return (block.rect.x // tw, block.rect.y // th)
			self.killable_tiles = [b for b in self.killable_tiles if pos_of(b) not in positions_to_clear]
			self.collidable_tiles = [b for b in self.collidable_tiles if pos_of(b) not in positions_to_clear]

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
				score=player_data.get('score', 0) or 0,  # Convert None to 0
				initial_bombs=player_data.get('bombs_left', 3) or 3,  # Convert None to 3
				health=player_data.get('health', 100) or 100,  # Convert None to 100
				killed=player_data.get('killed', False) or False,
				timeout=player_data.get('timeout', False) or False
			)
		if isinstance(player_data, PlayerState):
			# Ensure PlayerState has non-None values for critical attributes
			if player_data.bombs_left is None:
				player_data.bombs_left = 3
			if player_data.health is None:
				player_data.health = 100
			if player_data.score is None:
				player_data.score = 0
			return player_data
		# For unexpected types, create a safe default PlayerState
		logger.warning(f"Converting unexpected type {type(player_data)} to PlayerState")
		return PlayerState(
			position=(0, 0),
			client_id=str(getattr(player_data, 'client_id', 'unknown')),
			health=100,
			score=0
		)

	def cleanup_playerlist(self):
		"""Remove players with None positions from playerlist"""
		for client_id, player in list(self.playerlist.items()):
			if (isinstance(player, PlayerState) and player.position is None) or (isinstance(player, dict) and player.get('position') is None):
				logger.info(f"Removing player with None position: {client_id}")
				del self.playerlist[client_id]

	def update_remote_players(self, delta_time):
		"""Update remote player interpolation"""
		for client_id, player in self.playerlist.items():
			if client_id == self.client_id:
				continue  # Only remote players
			try:
				# Normalize dict players to have needed keys
				if isinstance(player, dict):
					pos = player.get('position')
					if pos is None:
						continue
					player.setdefault('prev_position', pos)
					player.setdefault('target_position', pos)
					player.setdefault('interp_time', 0)
					player.setdefault('position_updated', False)
					if player.get('position_updated'):
						player['prev_position'] = pos if isinstance(pos, list) else pos
						player['interp_time'] = 0
						player['position_updated'] = False
				else:
					# PlayerState objects
					if not hasattr(player, 'position') or player.position is None:
						continue
					if not hasattr(player, 'prev_position') or player.prev_position is None:
						player.prev_position = player.position
						player.target_position = player.position
						player.interp_time = 0
						player.position_updated = False
					if getattr(player, 'position_updated', False):
						player.prev_position = player.position
						player.interp_time = 0
						player.position_updated = False
			except Exception as e:
				logger.warning(f"Error in update_remote_players for {client_id}: {e}")

	def check_bullet_collisions(self):
		"""Check for collisions between bullets and players"""
		players = list(self.players_sprites)
		for bullet in self.bullets:
			bullet_owner = getattr(bullet, 'owner_id', None)
			brect = bullet.rect
			bpos = bullet.position
			for player in players:
				player_id = getattr(player, 'client_id', None)
				if player_id == bullet_owner:
					continue
				player_rect = getattr(player, 'rect', None)
				if player_rect is None:
					continue
				if brect.colliderect(player_rect):
					hit_event = {
						"event_time": time.time(),
						"event_type": "player_hit",
						"client_id": bullet_owner,
						"target_id": player_id,
						"damage": 10,
						"position": (bpos.x, bpos.y),
						"handled": False,
						"handledby": "check_bullet_collisions",
						"eventid": gen_randid()
					}
					asyncio.create_task(self.event_queue.put(hit_event))
					bullet.kill()
					return

	async def update_game_event(self, event: dict[str, Any]) -> None:
		# lots of if/elif event_type == ...
		handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
			"player_joined": self._on_player_joined,
			"map_info": self._on_map_info,
			"map_update": self._on_map_update,
			"bullet_fired": self._on_bullet_fired,
			"bulletfired": self._on_bullet_fired,
			"tile_changed": self._on_tile_changed,
			"acknewplayer": self._on_acknewplayer,
			"connection_event": self._on_connection_event,  # async
			"player_update": self._on_player_update,
			"player_drop_bomb": self._on_player_drop_bomb,
			"dropcooldown": self._on_noop_event,
			"nodropbomb": self._on_noop_event,
			"nodropbombkill": self._on_noop_event,
			"bomb_exploded": self._on_noop_event,
		}

		et_raw = event.get("event_type")
		et: str = cast(str, et_raw) if isinstance(et_raw, str) else ""
		handler = handlers.get(et, self._on_unknown_event)

		result = handler(event)
		if inspect.isawaitable(result):
			await result

	def _to_pos_tuple(self, pos: Any) -> tuple[int, int]:
		if isinstance(pos, (list, tuple)) and len(pos) == 2:
			x, y = pos
			if isinstance(x, (int, float)) and isinstance(y, (int, float)):
				return (int(x), int(y))
		return (100, 100)  # default as tuple

	def _on_player_joined(self, event: dict[str, Any]) -> None:
		pid_raw = event.get("client_id")
		if not isinstance(pid_raw, str):
			return
		pid = pid_raw
		pos_tuple = self._to_pos_tuple(event.get("position"))
		player_state = self.ensure_player_state({
			"client_id": pid,
			"position": pos_tuple,
			"health": DEFAULT_HEALTH,
			"bombs_left": 3,
			"score": 0,
		})
		self.playerlist[pid] = player_state

	def _on_acknewplayer(self, event: dict) -> None:
		# Mark client as ready upon ack from server
		self._ready = True
		event["handled"] = True
		# Optionally ensure local player is present
		pid = event.get("client_id")
		if isinstance(pid, str) and pid not in self.playerlist:
			self.playerlist[pid] = PlayerState(client_id=pid, position=(100, 100), health=DEFAULT_HEALTH, initial_bombs=3, score=0)

	async def _on_connection_event(self, event: dict) -> None:
		# Treat connection_event similarly to ack for clients
		self._ready = True
		event["handled"] = True
		pid = event.get("client_id")
		pos = self._to_pos_tuple(event.get("position", (100, 100)))
		if isinstance(pid, str) and pid not in self.playerlist:
			self.playerlist[pid] = PlayerState(client_id=pid, position=pos, health=DEFAULT_HEALTH, initial_bombs=3, score=0)
		# Broadcast ack to the client
		ack_event = {
			"event_type": "acknewplayer",
			"client_id": pid,
			"event": event
		}
		await self.broadcast_event(ack_event)

	def _on_map_info(self, event: dict) -> None:
		mods = event.get("modified_tiles") or {}
		self._apply_modifications_dict(mods)

	def _on_map_update(self, event: dict[str, Any]) -> None:
		pos_tuple = self._to_pos_tuple(event.get("position"))
		new_gid = event.get("new_gid")
		if not isinstance(new_gid, int):
			logger.debug(f"Bad map_update event (new_gid): {event}")
			return
		# Map updates are expressed in tile coords (x, y)
		x, y = pos_tuple
		# If the map isn't fully loaded yet, skip applying.
		if not hasattr(self, "tile_map") or not hasattr(self, "static_map_surface"):
			return
		self._apply_tile_change(x, y, new_gid)
		event["handled"] = True
		event["handledby"] = "gamestate._on_map_update"
		# Server should rebroadcast map changes; clients typically have no connections.
		try:
			if self.client_id == "theserver":
				asyncio.create_task(self.broadcast_event(event))
		except RuntimeError:
			pass

	def _on_bullet_fired(self, event: dict) -> None:
		pid_raw = event.get("client_id")
		if not isinstance(pid_raw, str):
			logger.debug(f"Bad bullet_fired event client_id: {event}")
			return

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
		player_sprite = self.get_playerone()
		if player_sprite and player_sprite.client_id != 'theserver':
			try:
				screen_rect = player_sprite.rect
			except Exception as e:
				logger.error(f'Error getting playerone for screen_rect: {e} {type(e)}')

			try:
				bullet = Bullet(position=pos_tuple, direction=direction, screen_rect=screen_rect, owner_id=pid_raw)
				self.bullets.add(bullet)
			except Exception as e:
				logger.error(f"Failed to create bullet from event: {e} event:{event}")
				return

			event["handled"] = True
			event["handledby"] = "gamestate._on_bullet_fired"
			# Server should rebroadcast bullet events so other clients can spawn the bullet.
			try:
				if self.client_id == "theserver":
					asyncio.create_task(self.broadcast_event(event))
			except RuntimeError:
				pass

	def _on_player_drop_bomb(self, event: dict[str, Any]) -> None:
		pid_raw = event.get("client_id")
		if not isinstance(pid_raw, str):
			logger.debug(f"Bad player_drop_bomb event client_id: {event}")
			return
		pos = self._to_pos_tuple(event.get("position"))
		# Create a bomb sprite locally. Server does not simulate bombs but should broadcast.
		try:
			bomb = Bomb(position=pos, client_id=pid_raw)
			self.bombs.add(bomb)
		except Exception as e:
			logger.error(f"Failed to create bomb from event: {e} event:{event}")
			return

		event["handled"] = True
		event["handledby"] = "gamestate._on_player_drop_bomb"
		try:
			if self.client_id == "theserver":
				asyncio.create_task(self.broadcast_event(event))
		except RuntimeError:
			pass

	def _on_noop_event(self, event: dict[str, Any]) -> None:
		# Intentionally ignore (used for client-side feedback events)
		event["handled"] = True
		event["handledby"] = "gamestate._on_noop_event"

	def _on_tile_changed(self, event: dict) -> None:
		pos_key = event.get("pos")
		gid = event.get("gid")
		if not isinstance(gid, int):
			logger.debug(f"Bad tile_changed event (gid): {event}")
			return
		pos = self._parse_pos_key(pos_key)
		if not isinstance(pos, tuple) or len(pos) != 2:
			logger.debug(f"Bad tile_changed event (pos): {event}")
			return
		x, y = pos
		self._apply_tile_change(x, y, gid)

	def _on_player_update(self, event: dict[str, Any]) -> None:
		# Normalize and update remote/local player state then broadcast
		pid_raw = event.get("client_id")
		if not isinstance(pid_raw, str):
			logger.debug(f"Bad player_update event client_id: {event}")
			return
		pid = pid_raw
		pos_tuple = self._to_pos_tuple(event.get("position"))

		pos = event.get("position")
		health = event.get("health")
		score = event.get("score")
		bombs_left = event.get("bombs_left")

		existing = self.playerlist.get(pid)
		if existing is None:
			self.playerlist[pid] = PlayerState(
				client_id=pid,
				position=pos_tuple,
				# position=pos if isinstance(pos, (list, tuple)) else [100, 100],
				health=health if isinstance(health, int) else DEFAULT_HEALTH,
				initial_bombs=bombs_left if isinstance(bombs_left, int) else 3,
				score=score if isinstance(score, int) else 0,
			)
		else:
			ps = self.ensure_player_state(existing)
			# if isinstance(pos, (list, tuple)):
			ps.position = pos_tuple
			ps.position_updated = True  # helps interpolation
			if isinstance(health, int):
				ps.health = health
			if isinstance(score, int):
				ps.score = score
			if isinstance(bombs_left, int):
				ps.bombs_left = bombs_left
			self.playerlist[pid] = ps

		# Mark handled and schedule broadcast without blocking
		event["handled"] = True
		event["handledby"] = "gamestate._on_player_update"
		try:
			asyncio.create_task(self.broadcast_event(event))
		except RuntimeError:
			# No running loop (e.g., during tests); skip scheduling
			pass

	def _on_unknown_event(self, event: dict) -> None:
		logger.debug(f"Unknown event_type: {event.get('event_type')}")
