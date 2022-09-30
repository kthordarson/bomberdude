#!/bin/python3.9
# bomberdude
import time
from argparse import ArgumentParser
from turtle import circle
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
from globals import Block, Powerup, Bomb
from map import Gamemap
from globals import ResourceHandler
from constants import DEBUG, DEBUGFONTCOLOR, GRIDSIZE, BLOCKSIZE, SCREENSIZE, FPS, DEFAULTGRID,DEFAULTFONT
from menus import Menu, DebugDialog
from player import Player
from threading import Thread, Event
import threading
import multiprocessing
from multiprocessing import Queue as mpQueue
from queue import Queue, Empty
#from bombserver import BombServer
from network import dataid, send_data, receive_data
from bclient import BombClient


class GameGUI:
	def __init__(self, screen):
		self.screen = screen
		self.show_mainmenu = True
		self.blocks = Group()
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.game_menu = Menu(self.screen, self.font)
		self.debug_dialog = DebugDialog(self.screen, self.font)
		self.font_color = (255, 255, 255)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
	# self.debugfont = pygame.freetype.Font(DEFAULTFONT, 10)
	def draw(self):
		pass


class Game(Thread):
	def __init__(self, screen=None, mainqueue=None, conn=None, sendq=None, netqueue=None):
		Thread.__init__(self, name='game')
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.conn = conn
		self.name = 'game'
		self.mainqueue = Queue()
		self.sendq = sendq
		self.netqueue = netqueue
		self.kill = False
		self.screen = screen
		self.gui = GameGUI(self.screen)
		self.bg_color = pygame.Color("black")
		self.running = False
		self.blocks = Group()
		self.players = Group()
		self.netplayers = Group()
		self.particles = Group()
		self.powerups = Group()
		self.bombs = Group()
		self.flames = Group()
		self.playerone = Player(pos=(300, 300), visible=False, mainqueue=self.mainqueue)
		self.p1connected = False
		self.players.add(self.playerone)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.authkey = 'foobar'
		self.netplayers = {}
		# self.authresp = {}


	def __repr__(self):
		return f'[game] {self.name}'

	def run(self):
		logger.debug(f'[game] {self} started mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
		while True:
			# logger.debug(f'[game] {self}  mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
			if self.kill:
				logger.warning(f'game kill')
				break
			self.draw()
			self.handle_input()
			#self.playerone.update(self.blocks)
			self.players.update(self.blocks)
			self.update_bombs()
			self.update_flames()
			self.update_particles()
			self.update_powerups(self.playerone)
			gamemsg = None
			netmsg = None
			try:
				gamemsg = self.mainqueue.get_nowait()
				# logger.debug(f'[game] gamemsg:{gamemsg}')
			except Empty as e:
				pass
				# logger.warning(f'[game] {self.mainqueue.qsize()}')
			if gamemsg:
				self.mainqueue.task_done()
				self.handle_mainq(gamemsg)				


	def handle_mainq(self, gamemsg):
		# logger.debug(f'[game] {self} gamemsg:{gamemsg}')
		type = gamemsg.get('msgtype')
		# logger.debug(f"[e] type:{type} cl:{gamemsg.get('client_id')} pos:{gamemsg.get('pos')} resp:{resp}")
		if type == 'playerpos':
			resp = {'msgtype':dataid["playerpos"], 'authkey':self.authkey, 'client_id': gamemsg.get('client_id'), 'pos': gamemsg.get('pos'), 'data_id': dataid['playerpos']}
		elif type == 'bombdrop':
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} gamemsg={gamemsg}')
		elif type == 'netbomb':
			bomber_id = gamemsg.get('bombdata').get('client_id')
			bombpos = gamemsg.get('bombdata').get('bombpos')
			newbomb = Bomb(pos=bombpos, bomber_id=bomber_id)
			self.bombs.add(newbomb)
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} bomb:{newbomb}')
		elif type == 'gamemapgrid':
			gamemapgrid = gamemsg.get('gamemapgrid')
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} gamemapgrid:{len(gamemapgrid)}')
			if len(gamemapgrid) > 1:
				self.gamemapgrid = gamemapgrid
				newblocks = Group()
				for k in range(0, GRIDSIZE[0]):
					for j in range(0, GRIDSIZE[1]):
						newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=gamemapgrid[j][k])
						newblocks.add(newblock)
				self.blocks.add(newblocks)
			

	def update_bombs(self):
		self.bombs.update()
		for bomb in self.bombs:
			bomb.dt = pygame.time.get_ticks() / 1000
			if bomb.dt - bomb.start_time >= bomb.bomb_fuse:				
				self.flames.add(bomb.gen_flames())
				# bomb.bomber_id.bombs_left += 1
				bomb.kill()
				#self.bombs.remove(bomb)

	def update_flames(self):
		self.flames.update()
		for flame in self.flames:
			# check if flame collides with blocks
			flame_coll = spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if block.solid:
					if block.block_type == 1 or block.block_type == 2: # or block.block_type == '3' or block.block_type == '4':
						# types 1 and 2 create powerups
						powerup = Powerup(pos=block.rect.center)
						if powerup.powertype != 0:
							self.powerups.add(powerup)
						pos, gridpos, particles = block.hit(flame)
						newblock =  Block(pos, gridpos, block_type=0)
						#self.gamemap.set_block(gridpos[0], gridpos[1], 0)
						self.particles.add(particles)
						flame.kill()
						block.kill()
						self.blocks.add(newblock)
				# self.blocks.remove(block)

	def update_particles(self):
		self.particles.update(self.blocks)
		for particle in self.particles:
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					particle.hit()
					#self.particles.remove(particle)

	def update_powerups(self, playerone):
		if len(self.powerups) > 0:
			powerblock_coll = spritecollide(playerone, self.powerups, False)
			for pc in powerblock_coll:
				logger.debug(f'[pwrb] type:{pc.powertype} colls:{len(powerblock_coll)} sp:{len(self.powerups)}')
				playerone.take_powerup(pc.powertype)
				pc.kill()

	def draw(self):
		# draw on screen
		try:
			pygame.display.flip()
		except pygame.error as e:
			logger.error(f'[pg] err:{e}')
			self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
			return
		self.screen.fill(self.bg_color)
		self.particles.draw(self.screen)
		self.bombs.draw(self.screen)
		self.blocks.draw(self.screen)
		self.flames.draw(self.screen)
		self.players.draw(self.screen)
		
		for np in self.playerone.client.netplayers:
			if self.playerone.client_id != np:
				pos = self.playerone.client.netplayers[np].get('pos')
				pygame.draw.circle(self.screen, (255, 0, 0), pos, 10, 0)
				self.font.render_to(self.screen, pos, str(np), (255, 255, 255))
			if self.playerone.client_id == np:
				pass
				#pos = self.playerone.client.netplayers[np].get('pos')
				#pygame.draw.circle(self.screen, (255, 255, 255), pos, 5, 0)
				#self.font.render_to(self.screen, pos, str(np), (255, 155, 255))
				#self.font.render_to(self.screen, pos+(0,10), f'p1:{self.playerone.pos} np:{pos}', (255, 155, 255))
		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
		self.gui.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, playerone=self.playerone, flames=self.flames)

		if DEBUG:
			pos = Vector2(10, self.screenh - 100)
			self.font.render_to(self.screen, pos, f"blk:{len(self.blocks)} pups:{len(self.powerups)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)} threads:{threading.active_count()}", (123, 123, 123))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"threads:{threading.active_count()} mainq:{self.mainqueue.qsize()} sendq:{self.sendq.qsize()} netq:{self.netqueue.qsize()} p1c:{self.p1connected} np:{len(self.playerone.client.netplayers)}", (123, 123, 123))

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			# self.playerone.start()
			self.gui.show_mainmenu ^= True
			self.p1connected = self.playerone.client.connect_to_server()
			if self.p1connected:
				self.playerone.connected = True
				logger.debug(f'[game] p1 connected:{self.p1connected} {self.playerone.connected} {self.playerone.client.connected}')
				self.playerone.start_client()
			

		if selection == "Connect to server":
			pass

		if selection == "Quit":
			self.running = False

		if selection == "Pause":
			self.gui.show_mainmenu ^= True
			# self.pause_game()

		if selection == "Restart":
			self.gui.show_mainmenu ^= True
			# self.restart_game()

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
						self.mainqueue.put_nowait({'msgtype': 'bombdrop', 'client_id': self.playerone.client_id, 'pos': self.playerone.pos})
						self.playerone.client.send_bomb()
				if event.key == pygame.K_ESCAPE:
					self.gui.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.kill = True
					self.playerone.kill = True
					self.running = False
				if event.key == pygame.K_1:
					self.playerone.client.send_mapreq()
				if event.key == pygame.K_2:
					self.playerone.client.send_pos(pos=self.playerone.pos)
				if event.key == pygame.K_3:
					pass
				if event.key == pygame.K_c:
					pass
				if event.key == pygame.K_f:
					pass
				if event.key == pygame.K_p:
					pass
				if event.key == pygame.K_m:
					pass
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



if __name__ == "__main__":
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	args = parser.parse_args()
	if args.testclient:
		pass

	else:
		pygame.init()
		screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
		dt = pygame.time.Clock()
		mainqueue = Queue()
		netqueue = Queue()
		sendq = Queue()
		stop_event = Event()
		#mainqueue = OldQueue()#  multiprocessing.Manager().Queue()
		# engine = Engine(stop_event=stop_event, name='engine')
		game = Game(screen=screen, mainqueue=mainqueue, sendq=sendq, netqueue=netqueue)
		game.daemon = True
		game.start()
		game.running = True
		while game.running:
			if game.kill:
				game.running = False
				break
			try:
				t1 = time.time()
			except KeyboardInterrupt as e:
				logger.warning(f'[kb] {e}')
				# game.kill_engine(killmsg=f'killed by {e}')
				break
		pygame.quit()



