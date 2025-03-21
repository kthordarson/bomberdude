import asyncio
import pygame
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Group
from loguru import logger
import time
from dataclasses import dataclass, field
from game.playerstate import PlayerState
from utils import gen_randid
from objects.player import KeysPressed
from objects.bullets import Bullet
from objects.bombs import Bomb
from objects.explosionmanager import ExplosionManager
from constants import DEFAULT_HEALTH, UPDATE_TICK, GLOBAL_RATE_LIMIT
import pytmx
from pytmx import load_pygame
import json


@dataclass
class GameState:
	def __init__(self, args, mapname=None, client_id=None):
		self.client_id = client_id
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
		floor_tile = self.tile_cache.get(1)
		self.static_map_surface.blit(floor_tile, (tile_x * self.tile_map.tilewidth, tile_y * self.tile_map.tileheight))

		# Broadcast the map modification to all clients
		map_update_event = {
			"event_type": "map_update",
			"position": (tile_x, tile_y),
			"new_gid": 0,  # 0 = removed
			"event_time": time.time(),
			"handled": False,
		}
		# await self.update_game_event(map_update_event)
		# await self.broadcast_event(map_update_event)
		# Send to server via event_queue instead of broadcast
		await self.event_queue.put(map_update_event)
		if self.args.debug:
			logger.debug(f"Sent map_update to server: {map_update_event}")

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
		event_type = event.get('event_type')

# 		if event_type == 'player_update':
		client_id = event.get('client_id')
		current_time = time.time()

		# Use per-client rate limiting
		if not hasattr(self, 'last_update_times'):
			self.last_update_times = {}

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
				if event_type == 'player_update':
					self.last_update_times[event.get('client_id')] = time.time()
		except Exception as e:
			logger.error(f"Error in broadcast_event: {e} {type(e)}")

	async def broadcast_state(self, game_state):
		"""Broadcast game state to all connected clients"""
		dead_connections = set()
		loop = asyncio.get_event_loop()
		try:
			# Fix the data encoding
			if isinstance(game_state, bytes):
				data = game_state + b'\n'  # Add newline for message boundary
			else:
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

	def get_player_attribute(self, player, attribute, default=None):
		"""Safely get attribute from either dict or PlayerState player"""
		if isinstance(player, dict):
			return player.get(attribute, default)
		return getattr(player, attribute, default)

	def get_playerone(self, client_id=None):
		for player in self.players_sprites:
			if player.client_id == self.client_id:
				return player
		target_id = client_id or self.client_id
		if target_id in self.playerlist:
			player = self.playerlist[target_id]
			# Ensure we can access .client_id regardless of type
			if isinstance(player, dict):
				# Create a temporary PlayerState for dict type
				player_state = PlayerState(
					client_id=player.get('client_id'),
					position=player.get('position'),
					health=player.get('health', DEFAULT_HEALTH),
					bombsleft=player.get('bombsleft', 3),
					score=player.get('score', 0)
				)
				return player_state
			return player

		logger.warning(f'player one NOT found in self.players_sprites:\n{self.players_sprites}')
		logger.warning(f'{self} playerlist: {self.playerlist}')
		raise AttributeError('player one NOT found in self.players_sprites or self.players')

	def load_tile_map(self, mapname):
		self.mapname = mapname
		self.tile_map = load_pygame(self.mapname)
		# Create a cache for tile images
		self.static_map_surface = pygame.Surface((self.tile_map.width * self.tile_map.tilewidth, self.tile_map.height * self.tile_map.tileheight))

		for layer in self.tile_map.visible_layers:
			if isinstance(layer, pytmx.TiledTileLayer):
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
							sprite.image = tile
							sprite.rect = pygame.Rect(x * self.tile_map.tilewidth, y * self.tile_map.tileheight, self.tile_map.tilewidth, self.tile_map.tileheight)
							sprite.layer = layer.name
							self.collidable_tiles.append(sprite)
							if layer.properties.get('killable'):
								self.killable_tiles.append(sprite)
			else:
				logger.warning(f'unknown layer {layer} {type(layer)}')
		if self.args.debug:
			logger.debug(f'loading {self.mapname} done. Cached {len(self.tile_cache)} unique tiles.')

	def render_map(self, screen, camera):
		"""Render the map using cached tile images"""
		self.explosion_manager.draw(screen, camera)
		screen.blit(self.static_map_surface, camera.apply(pygame.Rect(0, 0, self.static_map_surface.get_width(), self.static_map_surface.get_height())))

	def update_game_state(self, clid, msg):
		msg_event = msg.get('game_event')
		playerdict = {
			'client_id': clid,
			'position': msg_event.get('position'),
			'score': msg_event.get('score'),
			'health': msg_event.get('health'),
			'msg_dt': msg_event.get('msg_dt'),
			'timeout': msg_event.get('timeout'),
			'killed': msg_event.get('killed'),
			'event_type': 'update_game_state',
			'bombsleft': msg_event.get('bombsleft'),
		}
		self.playerlist[clid] = playerdict

	async def update_game_event(self, game_event):
		event_type = game_event.get('event_type')
		msg_client_id = game_event.get("client_id")
		match event_type:
			case 'map_info':
				# Get mapname and load it
				map_name = game_event.get('mapname')
				if map_name and map_name != self.mapname:
					logger.info(f"Loading map: {map_name}")
					self.load_tile_map(map_name)

				# Apply any tile modifications (destroyed blocks)
				modified_tiles = game_event.get('modified_tiles', {})
				for pos_str, new_gid in modified_tiles.items():
					if self.args.debug:
						logger.debug(f'[map_info] map modification: {pos_str=} -> {new_gid=}')
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

				logger.info(f"Applied {len(modified_tiles)} map modifications")

			case 'map_update':
				# Handle incremental map updates during gameplay
				tile_x, tile_y = game_event.get('position')
				new_gid = game_event.get('new_gid')

				# Apply modification
				layer = self.tile_map.get_layer_by_name('Blocks')
				if self.args.debug:
					logger.debug(f'[map_update] map modification: {tile_x=}, {tile_y=} -> {new_gid=}')
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
				logger.info(f"Player {msg_client_id} has joined the game!")

				# Add player to local playerlist if not present
				if msg_client_id not in self.playerlist:
					position = game_event.get('position', [100, 100])
					self.playerlist[msg_client_id] = PlayerState(
						client_id=msg_client_id,
						position=position,
						health=DEFAULT_HEALTH,
						bombsleft=3,
						score=0
					)
					if self.args.debug:
						logger.debug(f"Added new player {msg_client_id} at position {position}")

				# If client is the server, re-broadcast to ensure all clients get it
				if not hasattr(self, 'client_id'):
					await self.broadcast_event(game_event)

			case 'player_update':
				# Update other player's position in playerlist
				if msg_client_id != self.client_id:
					position = game_event.get('position')
					if msg_client_id in self.playerlist:
						player = self.playerlist[msg_client_id]
						if isinstance(player, dict):
							# Direct update without complex interpolation
							# player['position'] = position
							# player['client_id'] = msg_client_id
							self.playerlist[msg_client_id] = PlayerState(client_id=msg_client_id, position=position, health=player.get('health', DEFAULT_HEALTH), bombsleft=player.get('bombsleft', 3), score=player.get('score', 0))
						else:
							# Handle PlayerState objects
							player.position = position
					else:
						logger.warning(f'unknownplayer {msg_client_id=} {self.playerlist=} {game_event=}')
						# Add new player with minimal required fields
						self.playerlist[msg_client_id] = PlayerState(client_id=msg_client_id, position=position, health=DEFAULT_HEALTH, bombsleft=3, score=0)
				await self.broadcast_event(game_event)
				await asyncio.sleep(1 / UPDATE_TICK)
			case 'playerquit':
				client_id = game_event.get('client_id')
				if client_id in self.playerlist:
					logger.info(f"Player {client_id} has disconnected")
					del self.playerlist[client_id]

				# self.playerlist[msg_client_id]['playerquit'] = True
				await self.event_queue.put(game_event)
			case 'acknewplayer':
				self._ready = True
				game_event['handled'] = True
				await self.broadcast_state({"event_type": "acknewplayer", "event": game_event})

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
			case 'drop_bomb':
				game_event['handledby'] = 'ugsbomb'
				try:
					if msg_client_id == self.client_id:
						bomb = Bomb(position=game_event.get('position'))
					else:
						bomb = Bomb(position=game_event.get('position'), bomb_size=(5,5))
					self.bombs.add(bomb)
				except AttributeError as e:
					logger.error(f'{e} unable to add bomb {game_event=} players_sprites: {self.players_sprites}')
				game_event['event_type'] = 'ackbombdrop'
				await self.broadcast_event(game_event)

			case 'ackbombdrop':
				if msg_client_id != self.client_id:
					bomb = Bomb(position=game_event.get('position'), bomb_size=(5,5))
				elif msg_client_id == self.client_id:
					bomb = Bomb(position=game_event.get('position'), bomb_size=(10,10))
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
				if msg_client_id == self.get_playerone().client_id:
					bullet_size = (10,10)
				else:
					bullet_size = (5,5)
				bullet = Bullet(position=bullet_position, direction=bullet_direction, screen_rect=self.get_playerone().rect, bullet_size=bullet_size, owner_id=msg_client_id)
				self.bullets.add(bullet)

			case 'player_hit':
				target_id = game_event.get('target_id')
				damage = game_event.get('damage', 10)
				if hasattr(self, 'client_id') and self.client_id:
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
				player = self.playerlist[target_id]
				if isinstance(player, dict):
					try:
						player['health'] = player.get('health') - damage
					except Exception as e:
						logger.error(f'Error updating health: {e} {type(e)} {player=}')
					logger.info(f'dictplayer_hit {target_id=} {damage=} player: {player["client_id"]} {player["health"]}')
					# Check if player is killed
					if player['health'] <= 0:
						# Create kill event
						kill_event = {
							"event_time": time.time(),
							"event_type": "player_killed",
							"client_id": msg_client_id,  # Killer
							"target_id": target_id,      # Victim
							"position": game_event.get('position'),
							"handled": False,
							"handledby": "dictplayer_hit",
							"eventid": gen_randid()
						}
						await self.broadcast_event(kill_event)
				else:
					# Handle PlayerState objects
					player.health -= damage
					if self.args.debug:
						logger.debug(f'PlayerStateplayer_hit {target_id=} {damage=} {player.client_id=} {player.health=} ')
					if player.health <= 0:
						# Create kill event
						kill_event = {
							"event_time": time.time(),
							"event_type": "player_killed",
							"client_id": msg_client_id,
							"target_id": target_id,
							"position": game_event.get('position'),
							"handled": False,
							"handledby": "PlayerStateplayer_hit",
							"eventid": gen_randid()
						}
						await self.broadcast_event(kill_event)
				# game_event['health'] = player['health']  # Include updated health in event
				# Broadcast the hit event to all clients
				# await self.broadcast_event(game_event)
				asyncio.create_task(self.event_queue.put(game_event))

			case 'player_killed':
				killer_id = msg_client_id
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
				# Reset target player (respawn)
				if target_id in self.playerlist:
					if isinstance(self.playerlist[target_id], dict):
						self.playerlist[target_id]['health'] = 123
						self.playerlist[target_id]['killed'] = True
					else:
						self.playerlist[target_id].health = 321
						self.playerlist[target_id].killed = True

				# Broadcast the kill event
				await self.broadcast_event(game_event)
			case _:
				# payload = {'event_type': 'error99', 'payload': ''}
				logger.warning(f'unknown game_event:{event_type} from game_event={game_event}')
				# await self.event_queue.put(payload)

	def to_json(self):
		"""Convert game state to JSON-serializable format"""
		playerlist = []
		for player in self.playerlist.values():
			if hasattr(player, 'to_dict'):
				playerlist.append(player.to_dict())
			else:
				playerlist.append(player)

		# Ensure modified_tiles keys are strings for JSON
		# modified_tiles = {}
		# for pos, gid in self.modified_tiles.items():
		# 	modified_tiles[str(pos)] = gid
		modified_tiles = {str(pos): gid for pos, gid in self.modified_tiles.items()}
		return {
			'event_type': 'playerlistupdate',
			'playerlist': playerlist,
			'connections': len(self.connections),
			'mapname': self.mapname,
			'modified_tiles': modified_tiles,  # Include map modifications
		}

	async def from_json(self, data):
		if data.get('event_type') == 'acknewplayer':
			await self.update_game_event(data)
		elif data.get('event_type') == 'send_game_state':
			for player_data in data.get('playerlist', []):
				client_id = player_data.get('client_id')
				if client_id != self.client_id:  # Don't update our own player
					if client_id in self.playerlist:
						# Update existing player
						player = self.playerlist[client_id]
						player.position = player_data.get('position')
						player.health = player_data.get('health')
						player.score = player_data.get('score')
					else:
						# Create new player
						self.playerlist[client_id] = PlayerState(**player_data)
		elif data.get('event_type') == 'map_info':
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
		elif data.get('event_type') == 'playerlist':
			try:
				for player_data in data.get('playerlist', []):
					client_id = player_data.get('client_id')
					if client_id != self.client_id:  # Don't update our own player
						if client_id in self.playerlist:
							# Update existing player
							player = self.playerlist[client_id]
							position = player_data.get('position')
							if position:
								if hasattr(player, 'position'):
									if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
										player.position.x, player.position.y = position[0], position[1]
									else:
										player.position = position
								else:
									player['position'] = position

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
									bombsleft=player_data.get('bombsleft', 3),
									score=player_data.get('score', 0)
								)
							except Exception as e:
								logger.error(f"Could not create PlayerState: {e}")
			except Exception as e:
				logger.error(f"Error updating player from json: {e}")
		elif data.get('event_type') == 'playerlistupdate':
			try:
				for player_data in data.get('playerlist', []):
					client_id = player_data.get('client_id')
					if client_id != self.client_id:  # Don't update our own player
						if client_id in self.playerlist:
							# Update existing player
							player = self.playerlist[client_id]
							position = player_data.get('position')
							if position:
								if hasattr(player, 'position'):
									if hasattr(player.position, 'x') and hasattr(player.position, 'y'):
										player.position.x, player.position.y = position[0], position[1]
									else:
										player.position = position
								else:
									player['position'] = position

								# Set up interpolation data
								if hasattr(player, 'target_position'):
									player.target_position = position
									player.position_updated = True
						else:
							# Create new player
							newplayer = PlayerState(
									client_id=client_id,
									position=player_data.get('position', (0, 0)),
									health=DEFAULT_HEALTH,
									bombsleft=player_data.get('bombsleft', 3),
									score=player_data.get('score', 0)
								)
							logger.info(f'newplayer {client_id=} pos: {newplayer.position}')
							try:
								self.playerlist[client_id] = newplayer
							except Exception as e:
								logger.error(f"Could not create PlayerState: {e}")
			except Exception as e:
				logger.error(f"Error updating player from json: {e}")
		else:
			logger.warning(f"Unknown event_type: {data.get('event_type')} data: {data}")

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

				if bullet.rect.colliderect(player.rect):
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
