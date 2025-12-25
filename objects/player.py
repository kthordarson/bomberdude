import asyncio
from dataclasses import dataclass, field
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import json
import pygame
import time
from utils import gen_randid, generate_name, get_cached_image
from constants import PLAYER_MOVEMENT_SPEED, PLAYER_SCALING, BLOCK
from .bullets import Bullet

MOVE_MAP = {
	pygame.K_UP: (0, -PLAYER_MOVEMENT_SPEED),
	pygame.K_w: (0, -PLAYER_MOVEMENT_SPEED),
	119: (0, -PLAYER_MOVEMENT_SPEED),

	pygame.K_DOWN: (0, PLAYER_MOVEMENT_SPEED),
	pygame.K_s: (0, PLAYER_MOVEMENT_SPEED),
	115: (0, PLAYER_MOVEMENT_SPEED),

	pygame.K_LEFT: (-PLAYER_MOVEMENT_SPEED, 0),
	pygame.K_a: (-PLAYER_MOVEMENT_SPEED, 0),
	97: (-PLAYER_MOVEMENT_SPEED, 0),

	pygame.K_RIGHT: (PLAYER_MOVEMENT_SPEED, 0),
	pygame.K_d: (PLAYER_MOVEMENT_SPEED, 0),
	100: (PLAYER_MOVEMENT_SPEED, 0),
}

KEY_NAME_MAP = {v: k for k, v in pygame.key.__dict__.items() if isinstance(v, int)}

class KeysPressed:
	def __init__(self, name):
		self.name = name
		self.keys = {k: False for k in MOVE_MAP}

	def __repr__(self):
		return f'KeyPressed ({self.name})'

	def to_json(self):
		return json.dumps({"name": self.name, "keys": {KEY_NAME_MAP.get(k, str(k)): v for k, v in self.keys.items()}})

@dataclass(eq=True)
class Bomberplayer(Sprite):
	texture: str
	scale: float = PLAYER_SCALING
	client_id: str = 'Bomberplayer'
	client_name: str = 'Noname'
	position: Vec2d = field(default_factory=lambda: Vec2d(99, 99))
	health: int = 100
	killed: bool = False
	# name: str = 'xnonex'

	def __post_init__(self):
		super().__init__()
		self._alive_texture_path = self.texture
		# await self._set_texture(self.texture)
		self.change_x = 0
		self.change_y = 0
		self.bombs_left = 3
		self.health = 101
		self.killed = False
		self.timeout = False
		self.score = 0
		self.candrop = True
		self.lastdrop = 0
		self.keyspressed = KeysPressed('gamestate')
		self.client_name = generate_name()

	async def _set_texture(self, texture_path: str) -> None:
		# Cache disk loads globally; convert/scale only when a display surface exists.
		self.original_image = await get_cached_image(texture_path, scale=1.0, convert=True)
		self.image = await get_cached_image(texture_path, scale=float(self.scale), convert=True)
		self.rect = self.image.get_rect()
		self.rect.topleft = (int(self.position.x), int(self.position.y))

	async def set_dead(self, dead: bool) -> None:
		"""Swap sprite image based on health/killed state."""
		if dead:
			self.killed = True
			await self._set_texture('data/netplayerdead.png')
		else:
			self.killed = False
			alive_path = getattr(self, '_alive_texture_path', None) or self.texture
			await self._set_texture(alive_path)

	def __hash__(self):
		return hash((self.client_id))

	@property
	def bombs_left(self):
		return self._bombsleft

	@bombs_left.setter
	def bombs_left(self, value):
		# Never exceed 3 bombs
		self._bombsleft = min(3, max(0, value))

	def to_dict(self):
		"""Convert player object to dictionary"""
		try:
			return {
				'client_id': self.client_id,
				'position': [float(self.position.x), float(self.position.y)],
				'score': self.score,
				'health': self.health,
				'timeout': self.timeout,
				'msg_dt': time.time(),
				'killed': self.killed,
				'bombs_left': self.bombs_left,
			}
		except Exception as e:
			logger.error(f"Error converting player to dict: {e}")
			return {}

	def update(self, game_state):
		if not self.rect:
			return
		# Store previous position
		prev_x, prev_y = self.position.x, self.position.y
		prev_rect = self.rect.copy()

		# Apply movement
		self.position.x += self.change_x
		self.position.y += self.change_y

		# Update rect with integer positions for pixel-perfect collision
		self.rect.x = int(self.position.x)
		self.rect.y = int(self.position.y)

		# Check collisions (only nearby tiles when possible)
		# Use a swept rect so fast motion doesn't skip thin obstacles.
		query_rect = self.rect.union(prev_rect)
		# If a GameState is passed, use its spatial index.
		for tile in game_state.iter_collidable_in_rect(query_rect, pad_pixels=BLOCK):
			if self.rect.colliderect(tile.rect):
				self.position.x, self.position.y = prev_x, prev_y
				self.rect.x = int(prev_x)
				self.rect.y = int(prev_y)
				return

	def addscore(self, score):
		self.score += score
		logger.info(f'{self} score:{self.score}')

	async def take_damage(self, damage, attacker):
		self.health -= damage
		logger.info(f'{self} health:{self.health} {damage=} {attacker=}')
		if self.health <= 0:
			self.killed = True
			await self.player_kill(attacker)

	async def player_kill(self, attacker):
		logger.info(f'{self} killed by {attacker}')
		await self.set_dead(True)

	async def drop_bomb(self):
		"""Try to drop a bomb and return event"""
		current_time = time.time()
		cooldown_period = 0.5  # Half-second cooldown between bomb drops
		# Player has bombs and can drop

		# Calculate tile-centered position (snap to grid)
		# Use the player's rect center to choose the tile they are standing on.
		self.rect.x = int(self.position.x)
		self.rect.y = int(self.position.y)
		cx, cy = self.rect.center
		tile_size = BLOCK * self.scale
		tile_x = (int(cx) // tile_size) * tile_size + tile_size // 2
		tile_y = (int(cy) // tile_size) * tile_size + tile_size // 2
		bomb_pos = (tile_x, tile_y)

		# Check cooldown first
		if (current_time - self.lastdrop) < cooldown_period:
			return {
				"event_time": current_time,
				"event_type": "dropcooldown",
				"client_id": self.client_id,
				"position": self.rect.center,
				"handled": False,
				"handledby": self.client_id,
				"event_id": gen_randid(),
			}

		elif self.killed:
			return {
				"event_time": current_time,
				"event_type": "nodropbombkill",
				"client_id": self.client_id,
				"position": self.rect.center,
				"handled": False,
				"handledby": self.client_id,
				"event_id": gen_randid(),
			}

		# Check if player has any bombs left
		elif self.bombs_left <= 0:
			return {
				"event_time": current_time,
				"event_type": "nodropbomb",
				"client_id": self.client_id,
				"position": self.rect.center,
				"handled": False,
				"handledby": self.client_id,
				"event_id": gen_randid(),
			}
		else:
			if bomb_pos == (16,16):
				logger.warning(f"{self} Attempted to drop bomb at invalid position (16,16), ignoring. cx={cx} cy={cy} rect={self.rect}")
			else:
				self.lastdrop = current_time  # Set last drop time to prevent spam
				# Consume one bomb immediately (restored when the bomb explodes)
				self.bombs_left = self.bombs_left - 1
				return {
					"event_time": current_time,
					"event_type": "player_drop_bomb",
					"client_id": self.client_id,
					"position": bomb_pos,  # Snapped to tile center
					"bombs_left": self.bombs_left,
					"handled": False,
					"handledby": self.client_id,
					"event_id": gen_randid(),
				}
