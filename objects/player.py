from dataclasses import dataclass, field
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import orjson as json
import pygame
import time
from utils import gen_randid
from constants import PLAYER_MOVEMENT_SPEED, PLAYER_SCALING, BLOCK
from .bullets import Bullet

MOVE_MAP = {
	pygame.K_UP: (0, PLAYER_MOVEMENT_SPEED),
	pygame.K_w: (0, PLAYER_MOVEMENT_SPEED),
	119: (0, PLAYER_MOVEMENT_SPEED),

	pygame.K_DOWN: (0, -PLAYER_MOVEMENT_SPEED),
	pygame.K_s: (0, -PLAYER_MOVEMENT_SPEED),
	115: (0, -PLAYER_MOVEMENT_SPEED),

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
	position: Vec2d = field(default_factory=lambda: Vec2d(99, 99))
	# name: str = 'xnonex'

	def __post_init__(self):
		super().__init__()
		loaded_image = pygame.image.load(self.texture)
		if self.client_id == 'theserver':
			self.original_image = loaded_image
			self.image = loaded_image
		else:
			self.original_image = loaded_image.convert_alpha() if loaded_image.get_alpha() else loaded_image.convert()
			self.image = pygame.transform.scale(self.original_image, (int(self.original_image.get_width() * self.scale), int(self.original_image.get_height() * self.scale)))
		self.rect = self.image.get_rect()
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

	def update(self, collidable_tiles):
		# Store previous position
		prev_x, prev_y = self.position.x, self.position.y

		# Apply movement
		self.position.x += self.change_x
		self.position.y += self.change_y

		# Update rect with integer positions for pixel-perfect collision
		self.rect.x = int(self.position.x)
		self.rect.y = int(self.position.y)

		# Check collisions
		for tile in collidable_tiles:
			if self.rect.colliderect(tile.rect):
				self.position.x, self.position.y = prev_x, prev_y
				self.rect.x = int(prev_x)
				self.rect.y = int(prev_y)
				return

	def shoot(self, direction):
		# Calculate direction from player's position to target
		bullet_pos = Vec2d(self.rect.center)
		bullet = Bullet(position=bullet_pos,direction=direction, screen_rect=self.rect, owner_id=self.client_id)
		return bullet  # self.bullets.add(bullet)

	def draw(self, screen):
		screen.blit(self.image, self.rect.topleft)

	def respawn(self):
		self.killed = False
		self.health = 100
		self.position = Vec2d(101, 101)
		self.bombs_left = 3
		self.score = 0
		self.timeout = False
		self.image = pygame.image.load('data/playerone.png')
		logger.info(f'{self} respawned')

	def addscore(self, score):
		self.score += score
		logger.info(f'{self} score:{self.score}')

	def take_damage(self, damage, dmgfrom):
		self.health -= damage
		logger.info(f'{self} health:{self.health} {damage=} {dmgfrom=}')
		if self.health <= 0:
			self.killed = True
			self.player_kill(dmgfrom)

	def player_kill(self, dmgfrom):
		logger.info(f'{self} killed by {dmgfrom}')
		self.killed = True
		self.image = pygame.image.load('data/netplayerdead.png')

	def drop_bomb(self):
		"""Try to drop a bomb and return event"""
		current_time = time.time()
		cooldown_period = 0.5  # Half-second cooldown between bomb drops

		# Check cooldown first
		if (current_time - self.lastdrop) < cooldown_period:
			return {
				"event_time": current_time,
				"event_type": "dropcooldown",
				"client_id": self.client_id,
				"position": self.rect.center,
				"handled": False,
				"handledby": self.client_id,
				"eventid": gen_randid(),
			}

		if self.killed:
			return {
				"event_time": current_time,
				"event_type": "nodropbombkill",
				"client_id": self.client_id,
				"position": self.rect.center,
				"handled": False,
				"handledby": self.client_id,
				"eventid": gen_randid(),
			}

		# Check if player has any bombs left
		if self.bombs_left <= 0:
			return {
				"event_time": current_time,
				"event_type": "nodropbomb",
				"client_id": self.client_id,
				"position": self.rect.center,
				"handled": False,
				"handledby": self.client_id,
				"eventid": gen_randid(),
			}

		# Player has bombs and can drop
		self.lastdrop = current_time  # Set last drop time to prevent spam
		# Consume one bomb immediately (restored when the bomb explodes)
		self.bombs_left = self.bombs_left - 1

		# Calculate tile-centered position (snap to grid)
		tile_size = BLOCK
		tile_x = int(self.position.x / tile_size) * tile_size + tile_size // 2
		tile_y = int(self.position.y / tile_size) * tile_size + tile_size // 2

		return {
			"event_time": current_time,
			"event_type": "player_drop_bomb",
			"client_id": self.client_id,
			"position": (tile_x, tile_y),  # Snapped to tile center
			"bombs_left": self.bombs_left,
			"handled": False,
			"handledby": self.client_id,
			"eventid": gen_randid(),
		}
