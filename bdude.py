# bomberdude

import asyncio
import random
# import threading
import pygame
from pygame.math import Vector2
from pygame import mixer  # Load the popular external library

from debug import (
	draw_debug_sprite,
	draw_debug_block
)
from globals import FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT, BLOCKSIZE
from globals import Block, Bomb, Gamemap, Powerup
from globals import DEBUG
from globals import get_angle
from player import Player
from menus import Menu
from net.bombserver import UDPServer
# from net.bombserver import UDPServer
# from net.bombclient import UDPClient

mixer.init()

class Game:

	def __init__(self, screen=None, game_dt=None):
		# pygame.display.set_mode((GRIDSIZE[0] * BLOCKSIZE + BLOCKSIZE, GRIDSIZE[1] * BLOCKSIZE + panelsize), 0, 32)
		self.dt = game_dt
		self.screen = screen
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pygame.Color("black")
		self.show_mainmenu = True
		self.running = False
		self.show_panel = True
		self.gamemap = Gamemap()
		self.gamemap.grid = self.gamemap.generate()
		self.blocks = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.players = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.powerups = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.player1 = Player(pos=self.gamemap.place_player(location=0),  dt=self.dt, image='player1.png', bot=False)
		_ = [self.blocks.add(Block(gridpos=(j, k), dt=self.dt, block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
		self.players.add(self.player1)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.music_menu()
		self.snd_bombexplode = mixer.Sound('data/bomb.mp3')
		self.snd_bombdrop = mixer.Sound('data/bombdrop.mp3')
		self.server = UDPServer()
		self.server_thread = None
		self.netplayers = []

	def update(self):
		# [player.update(self.blocks) for player in self.players]
		if self.server.running and len(self.server.clients) <= 1:
			clients = self.server.get_clients()
			if len(clients) >= 1:
				try:
					for client in clients:
						# send netupdate to clients
						if client in str(self.netplayers):
							print(f'[update] {self.server.clients[client]} - {client}')
						else:
							netplayer = Player(pos=self.server.clients[client].pos, dt=self.dt, image='player1.png', bot=False)
							netplayer.set_clientid(client)
							self.netplayers.append(netplayer)
						# print(f'[CN] id: {client} ip: {self.server.clients[client].ipaddress} {self.server.clients[client].inpackets}|{self.server.clients[client].outpackets} pos:{self.server.clients[client].pos}')
				except RuntimeError as e:
					print(f'[update] ERR {e}')
		self.players.update(self.blocks)
		_ = [player.move(self.blocks, dt) for player in self.players]
		_ = [player.bot_move(self.blocks, dt) for player in self.players if player.bot]
		self.bombs.update()
		for bomb in self.bombs:
			bomb.dt = pygame.time.get_ticks() / 1000
			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
				bomb.gen_flames()
				self.flames.add(bomb.flames)
				bomb.kill()
				self.player1.bombs_left += 1
				mixer.Sound.play(self.snd_bombexplode)
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
		powerblock_coll = pygame.sprite.spritecollide(self.player1, self.powerups, False)
		for pc in powerblock_coll:
			self.player1.take_powerup(powerup=random.choice([1, 2, 3]))
			pc.kill()

		self.particles.update(self.blocks)
		self.blocks.update(self.blocks)
		self.powerups.update()

	def music_menu(self):
		mixer.music.stop()
		mixer.music.load('data/2021-03-26-bdosttest.mp3')
		# mixer.music.play()

	def music_game(self):
		mixer.music.stop()
		mixer.music.load('data/2021-03-26-bdosttest2.mp3')
		# mixer.music.play()

	def set_block(self, x, y, value):
		self.gamemap.grid[x][y] = value

	def bombdrop(self, player):
		if player.bombs_left > 0:
			bombpos = Vector2((player.rect.centerx, player.rect.centery))
			bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=player.client_id, bomb_power=player.bomb_power)
			self.bombs.add(bomb)
			player.bombs_left -= 1
			# mixer.Sound.play(self.snd_bombdrop)

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
		self.game_menu.draw_panel(blocks=self.blocks, particles=self.particles,player1=self.player1, flames=self.flames)
		self.game_menu.draw_server_debug(server=self.server, netplayers=self.netplayers)
		if DEBUG:
			# debug_draw_mouseangle(self.screen, self.player1)
			# debug_mouse_particles(self.screen, self.particles)
			# draw_debug_sprite(self.screen, self.particles)
			draw_debug_sprite(self.screen, self.players)

	# draw_debug_sprite(self.screen, self.flames)
	# draw_debug_particles(self.screen, self.particles, self.blocks)
	# draw_debug_sprite(self.screen, self.bombs)
	# draw_debug_blocks(self.screen, self.blocks, self.gamemap, self.particles)

	def start_server(self):
		pass
		# self.server.configure_server()
		# self.server_thread = threading.Thread(target=self.server.wait_for_client, daemon=True)
		# self.server.running = True
		# self.server_thread.start()

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Quit":
			if self.server.running:
				self.server.running = False
				self.server_thread.join()
				self.server_thread = None
			self.running = False
		if selection == "Pause":
			self.show_mainmenu ^= True
			self.music_menu()
		if selection == "Start":
			self.show_mainmenu ^= True
			if self.server.running:
				self.player1.connect()
			self.music_game()
		if selection == "Restart":
			self.show_mainmenu ^= True
			self.music_game()
		if selection == "Start server":
			print(f'[SRV] Starting server ...')
			self.start_server()
		if selection == "Connect to server":
			print(f'[SRV] Connecting to server ...')
			self.player1.client.Connect()


	def handle_input(self):
		# get player input
		for event in pygame.event.get():
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu:  # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					else:
						self.bombdrop(self.player1)
				if event.key == pygame.K_ESCAPE:
					self.show_mainmenu ^= True
				# if not self.show_mainmenu:
				# 	self.running = False
				# else:
				# 	self.show_mainmenu ^= True
				if event.key == pygame.K_q:
					self.running = False
				if event.key == pygame.K_1:
					_ = [particle.stop() for particle in self.particles]
				if event.key == pygame.K_2:
					_ = [particle.move() for particle in self.particles]
				if event.key == pygame.K_3:
					_ = [particle.set_vel() for particle in self.particles]
				if event.key == pygame.K_4:
					_ = [particle.set_vel(Vector2(1, 1)) for particle in self.particles]
				if event.key == pygame.K_5:
					_ = [particle.kill() for particle in self.particles]
				if event.key == pygame.K_c:
					self.player1.bomb_power = 100
					self.player1.max_bombs = 10
					self.player1.bombs_left = 10
					self.player1.speed = 7
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
						self.player1.vel.y = self.player1.speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						self.player1.vel.y = -self.player1.speed
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					self.player1.vel.x = self.player1.speed
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					# if not self.show_mainmenu:
					self.player1.vel.x = -self.player1.speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s} and not self.show_mainmenu:
					self.player1.vel.y = 0
				if event.key in {pygame.K_UP, pygame.K_w} and not self.show_mainmenu:
					self.player1.vel.y = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
					self.player1.vel.x = 0
				if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
					self.player1.vel.x = 0
			if event.type == pygame.MOUSEBUTTONDOWN:
				mousex, mousey = pygame.mouse.get_pos()
				gridx = mousex // BLOCKSIZE[0]
				gridy = mousey // BLOCKSIZE[1]
				angle = get_angle(self.player1.pos, pygame.mouse.get_pos())
				angle2 = get_angle(pygame.mouse.get_pos(), self.player1.pos)
				print(f"mouse x:{mousex} y:{mousey} [gx:{gridx} gy:{gridy}] |  b:{self.gamemap.get_block(gridx, gridy)} a:{angle:.1f} a2:{angle2:.1f}")
				print(f"mouse x:{mousex} y:{mousey} [x:{mousex//BLOCKSIZE[0]} y:{mousey//BLOCKSIZE[1]}]|  b:{self.gamemap.get_block(mousex // GRIDSIZE[0], mousey // GRIDSIZE[1])} ")
			# blockinf = self.gamemap.get_block_real(mousex, mousey)
			if event.type == pygame.QUIT:
				self.running = False


if __name__ == "__main__":
	pygame.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	game = Game(screen=pyscreen)
	mainClock = pygame.time.Clock()
	dt = mainClock.tick(FPS) / 1000
	game.running = True
	while game.running:
		# main game loop logic stuff
		game.handle_input()
		pygame.event.pump()
		game.update()
		game.draw()
	pygame.quit()
