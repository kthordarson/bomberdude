# bomberdude
# TODO
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import os
import random

import pygame

from globals import Block, Particle, Bomb, Player, Gamemap, Flame
from globals import BLOCKSIZE, FPS, GRIDSIZE, GRIDSIZE, SCREENSIZE
from globals import get_angle, get_entity_angle
from globals import DEBUG
from menus import Menu



class Game:
	def __init__(self, screen=None):
		# pygame.display.set_mode((GRIDSIZE[0] * BLOCKSIZE + BLOCKSIZE, GRIDSIZE[1] * BLOCKSIZE + panelsize), 0, 32)
		self.screen = screen
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pygame.Color("black")
		self.show_mainmenu = True
		self.running = False
		self.show_panel = True
		self.gamemap = Gamemap()
		self.blocks = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.players = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.powerups = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.player1 = Player(pos=self.gamemap.place_player(), player_id=33)

	def init(self):
		self.gamemap = Gamemap()	
		self.gamemap.generate()
		self.blocks = pygame.sprite.Group()
		self.players = pygame.sprite.Group()
		self.particles = pygame.sprite.Group()
		self.powerups = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.flames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		# foo = self.gamemap.place_player()
		# self.player1 = Player(pos=self.gamemap.place_player(), player_id=33)
		self.player1 = Player(pos=self.gamemap.place_player(), player_id=33)
		[self.blocks.add(Block(gridpos=(j, k),block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
		self.players.add(self.player1)

	def update(self):
		# todo network things
		#[player.update(self.blocks) for player in self.players]
		self.players.update(self.blocks)
		self.bombs.update()
		for bomb in self.bombs:
			if bomb.explode:
				[self.flames.add(flames) for flames in bomb.get_flames()]
		self.flames.update()
		flame_colls = pygame.sprite.groupcollide(self.blocks, self.flames, False, False)
		for block, flames in flame_colls.items():
			if block.solid:
				[flame.flamecollide(block) for flame in flames]
				[block.take_damage(flame) for flame in flames]
				self.particles.add(block.particles)
		self.particles.update(self.blocks)
				#block.hit = True
				#[self.particles.add(block.particles) for ]
				# print(f'[coll] b:{block} f:{flame}')
		# self.bombsflames.update(self.blocks)
		# [flame.check_coll(self.blocks) for flame in self.bombsflames]

	def set_block(self, x, y, value):
		self.gamemap.grid[x][y] = value

	def terminate(self):
		os._exit(1)

	def bombdrop(self, player):
		bombpos = pygame.math.Vector2((player.rect.centerx, player.rect.centery))
		bomb = Bomb(pos=bombpos, bomber_id=player.player_id, bomb_power=player.bomb_power)
		# print(f'[bombdrop] b:{bomb.rect} p:{player.rect} bp:{bombpos}')
		self.bombs.add(bomb)
		# player.bombs_left -= 1
		x = int(player.rect.centerx // BLOCKSIZE[0])
		y = int(player.rect.centery // BLOCKSIZE[1])
		self.gamemap.set_block(x, y, 0)

	def draw(self):
		# draw on screen
		pygame.display.flip()
		self.screen.fill(self.bg_color)
		# self.bombsflames.draw(self.screen)
		self.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.powerups.draw(self.screen)
		self.particles.draw(self.screen)
		self.players.draw(self.screen)
		for bomb in self.bombs:
			if bomb.explode:
				self.flames.draw(self.screen)
#		for block in self.blocks:

		if self.show_mainmenu:
			self.game_menu.draw_mainmenu(self.screen)
		if DEBUG:
			self.game_menu.draw_debug_sprite(self.screen, self.players)
			for block in self.blocks:
				if block.hit:
					self.game_menu.draw_debug_sprite(self.screen, self.particles)
			# self.game_menu.draw_debug_sprite(self.screen, self.bombs)
			# self.game_menu.draw_debug_blocks(self.screen, self.blocks, self.gamemap)
			for bomb in self.bombs:
				if bomb.explode:
					self.game_menu.draw_debug_sprite(self.screen, bomb.flames)
			self.game_menu.draw_panel(gamemap=self.gamemap, blocks=self.blocks, particles=self.particles, player1=self.player1)

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Quit":
			self.running = False
			self.terminate()
		if selection == "Pause":
			self.show_mainmenu ^= True
		if selection == "Start":
			self.show_mainmenu ^= True
		if selection == "Restart":
			self.show_mainmenu ^= True
		if selection == "Start server":
			pass
		if selection == "Connect to server":
			pass

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
					if not self.show_mainmenu:
						self.running = False
						# break
						self.terminate()
					else:
						self.show_mainmenu ^= True
				if event.key == pygame.K_c:
					self.player1.bomb_power = 100
					self.player1.max_bombs = 10
					self.player1.bombs_left = 10
					self.player1.speed = 10
				if event.key == pygame.K_p:
					self.show_panel ^= True
				if event.key == pygame.K_m:
					pass
					# self.paused ^= True
				if event.key == pygame.K_q:
					pass
					# DEBUG ^= True
				if event.key == pygame.K_g:
					pass
					# DEBUG = False
					# DEBUG_GRID ^= True
				if event.key == pygame.K_r:
					pass
					# game_init()
				if event.key in set([pygame.K_DOWN, pygame.K_s]):
					if self.show_mainmenu:
						self.game_menu.menu_down()
					else:
						self.player1.vel.y = self.player1.speed
				if event.key in set([pygame.K_UP, pygame.K_w]):
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						self.player1.vel.y = -self.player1.speed
				if event.key in set([pygame.K_RIGHT, pygame.K_d]) and not self.show_mainmenu:
					#if not self.show_mainmenu:
					self.player1.vel.x = self.player1.speed
				if event.key in set([pygame.K_LEFT, pygame.K_a]) and not self.show_mainmenu:
					#if not self.show_mainmenu:
					self.player1.vel.x = -self.player1.speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in set([pygame.K_DOWN, pygame.K_s]):
					if not self.show_mainmenu:
						self.player1.vel.y = 0
				if event.key in set([pygame.K_UP, pygame.K_w]):
					if not self.show_mainmenu:
						self.player1.vel.y = 0
				if event.key in set([pygame.K_RIGHT, pygame.K_d]):
					if not self.show_mainmenu:
						self.player1.vel.x = 0
				if event.key in set([pygame.K_LEFT, pygame.K_a]):
					if not self.show_mainmenu:
						self.player1.vel.x = 0
			if event.type == pygame.MOUSEBUTTONDOWN:
				mousex, mousey = pygame.mouse.get_pos()
				gridx = mousex // BLOCKSIZE[0]
				gridy = mousey // BLOCKSIZE[1]
				# blockinf = self.gamemap.get_block_real(mousex, mousey)
				print(f"mouse x:{mousex} y:{mousey} [gx:{gridx} gy:{gridy}] |  b:{self.gamemap.get_block(gridx, gridy)} ")
				# print(f"mouse x:{mousex} y:{mousey} [x:{mousex//BLOCKSIZE[0]} y:{mousey//BLOCKSIZE[1]}]|  b:{self.gamemap.get_block(mousex // GRIDSIZE[0], mousey // GRIDSIZE[1])} ")
			if event.type == pygame.QUIT:
				self.running = False


async def main_loop(game=None):
	mainClock = pygame.time.Clock()
	while True:
		# main game loop logic stuff
		dt = mainClock.tick(FPS) / 1000
		pygame.event.pump()
		game.handle_input()
		game.update()
		game.draw()

if __name__ == "__main__":
	pygame.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)	
	game = Game(screen=pyscreen)
	game.init()
	game_task = asyncio.Task(main_loop(game))
	try:
		game.gameloop.run_until_complete(game_task)
	finally:
		pygame.quit()
