# bomberdude
import time
import random
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
# from pygame import mixer  # Load the popular external library
from debug import draw_debug_sprite, draw_debug_block
from globals import Block, Powerup, Gamemap, BasicThing, ResourceHandler
from constants import *
from menus import Menu, DebugDialog
from player import Player
from threading import Thread, enumerate

class Game(Thread):
	def __init__(self, screen, game_dt):
		Thread.__init__(self, name='game')
		# StoppableThread.__init__(self, name='Game')
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
		self.gamemap = Gamemap()
		self.DEBUGFONTCOLOR = (123, 123, 123)
		self.DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
		self.rm = ResourceHandler()

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
			# try:
			# 	mixer.Sound.play(self.snd_bombexplode)q
			# except (AttributeError, TypeError) as e: logger.debug(f'[bdude] {e}')
	def update_flames(self):
		self.flames.update()
		for flame in self.flames:
			flame_coll = spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if block.block_type == 1 or block.block_type == 2:  # or block.block_type == '3' or block.block_type == '4':
					powerup = Powerup(pos=block.rect.center, dt=dt)
					self.powerups.add(powerup)
					draw_debug_block(self.screen, block)
				if block.solid:
					block.hit()
					block.gen_particles(flame)
					self.particles.add(block.particles)
					flame.kill()
					self.blocks.remove(block)
	def update_particles(self):
		self.particles.update(self.blocks)
		for particle in self.particles:
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.kill()
					self.particles.remove(particle)

	def update(self):		
		self.players.update(self.blocks)
		self.blocks.update()
		self.update_bombs()
		self.update_flames()
		self.update_particles()

		# powerblock_coll = [spritecollide(player, self.powerups, False) for player in self.players]
		# for pc in powerblock_coll:
		# 	[player.take_powerup(powerup=random.choice([1, 2, 3])) for player in self.players]
		# 	#pc.kill()
		self.blocks.update(self.blocks)
		self.powerups.update()

	def reset_map(self):
		# Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
		logger.debug(f'mapreset start')
		self.gamemap = Gamemap()
		self.gamemap.grid = self.gamemap.place_player(location=0, grid=self.gamemap.grid)
		logger.debug(f'mapreset gamegrid ready')
		self.blocks.empty()
		logger.debug(f'mapreset blocks cleared')
		idx = 0
		for k in range(0, GRIDSIZE[0] + 1): 
			for j in range(0, GRIDSIZE[1] + 1):
				newblock = Block(pos=Vector2(j*BLOCKSIZE[0], k*BLOCKSIZE[1]), gridpos=(j, k), block_type=self.gamemap.grid[j][k], reshandler=self.rm)
				self.blocks.add(newblock)
				idx += 1
		logger.debug(f'mapreset {idx} blocks loaded')

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


		if self.show_mainmenu:
			self.game_menu.draw_mainmenu(self.screen)
		self.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=player1, flames=self.flames)
		if DEBUG:
			draw_debug_sprite(self.screen, self.players, self.DEBUGFONT)
		if self.show_debug_diaglog:
			self.debug_dialog.draw_debug_players(players=self.players)

	def handle_menu(self, selection, player1):
		# mainmenu
		if selection == "Quit":
			self.running = False

		if selection == "Pause":
			self.show_mainmenu ^= True

		if selection == "Start":
			# self.gamemap.grid = self.gamemap.place_player(location=0, grid=self.gamemap.grid)
			self.show_mainmenu ^= True
			self.reset_map()
			# self.blocks.empty()
			#_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
			
		if selection == "Restart":
			self.show_mainmenu ^= True

		if selection == "Start server":
			logger.debug(f'Starting server ...')

		if selection == "Connect to server":
			self.show_mainmenu = False

	def handle_input(self, player1):
		events = pygame.event.get()
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu:  # or self.paused:
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
				if event.key == pygame.K_2:
					logger.debug(f'mapreset')
					self.reset_map()
				if event.key == pygame.K_c:
					pass
				if event.key == pygame.K_f:
					self.show_debug_dialog = True
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


if __name__ == "__main__":
	parser = ArgumentParser(description='bomberdude')
	parser.add_argument('--server', default=False, action='store_true', dest='startserver')
	args = parser.parse_args()
	pygame.init()

	# mixer.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	mainClock = pygame.time.Clock()
	dt = mainClock.tick(FPS) / 1000
	game = Game(pyscreen, dt)
	game.start()
	game.running = True
	player1 = Player(pos=(300, 300), dt=game.dt, image='data/player1.png')

	game.players.add(player1)
	player1.daemon = True
	player1.start()
	# if args.startserver:
	#	game.show_mainmenu = False
	while game.running:
		# main game loop logic stuff
		game.handle_input(player1)
		pygame.event.pump()
		game.update()
		game.draw()
	logger.debug(f'game end {game.running} {player1.kill}')
	player1.kill = True
	pygame.quit()
