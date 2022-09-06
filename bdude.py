#!/bin/python3.9
# bomberdude
import sys
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
from constants import DEBUG,DEBUGFONTCOLOR,DEFAULTFONT,GRIDSIZE,BLOCKSIZE,SCREENSIZE,FPS,DEFAULTGRID
from menus import Menu, DebugDialog
from player import Player
from threading import Thread
from queue import Empty, Queue
from netutils import DataReceiver, DataSender, data_identifiers
from bombserver import ServerThread


def add_input(input_queue):
    while True:
        input_queue.put(sys.stdin.read(1))

class GameGUI():
	def __init__(self):
		pass

class GameClient():
	def __init__(self):
		pass
class GameServer():
	def __init__(self):
		pass

class Engine(Thread):
	def __init__(self):
		Thread.__init__(self, name='engine')
		#pygame.init()
		self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
		self.dt = pygame.time.Clock().tick(FPS) / 1000
		self.gamemap = Gamemap(genmap=True)
		self.queue = Queue()
		self.game = Game(screen=self.screen, game_dt=self.dt, gamemap=self.gamemap, enginequeue=self.queue)
		self.gui = None
		self.gameclient = None
		self.gameserver = None
		self.running = False
	
	def poll(self):
		return self.dt

	def kill_engine(self, killmsg=None):
		self.running = False
		if killmsg:
			logger.debug(f'[engine] killed {killmsg}')
		#self.kill()
		#pygame.quit()

	def run(self):
		while True:
			if self.running:
				self.game.handle_input()
				self.game.update()
				self.game.draw()
				enginemsg = None
				try:
					enginemsg = self.queue.get_nowait()
				except Empty:
					pass
				if enginemsg:
					logger.info(f'[engine] got msg {enginemsg}')
					self.queue.task_done()
					self.kill_engine(killmsg=f'killed by q msg:{enginemsg}')
					break



class Game(Thread):
	def __init__(self, screen=None, game_dt=None, gamemap=None, enginequeue=None):
		Thread.__init__(self, name='game')
		self.enginequeue = enginequeue
		self.kill = False
		self.dt = game_dt
		self.screen = screen
		self.bg_color = pygame.Color("black")
		self.show_mainmenu = True
		self.running = False
		self.show_panel = True
		self.blocks = Group()
		self.players = Group()
		self.playerone = Player(pos=(300, 300), image='data/playerone.png')
		self.players.add(self.playerone)
		self.particles = Group()
		self.powerups = Group()
		self.bombs = Group()
		self.flames = Group()
		self.game_menu = Menu(self.screen)
		self.debug_dialog = DebugDialog(self.screen)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.rm = ResourceHandler()
		self.gamemap = gamemap
		# self.mapgrid = []
		self.gameserver = None
		self.server_mode = False
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		if DEBUG:
			self.debugfont = pygame.freetype.Font(DEFAULTFONT, 10)

	def update_bombs(self):
		self.bombs.update()
		for bomb in self.bombs:
			bomb.dt = pygame.time.get_ticks() / 1000
			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:				
				self.flames.add(bomb.gen_flames())
				bomb.bomber_id.bombs_left += 1
				bomb.kill()
				#self.bombs.remove(bomb)

	def update_flames(self):
		self.flames.update()
		for flame in self.flames:
			# check if flame collides with blocks
			flame_coll = spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if block.permanent:
					flame.kill()
				elif block.solid:
					if block.block_type in range(1,10):
						# types 1 and 2 create powerups						
						powerup = Powerup(pos=block.rect.center, reshandler=self.rm)
						if powerup.powertype != 0:
							self.powerups.add(powerup)
						pos, gridpos, particles = block.hit(flame)
						newblock = Block(pos, gridpos, block_type=0, reshandler=self.rm)
						self.gamemap.set_block(gridpos[0], gridpos[1], 0)
						self.particles.add(particles)
						flame.kill()
						block.kill()
						self.blocks.add(newblock)

	def update_particles(self):
		self.particles.update(self.blocks)
		for particle in self.particles:
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.hit()
					#self.particles.remove(particle)

	def update_powerups(self, player):
		self.powerups.update()
		powerblock_coll = spritecollide(player, self.powerups, False)
		for pc in powerblock_coll:
			# logger.debug(f'[pwrb] type:{pc.powertype} colls:{len(powerblock_coll)} sp:{len(self.powerups)}')
			player.take_powerup(pc.powertype)
			pc.kill()

	def update(self):
		self.players.update(self.blocks)
		self.update_bombs()
		self.update_flames()
		self.update_particles()
		self.update_powerups(self.playerone)
		

	def reset_map(self, reset_grid=False):
		# Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
		if reset_grid:
			self.gamemap.grid = DEFAULTGRID # self.gamemap.place_player(location=0, grid=self.gamemap.grid)
		self.blocks.empty()
		idx = 0
		for k in range(0, GRIDSIZE[0] ):
			for j in range(0, GRIDSIZE[1] ):
				newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=self.gamemap.grid[j][k], reshandler=self.rm)
				self.blocks.add(newblock)
			idx += 1
		logger.debug(f'[rm] r:{reset_grid} blks:{len(self.blocks)}')

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
		self.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=self.playerone, flames=self.flames)
		if DEBUG:
			pos = Vector2(10, self.screenh - 10)
			self.debugfont.render_to(self.screen, pos, f"blk:{len(self.blocks)} pups:{len(self.powerups)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)}", self.font_color)
			for block in self.blocks:
				self.debugfont.render_to(self.screen, block.rect.center, f"{block.block_type}", (150,150,150))
			for block in self.powerups:
				self.debugfont.render_to(self.screen, block.rect.center+(0,5), f"p:{block.time_left:.1f}", (190,190,190))
				

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			self.show_mainmenu ^= True
			self.reset_map(reset_grid=True)

		if selection == "Connect to server":
			pass

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

	def handle_input(self):
		events = pygame.event.get()
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu: # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					elif not self.show_mainmenu:
						b = self.playerone.bombdrop()
						if b != 0:
							self.bombs.add(b)
				if event.key == pygame.K_ESCAPE:
					self.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.playerone.kill = True
					self.running = False
					self.enginequeue.put('quit')
					# pygame.quit()
				if event.key == pygame.K_1:
					pass
				if event.key == pygame.K_2:
					pass
				if event.key == pygame.K_c:
					pass
				if event.key == pygame.K_f:
					pass
				if event.key == pygame.K_p:
					self.show_panel ^= True
				if event.key == pygame.K_m:
					self.reset_map(reset_grid=True)
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
						self.playerone.vel.y = self.playerone.speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						self.playerone.vel.y = -self.playerone.speed
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					# if not self.show_mainmenu:
					self.playerone.vel.x = self.playerone.speed
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					# if not self.show_mainmenu:
					self.playerone.vel.x = -self.playerone.speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s}:
					self.playerone.vel.y = 0
				if event.key in {pygame.K_UP, pygame.K_w}:
					self.playerone.vel.y = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					self.playerone.vel.x = 0
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					self.playerone.vel.x = 0
			if event.type == pygame.QUIT:
				logger.debug(f'[pgevent] quit {event.type}')
				self.running = False
		# if event_type == pygame.MOUSEBUTTONDOWN:
		#	mousex, mousey = pygame.mouse.get_pos()

if __name__ == "__main__":
	pygame.init()
	engine = Engine()
	engine.daemon = True
	engine.start()
	input_queue = Queue()
	input_thread = Thread(target=add_input, args=(input_queue,))
	input_thread.daemon = True
	input_thread.start()
	engine.running = True
	while engine.is_alive():
		last_update = time.time()
		try:
			#if not input_queue.empty():
			cmd = None
			try:
				cmd = input_queue.get_nowait()
			except Empty:
				pass
			if cmd:
				print(f'[ipq] {cmd}')
				if cmd == 's':
					pass
			elif not engine.running:
				logger.debug(f'[main] engine run stop {engine.running} {engine}')
				break
					#engine.running = True
#			cmd = input('> ')
#			if cmd[:1] == 's':
#				engine.running = True
		except KeyboardInterrupt as e:
			print(f'[kb] {e}')
			engine.kill_engine(killmsg=f'killed by {e}')

	


    
    # while True:

    #     if time.time()-last_update>0.5:
    #         sys.stdout.write(".")
    #         last_update = time.time()

    #     if not input_queue.empty():
    #         print "\ninput:", input_queue.get()

	# parser = ArgumentParser(description='bomberdude')
	# parser.add_argument('--server', default=False, action='store_true', dest='startserver')
	# args = parser.parse_args()
	# pygame.init()

	# mixer.init()
	#pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
	# mainClock = pygame.time.Clock()
	# dt = mainClock.tick(FPS) / 1000
	# mainmap = Gamemap(genmap=True)
	# game = Game(screen=pyscreen, game_dt=dt, gamemap=mainmap)
	# game.start()
	# game.running = True
	#playerone = Player(pos=(300, 300), image='data/playerone.png')

	#game.players.add(playerone)
	#playerone.daemon = True
	#playerone.start()
	# while game.running:
	# 	# main game loop logic stuff
	# 	game.handle_input()
	# 	game.update()
	# 	game.draw()

	# pygame.quit()
