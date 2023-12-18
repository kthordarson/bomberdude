#!/usr/bin/python
# bomberdude
# 07102022 todo fix mapsync, limit one bomb per grid on map,
# todo check player movement while holding now keys
import os, sys
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
from constants import (DEFAULTFONT, PLAYEREVENT, NEWGRIDEVENT, CONNECTTOSERVEREVENT,NEWCLIENTEVENT,STARTGAMEEVENT,STARTSERVEREVENT,NEWCONNECTIONEVENT,NETPLAYEREVENT)
from globals import Block, Bomb, ResourceHandler, BasicThing, NewBlock, NewBomb
from menus import GameMenu
from player import  NewPlayer

FPS = 60





class Game(Thread):
	def __init__ (self):
		Thread.__init__(self, name='game')
		self.kill = False
		self.running = False
		pygame.display.set_mode(size=(GRIDSIZE*BLOCK,GRIDSIZE*BLOCK), flags=pygame.DOUBLEBUF, vsync=1)
		self.screen = pygame.display.get_surface()
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.game_menu = GameMenu(self.screen)
		self.show_mainmenu = True
		self.clock = pygame.time.Clock()
		self.game_started = False
		self.rh = ResourceHandler()
		self.player = NewPlayer(gridpos=[10,10], image=self.rh.get_image('data/playerone.png'), rh=self.rh)
		self.bombs = Group()
		self.blocks = Group()
		self.debugfont = pygame.freetype.Font(DEFAULTFONT, 8)
		self.sprites = Group()

	def __repr__(self):
		return f'[G] k={self.kill} gs:{self.game_started} p:{self.player} pl:{len(self.player.playerlist)} '

	def create_blocks_from_grid(self):
		#draws the grid
		# block=BLOCK
		x = 0
		y = 0
		# blks = Group()
		self.sprites.empty()
		for i in self.player.grid:
			x=0
			for k in i:
				k = int(k)
				match k:
					case 0:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite0.png')))
					case 1:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite1.png')))
					case 2:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite2.png')))
					case 5:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite5.png')))
					case 7:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite7.png')))
					case 8:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite8.png')))
					case 9:
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite9.png')))
					case _:
						logger.warning(f'k:{k} {type(k)} x:{x} y:{y}')
						self.sprites.add(NewBlock(gridpos=(x,y), image=self.rh.get_image('data/blocksprite3.png')))
				x+= 1 # BLOCK
			y+= 1 # BLOCK

	def olddrawplayers(self):
		# if len(self.player.playerlist) > 1:
		#	logger.debug(f'{self} drawgrid {len(self.player.playerlist)}\nplayerlist: {self.player.playerlist}\n')
		textypos = 22
		self.debugfont.render_to(self.screen, (12 ,textypos), f'{self.player}', (255,255,255))
		for player in self.player.playerlist:
			# logger.debug(f'{player} {self.player.playerlist.get(player)}')
			plid = self.player.playerlist.get(player).get('client_id')
			pos = self.player.playerlist.get(player).get('pos')
			gridpos = self.player.playerlist.get(player).get('gridpos')
			# gridpos = (pos[0] * BLOCK, pos[1] * BLOCK)
			if self.player.client_id != plid:
				blk = NewBlock(gridpos=gridpos, image=self.rh.get_image('data/netplayer.png'))
			elif self.player.client_id == plid:
				blk = NewBlock(gridpos=gridpos, image=self.rh.get_image('data/playerone.png'))
				# blks.add(BasicBlock(gridpos=gridpos, image=self.rh.get_image('data/playerone.png'))
			else:
				logger.warning(f'{self} pliderror!')
				blk = NewBlock(gridpos=gridpos, image=self.rh.get_image('data/dummyplayer.png'))
			# blk.draw(self.screen)


	def handle_events(self, payload):
		msgtype = payload.get('msgtype')
		# logger.debug(f'{msgtype} PLAYEREVENT {event.payload}')
		match msgtype:
			case 'newgridfromserver':
				newgrid = payload.get('grid', None)
				if newgrid:
					logger.debug(f'NEWGRIDEVENT {self.player.gotgrid} {self.sprites}')
					self.player.grid = newgrid
					self.player.gotgrid = True
					self.create_blocks_from_grid()
					logger.debug(f'NEWGRIDEVENT {self.player.gotgrid} {self.sprites}')
				else:
					logger.error(f'NEWGRIDEVENT nogrid {self.player.gotgrid} : {event.payload} ')

			case 'ackplrbmb':
				# create bomb with timer and add to server objects....
				bombimg = self.rh.get_image(filename='data/bomb.png', force=False)
				bid = payload.get('client_id')
				bpos = payload.get('pos')
				gpos = payload.get('gridpos')
				clbombpos = payload.get('clbombpos')
				logger.info(f'{msgtype} PLAYEREVENT {bid} {bpos} {gpos} {clbombpos}')
				try:
					newbomb = NewBomb(bombimg, bomberid=bid, gridpos=clbombpos,  bombtimer=2000)
					self.sprites.add(newbomb)
				except Exception as e:
					logger.error(f'{e} {type(e)} msgtype:{msgtype} payload: {payload}')
			case _ :
				logger.warning(f'unknownmsgtypePLAYEREVENT {event.payload}')

	def run(self):
		while True:
			self.clock.tick(FPS)
			pygame.display.update()
			self.sprites.update()
			self.player.update()
			if self.show_mainmenu:
				self.game_menu.draw_mainmenu()
			else:
				self.draw()
			if self.kill:
				logger.warning(f'{self} gamerun kill')
				self.player.kill = True
				self.player.socket.close()
				break
			events_ = pygame.event.get()
			for event in events_:
				if event.type == pygame.KEYDOWN:
					self.handle_input_events(event)
				elif event.type == pygame.MOUSEBUTTONDOWN:
					self.handle_mouse_event(event)
				if event.type == pygame.QUIT:
					self.player.kill = True
					self.kill = True
					logger.info(f'{self} pygameeventquit {event.type} events: {len(events_)}')
					pygame.event.clear()
					break
				elif event.type == NEWCLIENTEVENT:
					# todo new client connected, create player and move on....
					logger.debug(f'NEWCLIENTEVENT {event.payload}')
				elif event.type == PLAYEREVENT:
					# todo new PLAYEREVENT, parse and move on....
					# logger.debug(f'PLAYEREVENT {event.payload}')
					self.handle_events(event.payload)
				elif event.type == NEWGRIDEVENT:
					# todo new client connected, create player and move on....
					self.handle_events(event.payload)
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


	def draw(self):
		self.sprites.draw(self.screen)
		self.player.draw(self.screen)

	def start_game(self):
		if self.game_started:
			logger.warning(f'game already started')
			return
		else:
			logger.info(f'startgame')
		self.screen.fill((0,0,0))
		self.player.start()
		self.game_started = True
		self.show_mainmenu = False
		# npevent = {'msgtype': 'newplayer0', 'conn' : np.socket, }

	def connect_to_server(self):
		logger.info(f'{self}')

	def start_server(self):
		logger.info(f'{self} ')

	def handle_input_events(self, event):
		#for idx,event in enumerate(events):
		#	if event.type == pygame.KEYDOWN:
		# event = events
		keypressed = event.key
		if keypressed in(pygame.K_q, 113,'q','Q'):
			logger.info(f'keyquit {keypressed} ')
			pygame.event.post(Event(pygame.QUIT))
		elif keypressed in {pygame.K_DOWN, pygame.K_s}:
			if self.show_mainmenu:
				self.game_menu.menu_down()
				logger.debug(f'item: {self.game_menu.active_item}')
			else:
				self.player.move('d')
		elif keypressed in {pygame.K_UP, pygame.K_w}:
			if self.show_mainmenu:
				self.game_menu.menu_up()
				logger.debug(f'item: {self.game_menu.active_item}')
			else:
				self.player.move('u')
		elif keypressed in {pygame.K_RIGHT, pygame.K_d}:
			if not self.show_mainmenu:
				self.player.move('r')
		elif keypressed in {pygame.K_LEFT, pygame.K_a}:
			if not self.show_mainmenu:
				self.player.move('l')
		elif keypressed == pygame.K_SPACE:
			# handle menu selection
			if not self.show_mainmenu:
				self.player.sendbomb()
			else:
				logger.debug(f'e:{event} k:{keypressed} K_SPACE item: {self.game_menu.active_item}')
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
		elif keypressed == pygame.K_ESCAPE:
			# escape show/hide menu
			logger.debug(f'K_ESCAPE item: {self.game_menu.active_item} show: {self.show_mainmenu}')
			self.show_mainmenu = not self.show_mainmenu
		else:
			logger.debug(f'keypressed {keypressed} ')

	def handle_mouse_event(self, event):
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
			game.player.kill = True
			game.player.socket.close()
			pygame.quit()
			logger.debug(f'main kill {game} ')
			os._exit(0)
			break


def run_testclient(args):
	logger.debug(f'testclient {args}')
	np = NewPlayer(testmode=True)
	logger.debug(f'testclient {np}')
	np.run()
	logger.debug(f'testclient run {np}')
	np.do_testing()
	logger.debug(f'testclient test {np}')

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

