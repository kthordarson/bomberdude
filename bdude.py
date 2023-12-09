#!/usr/bin/python
# bomberdude
# 07102022 todo fix mapsync, limit one bomb per grid on map,
# todo check player movement while holding now keys
import threading
from argparse import ArgumentParser
from threading import Thread

import pygame
from loguru import logger
from pygame.event import Event
from pygame.math import Vector2
from pygame.sprite import Group, spritecollide

from constants import (BDUDEEVENT, BLOCK, DEBUG, DEFAULTFONT, FPS, NETPLAYERSIZE, PLAYEREVENT, SENDPOSEVENT)
from globals import Block, Bomb, ResourceHandler
from menus import GameMenu
from player import Player

FPS = 60

class Game(Thread):
	def __init__ (self, args=None):
		Thread.__init__(self, name='game')
		self.kill = False
		pygame.display.set_mode(size=(800,800), flags=pygame.DOUBLEBUF, vsync=1)
		self.bgimage = pygame.transform.scale(pygame.image.load('data/blackfloor.png').convert(), (1000,900))
		self.screen = pygame.display.get_surface()
		self.game_menu = GameMenu(self.screen)
		self.show_mainmenu = True
		self.clock = pygame.time.Clock()

	def __repr__(self):
		return f'[g] kill={self.kill}'

	def run(self):
		while True:
			self.clock.tick(FPS)
			if self.kill:
				logger.warning(f'{self} gamerun kill')
				break
			events_ = pygame.event.get()
			for event in events_:
				self.handle_input_events([event for event in events_ if event.type in (pygame.KEYDOWN, pygame.KEYUP)])
				self.handle_mouse_events([event for event in events_ if event.type == pygame.MOUSEBUTTONDOWN])
				if event.type == pygame.QUIT:
					self.kill = True
					logger.info(f'{self} pygameeventquit {event.type} events: {len(events_)}')
					pygame.event.clear()
					break
			# self.handle_input_events(input_events)
			# self.handle_mouse_events(mouse_events)
			self.draw()


	def draw(self):
		pygame.display.update()
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu()
		# pygame.display.flip()
		# self.screen.fill((0,0,0))

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
						pass
						# self.playerone.move("down")
				elif keypressed in {pygame.K_UP, pygame.K_w, 'w',119}:
					if self.show_mainmenu:
						menuselection = self.game_menu.menu_up()
						logger.debug(f'item: {self.game_menu.active_item} events: {len(events)}')
					else:
						pass
						# self.playerone.move("up")
				elif keypressed in {pygame.K_RIGHT, pygame.K_d, 'd', 100}:
					if not self.show_mainmenu:
						pass
						# self.playerone.move("right")
				elif keypressed in {pygame.K_LEFT, pygame.K_a, 'a', 97}:
					if not self.show_mainmenu:
						pass
						# self.playerone.move("left")
				elif keypressed in {pygame.K_SPACE, 32}:
					# handle menu selection
					logger.debug(f'K_SPACE item: {self.game_menu.active_item}')
				elif keypressed in {pygame.K_ESCAPE, 27}:
					# escape show/hide menu
					logger.debug(f'K_ESCAPE item: {self.game_menu.active_item} show: {self.show_mainmenu}')
					self.show_mainmenu = not self.show_mainmenu
					self.screen.fill((0,0,0))
				else:
					logger.debug(f'keypressed {keypressed} events: {len(events)}')

	def handle_mouse_events(self, events):
		for event in events:
			if event.type == pygame.MOUSEBUTTONDOWN:
				mx,my = pygame.mouse.get_pos()
				logger.debug(f'[mouse] {mx},{my} ')

def main(args):

	game = Game(args)
	game.daemon = True
	game.running = True
	game.run()
	while game.running:
		if game.kill:
			game.running = False
			break
	pygame.quit()


if __name__ == "__main__":
	pygame.init()
	# pygame.key.set_repeat(1000,3000)
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--server', action='store', dest='server', default='localhost')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	args = parser.parse_args()
	if args.testclient:
		pass
	main(args)

