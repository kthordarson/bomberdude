#!/usr/bin/python
# bomberdude
# 07102022 todo fix mapsync, limit one bomb per grid on map,
# todo check player movement while holding now keys
import threading
from argparse import ArgumentParser
from threading import Thread
import numpy as np

import pygame
from loguru import logger
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import Group, spritecollide, Sprite

from constants import (BLOCK, FPS,  BLOCK, BLOCKSIZE, GRIDSIZE)
from constants import (CONNECTTOSERVEREVENT,NEWCLIENTEVENT,STARTGAMEEVENT,STARTSERVEREVENT,NEWCONNECTIONEVENT)
from globals import Block, Bomb, ResourceHandler, BasicThing, BasicBlock
from menus import GameMenu
from player import  NewPlayer
# from bombserver import NewBombSever, NewConnectionHandler
# from signal import signal, SIGPIPE, SIG_DFL
# signal(SIGPIPE,SIG_DFL)

FPS = 60


def drawGrid(screen, grid, rh):
	#draws the grid
	# block=BLOCK
	x = 0
	y = 0
	for i in grid:
		x=0
		for k in i:
			#convert k into int type instead of class numpy int32
			if int(k)==0:
				blk = BasicBlock(pos=(x,y), image=rh.get_image('data/blocksprite0.png'))
				screen.blit(blk.image, blk.pos)
				# pygame.draw.rect(screen, (50, 150, 200), pygame.Rect((x, y), Vector2(BLOCKSIZE)))
			elif int(k)==1:
				blk = BasicBlock(pos=(x,y), image=rh.get_image('data/blocksprite1.png'))
				screen.blit(blk.image, blk.pos)
				# pygame.draw.rect(screen, (123, 50, 200), pygame.Rect((x, y), Vector2(BLOCKSIZE)))
			elif int(k)==2:
				blk = BasicBlock(pos=(x,y), image=rh.get_image('data/blocksprite2.png'))
				# pygame.draw.rect(screen, (200, 50, 50), pygame.Rect((x, y), Vector2(BLOCKSIZE)))
			elif int(k)==5:
				blk = BasicBlock(pos=(x,y), image=rh.get_image('data/blocksprite5.png'))
				# pygame.draw.rect(screen, (0, 0, 0), pygame.Rect((x, y), Vector2(BLOCKSIZE)))
			else:
				blk = BasicBlock(pos=(x,y), image=rh.get_image('data/blocksprite3.png'))
				screen.blit(blk.image, blk.pos)
				# pygame.draw.rect(screen, (200, 200, 200), pygame.Rect((x, y), Vector2(BLOCKSIZE)))
			x+=BLOCK
		y+=BLOCK

class Game(Thread):
	def __init__ (self):
		Thread.__init__(self, name='game')
		self.kill = False
		self.running = False
		pygame.display.set_mode(size=(GRIDSIZE*BLOCK,GRIDSIZE*BLOCK), flags=pygame.DOUBLEBUF, vsync=1)
		self.bgimage = pygame.transform.scale(pygame.image.load('data/blackfloor.png').convert(), (1000,900))
		self.screen = pygame.display.get_surface()
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.game_menu = GameMenu(self.screen)
		self.show_mainmenu = True
		self.clock = pygame.time.Clock()
		self.game_started = False
		self.rh = ResourceHandler()
		self.players = []
		self.server_grid = []

	def __repr__(self):
		return f'[game] k={self.kill} gs:{self.game_started} mm:{self.show_mainmenu} '

	def run(self):
		while True:
			self.clock.tick(FPS)
			if self.kill:
				logger.warning(f'{self} gamerun kill')
				break
			if self.game_started:
				for p in self.players:
					if p.connected and p.client_id != 'newplayer1':
						# p.sendpos()
						p.send_cl_message(clmsgtype='gamemsg', payload='foobar')
			events_ = pygame.event.get()
			for event in events_:
				self.handle_input_events([event for event in events_ if event.type in (pygame.KEYDOWN, pygame.KEYUP)])
				self.handle_mouse_events([event for event in events_ if event.type == pygame.MOUSEBUTTONDOWN])
				if event.type == pygame.QUIT:
					self.kill = True
					logger.info(f'{self} pygameeventquit {event.type} events: {len(events_)}')
					pygame.event.clear()
					break
				elif event.type == NEWCLIENTEVENT:
					# todo new client connected, create player and move on....
					logger.debug(f'NEWCLIENTEVENT {event.payload}')
				elif event.type == STARTGAMEEVENT:
					# todo create new client
					# connect to server
					# get grid from server
					# start game
					self.start_game()
				elif event.type == CONNECTTOSERVEREVENT:
					self.connect_to_server()
				elif event.type == STARTSERVEREVENT:
					self.start_server()
			# self.handle_input_events(input_events)
			# self.handle_mouse_events(mouse_events)
			self.draw()


	def draw(self):
		try:
			pygame.display.update()
		except pygame.error as e:
			logger.warning(f'draw {e}')
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu()
		else:
			if self.game_started:
				drawGrid(self.screen, self.server_grid, self.rh)
		# pygame.display.flip()
		# self.screen.fill((0,0,0))

	def start_game(self):
		if self.game_started:
			logger.warning(f'game already started')
			return
		else:
			logger.info(f'startgame')
		self.screen.fill((0,0,0))
		conn = False
		np = NewPlayer()
		np.start()
		self.players.append(np)
		self.game_started = True
		self.show_mainmenu = False
		# npevent = {'msgtype': 'newplayer0', 'conn' : np.socket, }

	def oldstartgame(self):
		logger.debug(f'connectinnp: {np} players: {len(self.players)} ')
		try:
			conn = np.connect()
		except ConnectionRefusedError as e:
			logger.warning(f'connectnp: {np} {e}')
			self.game_started = False
			self.show_mainmenu = False
			return
		if conn:
			self.game_started = True
			self.show_mainmenu = False
			np.start()
			self.players.append(np)
			logger.info(f'connectednp: {np} players: {len(self.players)} ')
		else:
			logger.warning(f'startgame failed to connect! np: {np} ')
#			self.game_started = False
#			self.show_mainmenu = True


	def connect_to_server(self):
		logger.info(f'{self}')

	def start_server(self):
		logger.info(f'{self} ')

	def handle_input_events(self, events):
		menuselection = self.game_menu.menuitems[0]
		for event in events:
			if event.type == pygame.KEYDOWN:
				keypressed = event.key
				if keypressed in(pygame.K_q, 113,'q','Q'):
					logger.info(f'keyquit {keypressed} events: {len(events)}')
					pygame.event.post(Event(pygame.QUIT))
				elif keypressed in {pygame.K_DOWN, pygame.K_s, 's',115}:
					if self.show_mainmenu:
						menuselection = self.game_menu.menu_down()
						logger.debug(f'item: {self.game_menu.active_item} events: {len(events)}')
					else:
						[p.move('d') for p in self.players]
				elif keypressed in {pygame.K_UP, pygame.K_w, 'w',119}:
					if self.show_mainmenu:
						menuselection = self.game_menu.menu_up()
						logger.debug(f'item: {self.game_menu.active_item} events: {len(events)}')
					else:
						[p.move('u') for p in self.players]
				elif keypressed in {pygame.K_RIGHT, pygame.K_d, 'd', 100}:
					if not self.show_mainmenu:
						[p.move('r') for p in self.players]
				elif keypressed in {pygame.K_LEFT, pygame.K_a, 'a', 97}:
					if not self.show_mainmenu:
						[p.move('l') for p in self.players]
				elif keypressed in {pygame.K_SPACE, 32}:
					# handle menu selection
					if not self.show_mainmenu:
						[p.move('bomb') for p in self.players]
					else:
						logger.debug(f'K_SPACE item: {self.game_menu.active_item}')
						if self.game_menu.active_item == 'Start':
							if not self.game_started:
								pygame.event.post(Event(STARTGAMEEVENT))
							else:
								logger.warning(f'game already started')
						if self.game_menu.active_item == 'Connect to server':
							pygame.event.post(Event(CONNECTTOSERVEREVENT))
						if self.game_menu.active_item == 'Start server':
							pygame.event.post(Event(STARTSERVEREVENT))
						if self.game_menu.active_item == 'Quit':
							pygame.event.post(Event(pygame.QUIT))
				elif keypressed in {pygame.K_ESCAPE, 27}:
					# escape show/hide menu
					logger.debug(f'K_ESCAPE item: {self.game_menu.active_item} show: {self.show_mainmenu}')
					self.show_mainmenu = not self.show_mainmenu
				else:
					logger.debug(f'keypressed {keypressed} events: {len(events)}')

	def handle_mouse_events(self, events):
		for event in events:
			if event.type == pygame.MOUSEBUTTONDOWN:
				mx,my = pygame.mouse.get_pos()
				logger.debug(f'[mouse] {mx},{my} ')

def main(args):
	game = Game()
	logger.debug(f'main game: {game}')
	game.daemon = True
	game.running = True
	game.run()
	while game.running:
		if game.kill:
			game.running = False
			logger.debug(f'main kill {game} ')
			break
	pygame.quit()

def run_testclient(args):
	logger.debug(f'testclient {args}')
	np = NewPlayer(testmode=True)
	np.do_testing()
	np.run()

if __name__ == "__main__":
	pygame.init()
	# pygame.key.set_repeat(1000,3000)
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--server', action='store', dest='server', default='localhost')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	args = parser.parse_args()
	if args.testclient:
		run_testclient(args)
	else:
		main(args)

