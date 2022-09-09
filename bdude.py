#!/bin/python3.9
# bomberdude
import sys
import socket
import time
from random import randint
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
# from pygame import mixer # Load the popular external library
from things import Block, Powerup
from map import Gamemap
from globals import ResourceHandler
from constants import DEBUG, DEBUGFONTCOLOR, GRIDSIZE, BLOCKSIZE, SCREENSIZE, FPS, DEFAULTGRID
from menus import Menu, DebugDialog
from player import Player
from threading import Thread, Event
import threading
from queue import Empty, Queue
# from testclient import BombClient
# from bombserver import BombServer


def add_input(inputqueue):
	while True:
		inputqueue.put(sys.stdin.read(1))


class GameGUI:
	def __init__(self, screen, font):
		self.screen = screen
		self.show_mainmenu = True
		self.blocks = Group()
		self.game_menu = Menu(self.screen, font)
		self.debug_dialog = DebugDialog(self.screen, font)
		# self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()

	# self.debugfont = pygame.freetype.Font(DEFAULTFONT, 10)

	def draw(self):
		pass


class GameClient:
	def __init__(self):
		pass


class GameServerDummy:
	def __init__(self, *args, **kwargs):
		self.clients = []
		self.clist = []

	def get_clients(self):
		return []
	def get_client_count(self):
		return 0
	def start(self):
		pass


class Engine(Thread):
	def __init__(self, stop_event=None, name=None):
		Thread.__init__(self, name=name, args=(stop_event,))
		pygame.init()
		self.name = name
		self.stop_event = stop_event
		self.font = pygame.freetype.Font("data/DejaVuSans.ttf", 12)
		self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
		self.dt = pygame.time.Clock()
		self.gamemap = Gamemap(genmap=False)
		self.enginequeue = Queue()
		self.serverqueue = Queue()
		self.rm = ResourceHandler()
		self.game = Game(screen=self.screen, game_dt=self.dt, gamemap=self.gamemap, enginequeue=self.enginequeue, serverqueue=self.serverqueue, rm=self.rm, font=self.font, stop_event=stop_event)
		self.running = False
		self.kill = False

	def __repr__(self):
		return f'[engine] running:{self.running} kill:{self.kill}'

	def kill_engine(self, killmsg=None):
		threads = [t for t in threading.enumerate()]
		for t in threads:
			logger.info(f'[engine] thread:{t} active:{threading.active_count()} tl:{len(threads)} tle:{len(threading.enumerate())}')
			try:
				if t.name != 'engine':
					t.join(0)
			except RuntimeError as e:
				logger.error(f'[engine] {e} failed to join {t} active:{threading.active_count()} tl:{len(threads)} tle:{len(threading.enumerate())}')

	def engine_init(self):	
		pass

	def network_update(self):
		clients = self.game.get_players()
		# logger.debug(f'[engine] clients:{len(clients)}')

	def run(self):
		while True:
			if self.kill or self.stop_event.is_set():
				self.kill_engine(killmsg=f'killed by kill signal r:{self.running}')
				return
			self.game.handle_input()
			self.game.update()
			self.game.draw()
			self.network_update()
			enginemsg = None
			try:
				enginemsg = self.enginequeue.get_nowait()
			except Empty:
				pass
			if enginemsg:
				logger.info(f'[engine] got msg {enginemsg}')
				self.enginequeue.task_done()
				if enginemsg == 'quit':
					self.kill_engine(killmsg=f'killed by q msg:{enginemsg} r:{self.running}')
					self.running = False
					break
				if enginemsg == 'reset_map':
					newblocks = self.reset_map(reset_grid=False)
					response = {'blocks': newblocks}
					logger.debug(f'[e] msg:{enginemsg} resp:{response}')
					self.game.gamequeue.put(response)

	def reset_map(self, reset_grid=False):
		# Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
		if reset_grid:
			self.gamemap.grid = DEFAULTGRID  # self.gamemap.place_player(location=0, grid=self.gamemap.grid)
		# self.blocks.empty()
		# idx = 0
		newblocks = Group()
		for k in range(0, GRIDSIZE[0]):
			for j in range(0, GRIDSIZE[1]):
				newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=self.gamemap.grid[j][k], reshandler=self.rm)
				newblocks.add(newblock)
		return newblocks


class Game(Thread):
	def __init__(self, screen=None, game_dt=None, gamemap=None, enginequeue=None, serverqueue=None, rm=None, font=None, stop_event=None):
		Thread.__init__(self, name='game', args=(stop_event,))
		self.enginequeue = enginequeue
		self.serverqueue = serverqueue
		self.gamequeue = Queue()
		self.kill = False
		self.dt = game_dt
		self.screen = screen
		self.font = font
		self.gui = GameGUI(self.screen, font)
		self.bg_color = pygame.Color("black")
		self.running = False
		self.all_sprites = []
		self.blocks = Group()
		self.all_sprites.append(self.blocks)
		self.players = Group()
		self.all_sprites.append(self.players)
		self.netplayers = Group()
		self.all_sprites.append(self.netplayers)
		self.particles = Group()
		self.all_sprites.append(self.particles)
		self.powerups = Group()
		self.all_sprites.append(self.powerups)
		self.bombs = Group()
		self.all_sprites.append(self.bombs)
		self.flames = Group()
		self.all_sprites.append(self.flames)
		self.playerone = Player(pos=(300, 300), image='data/playerone.png', stop_event=stop_event)
		self.players.add(self.playerone)
		# self.gameclient = BombClient(name=self.playerone.client_id, stop_event=stop_event, playerone=self.playerone)
		#self.gameserver = BombServer(name=f'bombserver-{self.playerone.client_id}', serverqueue=self.serverqueue, enginequeue=self.enginequeue, stop_event=stop_event)
		# self.gameserver = GameServerDummy()
		self.is_server = False
		self.gamemap = gamemap
		# self.mapgrid = []
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.rm = rm
		
		#= [(self.blocks, self.players, self.netplayers, self.particles, self.powerups, self.bombs, self.flames)]
		

	def __repr__(self):
		return f'[game] {self.name}'

	def update_players(self):
		pass
		# players = self.gameserver.get_clients()
		# local_ids = [k.clid for k in players]
		# for p in players:
		# 	# logger.debug(f'[GP] p:{len(players)} lids:{len(local_ids)} player:{p}')
		# 	if p.clid not in local_ids:
		# 		np = Player(pos=(300, 300), image='data/netplayer.png', client_id=p.clid)
		# 		self.netplayers.add(p)
		# 		logger.debug(f'[GP] adding player p:{p} np:{np} players:{len(players)} lids:{len(local_ids)} netplayers:{len(self.netplayers)}')
		# 	else:
		# 		logger.warning(f'[GP] not adding player p:{p} players:{len(players)} lids:{len(local_ids)} netplayers:{len(self.netplayers)}')
		# 		logger.info(f'[GP] lids: {local_ids}')
		# logger.debug(f'[G] get_players:{len(players)}')

	def get_players(self):
		pass
		#players = self.gameserver.get_clients()
		#return players

	def update_bombs(self):
		self.bombs.update()
#		qtemp = [b.thingq.qsize() for b in self.bombs]
#		if len(qtemp) > 0:
#			logger.debug(f'[btq] q:{qtemp}')
		for bomb in self.bombs:
			# logger.debug(f'[btq] b:{bomb} q:{bomb.thingq.qsize()}')
			if not bomb.thingq.empty():
				bmsg = bomb.thingq.get_nowait()
				self.flames = bmsg.get('flames')
				bomb.thingq.task_done()
				#logger.debug(f'[btq] {flames} q:{bomb.thingq.qsize()}')
				bomb.kill()

#			bomb.dt = pygame.time.get_ticks()
#			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
#				self.flames.add(bomb.gen_flames())
#				bomb.bomber_id.bombs_left += 1
#				bomb.kill()

	def update_flames(self):
		self.flames.update()
		for flame in self.flames:
			# check if flame collides with blocks
			flame_coll = spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if block.block_type != 0:
					pos, gridpos, particles = block.hit(flame)
					self.particles.add(particles)
					flame.kill()
				if block.permanent:
					flame.kill()
				elif block.solid:
					if block.block_type in range(1, 10):
						# types 1 and 2 create powerups
						powerup = Powerup(pos=block.rect.center, reshandler=self.rm)
						if powerup.powertype != 0:
							self.powerups.add(powerup)

						newblock = Block(pos, gridpos, block_type=0, reshandler=self.rm)
						self.gamemap.set_block(gridpos[0], gridpos[1], 0)

						block.kill()
						self.blocks.add(newblock)

	def update_particles(self):
		self.particles.update(self.blocks)
		for particle in self.particles:
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.hit()

	# self.particles.remove(particle)

	def update_powerups(self, player):
		self.powerups.update()
		powerblock_coll = spritecollide(player, self.powerups, False)
		for pc in powerblock_coll:
			# logger.debug(f'[pwrb] type:{pc.powertype} colls:{len(powerblock_coll)} sp:{len(self.powerups)}')
			player.take_powerup(pc.powertype)
			pc.kill()

	def update(self):
		if not self.kill:
			# self.update_players()
			# self.netplayers.update(self.blocks)
			# self.playerone.refresh_netplayers()
			self.players.update(self.blocks)
			self.update_bombs()
			#self.bombs.update()
			self.update_flames()
			self.update_particles()
			self.update_powerups(self.playerone)
			gamemsg = None
			try:
				gamemsg = self.gamequeue.get_nowait()
			except Empty:
				pass
			if gamemsg:
				logger.debug(f'[e] engmsg:{gamemsg}')
				self.gamequeue.task_done()
				if isinstance(gamemsg, dict):
					newblocks = gamemsg.get('blocks')
					flames = gamemsg.get('flames')
					if newblocks:
						logger.debug(f'[g] msg:{gamemsg} newblocks: {newblocks} ')
						self.blocks = newblocks
					if flames:
						logger.debug(f'[g] msg:{gamemsg} fl: {flames} ')
						self.flames = flames


	def draw(self):
		# draw on screen
		pygame.display.flip()
		self.screen.fill(self.bg_color)
#		for spg in self.all_sprites:
#			logger.debug(f'[draw] spg:{spg}')
#			spg.draw(self.screen)
		self.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.powerups.draw(self.screen)
		self.particles.draw(self.screen)
		self.players.draw(self.screen)
		self.netplayers.draw(self.screen)
		self.flames.draw(self.screen)
		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
		self.gui.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=self.playerone, flames=self.flames)
		if DEBUG:
			pos = Vector2(10, self.screenh - 50)			
			self.font.render_to(self.screen, pos, f"blk:{len(self.blocks)} pups:{len(self.powerups)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)} threads:{threading.active_count()}", (123, 123, 123))
			pos += (0,15)
			netdebug = self.playerone.get_netdebug()
			self.font.render_to(self.screen, pos, f"connected: {self.playerone.connected} dbg:{netdebug}", (123, 123, 123))
			#self.font.render_to(self.screen, pos, f"p1c:{self.playerone.connected} sendp:{self.playerone.ds.sendpkts} qget:{self.playerone.ds.qgetcnt} qsize:{self.playerone.ds.queue.qsize()}", (123, 123, 123))
			for block in self.blocks:
				pass
				#self.font.render_to(self.screen, block.rect.center, f"{block.block_type}", (150, 150, 150))
			for block in self.powerups:
				pass
				#self.font.render_to(self.screen, block.rect.center + (0, 5), f"p:{block.timeleft:.1f}", (190, 190, 190))
			for p in self.particles:
				pass

	# self.font.render_to(self.screen, p.rect.center, f"{p.hits}", (10,255,190))

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			# self.gameserver.start()
			self.playerone.start()
			self.playerone.connect_to_server()
			self.gui.show_mainmenu ^= True			
			self.enginequeue.put('reset_map')
		# self.reset_map(reset_grid=True)

		if selection == "Connect to server":
			pass

		if selection == "Quit":
			self.running = False

		if selection == "Pause":
			self.gui.show_mainmenu ^= True
			self.pause_game()

		if selection == "Restart":
			self.gui.show_mainmenu ^= True
			self.restart_game()

		if selection == "Start server":
			pass
			#self.gameserver.start()
			#self.is_server = True

	def handle_input(self):
		events = pygame.event.get()
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.gui.show_mainmenu:  # or self.paused:
						selection = self.gui.game_menu.get_selection()
						self.handle_menu(selection)
					elif not self.gui.show_mainmenu:
						b = self.playerone.bombdrop()
						if b != 0:
							self.bombs.add(b)
				if event.key == pygame.K_ESCAPE:
					self.gui.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.playerone.kill = True
					self.running = False
					self.enginequeue.put('quit')
				if event.key == pygame.K_1:
					if not self.playerone.connected:
						logger.debug(f'[c] connecting to server p1c:{self.playerone.connected}')
						self.playerone.connect_to_server()
					else:
						logger.warning(f'[c] already connected p1c:{self.playerone.connected}')
				if event.key == pygame.K_2:
					logger.debug(f'[c] req serverinfo p1c:{self.playerone.connected}')
					self.playerone.get_server_info()
					logger.debug(f'[c] req netplayers p1c:{self.playerone.connected}')
					self.playerone.refresh_netplayers()
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
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_down()
					else:
						self.playerone.vel.y = self.playerone.speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_up()
					else:
						self.playerone.vel.y = -self.playerone.speed
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					if not self.gui.show_mainmenu:
						self.playerone.vel.x = self.playerone.speed
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					if not self.gui.show_mainmenu:
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
				logger.warning(f'[pgevent] quit {event.type}')
				self.running = False


# if event_type == pygame.MOUSEBUTTONDOWN:
#	mousex, mousey = pygame.mouse.get_pos()


if __name__ == "__main__":
	stop_event = Event()
	engine = Engine(stop_event=stop_event, name='engine')
	engine.daemon = True
	engine.start()
	#input_queue = Queue()
	#input_thread = Thread(target=add_input, args=(input_queue,))
	#input_thread.daemon = True
	#input_thread.start()
	engine.running = True
	while True:
		try:
			if not engine.running or engine.kill:
				threads = threading.enumerate()
				logger.debug(f'[main] {engine} run stop run:{engine.running} k:{engine.kill} alive:{engine.is_alive()} active:{threading.active_count()} tl:{len(threads)} tle:{len(threading.enumerate())} ')
				engine.join(0)
				logger.debug(f'[main] joindone {engine} run stop run:{engine.running} k:{engine.kill} alive:{engine.is_alive()} active:{threading.active_count()} tl:{len(threads)} tle:{len(threading.enumerate())} ')
				break
		except KeyboardInterrupt as e:
			print(f'[kb] {e}')
			engine.kill_engine(killmsg=f'killed by {e}')
	pygame.quit()
