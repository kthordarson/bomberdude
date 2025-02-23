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
		direction = Vec2d(target_pos) - self.position
		direction = direction.normalize() * 10
		# bullet = Bullet(self.position, direction, pygame.display.get_surface().get_rect())
		bullet = Bullet(self.position, direction, pygame.display.get_surface().get_rect(), bounce_count=115)  # Increase bounce count
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
	def __init__(self, position, velocity, screen_rect, bounce_count=113):
		super().__init__()
		self.image = pygame.Surface((10, 10))
		self.image.fill((255, 0, 0))
		self.rect = self.image.get_rect(center=position)
		self.velocity = Vec2d(velocity)
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count
		self.position = position

	def update(self, collidable_tiles):
		# self.rect.x += self.velocity.x
		# self.rect.y += self.velocity.y

		new_x = self.position.x + self.velocity.x
		new_y = self.position.y + self.velocity.y

		# Check for collisions
		new_rect = self.rect.copy()
		new_rect.topleft = (new_x, new_y)
		collision = any(new_rect.colliderect(tile) for tile in collidable_tiles)
		if not collision:
			self.position.update(new_x, new_y)
			self.rect.topleft = self.position
		else:
			# Check for collisions with screen boundaries and bounce
			if self.rect.left <= self.screen_rect.left or self.rect.right >= self.screen_rect.right:
				self.velocity.x *= -1
				self.bounce_count -= 1
			if self.rect.top <= self.screen_rect.top or self.rect.bottom >= self.screen_rect.bottom:
				self.velocity.y *= -1
				self.bounce_count -= 1

		# Destroy the bullet if it has bounced too many times
		if self.bounce_count <= 0:
			self.kill()

class xoldBullet(pygame.sprite.Sprite):
	def __init__(self, position, velocity, screen_rect, bounce_count=3):
		super().__init__()
		self.image = pygame.image.load('data/bullet0.png').convert_alpha()
		self.rect = self.image.get_rect(center=position)
		# self.image = pygame.Surface((10, 10))
		# self.image.fill((255, 0, 0))
		# self.rect = self.image.get_rect(center=position)
		self.velocity = Vec2d(velocity)
		self.screen_rect = screen_rect
		self.bounce_count = bounce_count

	def update(self):
		self.rect.move_ip(self.velocity)
		self.rect.x += self.velocity.x
		self.rect.y += self.velocity.y

		# Check for collisions with screen boundaries and bounce
		if self.rect.left <= self.screen_rect.left or self.rect.right >= self.screen_rect.right:
			self.velocity.x *= -1
			self.bounce_count -= 1
		if self.rect.top <= self.screen_rect.top or self.rect.bottom >= self.screen_rect.bottom:
			self.velocity.y *= -1
			self.bounce_count -= 1

		# Destroy the bullet if it has bounced too many times
		if self.bounce_count <= 0:
			self.kill()

class oldBullet(Sprite):
	def __init__(self, texture, scale=1, shooter=None, timer=1000):
		super().__init__()
		self.image = pygame.image.load(texture)
		self.rect = self.image.get_rect()
		self.shooter = shooter
		self.timer = timer
		self.angle = 90
		self.do_rotate = False
		self.do_shrink = False
		self.can_kill = True
		self.bullet_id = gen_randid()
		self.hit_count = 0
		self.damage = 1

	def rotate_around_point(self, point, degrees):
		self.angle += degrees
		self.position = pygame.math.Vector2(self.rect.center).rotate_around(point, degrees)

	def hit(self, oldpos, other):
		if self.hit_count <= 1:
			if self.rect.left <= other.rect.left + self.change_x or self.rect.right <= other.rect.right + self.change_x:
				self.change_x *= -1
			if self.rect.top <= other.rect.top + self.change_y or self.rect.bottom <= other.rect.bottom + self.change_y:
				self.change_y *= -1
			if self.hit_count > 1:
				logger.warning(f'{self} hit {other} {self.hit_count=}')
			self.hit_count += 1
			self.can_kill = False
			self.do_shrink = True
		else:
			self.kill()

	def update(self):
		self.timer -= BULLET_TIMER
		if self.do_shrink:
			self.scale -= 0.02
			if self.scale <= 0.1:
				self.kill()
		self.rect.x += self.change_x
		self.rect.y += self.change_y
		if self.timer <= 0:
			self.kill()

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
