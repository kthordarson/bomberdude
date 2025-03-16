from dataclasses import dataclass, field
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
import orjson as json
import pygame
import time
from utils import gen_randid
from constants import PLAYER_MOVEMENT_SPEED
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
	scale: float = 0.7
	client_id: str = None
	position: Vec2d = field(default_factory=lambda: Vec2d(99, 99))
	# name: str = 'xnonex'

	def __post_init__(self):
		super().__init__()
		self.image = pygame.image.load(self.texture)
		self.rect = self.image.get_rect()
		self.change_x = 0
		self.change_y = 0
		self.bombsleft = 3
		self.health = 101
		self.killed = False
		self.timeout = False
		self.score = 0
		self.candrop = True
		self.lastdrop = 0
		self.keyspressed = KeysPressed('gamestate')
		# self.bullets = pygame.sprite.Group()

	def __hash__(self):
		return hash((self.client_id))

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
				'bombsleft': self.bombsleft,
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

	def drop_bomb(self):
		event = {"event_time": 0,
				"event_type": "drop_bomb",
				"client_id": self.client_id,
				"position": (self.rect.x, self.rect.y),
				"ba": 1,
				"timer": 1,
				"handled": False,
				"handledby": self.client_id,
				"eventid": gen_randid(),}
		return event

	def draw(self, screen):
		screen.blit(self.image, self.rect.topleft)

	def respawn(self):
		self.killed = False
		self.health = 100
		self.position = Vec2d(101, 101)
		self.bombsleft = 3
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
			self.kill(dmgfrom)
			return 5
		return 1

	def kill(self, dmgfrom):
		logger.info(f'{self} killed by {dmgfrom}')
		self.killed = True
		self.image = pygame.image.load('data/netplayerdead.png')
		return 11
