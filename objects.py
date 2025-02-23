from dataclasses import dataclass, field
import asyncio
from loguru import logger
from pygame.math import Vector2 as Vec2d
from pygame.sprite import Sprite
# from pymunk import Vec2d
import json
import math
import pygame
import random
import time
from utils import gen_randid
from constants import PLAYER_MOVEMENT_SPEED, PARTICLE_COUNT, PARTICLE_RADIUS, PARTICLE_SPEED_RANGE, PARTICLE_MIN_SPEED, PARTICLE_FADE_RATE, PARTICLE_GRAVITY, FLAME_SPEED, FLAME_TIME, FLAME_RATE, BOMBTICKER, BULLET_TIMER, FLAMEX, FLAMEY

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

		# return json.dumps({
		# 	"name": self.name,
		# 	"keys": {arcade.key.symbol_string(k): v for k, v in self.keys.items()}
		# })

class oldKeysPressed:
	def __init__(self, name):
		self.name = name
		self.keys = {k: False for k in MOVE_MAP}

	def __repr__(self):
		return f'KeyPressed ({self.name})'

@dataclass(eq=True)
class Bomberplayer(Sprite):
	texture: str
	scale: float = 0.7
	client_id: str = None
	position: Vec2d = field(default_factory=lambda: Vec2d(99, 99))
	name: str = 'xnonex'
	# eventq: asyncio.Queue = None

	def __post_init__(self):
		super().__init__()
		self.image = pygame.image.load(self.texture)
		self.rect = self.image.get_rect()
		self.change_x = 0
		self.change_y = 0
		self.bombsleft = 3
		self.health = 100
		self.killed = False
		self.timeout = False
		self.score = 0
		self.angle = 0
		self.candrop = True
		self.lastdrop = 0
		self.keys_pressed = KeysPressed('gamestate')
		# self.bullets = pygame.sprite.Group()

	def __hash__(self):
		return hash((self.client_id, self.name))

	def update(self, collidable_tiles):
		# Calculate new position
		new_x = self.position.x + self.change_x
		new_y = self.position.y + self.change_y

		# Check for collisions
		new_rect = self.rect.copy()
		new_rect.topleft = (new_x, new_y)
		collision = any(new_rect.colliderect(tile) for tile in collidable_tiles)
		if not collision:
			self.position.update(new_x, new_y)
			self.rect.topleft = self.position
		# self.bullets.update()

	def shoot(self, target_pos):
		# Calculate direction from player's position to target
		start_pos = Vec2d(self.rect.center)
		target = Vec2d(target_pos)
		direction = target - start_pos

		# direction = Vec2d(target_pos) - self.position
		if direction.length() > 0:
			direction = direction.normalize() * 10
		# bullet = Bullet(self.position, direction, pygame.display.get_surface().get_rect())
		bullet = Bullet(self.position, direction, pygame.display.get_surface().get_rect(), bounce_count=5)  # Increase bounce count
		return bullet  # self.bullets.add(bullet)

	def draw(self, screen):
		screen.blit(self.image, self.rect.topleft)

	# async def dropbomb(self, bombtype) -> None:
	# 	if self.bombsleft <= 0:
	# 		logger.warning(f'p1: {self} has no bombs left {self.lastdrop}...')
	# 		return None
	# 	else:
	# 		bombpos = Vec2d(self.rect.centerx, self.rect.centery)
	# 		bombevent = {'event_time': 0, 'event_type': 'bombdrop', 'bombtype': bombtype, 'bomber': self.client_id, 'pos': bombpos, 'timer': 1, 'handled': False, 'handledby': self.client_id, 'ld': self.lastdrop, 'eventid': gen_randid()}
	# 		await self.eventq.put(bombevent)
	# 		self.lastdrop = bombevent['eventid']
	# 		logger.debug(f'{self} dropped bomb {bombevent["eventid"]}')
	# 		# return bombevent

	def rotate_around_point(self, point, degrees):
		self.angle += degrees
		self.position = pygame.math.Vector2(self.rect.center).rotate_around(point, degrees)

	def respawn(self):
		self.killed = False
		self.health = 100
		self.position = Vec2d(101, 101)
		self.bombsleft = 3
		self.score = 0
		self.timeout = False
		self.image = pygame.image.load('data/playerone.png')
		logger.info(f'{self} respawned')

	def set_texture(self, texture):
		self.image = pygame.image.load(texture)

	def addscore(self, score):
		self.score += score
		logger.info(f'{self} score:{self.score}')

	def get_playerstate(self):
		playerstate = {
			'client_id': self.client_id,
			'position': self.position,
			'health': self.health,
			'msgsource': 'get_playerstate',
			'msg_dt': time.time(),
			'timeout': self.timeout,
			'killed': self.killed,
			'score': self.score,
			'bombsleft': self.bombsleft,
		}
		return json.dumps({self.client_id: playerstate})

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

	def set_pos(self, newpos):
		self.rect.topleft = newpos
		self.update()

class Bomb(Sprite):
	def __init__(self, image=None, scale=1.0, bomber=None, timer=1000, eventq=None):
		super().__init__()
		self.image = pygame.image.load(image)
		self.rect = self.image.get_rect()
		self.eventq = eventq
		self.bomber = bomber
		self.timer = timer

	def update(self, scene, eventq=None):
		if self.timer <= 0:
			for k in range(PARTICLE_COUNT):
				p = Particle()
				p.rect.center = self.rect.center
				scene.add(p)
			for k in ['left', 'right', 'up', 'down']:
				f = Flame(flamespeed=FLAME_SPEED, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.rect.center = self.rect.center
				scene.add(f)
			event = {'event_time': 0, 'event_type': 'bombxplode', 'bomber': self.bomber, 'eventid': gen_randid()}
			self.eventq.put(event)
			self.kill()
		else:
			self.timer -= BOMBTICKER

class BiggerBomb(Sprite):
	def __init__(self, image=None, scale=1.0, bomber=None, timer=1000, eventq=None):
		super().__init__()
		self.image = pygame.image.load(image)
		self.rect = self.image.get_rect()
		self.eventq = eventq
		self.bomber = bomber
		self.timer = timer

	def update(self, scene):
		if self.timer <= 0:
			for k in range(PARTICLE_COUNT * 2):
				p = Particle(xtra=3)
				p.rect.center = self.rect.center
				scene.add(p)
			for k in ['left', 'right', 'up', 'down']:
				f = Flame(flamespeed=FLAME_SPEED * 2, timer=FLAME_TIME, direction=k, bomber=self.bomber)
				f.rect.center = self.rect.center
				scene.add(f)
			event = {'event_time': 0, 'event_type': 'bombxplode', 'bomber': self.bomber, 'eventid': gen_randid()}
			self.eventq.put(event)
			self.kill()
		else:
			self.timer -= BOMBTICKER

class Bullet(pygame.sprite.Sprite):
	def __init__(self, position, velocity, screen_rect, bounce_count=3):
		super().__init__()
		self.image = pygame.Surface((10, 10))
		self.image.fill((255, 0, 0))
		self.position = Vec2d(position)
		self.rect = self.image.get_rect(center=self.position)
		self.velocity = Vec2d(velocity)
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count

	def update(self, collidable_tiles):
		if self.bounce_count <= 0:
			self.kill()
			return

		# Update position based on velocity
		new_x = self.position.x + self.velocity.x
		new_y = self.position.y + self.velocity.y

		# Store original position for collision resolution
		original_x = self.position.x
		original_y = self.position.y

		# Move and check collisions
		self.position.x = new_x
		self.position.y = new_y
		self.rect.center = (int(self.position.x), int(self.position.y))

		# Check collisions only with collidable tiles
		hit_tile = None
		for tile in collidable_tiles:
			if hasattr(tile, 'collidable') and tile.collidable and self.rect.colliderect(tile):
				hit_tile = tile
				break

		if hit_tile:
			# Determine which side was hit by checking the previous position
			left_collision = original_x < hit_tile.left and self.rect.right > hit_tile.left
			right_collision = original_x > hit_tile.right and self.rect.left < hit_tile.right
			top_collision = original_y < hit_tile.top and self.rect.bottom > hit_tile.top
			bottom_collision = original_y > hit_tile.bottom and self.rect.top < hit_tile.bottom

			if left_collision or right_collision:
				self.velocity.x *= -1
			if top_collision or bottom_collision:
				self.velocity.y *= -1

			# Reset position and update with new velocity
			self.position.x = original_x
			self.position.y = original_y
			self.rect.center = (int(self.position.x), int(self.position.y))
			self.bounce_count -= 1

		# Handle screen boundaries
		if self.rect.left <= self.screen_rect.left:
			self.velocity.x = abs(self.velocity.x)
			self.bounce_count -= 1
		elif self.rect.right >= self.screen_rect.right:
			self.velocity.x = -abs(self.velocity.x)
			self.bounce_count -= 1
		if self.rect.top <= self.screen_rect.top:
			self.velocity.y = abs(self.velocity.y)
			self.bounce_count -= 1
		elif self.rect.bottom >= self.screen_rect.bottom:
			self.velocity.y = -abs(self.velocity.y)
			self.bounce_count -= 1


class Bxxxullet(pygame.sprite.Sprite):
	def __init__(self, position, velocity, screen_rect, bounce_count=3):
		super().__init__()
		self.image = pygame.Surface((10, 10))
		self.image.fill((255, 0, 0))
		self.position = Vec2d(position)
		self.rect = self.image.get_rect(center=self.position)
		self.velocity = Vec2d(velocity)
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count

	def update(self, collidable_tiles):
		if self.bounce_count <= 0:
			self.kill()
			return

		# Update position based on velocity
		new_x = self.position.x + self.velocity.x
		new_y = self.position.y + self.velocity.y

		# Move horizontally first and check for collisions
		self.position.x = new_x
		self.rect.centerx = int(self.position.x)
		self.collided = False

		# Only check collisions with actually collidable tiles
		for tile in [t for t in collidable_tiles if hasattr(t, 'collidable') and t.collidable]:
			if self.rect.colliderect(tile):
				self.collided = True
				if self.velocity.x > 0:  # Moving right
					self.rect.right = tile.left
					self.velocity.x *= -1
				elif self.velocity.x < 0:  # Moving left
					self.rect.left = tile.right
					self.velocity.x *= -1
				self.position.x = self.rect.centerx
				break

		# Move vertically and check for collisions
		self.position.y = new_y
		self.rect.centery = int(self.position.y)

		# Only check collisions with actually collidable tiles
		for tile in [t for t in collidable_tiles if hasattr(t, 'collidable') and t.collidable]:
			if self.rect.colliderect(tile):
				self.collided = True
				if self.velocity.y > 0:  # Moving down
					self.rect.bottom = tile.top
					self.velocity.y *= -1
				elif self.velocity.y < 0:  # Moving up
					self.rect.top = tile.bottom
					self.velocity.y *= -1
				self.position.y = self.rect.centery
				break

		# Only decrement bounce count if we actually collided with something
		if self.collided:
			self.bounce_count -= 1

		# Keep bullet within screen bounds
		if self.rect.left <= self.screen_rect.left:
			self.rect.left = self.screen_rect.left
			self.velocity.x *= -1
			self.bounce_count -= 1
		elif self.rect.right >= self.screen_rect.right:
			self.rect.right = self.screen_rect.right
			self.velocity.x *= -1
			self.bounce_count -= 1

		if self.rect.top <= self.screen_rect.top:
			self.rect.top = self.screen_rect.top
			self.velocity.y *= -1
			self.bounce_count -= 1
		elif self.rect.bottom >= self.screen_rect.bottom:
			self.rect.bottom = self.screen_rect.bottom
			self.velocity.y *= -1
			self.bounce_count -= 1

		# Update position from rect
		self.position = Vec2d(self.rect.center)

class xBullet(pygame.sprite.Sprite):
	def __init__(self, position, velocity, screen_rect, bounce_count=3):
		super().__init__()
		self.image = pygame.Surface((10, 10))
		self.image.fill((255, 0, 0))
		self.position = Vec2d(position)
		self.rect = self.image.get_rect(center=self.position)
		self.velocity = Vec2d(velocity)
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count

	def update(self, collidable_tiles):
		if self.bounce_count <= 0:
			self.kill()
			return

		# Update position based on velocity
		new_x = self.position.x + self.velocity.x
		new_y = self.position.y + self.velocity.y

		# Move horizontally first and check for collisions
		self.position.x = new_x
		self.rect.centerx = int(self.position.x)
		self.collided = False

		for tile in collidable_tiles:
			if self.rect.colliderect(tile):
				self.collided = True
				if self.velocity.x > 0:  # Moving right
					self.rect.right = tile.left
					self.velocity.x *= -1
				elif self.velocity.x < 0:  # Moving left
					self.rect.left = tile.right
					self.velocity.x *= -1
				self.position.x = self.rect.centerx
				break

		# Move vertically and check for collisions
		self.position.y = new_y
		self.rect.centery = int(self.position.y)

		for tile in collidable_tiles:
			if self.rect.colliderect(tile):
				self.collided = True
				if self.velocity.y > 0:  # Moving down
					self.rect.bottom = tile.top
					self.velocity.y *= -1
				elif self.velocity.y < 0:  # Moving up
					self.rect.top = tile.bottom
					self.velocity.y *= -1
				self.position.y = self.rect.centery
				break

		# Only decrement bounce count if we actually collided with something
		if self.collided:
			self.bounce_count -= 1

		# Keep bullet within screen bounds
		if self.rect.left <= self.screen_rect.left:
			self.rect.left = self.screen_rect.left
			self.velocity.x *= -1
			self.bounce_count -= 1
		elif self.rect.right >= self.screen_rect.right:
			self.rect.right = self.screen_rect.right
			self.velocity.x *= -1
			self.bounce_count -= 1

		if self.rect.top <= self.screen_rect.top:
			self.rect.top = self.screen_rect.top
			self.velocity.y *= -1
			self.bounce_count -= 1
		elif self.rect.bottom >= self.screen_rect.bottom:
			self.rect.bottom = self.screen_rect.bottom
			self.velocity.y *= -1
			self.bounce_count -= 1

		# Update position from rect
		self.position = Vec2d(self.rect.center)

class Particle(Sprite):
	def __init__(self, my_list=None, xtra=0):
		super().__init__()
		color = (123,123,123)  # random.choice(PARTICLE_COLORS)
		self.image = pygame.Surface((PARTICLE_RADIUS * 2, PARTICLE_RADIUS * 2), pygame.SRCALPHA)
		pygame.draw.circle(self.image, color, (PARTICLE_RADIUS, PARTICLE_RADIUS), PARTICLE_RADIUS)
		self.rect = self.image.get_rect()
		speed = random.random() * PARTICLE_SPEED_RANGE + PARTICLE_MIN_SPEED
		direction = random.randrange(360)
		self.change_x = math.sin(math.radians(direction)) * speed + xtra
		self.change_y = math.cos(math.radians(direction)) * speed + xtra
		self.my_alpha = 255
		self.my_list = my_list

	def update(self):
		if self.my_alpha <= 0:
			self.kill()
		else:
			self.my_alpha -= PARTICLE_FADE_RATE
			self.image.set_alpha(self.my_alpha)
			self.rect.x += self.change_x
			self.rect.y += self.change_y
			self.change_y -= PARTICLE_GRAVITY

class Flame(Sprite):
	def __init__(self, flamespeed=10, timer=3000, direction='', bomber=None):
		super().__init__()
		self.image = pygame.Surface((FLAMEX, FLAMEY))
		self.image.fill((255, 165, 0))  # ORANGE equivalent
		self.rect = self.image.get_rect()
		self.bomber = bomber
		self.speed = flamespeed
		self.timer = timer
		self.direction = direction
		if self.direction == 'left':
			self.change_y = 0
			self.change_x = -self.speed
		if self.direction == 'right':
			self.change_y = 0
			self.change_x = self.speed
		if self.direction == 'up':
			self.change_y = -self.speed
			self.change_x = 0
		if self.direction == 'down':
			self.change_y = self.speed
			self.change_x = 0

	def update(self):
		if self.timer <= 0:
			self.kill()
		else:
			self.timer -= FLAME_RATE
			self.rect.x += self.change_x
			self.rect.y += self.change_y

class Upgrade(Sprite):
	def __init__(self, upgradetype, image, position, scale, timer=1000):
		super().__init__()
		self.image = pygame.image.load(image)
		self.rect = self.image.get_rect()
		self.upgradetype = upgradetype
		self.position = position
		self.rect.topleft = self.position
		self.timer = timer

	def update(self):
		if self.timer <= 0:
			self.kill()
		else:
			self.timer -= 1
