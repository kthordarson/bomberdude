# bomberdude
import asyncio
import random
from queue import Queue
from threading import Thread
from argparse import ArgumentParser
import pygame
from pygame.math import Vector2
from pygame import mixer  # Load the popular external library
from loguru import logger
from debug import (
	draw_debug_sprite,
	draw_debug_block,
	debug_dummies
)
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE, TextInputVisualizer, TextInputManager
from netutils import data_identifiers
from globals import Block, Bomb, Powerup, Gamemap
from globals import DEBUG
from globals import get_angle
from player import Player
from globals import StoppableThread
from menus import Menu
# from net.bombserver import ServerThread
import time
class Game(StoppableThread):
	def __init__(self, screen, game_dt):
		StoppableThread.__init__(self)
		self.kill = False
		self.dt = game_dt
		self.screen = screen
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pygame.Color("black")
		self.show_mainmenu = True
		self.running = False
		self.show_panel = True
		self.blocks = pygame.sprite.Group()
		self.players = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.powerups = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.get_input = False
		self.textmanager = TextInputManager(initial='server ip:')
		self.textinput = TextInputVisualizer(screen=self.screen, font_color=(255,255,255), manager=self.textmanager)
		self.gamemap = Gamemap()
		self.net_players = {}
		try:
			self.snd_bombexplode = mixer.Sound('data/bomb.mp3')
			self.snd_bombdrop = mixer.Sound('data/bombdrop.mp3')
		except pygame.error as e:
			logger.error(f'[bdude] music err {e}')
			self.snd_bombexplode = None
			self.snd_bombdrop = None

	def network_debug(self, player1):
		for dummy in player1.dummies:
			dummy.draw(self.screen)
		for np in player1.dummies:
			debug_dummies(self.screen, np)

	def network_handler(self, player1):
		player1.request_data('getnetplayers')
		# self.net_players = []
		# for player in self.players:
		# 	self.net_players = player.update_net_players()
		# 	logger.debug(f'nethandler p:{player} pnp:{len(player.net_players)} pd:{len(player.dummies)} np: {len(self.net_players)} pl: {len(self.players)}')

	def update(self):
		self.players.update(self.blocks)
		self.blocks.update()
		self.bombs.update()
		for bomb in self.bombs:
			bomb.dt = pygame.time.get_ticks() / 1000
			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
				bomb.gen_flames()
				self.flames.add(bomb.flames)
				bomb.bomber_id.bombs_left += 1
				bomb.kill()
				# try:
				# 	mixer.Sound.play(self.snd_bombexplode)
				# except (AttributeError, TypeError) as e: logger.debug(f'[bdude] {e}')
		self.flames.update()
		for flame in self.flames:
			flame_coll = pygame.sprite.spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if block.block_type == '1' or block.block_type == "2":  # or block.block_type == '3' or block.block_type == '4':
					powerup = Powerup(pos=block.rect.center, dt=dt)
					self.powerups.add(powerup)
					draw_debug_block(self.screen, block)
				if block.solid:
					block.hit()
					block.gen_particles(flame)
					self.particles.add(block.particles)
					flame.kill()

		for particle in self.particles:
			blocks = pygame.sprite.spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.kill()
		# powerblock_coll = pygame.sprite.spritecollide(self.server.players[0], self.powerups, False)
		# for pc in powerblock_coll:
		#s	pass
			# self.server.players[0].take_powerup(powerup=random.choice([1, 2, 3]))
			# pc.kill()

		self.particles.update(self.blocks)
		self.blocks.update(self.blocks)
		self.powerups.update()

	def draw(self):
		# draw on screen
		pygame.display.flip()
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.powerups.draw(self.screen)
		self.particles.draw(self.screen)
		self.players.draw(self.screen)
		self.flames.draw(self.screen)

		if self.get_input:
			self.textinput.draw(self.screen)

		if self.show_mainmenu and not self.get_input:
			self.game_menu.draw_mainmenu(self.screen)
		self.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=player1, flames=self.flames)
		# self.game_menu.draw_netpanel(self.net_players)
		# self.game_menu.draw_server_debug(server=self.server)
		if DEBUG:
			draw_debug_sprite(self.screen, self.players)

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Quit":
			self.running = False
		if selection == "Pause":
			self.show_mainmenu ^= True
		if selection == "Start":
			for pl in self.players:
				pl.request_data(datatype='gamedata')
				time.sleep(1)
				self.gamemap.grid = pl.get_mapgrid()
				self.gamemap.grid = self.gamemap.place_player(self.gamemap.grid, 0)				
				self.blocks = pl.get_blocks()
				_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
				for bl in self.blocks:
					bl.init_image()
				pl.connected = True

			self.show_mainmenu ^= True

		if selection == "Restart":
			self.show_mainmenu ^= True
		if selection == "Start server":
			logger.debug(f'Starting server ...')
			# self.server.start_backend()
			# pass
			# self.start_server()
		if selection == "Connect to server":
			#player1.connect_to_server()
			# self.server.AddPlayer(player1)
			# self.server.players.add(player1)
			#self.get_input = True
			self.show_mainmenu = False
			# self.server.players[0].playerconnect()

	def handle_input(self, player1):
		# get player input
		events = pygame.event.get()
		if self.get_input:
			self.textinput.update(events)
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu:  # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					elif not self.show_mainmenu and not self.get_input:
						b = player1.bombdrop()
						if b != 0:
							self.bombs.add(b)
					elif not self.show_mainmenu and self.get_input:
						logger.debug(f'[input] {self.textinput.value}')
						self.server_text = self.textinput.value.split(':')[1]
						self.get_input = False
						self.show_mainmenu = False
						# player1.connect_to_server(self.server_text)
						# self.bombdrop(self.server.players[0])
				if event.key == pygame.K_ESCAPE:
					self.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.running = False
					#self.player1.stop()
					self.stop()
				if event.key == pygame.K_c:
					pass
					# self.server.players[0].bomb_power = 100
					# self.server.players[0].max_bombs = 10
					# self.server.players[0].bombs_left = 10
					# self.server.players[0].speed = 7
				if event.key == pygame.K_p:
					self.show_panel ^= True
				if event.key == pygame.K_m:
					pass
				if event.key == pygame.K_q:
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
						player1.send_pos()
						#player1.player_action(player1, action=f'd')
						# self.server.players[0].vel.y = self.server.players[0].speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						player1.vel.y = -player1.speed
						player1.send_pos()
						#player1.player_action(player1, action=f'u')
						# self.server.players[0].vel.y = -self.server.players[0].speed
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					player1.vel.x = player1.speed
					player1.send_pos()
					# player1.player_action(player1, action=f'r')
					# self.server.players[0].vel.x = self.server.players[0].speed
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					player1.vel.x = -player1.speed
					player1.send_pos()
					#player1.player_action(player1, action=f'l')
					# self.server.players[0].vel.x = -self.server.players[0].speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s} and not self.show_mainmenu:
					player1.vel.y = 0
				if event.key in {pygame.K_UP, pygame.K_w} and not self.show_mainmenu:
					player1.vel.y = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					player1.vel.x = 0
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					player1.vel.x = 0
			if event.type == pygame.QUIT:
				self.running = False


if __name__ == "__main__":
	parser = ArgumentParser(description='bomberdude')
	parser.add_argument('--server',  default=False, action='store_true', dest='startserver')
	args = parser.parse_args()
	
	pygame.init()
	mixer.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	mainClock = pygame.time.Clock()
	dt = mainClock.tick(FPS) / 1000
	game = Game(pyscreen, dt)
	game.start()
	game.running = True
	player1 = Player((300,300), game.dt, 'player1.png')
	pygame.display.set_caption(f'{player1.client_id}')
	game.players.add(player1)
	player1.daemon = True
	player1.start()
	if args.startserver:
		game.show_mainmenu = False
	while game.running:
		# main game loop logic stuff
		game.handle_input(player1)
		game.network_debug(player1)
		if player1.connected:
			game.network_handler(player1)
		pygame.event.pump()
		game.update()
		game.draw()
	player1.kill = True
	player1.socket.close()
		# game.net_draw()
	# game.server.kill = True
	pygame.quit()
