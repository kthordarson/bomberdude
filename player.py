import pygame as pg
# from pygame.locals import *
# from pygame.colordict import THECOLORS as colordict
from globals import BLOCKSIZE, PLAYERSIZE

# from blocks import Block, Powerup_Block
from bombs import BlockBomb
class Player(pg.sprite.Sprite):
	def __init__(self, pos, player_id, screen):
		super().__init__()
		self.screen = screen
		self.pos = pos # pg.math.Vector2(pos)
		self.vel = pg.math.Vector2(0,0)
		self.image = pg.Surface((PLAYERSIZE,PLAYERSIZE)) # , pg.SRCALPHA, 32)
		self.color = pg.Color('blue')
		pg.draw.rect(self.image, self.color, [self.pos.x, self.pos.y, PLAYERSIZE,PLAYERSIZE])
		self.rect = self.image.get_rect()
		self.image.fill(self.color, self.rect)
		self.rect.centerx = self.pos.x
		self.rect.centery = self.pos.y
		self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
		self.max_bombs = 3
		self.bombs_left = self.max_bombs
		self.bomb_power = 1
		self.speed = 3
		self.player_id = player_id
		self.health = 100
		self.dead = False
		self.clock = pg.time.Clock()
		self.score = 0
		self.font = pg.font.SysFont('calibri', 10, True)

	def drop_bomb(self, game_data):
		# get grid pos of player
		x = self.gridpos[0]
		y = self.gridpos[1]
		if self.bombs_left > 0: #  and game_data.game_map[x][y] == 0:  # only place bombs if we have bombs... and on free spot...
			game_data.game_map[x][y] = self.player_id
			# create bomb at gridpos xy, multiply by BLOCKSIZE for screen coordinates
			bomb = BlockBomb(pos=(self.rect.centerx, self.rect.centery), bomber_id=self.player_id, block_color=pg.Color('yellow'), screen=self.screen, bomb_power=self.bomb_power, gridpos=self.gridpos)
			# bomb = BlockBomb(x=x, y=y, bomber_id=self.player_id, block_color=pg.Color('yellow'), screen=self.screen, bomb_power=self.bomb_power)
			game_data.bombs.add(bomb)
			self.bombs_left -= 1
		else:
			print(f'cannot drop bomb on gridpos: {x} {y} bl:{self.bombs_left} griddata: {game_data.game_map[x][y]}')
		return game_data

	def take_damage(self, amount=25):
		self.health -= amount
		if self.health <= 0:
			self.dead = True

	def draw(self):
		pg.draw.rect(self.screen, self.color, [self.pos.x, self.pos.y, PLAYERSIZE,PLAYERSIZE])

	def update(self, game_data):

		# Move left/right
		self.rect.centerx += self.vel.x
		self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
		block_hit_list = pg.sprite.spritecollide(self, game_data.blocks, False)
		for block in block_hit_list:
			# If we are moving right, set our right side to the left side of the item we hit
			if self.vel[0] > 0 and block.solid:
				self.rect.right = block.rect.left
				self.vel = pg.math.Vector2(0,0)
			else:
				# Otherwise if we are moving left, do the opposite.
				if self.vel[0] < 0 and block.solid:
					self.rect.left = block.rect.right
					self.vel = pg.math.Vector2(0,0)

		# Move up/down
		self.rect.centery += self.vel.y
		# Check and see if we hit anything
		block_hit_list = pg.sprite.spritecollide(self, game_data.blocks, False)
		for block in block_hit_list:
			# Reset our position based on the top/bottom of the object.
			if self.vel[1] > 0 and block.solid:
				self.rect.bottom = block.rect.top
				self.vel = pg.math.Vector2(0,0)
			else:
				if self.vel[1] < 0 and block.solid:
					self.rect.top = block.rect.bottom
					self.vel = pg.math.Vector2(0,0)
		self.pos = pg.math.Vector2(self.rect.x, self.rect.y)

	def take_powerup(self, powerup):
		# pick up powerups...
		if powerup.powerup_type[0] == 'addbomb':
			if self.max_bombs < 10:
				self.max_bombs += 1
				self.bombs_left += 1
		if powerup.powerup_type[0] == 'bombpower':
			if self.bomb_power < 10:
				self.bomb_power += 1
		if powerup.powerup_type[0] == 'speedup':
			if self.speed < 10:
				self.speed += 1
		if powerup.powerup_type[0] == 'healthup':
				self.health += 10
	def add_score(self):
		self.score += 1
