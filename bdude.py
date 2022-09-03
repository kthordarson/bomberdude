#!/bin/python3.9
# bomberdude
import socket
import time
import random
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
# from pygame import mixer # Load the popular external library
from debug import draw_debug_sprite, draw_debug_block
from globals import Block, Powerup, Gamemap, ResourceHandler
from constants import DEBUG,DEBUGFONTCOLOR,DEFAULTFONT,GRIDSIZE,BLOCKSIZE,SCREENSIZE,FPS
from menus import Menu, DebugDialog
from player import Player
from threading import Thread
from queue import Empty, Queue
from netutils import DataReceiver, DataSender, data_identifiers
from bombserver import ServerThread

class Game(Thread):
	def __init__(self, screen=None, game_dt=None, gamemap=None):
		Thread.__init__(self, name='game')
		self.kill = False
		self.dt = game_dt
		self.screen = screen
		self.bg_color = pygame.Color("black")
		self.show_mainmenu = True
		self.show_debug_diaglog = False
		self.running = False
		self.show_panel = True
		self.blocks = Group()
		self.players = Group()
		self.particles = Group()
		self.powerups = Group()
		self.bombs = Group()
		self.flames = Group()
		self.game_menu = Menu(self.screen)
		self.debug_dialog = DebugDialog(self.screen)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.DEBUGFONTCOLOR = (123, 123, 123)
		self.DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
		self.rm = ResourceHandler()
		self.gamemap = gamemap
		# self.mapgrid = []
		self.gameserver = None
		self.server_mode = False

	def update_bombs(self):
		self.bombs.update()
		for bomb in self.bombs:
			bomb.dt = pygame.time.get_ticks() / 1000
			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
				bomb.gen_flames()
				self.flames.add(bomb.flames)
				bomb.bomber_id.bombs_left += 1
				bomb.kill()
				self.bombs.remove(bomb)

	def update_flames(self):
		self.flames.update()
		for flame in self.flames:
			flame_coll = spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if block.block_type == 1 or block.block_type == 2: # or block.block_type == '3' or block.block_type == '4':
					powerup = Powerup(pos=block.rect.center, dt=dt, reshandler=self.rm)
					self.powerups.add(powerup)
				if block.solid:
					block.hit()					
					self.particles.add(block.gen_particles(flame))
					flame.kill()
				# self.blocks.remove(block)

	def update_particles(self):
		self.particles.update(self.blocks)
		for particle in self.particles:
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.hit()
					#self.particles.remove(particle)

	def update(self, player1):
		self.players.update(self.blocks)
		self.blocks.update()
		self.update_bombs()
		self.update_flames()
		self.update_particles()

		powerblock_coll = spritecollide(player1, self.powerups, False)
		for pc in powerblock_coll:
			player1.take_powerup(powerup=random.choice([1, 2, 3]))
			pc.kill()
		self.blocks.update(self.blocks)
		self.powerups.update()

	def reset_blocks(self, newgrid=[]):
		self.grid = newgrid
		self.blocks.empty()
		logger.debug(f'mapreset blocks cleared')
		idx = 0
		for k in range(0, GRIDSIZE[0] + 1):
			for j in range(0, GRIDSIZE[1] + 1):
				newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=self.gamemap.grid[j][k], reshandler=self.rm)
				self.blocks.add(newblock)
				idx += 1

	def reset_map(self, reset_grid=False):
		# Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
		logger.debug(f'[rm] reset_grid: rg:{reset_grid} gmg:{type(self.gamemap)} ')
		self.gamemap.grid = self.gamemap.place_player(location=0, grid=self.gamemap.grid)
		logger.debug(f'[rm] newgrid {len(self.gamemap.grid)}')
		self.blocks.empty()
		idx = 0
		try:
			for k in range(0, GRIDSIZE[0] + 1):
				for j in range(0, GRIDSIZE[1] + 1):
					newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=self.gamemap.grid[j][k], reshandler=self.rm)
					self.blocks.add(newblock)
				idx += 1
		except IndexError as e:
			logger.error(f'Err {e} idx: {idx} k:{k} j:{j}')
			#logger.error(f'[e] {e} {self.gamemap.grid}')
		logger.debug(f'[mr] {idx} blocks loaded')

	def draw(self, player1):
		# draw on screen
		pygame.display.flip()
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.powerups.draw(self.screen)
		self.particles.draw(self.screen)
		self.players.draw(self.screen)
		self.flames.draw(self.screen)
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu(self.screen)
		self.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=player1, flames=self.flames)
		if self.show_debug_diaglog:
			self.debug_dialog.draw_debug_players(players=self.players)

	def connect_server(self, player1):
		server = ('127.0.0.1', 6666)
		logger.debug(f'[{player1.client_id}] connecting to {server}')
		try:
			self.socket.connect(server)
		except (ConnectionRefusedError, OSError) as e:
			logger.error(f'{e}')

	def handle_menu(self, selection, player1):
		# mainmenu
		if selection == "Start":
			self.show_mainmenu ^= True
			self.reset_map()

		if selection == "Connect to server":
			pass
			# self.show_mainmenu = False
			# self.connect_server(player1)
			# self.request_servermap(player=player1)

		if selection == "Quit":
			self.running = False

		if selection == "Pause":
			self.show_mainmenu ^= True
			self.pause_game()

		if selection == "Restart":
			self.show_mainmenu ^= True
			self.restart_game()

		if selection == "Start server":
			pass
			# self.gameserver = ServerThread()
			# self.gameserver.daemon = True
			# self.gameserver.start()
			# self.server_mode = True
			# pygame.display.set_caption('server')

	def handle_input(self, player1=None):
		events = pygame.event.get()
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu: # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection, player1)
					elif not self.show_mainmenu:
						b = player1.bombdrop()
						if b != 0:
							self.bombs.add(b)
				if event.key == pygame.K_ESCAPE:
					self.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					player1.kill = True
					self.running = False
				# self.player1.stop()
				if event.key == pygame.K_1:
					self.request_servermap(player=player1)
					self.reset_map()
				if event.key == pygame.K_2:
					pass
				if event.key == pygame.K_c:
					pass
				if event.key == pygame.K_f:
					pass
				# self.show_debug_dialog ^= True
				if event.key == pygame.K_p:
					self.show_panel ^= True
				if event.key == pygame.K_m:
					logger.debug(f'mapreset')
					self.reset_map()
				if event.key == pygame.K_n:
					pass
				if event.key == pygame.K_g:
					pass
				if event.key == pygame.K_r:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s}:
					if self.show_mainmenu:
						self.game_menu.menu_down()
					else:
						player1.vel.y = player1.speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						player1.vel.y = -player1.speed
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					# if not self.show_mainmenu:
					player1.vel.x = player1.speed
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					# if not self.show_mainmenu:
					player1.vel.x = -player1.speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s}:
					player1.vel.y = 0
				if event.key in {pygame.K_UP, pygame.K_w}:
					player1.vel.y = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					player1.vel.x = 0
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					player1.vel.x = 0
			if event.type == pygame.QUIT:
				self.running = False
		# if event_type == pygame.MOUSEBUTTONDOWN:
		#	mousex, mousey = pygame.mouse.get_pos()

if __name__ == "__main__":

	parser = ArgumentParser(description='bomberdude')
	parser.add_argument('--server', default=False, action='store_true', dest='startserver')
	args = parser.parse_args()
	pygame.init()

	# mixer.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	mainClock = pygame.time.Clock()
	dt = mainClock.tick(FPS) / 1000
	mainmap = Gamemap(genmap=True)
	game = Game(screen=pyscreen, game_dt=dt, gamemap=mainmap)
	game.start()
	game.running = True
	player1 = Player(pos=(300, 300), dt=game.dt, image='data/player1.png')

	game.players.add(player1)
	player1.daemon = True
	player1.start()
	font = pygame.freetype.Font(DEFAULTFONT, 12)
	font_color = (255, 255, 255)
	while game.running:
		# main game loop logic stuff
		game.handle_input(player1=player1)
		game.update(player1)
		game.draw(player1)

	logger.debug(f'game end {game.running} {player1.kill}')
	player1.kill = True
	pygame.quit()
