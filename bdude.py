# bomberdude
import asyncio
import random
from threading import Thread
import pygame
from pygame.math import Vector2
from pygame import mixer  # Load the popular external library
from loguru import logger
from debug import (
	draw_debug_sprite,
	draw_debug_block
)
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE
from globals import Block, Bomb, Powerup
from globals import DEBUG
from globals import get_angle
from player import Player
from menus import Menu
from net.bombserver import ServerThread

class Game(Thread):
	def __init__(self, screen, game_dt):
		Thread.__init__(self)
		self.kill = False
		self.dt = game_dt
		self.screen = screen
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pygame.Color("black")
		self.show_mainmenu = True
		self.running = False
		self.show_panel = True
		self.particles = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.powerups = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.server = ServerThread(name='gameserver', dt=self.dt)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		try:
			self.snd_bombexplode = mixer.Sound('data/bomb.mp3')
			self.snd_bombdrop = mixer.Sound('data/bombdrop.mp3')
		except pygame.error as e:
			logger.debug(f'[bdude] music err {e}')
			self.snd_bombexplode = None
			self.snd_bombdrop = None

	def update(self):
		self.server.players.update(self.server.blocks)
		self.bombs.update()
		for bomb in self.bombs:
			bomb.dt = pygame.time.get_ticks() / 1000
			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
				bomb.gen_flames()
				self.flames.add(bomb.flames)
				bomb.bomber_id.bombs_left += 1
				bomb.kill()
				#self.server.players[0].bombs_left += 1
				try:
					mixer.Sound.play(self.snd_bombexplode)
				except (AttributeError, TypeError) as e: logger.debug(f'[bdude] {e}')
		self.flames.update()
		for flame in self.flames:
			flame_coll = pygame.sprite.spritecollide(flame, self.server.blocks, False)
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
			blocks = pygame.sprite.spritecollide(particle, self.server.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.kill()
		# powerblock_coll = pygame.sprite.spritecollide(self.server.players[0], self.powerups, False)
		# for pc in powerblock_coll:
		#s	pass
			# self.server.players[0].take_powerup(powerup=random.choice([1, 2, 3]))
			# pc.kill()

		self.particles.update(self.server.blocks)
		self.server.blocks.update(self.server.blocks)
		self.powerups.update()

	def draw(self):
		# draw on screen
		pygame.display.flip()
		self.screen.fill(self.bg_color)
		self.server.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.powerups.draw(self.screen)
		self.particles.draw(self.screen)
		self.server.players.draw(self.screen)
		self.flames.draw(self.screen)

		if self.show_mainmenu:
			self.game_menu.draw_mainmenu(self.screen)
		# self.game_menu.draw_panel(blocks=self.server.blocks, particles=self.particles, player1=self.server.players[0], flames=self.flames)
		# self.game_menu.draw_server_debug(server=self.server, netplayers=self.netplayers)
		if DEBUG:
			draw_debug_sprite(self.screen, self.server.players)

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Quit":
			self.running = False
		if selection == "Pause":
			self.show_mainmenu ^= True
		if selection == "Start":
			self.show_mainmenu ^= True
		if selection == "Restart":
			self.show_mainmenu ^= True
		if selection == "Start server":
			logger.debug(f'Starting server ...')
			self.start_server()
		if selection == "Connect to server":
			pass
			# self.server.players[0].playerconnect()

	def handle_input(self, player1):
		# get player input
		for event in pygame.event.get():
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu:  # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					else:
						b = self.server.player_action(player1, 'b')
						if b != 0:
							self.bombs.add(b)
						# self.bombdrop(self.server.players[0])
				if event.key == pygame.K_ESCAPE:
					self.show_mainmenu ^= True
				if event.key == pygame.K_q:
					self.running = False
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
						#player1.vel.y = player1.speed
						self.server.player_action(player1, action=f'd')
						# self.server.players[0].vel.y = self.server.players[0].speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						#player1.vel.y = -player1.speed
						self.server.player_action(player1, action=f'u')
						# self.server.players[0].vel.y = -self.server.players[0].speed
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					#player1.vel.x = player1.speed
					self.server.player_action(player1, action=f'r')
					# self.server.players[0].vel.x = self.server.players[0].speed
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					#player1.vel.x = -player1.speed
					self.server.player_action(player1, action=f'l')
					# self.server.players[0].vel.x = -self.server.players[0].speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s} and not self.show_mainmenu:
					player1.vel.y = 0
					# self.server.player_action(player1, action='vel:y:0')
					# self.server.players[0].vel.y = 0
				if event.key in {pygame.K_UP, pygame.K_w} and not self.show_mainmenu:
					player1.vel.y = 0
					# self.server.player_action(player1, action='vel:y:0')
					# self.server.players[0].vel.y = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					player1.vel.x = 0
					# self.server.player_action(player1, action='vel:x:0')
					# self.server.players[0].vel.x = 0
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					player1.vel.x = 0
					# self.server.player_action(player1, action='vel:x:0')
					# self.server.players[0].vel.x = 0
			if event.type == pygame.QUIT:
				self.running = False


if __name__ == "__main__":
	pygame.init()
	mixer.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	mainClock = pygame.time.Clock()
	dt = mainClock.tick(FPS) / 1000
	game = Game(pyscreen, dt)
	game.start()
	game.running = True
	game.server.start()
	game.server.gamemap = game.server.generate_map()
	startpos = game.server.place_player(location=0)
	player1 = Player(startpos, game.dt, 'player1.png')
	game.server.add_player(player1)
	game.server.init_blocks()
	# game.server.clear_spot()
	while game.running:
		# main game loop logic stuff
		game.handle_input(player1)
		# pygame.event.pump()
		player1.Loop()
		game.update()
		game.draw()
		
		# game.net_draw()
	game.server.kill = True
	pygame.quit()
