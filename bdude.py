# bomberdude
import time
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
from pygame import mixer  # Load the popular external library
from netutils import data_identifiers
from debug import (
	draw_debug_sprite,
	draw_debug_block,
	debug_dummies
)
from globals import Block, Powerup, Gamemap, BasicThing
from globals import DEBUG
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, TextInputVisualizer, TextInputManager
from globals import StoppableThread
from menus import Menu
from player import Player, DummyPlayer
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
		self.running = False
		self.show_panel = True
		self.blocks = Group()
		self.players = Group()
		self.particles = Group()
		self.particles = Group()
		self.powerups = Group()
		self.bombs = Group()
		self.flames = Group()
		self.game_menu = Menu(self.screen)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.get_input = False
		self.textmanager = TextInputManager(initial='server ip:')
		self.textinput = TextInputVisualizer(screen=self.screen, font_color=(255, 255, 255), manager=self.textmanager)
		self.gamemap = Gamemap(genmap=False)
		self.net_players = {}
		self.dummies = Group()
		self.game_ready = False
		try:
			self.snd_bombexplode = mixer.Sound('data/bomb.mp3')
			self.snd_bombdrop = mixer.Sound('data/bombdrop.mp3')
		except pygame.error as e:
			logger.error(f'[bdude] music err {e}')
			self.snd_bombexplode = None
			self.snd_bombdrop = None

	def network_debug(self, player1):
		_playpos = None
		if not player1.connected:
			return
		else:
			for d in self.dummies:
				dpos = player1.get_netplayer_pos(d.client_id)
				d.pos = dpos
			for np in list(player1.net_players):
				if np == '-1' or np == player1.client_id or np == '-2':
					pass
					# logger.debug(f'[{player1.client_id}] dummies:{len(self.dummies)} not adding {np} == {player1.client_id}')
				else:
				#elif len([k.client_id for k in self.dummies if k.client_id == player1.client_id]) == 0 and len([k.client_id for k in self.dummies if k.client_id == np]) == 0:
				
					try:
						_playpos = player1.net_players[np]
						if _playpos == 0 or _playpos == '0':
							posx = int(_playpos)
							posy = int(_playpos)
						else:
							posx = int(_playpos.split(',')[0].replace('[',''))
							posy = int(_playpos.split(',')[1].replace(']',''))
						d = DummyPlayer(client_id=np, pos=Vector2(posx, posy))
					except (TypeError, IndexError, ValueError) as e:
						logger.error(f'[{player1.client_id}] err {e} np:{np} pp:{_playpos}')
						d = None
						# d = DummyPlayer(client_id=np, pos=Vector2(120,120))
						# logger.debug(f'[{player1.client_id}] {len(self.dummies)} dummy id: {d.client_id} {d}')
					if player1.client_id != '-2' and d is not None and d.client_id != player1.client_id and len([d.client_id for d in self.dummies if np == d.client_id]) == 0:
						self.dummies.add(d)
						logger.debug(f'[{player1.client_id}] dummies: {len(self.dummies)} newdummy id: {d.client_id} {d}')

	def network_handler(self, player1):
		if player1.client_id != '-2':
			pygame.display.set_caption(f'{player1.client_id}')
		if not self.game_ready:
			if player1.got_gamemap:
				self.gamemap.grid = player1.gamemap.grid
				_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
				self.gamemap.place_player(self.gamemap.grid, 0)
				self.game_ready = True

	def update(self):		
		self.players.update(self.blocks)
		self.dummies.update()
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
			flame_coll = spritecollide(flame, self.blocks, False)
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
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.kill()
		# powerblock_coll = spritecollide(self.server.players[0], self.powerups, False)
		# for pc in powerblock_coll:
		# s	pass
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
		self.dummies.draw(self.screen)
		#for dummy in self.dummies:
		#	dummy.draw(self.screen)
		self.flames.draw(self.screen)

		if self.get_input:
			self.textinput.draw(self.screen)

		if self.show_mainmenu and not self.get_input:
			self.game_menu.draw_mainmenu(self.screen)
		self.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=player1, flames=self.flames, dummies=self.dummies)
		if DEBUG:
			draw_debug_sprite(self.screen, self.players)

	def handle_menu(self, selection, player1):
		# mainmenu
		if selection == "Quit":
			self.running = False
		if selection == "Pause":
			self.show_mainmenu ^= True
		if selection == "Start":
			connstatus = player1.connect_to_server()
			logger.debug(f'player connect {connstatus}')
			if connstatus != -3:
				self.show_mainmenu ^= True

		if selection == "Restart":
			self.show_mainmenu ^= True
		if selection == "Start server":
			logger.debug(f'Starting server ...')
		if selection == "Connect to server":
			self.show_mainmenu = False

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
						self.handle_menu(selection, player1)
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
					player1.kill = True
					self.running = False
					# self.player1.stop()
				if event.key == pygame.K_1:
					logger.debug(f'rq:{player1.rq.qsize()} sq:{player1.sq.qsize()} t:{len(enumerate())}')
				if event.key == pygame.K_2:
					logger.debug(f'mapreset')
					self.gamemap = player1.gamemap
					self.blocks.empty()
					_ = [self.blocks.add(Block(gridpos=(j, k), block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
				if event.key == pygame.K_c:
					pass
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
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					player1.vel.x = player1.speed
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					player1.vel.x = -player1.speed
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
	parser.add_argument('--server', default=False, action='store_true', dest='startserver')
	args = parser.parse_args()
	pygame.init()
	mixer.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	mainClock = pygame.time.Clock()
	dt = mainClock.tick(FPS) / 1000
	game = Game(pyscreen, dt)
	game.start()
	game.running = True
	player1 = Player((300, 300), game.dt, 'player1.png')

	game.players.add(player1)
	player1.daemon = True
	player1.start()
	# if args.startserver:
	#	game.show_mainmenu = False
	while game.running:
		# main game loop logic stuff
		game.handle_input(player1)
		game.network_handler(player1)
		game.network_debug(player1)
		pygame.event.pump()
		game.update()
		game.draw()
	logger.debug(f'game end {game.running} {player1.kill}')
	player1.kill = True
	player1.socket.close()
	pygame.quit()
