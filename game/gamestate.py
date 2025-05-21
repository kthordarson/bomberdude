import asyncio
from typing import Any
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
from constants import DEFAULT_HEALTH, UPDATE_TICK, GLOBAL_RATE_LIMIT
import pytmx
from pytmx import load_pygame
import json


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

	def __repr__(self):
		return f'Gamestate ( event_queue:{self.event_queue.qsize()} client_queue:{self.client_queue.qsize()}  players:{len(self.playerlist)} players_sprites:{len(self.players_sprites)})'

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
		layer.data[tile_y][tile_x] = 0  # Set to empty tile
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
				logger.debug(f'Rate limiting {client_id}: {timediff:.3f}s GLOBAL_RATE_LIMIT: {GLOBAL_RATE_LIMIT}')
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
				if hasattr(conn, 'write'):
					if not conn.is_closing():
						conn.write(data)
						tasks.append(conn.drain())

			if tasks:
				await asyncio.gather(*tasks, return_exceptions=True)

		except Exception as e:
			logger.error(f"Error in broadcast_state: {e} {type(e)}")

	async def broadcast_state_v1(self, game_state):
		"""Broadcast game state to all connected clients"""
		dead_connections = set()
		loop = asyncio.get_event_loop()
		try:
			data = json.dumps(game_state).encode('utf-8') + b'\n'
		except TypeError as e:
			logger.error(f"Error encoding game_state: {e} game_state: {game_state}")
			return

		modified_tiles = {}
		for pos, gid in self.modified_tiles.items():
			modified_tiles[str(pos)] = gid
		game_state['modified_tiles'] = modified_tiles

		try:
			for conn in self.connections:
				try:
					# Check if it's a StreamWriter (from NewBombServer) or a socket
					if hasattr(conn, 'write'):  # StreamWriter
						if conn.is_closing():
							dead_connections.add(conn)
							continue
						conn.write(data)
						await conn.drain()
					else:  # Socket
						logger.warning(f'{conn} {type(conn)}')
						await loop.sock_sendall(conn, data)
				except Exception as e:
					logger.error(f"Error broadcasting to client: {e}")
					dead_connections.add(conn)
			# Clean up dead connections
			for dead_conn in dead_connections:
				logger.warning(f"Removing {dead_conn} from connections")
				self.remove_connection(dead_conn)
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
		logger.warning("Creating default player - no player found!")
		player = Bomberplayer(texture="data/playerone.png", client_id=self.client_id)
		self.players_sprites.add(player)
		return player

	def load_tile_map(self, mapname):
		self.mapname = mapname
		self.tile_map = load_pygame(self.mapname)
		# Create a cache for tile images
		self.static_map_surface = pygame.Surface((self.tile_map.width * self.tile_map.tilewidth, self.tile_map.height * self.tile_map.tileheight))

		for layer in self.tile_map.visible_layers:
			for x, y, gid in layer:
				# Skip empty tiles (gid = 0)
				if gid == 0:
					continue
				# Cache the tile image if not already cached
				if gid not in self.tile_cache:
					self.tile_cache[gid] = self.tile_map.get_tile_image_by_gid(gid)

				tile = self.tile_cache[gid]
				if tile:
					self.static_map_surface.blit(tile, (x * self.tile_map.tilewidth, y * self.tile_map.tileheight))
					if layer.properties.get('collidable'):
						sprite = pygame.sprite.Sprite()
						sprite: Any = sprite  # or use a Protocol class
						sprite.image = tile
						sprite.rect = pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)
						sprite.layer = layer.name
						self.collidable_tiles.append(sprite)
						if layer.properties.get('killable'):
							self.killable_tiles.append(sprite)
		if self.args.debug:
			logger.debug(f'loading {self.mapname} done. Cached {len(self.tile_cache)} unique tiles.')

	def render_map(self, screen, camera):
		"""Render the map using cached tile images"""
		self.explosion_manager.draw(screen, camera)
		screen.blit(self.static_map_surface, camera.apply(pygame.Rect(0, 0, self.static_map_surface.get_width(), self.static_map_surface.get_height())))

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
				'bombsleft': msg_event.get('bombsleft'),
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
				initial_bombs=player_data.get('bombsleft', 3) or 3,  # Convert None to 3
				health=player_data.get('health', 100) or 100,  # Convert None to 100
				killed=player_data.get('killed', False) or False,
				timeout=player_data.get('timeout', False) or False
			)
		if isinstance(player_data, PlayerState):
			# Ensure PlayerState has non-None values for critical attributes
			if player_data.bombsleft is None:
				player_data.bombsleft = 3
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

	async def update_game_event(self, game_event):
		event_type = game_event.get('event_type')
		client_id = game_event.get("client_id")
		# Ensure client_id is always a string
		if client_id is not None and not isinstance(client_id, str):
			client_id = str(client_id)
			game_event["client_id"] = client_id

		# If owner_id exists, ensure it's a string too
		if "owner_id" in game_event and not isinstance(game_event["owner_id"], str):
			game_event["owner_id"] = str(game_event["owner_id"])

		match event_type:
			case 'map_info':
				# Get mapname and load it
				map_name = game_event.get('mapname')
				pos_str = ''
				new_gid = 0
				if map_name and map_name != self.mapname:
					logger.info(f"Loading map: {map_name}")
					self.load_tile_map(map_name)

				# Apply any tile modifications (destroyed blocks)
				modified_tiles = game_event.get('modified_tiles', {})
				for pos_str, new_gid in modified_tiles.items():
					# Convert string key back to tuple
					x, y = eval(pos_str) if isinstance(pos_str, str) else pos_str

					# Apply the modification
					layer = self.tile_map.get_layer_by_name('Blocks')
					if layer and 0 <= y < len(layer.data) and 0 <= x < len(layer.data[0]):
						layer.data[y][x] = new_gid

						# Update visual representation too
						if new_gid == 0:  # If block was destroyed
							floor_tile = self.tile_cache.get(1)  # Get floor tile
							if floor_tile:
								self.static_map_surface.blit(floor_tile,
									(x * self.tile_map.tilewidth, y * self.tile_map.tileheight))

							# Remove from collision handling if applicable
							for block in self.killable_tiles[:]:
								block_x = block.rect.x // self.tile_map.tilewidth
								block_y = block.rect.y // self.tile_map.tileheight
								if block_x == x and block_y == y:
									self.killable_tiles.remove(block)
									if block in self.collidable_tiles:
										self.collidable_tiles.remove(block)
									break
				if self.args.debug:
					logger.info(f"[map_info] Applied {len(modified_tiles)} map modifications {pos_str=} -> {new_gid=}")

			case 'map_update':
				# Handle incremental map updates during gameplay
				tile_x, tile_y = game_event.get('position')
				new_gid = game_event.get('new_gid')

				# Apply modification
				layer = self.tile_map.get_layer_by_name('Blocks')
				layer.data[tile_y][tile_x] = new_gid

				# Track the modification
				self.modified_tiles[(tile_x, tile_y)] = new_gid

				# Update visual representation
				if new_gid == 0:  # If block was destroyed
					floor_tile = self.tile_cache.get(1)
					if floor_tile:
						self.static_map_surface.blit(floor_tile,
							(tile_x * self.tile_map.tilewidth, tile_y * self.tile_map.tileheight))

					# Remove from collision lists if applicable
					for block in self.killable_tiles[:]:
						block_x = block.rect.x // self.tile_map.tilewidth
						block_y = block.rect.y // self.tile_map.tileheight
						if block_x == tile_x and block_y == tile_y:
							self.killable_tiles.remove(block)
							if block in self.collidable_tiles:
								self.collidable_tiles.remove(block)
							break
				await self.broadcast_event(game_event)

			case 'player_joined':
				# Add a visual notification for clients
				logger.info(f"Player {client_id} has joined the game!")

				# Add player to local playerlist if not present
				if client_id not in self.playerlist:
					position = game_event.get('position', [100, 100])
					self.playerlist[client_id] = PlayerState(client_id=client_id, position=position, health=DEFAULT_HEALTH, initial_bombs=3, score=0)
					if self.args.debug:
						logger.debug(f"Added new player {client_id} at position {position}")

				await self.broadcast_event(game_event)

			case 'player_update':
				# Update other player's position in playerlist
				if client_id != self.client_id:
					position = game_event.get('position')
					bombsleft = game_event.get('bombsleft')
					if client_id in self.playerlist:
						player = self.ensure_player_state(self.playerlist[client_id])
						if player:
							if isinstance(player, dict):
								# Direct update without complex interpolation
								self.playerlist[client_id] = PlayerState(client_id=client_id, position=position, health=player.get('health',0), score=player.get('score',0))
								logger.warning(f'playerdict {player} {game_event=}')
							else:
								# Handle PlayerState objects
								player.position = position
								player.bombsleft = bombsleft
					else:
						logger.warning(f'newunknownplayer {client_id=}')
						# Add new player with minimal required fields
						self.playerlist[client_id] = PlayerState(client_id=client_id, position=position, health=DEFAULT_HEALTH, score=0)
				await self.broadcast_event(game_event)
				await asyncio.sleep(1 / UPDATE_TICK)

			case 'playerquit':
				client_id = game_event.get('client_id')
				if client_id in self.playerlist:
					logger.info(f"Player {client_id} has disconnected")
					del self.playerlist[client_id]
					# Broadcast quit event to all clients so they can update their playerlists
					await self.broadcast_event(game_event)
				# Still pass the event to the local event queue for local handling
				await self.event_queue.put(game_event)

			case 'acknewplayer':
				game_event['handled'] = True
				self._ready = True
				ack_event = {"event_type": "acknewplayer", "client_id": self.client_id, "event": game_event}
				if self.args.debug:
					logger.info(f"acknewplayer {ack_event.get('event_type')} {ack_event.get('client_id')} ")
				# await self.broadcast_state(ack_event)

			case 'connection_event':
				game_event['handled'] = True
				game_event['handledby'] = 'ugsnc'
				game_event['event_type'] = 'acknewplayer'
				client_id = game_event.get('client_id')
				if client_id not in self.playerlist:
					self.playerlist[client_id] = PlayerState(client_id=client_id, position=game_event.get('position'), health=100)
				# await self.broadcast_state({"event_type": "acknewplayer", "event": game_event})
				await self.broadcast_event(game_event)
				# await self.event_queue.put(game_event)

			case 'player_drop_bomb':
				# Server-side validation of bomb limit
				owner_id = game_event.get('client_id')

				# Count active bombs for this player
				active_bomb_count = sum(1 for bomb in self.bombs if bomb.client_id == owner_id and not bomb.exploded)

				# Check if player already has 3 bombs on the field
				if active_bomb_count >= 3:
					# Reject the bomb drop and notify the client
					game_event['event_type'] = "dropcooldown"
					game_event['handledby'] = "server_validation"
					game_event['message'] = "Maximum bombs reached (3)"

					# Only send back to the requesting client
					if owner_id in self.playerlist:
						# Update client's bombsleft to match server state (3 - active bombs)
						player = self.playerlist[owner_id]
						if isinstance(player, Bomberplayer):
							player.bombsleft = max(0, 3 - active_bomb_count)
						elif isinstance(player, dict) and 'bombsleft' in player:
							player['bombsleft'] = max(0, 3 - active_bomb_count)

						game_event['bombsleft'] = max(0, 3 - active_bomb_count)

						# Send only to the client who tried to drop the bomb
						for conn in self.connections:
							if hasattr(conn, 'client_id') and conn.client_id == owner_id:
								await self.send_to_client(conn, game_event)
								break
				else:
					# Allow bomb drop
					game_event['handledby'] = 'ugsbomb'
					game_event['event_type'] = 'ackbombdrop'
					game_event['active_bombs'] = active_bomb_count + 1
					await self.broadcast_event(game_event)

			case 'ackbombdrop':
				if self.args.debug:
					logger.debug(f'ackbombdrop {client_id=} {self.client_id=}')
				bomb = Bomb(position=game_event.get('position'), client_id=game_event.get('client_id'))
				self.bombs.add(bomb)

			case 'bulletfired':
				game_event['handledby'] = 'ackbulletupdate_game_event'
				game_event['event_type'] = 'ackbullet'
				game_event['handled'] = True
				await self.broadcast_event(game_event)

			case 'ackbullet':
				# bullet = Bullet()
				bullet_position = Vec2d(game_event.get('position')[0], game_event.get('position')[1])
				bullet_direction = Vec2d(game_event.get('direction')[0], game_event.get('direction')[1])
				if client_id == self.get_playerone().client_id:
					bullet_size = (7,7)
				else:
					bullet_size = (7,7)
				bullet = Bullet(position=bullet_position, direction=bullet_direction, screen_rect=self.get_playerone().rect, bullet_size=bullet_size, owner_id=client_id)
				self.bullets.add(bullet)

			case 'player_hit':
				target_id = game_event.get('target_id')
				damage = game_event.get('damage', 10)
				try:
					player_one = self.get_playerone()
					if player_one.client_id == target_id:
						player_one.take_damage(damage, game_event.get('client_id'))
				except Exception as e:
					logger.error(f'{e} {type(e)}')
				# Apply damage to target player
				if target_id not in self.playerlist:
					logger.warning(f'target_id not in playerlist: {target_id=}')
					logger.warning(f'playerlist: {self.playerlist}')
					self.playerlist[target_id] = PlayerState(client_id=target_id, position=game_event.get('position', [0, 0]), health=100 - damage)
				# else:  # target_id in self.playerlist:
				player = self.ensure_player_state(self.playerlist[target_id])
				if isinstance(player, dict):
					try:
						player['health'] = player.get('health') - damage
					except Exception as e:
						logger.error(f'Error updating health: {e} {type(e)} {player=}')
					logger.info(f'dictplayer_hit {target_id=} {damage=} player: {player["client_id"]} {player["health"]}')
					# Check if player is killed
					if player['health'] <= 0:
						# Create kill event
						game_event["event_time"] = time.time()
						game_event["event_type"] = "player_killed"
						game_event["client_id"] = client_id
						game_event["target_id"] = target_id
						game_event["position"] = game_event.get('position')
						game_event["handledby"] = "PlayerStateplayer_hit"
						# await self.broadcast_event(kill_event)
				else:
					# Handle PlayerState objects
					player.health -= damage
					if self.args.debug:
						logger.debug(f'PlayerStateplayer_hit {target_id=} {damage=} {player.client_id=} {player.health=} ')
					if player.health <= 0:
						# Create kill event
						game_event["event_time"] = time.time()
						game_event["event_type"] = "player_killed"
						game_event["client_id"] = client_id
						game_event["target_id"] = target_id
						game_event["position"] = game_event.get('position')
						game_event["handledby"] = "PlayerStateplayer_hit"
				if not game_event.get('handled'):
					game_event['handled'] = True
					game_event['health'] = player.health  # Include updated health in event
					# Broadcast the hit event to all clients
				await self.broadcast_event(game_event)
				# asyncio.create_task(self.event_queue.put(game_event))

			case 'player_killed':
				killer_id = client_id
				target_id = game_event.get('target_id')

				logger.info(f'player_killed {target_id} by {killer_id} ')

				# Award points to killer
				if killer_id in self.playerlist:
					if isinstance(self.playerlist[killer_id], dict):
						self.playerlist[killer_id]['score'] = self.playerlist[killer_id].get('score', 0) + 1
					else:
						try:
							self.playerlist[killer_id].score += 1
						except TypeError as e:
							logger.error(f'{e} {type(e)} {killer_id=} playerlist: {self.playerlist}')

					await self.broadcast_event(game_event)

			case 'bomb_exploded':
				# Process the explosion
				client_id = game_event.get('owner_id') or game_event.get('client_id')
				position = game_event.get('position')

				# Unique ID to prevent duplicate processing
				event_id = game_event.get('event_id', str(time.time()))

				# Create visual explosion
				if hasattr(self, 'explosion_manager'):
					self.explosion_manager.create_explosion(position)

				# Count remaining bombs for this player AFTER this one exploded
				active_bomb_count = sum(1 for bomb in self.bombs
										if bomb.client_id == client_id and not bomb.exploded)

				# Restore bomb to the player's inventory - server is authoritative on bomb count
				if client_id in self.playerlist:
					player = self.playerlist[client_id]
					bombs_restored = False

					if isinstance(player, Bomberplayer):
						# Always set to correct value (3 - active bombs)
						player.bombsleft = min(3, 3 - active_bomb_count)
						game_event['bombsleft'] = player.bombsleft
					elif isinstance(player, dict) and 'bombsleft' in player:
						player['bombsleft'] = min(3, 3 - active_bomb_count)
						game_event['bombsleft'] = player['bombsleft']
						logger.debug(f"Restored bomb to {client_id}, now has {player['bombsleft']}")

				# Broadcast the explosion event to all clients with updated bomb count
				await self.broadcast_event(game_event)

			case _:
				# payload = {'event_type': 'error99', 'payload': ''}
				logger.warning(f'unknown game_event:{event_type} from game_event={game_event}')
				# await self.event_queue.put(payload)

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

	async def from_json(self, data):
		event_type = data.get('event_type')
		sender_client_id = data.get('client_id')
		match event_type:
			case 'playerquit':
				if sender_client_id and sender_client_id in self.playerlist:
					logger.info(f"Removing quit player {sender_client_id} from local playerlist")
					del self.playerlist[sender_client_id]

					# Also remove from sprites if present
					for sprite in list(self.players_sprites):
						if getattr(sprite, 'client_id', None) == sender_client_id:
							sprite.kill()

			case 'acknewplayer':
				if self.args.debug:
					logger.info(f"{event_type} {data=}")
				await self.update_game_event(data)

			case 'send_game_state':
				for player_data in data.get('playerlist', []):
					client_id = player_data.get('client_id')
					if client_id != self.client_id:  # Don't update our own player
						if client_id in self.playerlist:
							# Update existing player
							player = self.ensure_player_state(self.playerlist[client_id])
							player.position = player_data.get('position')
							player.health = player_data.get('health')
							player.score = player_data.get('score')
						else:
							if self.args.debug:
								logger.info(f"{event_type} {data=}")
							# Create new player
							self.playerlist[client_id] = PlayerState(**player_data)
			case 'map_info':
				# Handle map info messages
				if self.args.debug:
					logger.info(f"Received map info: {data.get('mapname')} {data=}")
				# Get mapname and load it if needed
				map_name = data.get('mapname')
				if map_name and map_name != self.mapname:
					logger.info(f"Loading map from map_info: {map_name}")
					self.load_tile_map(map_name)

				# Apply any tile modifications (destroyed blocks)
				modified_tiles = data.get('modified_tiles', {})
				for pos_str, new_gid in modified_tiles.items():
					# Convert string key back to tuple
					x, y = eval(pos_str) if isinstance(pos_str, str) else pos_str

					# Apply the modification
					layer = self.tile_map.get_layer_by_name('Blocks')
					if layer and 0 <= y < len(layer.data) and 0 <= x < len(layer.data[0]):
						layer.data[y][x] = new_gid

						# Update visual representation
						if new_gid == 0:  # If block was destroyed
							floor_tile = self.tile_cache.get(1)  # Get floor tile
							if floor_tile:
								self.static_map_surface.blit(floor_tile,
									(x * self.tile_map.tilewidth, y * self.tile_map.tileheight))

								# Update collision lists if applicable - no sprites to remove here
								# but we can update our internal tracking
								self.modified_tiles[(x, y)] = new_gid
					if self.args.debug:
						logger.info(f"Applied {len(modified_tiles)} map modifications from map_info")
			case 'playerlist':
				try:
					for player_data in data.get('playerlist', []):
						client_id = player_data.get('client_id')
						if not client_id:
							logger.error(f'client_id missing in player_data: {player_data}')
							continue
						elif client_id != self.client_id:  # Don't update our own player
							if client_id in self.playerlist:
								# Update existing player
								player = self.ensure_player_state(self.playerlist[client_id])
								position = player_data.get('position')
								if position:
									if hasattr(player, 'position'):
										if isinstance(player.position, Vec2d):
											if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
												player.position.x, player.position.y = position[0], position[1]
										else:
											player.position = position
									else:
										# Safely handle either dict or object
										if isinstance(player, dict):
											player['position'] = position
										else:
											setattr(player, 'position', position)
									# Set up interpolation data
									if hasattr(player, 'target_position'):
										player.target_position = position
										player.position_updated = True
							else:
								# Create new player
								logger.debug(f'newplayer {client_id=} {player_data=}')
								try:
									self.playerlist[client_id] = PlayerState(
										client_id=client_id,
										position=player_data.get('position', (0, 0)),
										health=DEFAULT_HEALTH,
										initial_bombs=player_data.get('bombsleft', 3),
										score=player_data.get('score', 0)
									)
								except Exception as e:
									logger.error(f"Could not create PlayerState: {e}")
						else:
							logger.warning(f"Skipping player: {client_id} {data=}")
				except Exception as e:
					logger.error(f"Error updating player from json: {e}")
			case 'playerlistupdate':
				try:
					for player_data in data.get('playerlist', []):
						client_id = player_data.get('client_id')
						if not client_id:
							logger.error(f'client_id missing in player_data: {player_data}')
							continue
						if client_id == 'bombserver':
							logger.warning(f'bombserverplayer_data: {player_data} data={data}')
							continue
						if client_id == 'gamestatenotset':
							logger.warning(f'gamestatenotset: {player_data} data={data}')
							continue
						# IMPORTANT: Update bombsleft for local player
						if client_id == self.client_id and 'bombsleft' in player_data:
							player_one = self.get_playerone()
							player_one.bombsleft = player_data['bombsleft']
							# logger.debug(f"Local player bombs updated: {player_one.bombsleft}")
						elif client_id != self.client_id:  # Don't update our own player
							if client_id in self.playerlist:
								# Update existing player
								player = self.ensure_player_state(self.playerlist[client_id])
								position = player_data.get('position')
								if position:
									if hasattr(player, 'position'):
										if isinstance(player.position, Vec2d):
											if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
												player.position.x, player.position.y = position[0], position[1]
										else:
											player.position = position
									else:
										# Safely handle either dict or object
										if isinstance(player, dict):
											player['position'] = position
										else:
											setattr(player, 'position', position)

									# Set up interpolation data
									if hasattr(player, 'target_position'):
										player.target_position = position
										player.position_updated = True
							else:
								# Create new player
								newplayer = PlayerState(client_id=client_id, position=player_data.get('position', (0, 0)), health=DEFAULT_HEALTH, initial_bombs=player_data.get('bombsleft', 3), score=player_data.get('score', 0))
								if newplayer.position:
									logger.info(f'newplayer {client_id=} pos: {newplayer.position}')
									try:
										self.playerlist[client_id] = newplayer
									except Exception as e:
										logger.error(f"Could not create PlayerState: {e}")
				except Exception as e:
					logger.error(f"Error updating player from json: {e} {data}")
			case _:
				logger.warning(f"Unknown event_type: {data.get('event_type')} data: {data}")

	def cleanup_playerlist(self):
		"""Remove players with None positions from playerlist"""
		for client_id, player in list(self.playerlist.items()):
			if (isinstance(player, PlayerState) and player.position is None) or (isinstance(player, dict) and player.get('position') is None):
				logger.info(f"Removing player with None position: {client_id}")
				del self.playerlist[client_id]

	def update_remote_players(self, delta_time):
		"""Update remote player interpolation"""
		for client_id, player in self.playerlist.items():
			if client_id != self.client_id:  # Only update remote players
				try:
					# Check if player is dictionary or PlayerState object
					if isinstance(player, dict):
						# Dictionary players (server-originated)
						if 'position' not in player:
							logger.warning(f'missing position in player: {player}')
							continue

						# Initialize interpolation properties if needed
						if 'prev_position' not in player:
							player['prev_position'] = player['position']
							player['target_position'] = player['position']
							player['interp_time'] = 0
							player['position_updated'] = False

						# Handle interpolation
						if player.get('position_updated', False):
							if isinstance(player['position'], list):
								player['prev_position'] = player['position'].copy()
							else:
								player['prev_position'] = player['position']
							player['interp_time'] = 0
							player['position_updated'] = False

					else:
						# PlayerState objects (client-originated)
						if not hasattr(player, 'position'):
							logger.warning(f'missing position in player: {player}')
							continue

						# Initialize interpolation attributes if needed
						if not hasattr(player, 'prev_position') or player.prev_position is None:
							player.prev_position = player.position
							player.target_position = player.position
							player.interp_time = 0
							player.position_updated = False

						# Update interpolation
						if getattr(player, 'position_updated', False):
							player.prev_position = player.position
							player.interp_time = 0
							player.position_updated = False
				except Exception as e:
					logger.warning(f"Error in update_remote_players for {client_id}: {e}")

	def check_bullet_collisions(self):
		"""Check for collisions between bullets and players"""
		for bullet in self.bullets:
			# Skip checking collision with the player who shot the bullet
			bullet_owner = getattr(bullet, 'owner_id', None)

			# Check collision with player sprites
			for player in self.players_sprites:

				# Skip self-collision
				player_id = player.client_id if hasattr(player, 'client_id') else player.get('client_id')
				if player_id == bullet_owner:
					continue

				# Get rect for collision check
				if hasattr(player, 'rect'):
					player_rect = player.rect
				elif hasattr(player, 'position'):
					# Create temporary rect for PlayerState objects
					pos = player.position
					player_rect = pygame.Rect(pos[0], pos[1], 32, 32)  # Assumed size
				else:
					continue  # Skip if no position data

				if bullet.rect.colliderect(player_rect):
					# Create hit event to send to server
					hit_event = {
						"event_time": time.time(),
						"event_type": "player_hit",
						"client_id": bullet_owner,  # Who shot the bullet
						"target_id": player.client_id,  # Who got hit
						"damage": 10,
						"position": (bullet.position.x, bullet.position.y),
						"handled": False,
						"handledby": "check_bullet_collisions",
						"eventid": gen_randid()
					}

					# Add to event queue to be sent to server
					asyncio.create_task(self.event_queue.put(hit_event))

					# Remove the bullet
					bullet.kill()
					return  # One hit per bullet
