#!/bin/python3.9
# bomberdude
import struct
import sys
import socket
import time
from argparse import ArgumentParser
from random import randint
from argparse import ArgumentParser
from turtle import circle
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
# from pygame import mixer # Load the popular external library
from things import Block, Powerup, Bomb
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
			self.players.update()
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
			# try:
			# 	netmsg = self.netqueue.get_nowait()
			# 	# logger.debug(f'[game] netmsg:{netmsg}')
			# except Empty as e:
			# 	pass
			# 	# logger.warning(f'[game] {self.mainqueue.qsize()}')
			# if netmsg:
			# 	self.netqueue.task_done()
			# 	self.handle_netq(netmsg)
			# 	# self.netqueue.task_done()
			# 	logger.debug(f'[game] done netmsg:{netmsg}')
			# 	netmsg = None


	def handle_mainq(self, gamemsg):
		type = gamemsg.get('msgtype')
		# logger.debug(f"[e] type:{type} cl:{gamemsg.get('client_id')} pos:{gamemsg.get('pos')} resp:{resp}")
		if type == 'playerpos':
			resp = {'msgtype':dataid["playerpos"], 'authkey':self.authkey, 'client_id': gamemsg.get('client_id'), 'pos': gamemsg.get('pos'), 'data_id': dataid['playerpos']}
			# if self.playerone.connected:
			# 	self.sendq.put_nowait(resp)
			#send_data(conn=self.conn, data_id=dataid['playerpos'], payload=resp)
			# resp = receive_data(self.conn)
			#logger.debug(f"[e] type:{type} cl:{gamemsg.get('client_id')} pos:{gamemsg.get('pos')} resp:{resp}")
		elif type == 'bombdrop':
			resp = {'authkey':self.authkey, 'msgtype':'bombdrop', 'client_id': gamemsg.get('client_id'), 'pos': gamemsg.get('pos'), 'data_id': dataid['gameevent']}
			# if self.playerone.connected:
			# 	self.sendq.put_nowait(resp)
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} Sending to sendq resplen:{len(resp)} resp={resp}')
		elif type == 'gamemap':
			gamemap = gamemsg.get('gamemap')
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} gamemap:{len(gamemap.grid)}')
			if len(gamemap.grid) > 1:
				self.gamemap = gamemap
				newblocks = Group()
				for k in range(0, GRIDSIZE[0]):
					for j in range(0, GRIDSIZE[1]):
						newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=gamemap.grid[j][k])
						newblocks.add(newblock)
				self.blocks.add(newblocks)
			
	def handle_netq(self, gamemsg):
		netmsg = gamemsg.get('data').get('msgtype')
		# logger.debug(F'[netq] {self.netqueue.qsize()} got type:{netmsg} engmsg:{len(gamemsg)}')
		# if type == 'network':
		# 	netmsg = None
		# 	try:
		# 		netmsg = gamemsg.get('data').get('msgtype')
		# 	except AttributeError as e:
		# 		logger.error(f'[game]{self.mainqueue.qsize()} {self.sendq.qsize()}  {type} AttributeError:{e} {gamemsg}')
		# 		netmsg = None
		# 	if netmsg:
		if netmsg == 'bcnetupdate':
			if gamemsg.get('data').get('payload').get('netplayers'):
				self.netplayers = gamemsg.get('data').get('payload').get('netplayers')
			if gamemsg.get('data').get('payload').get('msgtype') == 'bcpoll':
				resp = {'msgtype':dataid["playerpos"], 'authkey':self.authkey, 'client_id': self.playerone.client_id, 'pos': self.playerone.pos, 'data_id': dataid['playerpos']}
				# resp = {'data_id':dataid["auth"], 'msgtype':'auth', 'authkey':self.authkey, 'client_id':self.playerone.client_id}
				self.sendq.put_nowait(resp)
		elif gamemsg.get('msgtype') == 'auth' or gamemsg.get('data').get('msgtype') == 'auth':
			resp = {'data_id':dataid["auth"], 'msgtype':'auth', 'authkey':self.authkey, 'client_id':self.playerone.client_id}
			# resp = self.authresp
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()}  auth got type:{type} engmsg:{len(gamemsg)} Sending to sendq resplen:{len(resp)} resp={resp}')
			if self.playerone.connected:
				self.sendq.put_nowait(resp)
		else:
			logger.warning(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()}  unknown type:{type} gamemsg:{gamemsg}')


	def update_players(self):
		pass

	def get_players(self):
		pass

	def update_bombs(self):
		pass

	def update_flames(self):
		pass

	def update_particles(self):
		pass

	def update_powerups(self, player):
		pass

	def draw(self):
		# draw on screen
		try:
			pygame.display.flip()
		except pygame.error as e:
			logger.error(f'[pg] err:{e}')
			self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
			return
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
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
		self.gui.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, player1=self.playerone, flames=self.flames)

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
#						if b != 0:
#							self.bombs.add(b)
				if event.key == pygame.K_ESCAPE:
					self.gui.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.kill = True
					self.playerone.kill = True
					self.running = False
				if event.key == pygame.K_1:
					pass
				if event.key == pygame.K_2:
					pass
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

def run_testclient():
	bc = BombClient(client_id=1, serveraddress='127.0.0.1', serverport=9696)
	logger.info(f'test bombclient bc:{bc}')
	conn = bc.connect_to_server()
	if conn:
		logger.info(f'test bombclient bc:{bc} conn={conn}')
		while True:
			msgid, payload = None, None
			testpayload = {'client_id': bc.client_id, 'pos': (100,100)}
			send_data(conn=bc.socket, data_id=dataid['playerpos'], payload=testpayload)
			msgid,payload = receive_data(conn=bc.socket)
			if msgid == 4:
				if payload.get('msgtype') == 'bcnetupdate':
					if payload.get('payload').get('msgtype') == 'bcgetid':
						if payload.get('payload').get('payload') == 'sendclientid':
							logger.debug(f'[bct] resp={payload}')
							authpayload = {'client_id': bc.client_id, 'pos': (100,100)}
							send_data(conn=bc.socket, data_id=dataid['auth'], payload=authpayload)
			else:
				logger.warning(f'[')
	else:
		logger.warning(f'test bombclient bc:{bc} conn failed conn={conn}')
	#client.run()


if __name__ == "__main__":
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	args = parser.parse_args()
	if args.testclient:
		run_testclient()
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



