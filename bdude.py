import asyncio
import pygame as pg
import random
from functools import partial
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict

import time
import os
import threading

from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS, PLAYERSIZE, BOMBSIZE, CHEAT, DEBUG_GRID
from globals import inside_circle as inside_circle
from player import Player as Player
from blocks import Block, Powerup_Block, BlockBomb
from menus import Menu as Menu
from menus import Info_panel as Info_panel
import socket 
SIZE = 800, 600
CHAR_SIZE=  64, 64

BLUE = 0,0 ,255; RED = 255, 0,0; YELLOW = 255,255,0 ; GREEN=0 ,255,0; WHITE = 255,255,255; MAGENTA = 255,0,255; CYAN = 0,255,255; BLACK=0,0,0; GREY = 128,128,128


class GameOver(BaseException):
	pass

class Game_Data():
	def __init__(self, screen):
		# super().__init__()
		# make a random grid map
		self.screen = screen
		# make a random map
		self.game_map = [[random.randint(0,9) for k in range(GRID_Y+1)] for j in range(GRID_X+1)]

		self.bombs = pg.sprite.Group()
		self.blocks = pg.sprite.Group()
		self.powerblocks = pg.sprite.Group()
		# set edges to solid blocks, 0 = solid block
		for x in range(GRID_X+1):
			self.game_map[x][0] = 1
			self.game_map[x][GRID_Y] = 1
		for y in range(GRID_Y+1):
			self.game_map[0][y] = 1
			self.game_map[GRID_X][y] = 1
				
	def place_player(self):
		# place player somewhere where there is no block
		placed = False
		while not placed:
			x = random.randint(1,GRID_X-1)
			y = random.randint(1,GRID_Y-1)
			self.game_map[x][y] = 0
			# make a clear radius around spawn point
			for clear_bl in list(inside_circle(3,x,y)):
				try:
					if self.game_map[clear_bl[0]][clear_bl[1]] > 1:
						self.game_map[clear_bl[0]][clear_bl[1]] = 0
				except:
					print(f'exception in place_player {clear_bl}')
			placed = True
			return (x*BLOCKSIZE,y*BLOCKSIZE)

	def get_block(self, x, y):
		# get block inf from grid
		return self.game_map[x][y]

	def kill_block(self, x, y):
		# remove block at gridpos x,y
		for block in self.blocks:
			if block.gridpos[0] == x and block.gridpos[1] == y:
				block.kill()
				self.game_map[x][y] = 0
				block = Block(x,y, screen=self.screen, block_type=0)
				self.blocks.add(block)

	def place_blocks(self):
		global DEBUG
		if DEBUG:
			t1 = time.time()
		self.blocks = pg.sprite.Group()
		# self.powerblocks = pg.sprite.Group()
		for k in range(0,GRID_X+1):
			for j in range(0, GRID_Y+1):
				try:                    
					block = Block(k,j, screen=self.screen, block_type=self.game_map[k][j])
					self.blocks.add(block)
				except Exception as e:
					print(f'{type(self.game_map)}')
					print(f'{k}.{j} {e}')
					os._exit(-1)
		if DEBUG:
			print(f'place_blocks: done time {time.time() - t1:.2f}')

	def update_map(self, mapinfo):
		global DEBUG
		for item in mapinfo:
			if DEBUG:
				print(f'update_map items: {len(mapinfo)} item: {item}')
			gridpos = [item[0], item[1]]
			block_id = self.game_map[gridpos[0]][gridpos[1]]
			if 3 <= block_id <= 9:
				# powerblock = Powerup_Block(gridpos[0], gridpos[1], screen=self.screen)
				# self.powerblocks.add(powerblock)
				self.game_map[item[0]][item[1]] = powerblock.powerup_type[1]
				self.kill_block(item[0], item[1])
				if DEBUG:
					print(f'update_map: powerupdrop on {gridpos} bid {block_id} p {powerblock.powerup_type[1]} newbid: {self.game_map[item[0]][item[1]]}')
			# self.game_map[item[0]][item[1]] = 30

	def destroy_blocks(self, block_list):
		pass

class Game():
	def __init__(self):
		panelsize = BLOCKSIZE * 5
		self.screen = pg.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize),0,32)
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pg.Color('gray12')
		self.font = pg.font.SysFont('calibri', 15, True)
		self.show_mainmenu = True
		# self.paused = True
		self.game_menu = Menu(self.screen)
		self.info_panel = Info_panel(BLOCKSIZE, GRID_Y*BLOCKSIZE+BLOCKSIZE, self.screen)
		# return screen
	def terminate(self):
		os._exit(1)
	def set_data(self, game_data):
		# set game data
		self.game_data = game_data
	def update(self):
		# do network things
		pass
	
	def draw(self):
		# draw on screen
		self.screen.fill(self.bg_color)
		self.game_data.blocks.draw(self.screen)
		self.players.draw(self.screen)
		self.game_data.powerblocks.draw(self.screen)
		self.game_data.bombs.draw(self.screen)
		for bomb in self.game_data.bombs:
			if bomb.exploding:
				bomb.draw_explotion()                                
				for flame in bomb.flames:
					flame.draw_flame()
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu()
		self.info_panel.draw_panel(self.game_data, self.player1)

	def handle_bombs(self):
		# update bombs
		for bomb in self.game_data.bombs:
			if bomb.exploding:
				bomb.explode(self.game_data.game_map)
				for flame in bomb.flames:
					flame.update()
					flame_hits = pg.sprite.spritecollide(flame, self.game_data.blocks, False)  # get blocks that flames touch
					for block in flame_hits:
						if block.block_type > 0:  # if block_type is larger than 0, stop expanding flame, else keep expanding until solid is hit
							flame.set_adder(0)
							flame.stop_expander()
							flame.kill()
						if block.block_type > 2: # if block_type is larger than 2 (less than 2 are permanent blocks)
							block.kill()
							self.player1.add_score()
							powerblock = Powerup_Block(block.gridpos[0], block.gridpos[1], screen=self.screen)  # drop powerup where destroyed block was before
							self.game_data.powerblocks.add(powerblock)
							newblock = Block(block.gridpos[0], block.gridpos[1], screen=self.screen, block_type=0)  # make a new type 0 block....
							self.game_data.blocks.add(newblock)
							if DEBUG:
								pass
								# print(f'blhit: {block.gridpos} x:{block.x} y:{block.y} {block.block_type} fl: dir: {flame.dir} u:{flame.l_up} d:{flame.l_dn} r:{flame.l_r} l:{flame.l_l} a:{flame.flame_adder} fl:{flame.flame_length} fe:{flame.expand}')
					player_hits = pg.sprite.spritecollide(flame, self.players, False)  # did flame touch player?
					for player in player_hits:
						player.take_damage(10)
						if player.dead:
							player.kill()
							# game over
			if bomb.done:
				self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]] = 0
				self.player1.bombs_left += 1  # update bombs_left for player1
				for flame in bomb.flames:
					flame.kill()
				bomb.kill()

	def handle_powerups(self):
		# powerups stuff
		for powerblock in self.game_data.powerblocks:
			powerplayers = pg.sprite.spritecollide(powerblock, self.players, False)
			# powerblock.time_left = 0
			for player in powerplayers:
				player.take_powerup(powerblock)
				powerblock.taken = True
			if powerblock.time_left <= 0 or powerblock.taken:
#                if DEBUG:
#                    print(f'pb pos: {powerblock.gridpos[0]}, {powerblock.gridpos[1]} map: {self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]]}')
				self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]] = 0
				newblock = Block(powerblock.gridpos[0], powerblock.gridpos[1], screen=self.screen, block_type=0) 
				self.game_data.blocks.add(newblock)
#                if DEBUG:
#                    print(f'nb pos: {newblock.gridpos[0]}, {newblock.gridpos[1]} map: {self.game_data.game_map[newblock.gridpos[0]][newblock.gridpos[1]]}')
				powerblock.kill()
			if powerblock.ending_soon:
				powerblock.flash()

	def handle_menu(self, selection):
		# mainmenu
		if selection == 'Quit':
			self.running = False
			self.terminate()
		if selection == 'Pause':
			#self.paused^= True
			self.show_mainmenu^= True
		if selection == 'Start':
			#self.paused^= True
			self.show_mainmenu^= True
		if selection == 'Restart':
			#self.paused^= True
			self.show_mainmenu^= True
			self.game_init()
			self.run()
		if selection == 'Start server':
			pass
		if selection == 'Connect to server':
			pass

	def handle_input(self):
		# get player input
		global CHEAT, DEBUG, DEBUG_GRID
		for event in pg.event.get():
			if event.type == pg.KEYDOWN:
				if event.key == pg.K_SPACE or event.key == pg.K_RETURN:
					if self.show_mainmenu: # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					else:
						self.game_data = self.player1.drop_bomb(self.game_data)

				if event.key == pg.K_ESCAPE:
					if not self.show_mainmenu:
						self.running = False
						self.terminate()
					else:
						#self.paused^= True
						self.show_mainmenu^= True

				if event.key == pg.K_a:
					pass
				if event.key == pg.K_c:
					self.player1.bomb_power = 100
					self.player1.max_bombs = 10
					self.player1.bombs_left = 10
					self.player1.speed = 10
					CHEAT = True
				if event.key == pg.K_p:
					#self.paused^= True
					self.show_mainmenu^= True
				if event.key == pg.K_m:
					#self.show_mainmenu^= True
					self.paused^= True
				if event.key == pg.K_d:
					DEBUG^= True
				if event.key == pg.K_g:
					DEBUG = False
					DEBUG_GRID^= True
				if event.key == pg.K_r:
					pass
					#self.game_init()
					#self.run()
				if event.key == pg.K_DOWN:
					#if not self.paused:
						#self.player1.changespeed(0,self.player1.speed)
					if self.show_mainmenu:
						self.game_menu.menu_down()
					else:
						self.player1.changespeed(0,self.player1.speed)
				if event.key == pg.K_UP:
##					if not self.paused:#
#						self.player1.changespeed(0,-self.player1.speed)
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						self.player1.changespeed(0,-self.player1.speed)
				if event.key == pg.K_RIGHT:
					if not self.show_mainmenu:
						self.player1.changespeed(self.player1.speed,0)
				if event.key == pg.K_LEFT:
					if not self.show_mainmenu:
						self.player1.changespeed(-self.player1.speed,0)
			if event.type == pg.KEYUP:
				if event.key == pg.K_a:
					pass
				if event.key == pg.K_d:
					pass
				if event.key == pg.K_DOWN:
					if not self.show_mainmenu:
						self.player1.changespeed(0,0)
						self.player1.change_y = 0
				if event.key == pg.K_UP:
					if not self.show_mainmenu:
						self.player1.changespeed(0,0)
						self.player1.change_y = 0
				if event.key == pg.K_RIGHT:
					if not self.show_mainmenu:
						self.player1.changespeed(0,0)
						self.player1.change_x = 0
				if event.key == pg.K_LEFT:
					if not self.show_mainmenu:
						self.player1.changespeed(0,0)
						self.player1.change_x = 0
			if event.type == pg.MOUSEBUTTONDOWN:
				pass
			if event.type == pg.QUIT:
				self.running = False
#                print(f's r f')

async def main_loop(game):
	mainClock = pg.time.Clock()
	game_data = Game_Data(screen=game.screen)
	game.set_data(game_data)
	
	game.players = pg.sprite.Group()
	player_pos = game_data.place_player()
	game.player1 = Player(x=player_pos[0], y=player_pos[1], player_id=33, screen=game.screen)
	game.players.add(game.player1)
	game_data.place_blocks()
	
	while True:
		dt = mainClock.tick(FPS)
		#if random.random()<0.2:
		#	main_group.add(create_object())
		pg.event.pump()
		game.handle_input()
		game.handle_bombs()
		game.handle_powerups()

		game.players.update(game.game_data)
		game.game_data.blocks.update()
		game.game_data.powerblocks.update()
		game.game_data.bombs.update()
		# game.players.update(game.game_data)
		game.update()
		game.draw()
		#main_group.clear(game.screen, clear_callback)
		#main_group.update()
		#main_group.draw(game.screen)
		pg.display.flip()
		#pg.time.delay(30)
		await asyncio.sleep(0.00001)
		

def main(game):
	#main_group = pg.sprite.OrderedUpdates()
	#main_group.add(Object(pos=(0, 300), move_function=move1))

	game_task = asyncio.Task(main_loop(game))

	game.gameloop.run_until_complete(game_task)


if __name__ == "__main__":
	pg.init()
	game = Game()
	# init()
	try:
		main(game)
	finally:
		game.gameloop.stop()
		pg.quit()