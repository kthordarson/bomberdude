# bomberdude
# TODO
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import os
import random

import pygame as pg

from blocks import Block, Powerup_Block, Particle
from bombs import BlockBomb
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y
from globals import inside_circle
from menus import Info_panel
from menus import Menu
from player import Player

DEBUG = False

class Game_Data():
	def __init__(self, screen):
		self.screen = screen
		self.game_map = None # [[random.randint(0, 9) for k in range(GRID_Y + 1)] for j in range(GRID_X + 1)]

	def generate_map(self):
		self.game_map = [[random.randint(0, 9) for k in range(GRID_Y + 1)] for j in range(GRID_X + 1)]
		# set edges to solid blocks, 0 = solid block
		for x in range(GRID_X + 1):
			self.game_map[x][0] = 1
			self.game_map[x][GRID_Y] = 1
		for y in range(GRID_Y + 1):
			self.game_map[0][y] = 1
			self.game_map[GRID_X][y] = 1

	def place_player(self):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridmap
		x = int(GRID_X // 2) # random.randint(2, GRID_X - 2)
		y = int(GRID_Y // 2)  # random.randint(2, GRID_Y - 2)
		self.game_map[x][y] = 0
		# make a clear radius around spawn point
		for block in list(inside_circle(3, x, y)):
			try:
				# if self.game_map[clear_bl[0]][clear_bl[1]] > 1:
				self.game_map[block[0]][block[1]] = 0
			except Exception as e:
				print(f'exception in place_player {block} {e}')
		return (x * BLOCKSIZE, y * BLOCKSIZE)

	def get_block(self, x, y):
		# get block inf from grid
		return self.game_map[x][y]

	def get_block_real(self, x, y):
		# get block inf from grid
		mapx = x // BLOCKSIZE
		mapy = y // BLOCKSIZE
		return self.game_map[mapx][mapy]

	def set_block(self, x, y, value):
		self.game_map[x][y] = value


	def get_blocks(self):
		# block placing stuff
		blocks = pg.sprite.Group()
		for k in range(0, GRID_X + 1):
			for j in range(0, GRID_Y + 1):
				try:
					block_type = int(self.game_map[k][j])
#					block = Block(gridpos=(k, j), block_type=block_type, solid=False, permanent=False, block_color=pg.Color('black'))
					if block_type == 0:
						block = Block(gridpos=(k, j), block_type=block_type, solid=False, permanent=False, block_color=pg.Color('black'))		# black nothing
					elif block_type == 1:
						block = Block(gridpos=(k, j), block_type=block_type, solid=True, permanent=True, block_color=pg.Color('orangered1'))	# wall solid, permanent
					elif block_type == 2:
						block = Block(gridpos=(k, j), block_type=block_type, solid=True, permanent=True, block_color=pg.Color('orangered2'))	# wall solid, permanent
					elif block_type == 3:
						block = Block(gridpos=(k, j), block_type=block_type, solid=True, permanent=True, block_color=pg.Color('orangered3'))	# wall solid, permanent
					elif 4 <= block_type <= 9:
						block = Block(gridpos=(k, j), block_type=block_type, solid=True, permanent=False, block_color=pg.Color('gray31'))		# solid not permanent
					elif block_type == 99:
						block = Block(gridpos=(k, j), block_type=block_type, solid=False, permanent=False, block_color=pg.Color('black'))		# not solid not permanent
					else:
						block = Block(gridpos=(k, j), block_type=block_type, solid=False, permanent=False, block_color=pg.Color('black'))		# not solid not permanent
					blocks.add(block)
				except Exception as e:
					print(f'[get_blocks] {k}.{j} {type(block)} {block_type} {e}')
		return blocks

class Game():
	def __init__(self, game_data, screen):
		self.game_data = game_data
		self.game_data.generate_map()
		self.screen = screen  #  pg.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize), 0, 32)
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pg.Color('gray12')
		self.font = pg.font.SysFont('calibri', 15, True)
		self.show_mainmenu = True
		self.running = False
		self.players = pg.sprite.Group()
		self.player1 = Player(pos=self.game_data.place_player(), player_id=33)
		self.players.add(self.player1)
		self.blocks = self.game_data.get_blocks()
		self.blocks.particles = pg.sprite.Group()
		self.powerblocks = pg.sprite.Group()
		self.bombs = pg.sprite.Group()
		self.bombs.flames = pg.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.info_panel = Info_panel(BLOCKSIZE, GRID_Y * BLOCKSIZE + BLOCKSIZE, self.screen)

	def set_block(self, x, y, value):
		self.game_data.game_map[x][y] = value

	def terminate(self):
		os._exit(1)

	def set_data(self, game_data):
		# set game data
		self.game_data = game_data

	def bombdrop(self, player):
		# get grid pos of player
		x = player.gridpos[0]
		y = player.gridpos[1]
		if player.bombs_left > 0: #  and game_data.game_map[x][y] == 0:  # only place bombs if we have bombs... and on free spot...
			# self.game_data.game_map[x][y] = player.player_id
			# create bomb at gridpos xy, multiply by BLOCKSIZE for screen coordinates
			bomb = BlockBomb(pos=(player.rect.centerx, player.rect.centery), bomber_id=player.player_id, block_color=pg.Color('yellow'), bomb_power=player.bomb_power, gridpos=player.gridpos)
			self.bombs.add(bomb)
			player.bombs_left -= 1
		#else:
		#	print(f'cannot drop bomb')

	def update(self):
		# todo network things
		self.player1.update(self.blocks)
		self.update_bombs()
		# self.update_powerblock()
		self.update_blocks()

	def update_blocks(self):
		for block in self.blocks:
			block.update()
			if not block.powerblock:
				colls = pg.sprite.spritecollide(block, block.particles, False)				
				if len(colls) > 0:
					for item in colls:
						if type(item) is Particle:
							if block.powerblock:
								block.block_color = (255, 255, 255)
							else:
								block.take_damage(self.screen, item)
							item.vel = pg.math.Vector2(0, 0)
							item.color = (255, 255, 255)
							item.alpha = 1
							print(f'[update_blocks] coll {len(colls)} {type(colls)} item {item.pos} {item.vel}')
						else:
							print(f'[update_blocks] xcoll {len(colls)} {type(colls)} item {item.pos} {item.vel}')

	def update_bombs(self):
		self.bombs.update()
		self.bombs.flames.update()
		for bomb in self.bombs:
			if bomb.exploding:
				for flame in bomb.flames:
					blocks = pg.sprite.spritecollide(flame, self.blocks, False)
					for block in blocks:
						if block.block_type >= 1:
							block.take_damage(self.screen, flame)  #  = True		# block particles
							flame.stop()
							# flame.explode = True
						if block.block_type >= 3: 		# block_type 1,2,3 = solid orange
							# block.explode = True
							# block.set_zero()      	# block_type 4 and up can be destroyed
							block.drop_powerblock()		# make block drop the powerup
							self.player1.add_score()	# give player some score
							# self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]] = 0

			if bomb.done:
				self.player1.bombs_left += 1  # return bomb to owner when done
				bomb.kill()


	# def update_powerblock(self):
	# 	self.powerblocks.update()
	# 	for powerblock in self.powerblocks:
	# 		powerplayers = pg.sprite.spritecollide(powerblock, self.players, False)
	# 		for player in powerplayers:
	# 			player.take_powerup(powerblock)
	# 			powerblock.taken = True
	# 		if powerblock.time_left <= 0 or powerblock.taken:
	# 			#self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]] = 0
	# 			#newblock = Block(powerblock.gridpos[0], powerblock.gridpos[1], block_type=0, solid=False)
	# 			#self.blocks.add(newblock)
	# 			powerblock.kill()
	# 		if powerblock.ending_soon:
	# 			powerblock.flash()

	def draw(self):
		# draw on screen
		pg.display.flip()
		self.screen.fill(self.bg_color)
		[block.draw(self.screen) for block in self.blocks]
		[bomb.draw(self.screen) for bomb in self.bombs]
		[flame.draw(self.screen) for flame in self.bombs.flames]
		[powerblock.draw(self.screen) for powerblock in self.powerblocks]
		self.players.draw(self.screen)
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu(self.screen)
		self.info_panel.draw_panel(self.game_data, self.player1)

	def handle_menu(self, selection):
		# mainmenu
		if selection == 'Quit':
			self.running = False
			self.terminate()
		if selection == 'Pause':
			self.show_mainmenu ^= True
		if selection == 'Start':
			self.show_mainmenu ^= True
		if selection == 'Restart':
			self.show_mainmenu ^= True
		if selection == 'Start server':
			pass
		if selection == 'Connect to server':
			pass

	def handle_input(self):
		# get player input
		for event in pg.event.get():
			if event.type == pg.KEYDOWN:
				if event.key == pg.K_SPACE or event.key == pg.K_RETURN:
					if self.show_mainmenu:  # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					else:
						self.bombdrop(self.player1)
				if event.key == pg.K_ESCAPE:
					if not self.show_mainmenu:
						self.running = False
						# break
						self.terminate()
					else:
						self.show_mainmenu ^= True
				if event.key == pg.K_c:
					self.player1.bomb_power = 100
					self.player1.max_bombs = 10
					self.player1.bombs_left = 10
					self.player1.speed = 10
				if event.key == pg.K_p:
					self.show_mainmenu ^= True
				if event.key == pg.K_m:
					pass
					# self.paused ^= True
				if event.key == pg.K_q:
					pass
					# DEBUG ^= True
				if event.key == pg.K_g:
					pass
					# DEBUG = False
					# DEBUG_GRID ^= True
				if event.key == pg.K_r:
					pass
					# game_init()
				if event.key in set([pg.K_DOWN, pg.K_s]):
					if self.show_mainmenu:
						self.game_menu.menu_down()
					else:
						self.player1.vel.y = self.player1.speed
				if event.key in set([pg.K_UP, pg.K_w]):
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						self.player1.vel.y = -self.player1.speed
				if event.key in set([pg.K_RIGHT, pg.K_d]):
					if not self.show_mainmenu:
						self.player1.vel.x = self.player1.speed
				if event.key in set([pg.K_LEFT, pg.K_a]):
					if not self.show_mainmenu:
						self.player1.vel.x = -self.player1.speed
			if event.type == pg.KEYUP:
				if event.key == pg.K_a:
					pass
				if event.key == pg.K_d:
					pass
				if event.key in set([pg.K_DOWN, pg.K_s]):
					if not self.show_mainmenu:
						self.player1.vel.y = 0
				if event.key in set([pg.K_UP, pg.K_w]):
					if not self.show_mainmenu:
						self.player1.vel.y = 0
				if event.key in set([pg.K_RIGHT, pg.K_d]):
					if not self.show_mainmenu:
						self.player1.vel.x = 0
				if event.key in set([pg.K_LEFT, pg.K_a]):
					if not self.show_mainmenu:
						self.player1.vel.x = 0
			if event.type == pg.MOUSEBUTTONDOWN:
				mousex, mousey = pg.mouse.get_pos()
				blockinf = self.game_data.get_block_real(mousex, mousey)
				gx = mousex // BLOCKSIZE
				gy = mousey // BLOCKSIZE
				print(f'mouse x:{mousex} y:{mousey} | gx:{gx} gy:{gy} | b:{blockinf}')
			if event.type == pg.QUIT:
				self.running = False

async def main_loop(game):
	mainClock = pg.time.Clock()
	# game.game_init(game)
	while True:
		# main game loop logic stuff
		dt = mainClock.tick(FPS)
		pg.event.pump()
		game.handle_input()
		game.update()
		game.draw()


def main():
	panelsize = BLOCKSIZE * 5
	screen  = pg.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize), 0, 32)
	game_data = Game_Data(screen)
	game = Game(game_data=game_data, screen=screen)
	game_task = asyncio.Task(main_loop(game))
	game.gameloop.run_until_complete(game_task)


if __name__ == "__main__":
	pg.init()
	try:
		main()
	finally:
		pg.quit()
