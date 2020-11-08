# TODO
# fix player random teleports
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import os
import random
import time

import pygame as pg

from blocks import Block, Powerup_Block
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y
from globals import inside_circle as inside_circle
from menus import Info_panel as Info_panel
from menus import Menu as Menu
from player import Player as Player

DEBUG = False

class GameOver(BaseException):
	pass


class Game_Data():
	def __init__(self, screen):
		self.screen = screen
		# make a random map
		self.game_map = [[random.randint(0, 9) for k in range(GRID_Y + 1)] for j in range(GRID_X + 1)]

		self.bombs = pg.sprite.Group()
		self.blocks = pg.sprite.Group()
		self.powerblocks = pg.sprite.Group()
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

	def kill_block(self, x, y):
		# remove block at gridpos x,y
		for block in self.blocks:
			if block.gridpos[0] == x and block.gridpos[1] == y:
				block.kill()
				self.game_map[x][y] = 0
				block = Block(x, y, screen=self.screen, block_type=0)
				self.blocks.add(block)

	def place_blocks(self):
		# block placing stuff		
		for k in range(0, GRID_X + 1):
			for j in range(0, GRID_Y + 1):
				try:
					block = Block(k, j, screen=self.screen, block_type=self.game_map[k][j])
					self.blocks.add(block)
				except Exception as e:
					print(f'{type(self.game_map)}')
					print(f'{k}.{j} {e}')
					os._exit(-1)

class Game():
	def __init__(self):
		panelsize = BLOCKSIZE * 5
		self.screen = pg.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize), 0, 32)
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pg.Color('gray12')
		self.font = pg.font.SysFont('calibri', 15, True)
		self.show_mainmenu = True
		# self.paused = True
		self.game_menu = Menu(self.screen)
		self.info_panel = Info_panel(BLOCKSIZE, GRID_Y * BLOCKSIZE + BLOCKSIZE, self.screen)

	def set_block(self, x, y, value):
		self.game_data.game_map[x][y] = value

	def terminate(self):
		os._exit(1)

	def set_data(self, game_data):
		# set game data
		self.game_data = game_data

	def check_flame(self, object_one, object_two):
		# testfunction for collision callbacks
		if (pg.sprite.collide_mask(object_one, object_two) != None):
			#object_one.destroy()
			#object_two.destroy()
			return True
		else:
			return False

	def update(self):
		# todo network things
		for bomb in self.game_data.bombs:
			if bomb.exploding:
				for flame in bomb.flames:
					blocks = pg.sprite.spritecollide(flame, self.game_data.blocks, False)
					for block in blocks:
						if block.block_type >= 1:
							flame.vel.x = 0
							flame.vel.y = 0
						if block.block_type >= 3: 		# block_type 1,2,3 = solid orange
							block.set_zero()      		# block_type 4 and up can be destroyed
							self.player1.add_score()	# give player some score
							powerblock = Powerup_Block(block.gridpos[0], block.gridpos[1], screen=self.screen)  # create powerupblock
							self.game_data.powerblocks.add(powerblock) # add new powerblock to powerblocks list
							# print(f'Bomb PID {bomb.bomber_id} {bomb.pos} {flame.name:<6} {flame.pos} {type(block)} {block.x} {block.y} {block.pos}' )
			if bomb.done:
				self.player1.bombs_left += 1  # return bomb to owner when done
				mapx = bomb.gridpos[0]
				mapy = bomb.gridpos[1]
				mapdata = self.game_data.get_block(mapx, mapy)
				# print(f'Bombdone {mapx} {mapy} {mapdata}')
				self.set_block(mapx, mapy, 0)
				# mapdata = self.game_data.get_block(mapx, mapy)
				# print(f'Bombdone {mapx} {mapy} {mapdata}')
				bomb.kill()

		for powerblock in self.game_data.powerblocks:
			powerplayers = pg.sprite.spritecollide(powerblock, self.players, False)
			for player in powerplayers:
				player.take_powerup(powerblock)
				powerblock.taken = True
			if powerblock.time_left <= 0 or powerblock.taken:
				self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]] = 0
				newblock = Block(powerblock.gridpos[0], powerblock.gridpos[1], screen=self.screen, block_type=0)
				self.game_data.blocks.add(newblock)
				powerblock.kill()
			if powerblock.ending_soon:
				powerblock.flash()

	def draw(self):
		# draw on screen
		self.screen.fill(self.bg_color)
		[block.draw() for block in self.game_data.blocks]
		# self.game_data.blocks.draw(self.screen)
		self.players.draw(self.screen)
		self.game_data.powerblocks.draw(self.screen)
		[bomb.draw() for bomb in self.game_data.bombs]
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu()
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
			game_init()
			self.run()
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
						self.game_data = self.player1.drop_bomb(self.game_data)
				if event.key == pg.K_ESCAPE:
					if not self.show_mainmenu:
						self.running = False
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
					self.paused ^= True
				if event.key == pg.K_q:
					pass
					# DEBUG ^= True
				if event.key == pg.K_g:
					pass
					# DEBUG = False
					# DEBUG_GRID ^= True
				if event.key == pg.K_r:
					game_init()
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
def game_init():
	game = Game()
	game_data = Game_Data(screen=game.screen)
	game.set_data(game_data)

	game.players = pg.sprite.Group()
	player_pos = game_data.place_player() # randomly place player and clear blocks around spawnpoint
	pos = pg.math.Vector2(player_pos[0], player_pos[1])
	game.player1 = Player(pos=pos, player_id=33, screen=game.screen)
	game.players.add(game.player1)
	game_data.place_blocks()
	return game

async def main_loop(game):
	mainClock = pg.time.Clock()
	# game.game_init(game)
	while True:
		# main game loop logic stuff
		dt = mainClock.tick(FPS)
		pg.event.pump()
		game.handle_input()
		game.players.update(game.game_data)
		game.game_data.blocks.update()
		game.game_data.powerblocks.update()
		game.game_data.bombs.update()
		game.update()
		game.draw()
		pg.display.flip()


def main():
	game = game_init()
	game_task = asyncio.Task(main_loop(game))
	game.gameloop.run_until_complete(game_task)


if __name__ == "__main__":
	pg.init()
	# game = Game()
	# init()
	try:
		main()
	finally:
		# game.gameloop.stop()
		pg.quit()
