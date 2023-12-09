import pygame
import pygame.freetype
from pygame.math import Vector2
from constants import *

class GameMenu:
	def __init__(self, screen):
		self.screen = screen
		self.screenw, self.screenh = self.screen.get_size()
		self.menusize = (250, 180)
		self.pos = Vector2(self.screenw // 2 - self.menusize[0] // 2, self.screenh // 2 - self.menusize[1] // 2)
		self.menuitems = ['Start', 'Connect to server', 'Start server', 'Stop server', 'Pause', 'Restart', 'Quit']
		self.menufont = pygame.freetype.Font(DEFAULTFONT, 16)
		self.inactive_color = (155, 155, 155)
		self.selected_color = (255, 255, 255)
		self.menufont.fgcolor = self.selected_color
		self.selected_item = 0
		self.active_item = self.menuitems[self.selected_item]

	def draw_mainmenu(self):
		pos_y = self.pos.y
		for item in enumerate(self.menuitems):
			if item[0] == self.selected_item:
				self.menufont.fgcolor = self.selected_color
			else:
				self.menufont.fgcolor = self.inactive_color
			self.menufont.render_to(self.screen, (self.pos.x, pos_y), item[1], self.menufont.fgcolor)
			pos_y += 25

	def get_selection(self):
		return self.menuitems[self.selected_item]

	def menu_up(self):
		if self.selected_item > 0:
			self.selected_item -= 1
		else:
			self.selected_item = len(self.menuitems) - 1
		self.active_item = self.menuitems[self.selected_item]
		return self.menuitems[self.selected_item]

	def menu_down(self):
		if self.selected_item < len(self.menuitems) - 1:
			self.selected_item += 1
		else:
			self.selected_item = 0
		self.active_item = self.menuitems[self.selected_item]
		return self.menuitems[self.selected_item]

class Menu:
	def __init__(self, screen, font):
		self.screen = screen # pygame.display.get_surface()
		self.screenw, self.screenh = self.screen.get_size()
		self.menusize = (250, 180)
		self.image = pygame.Surface(self.menusize)
		self.pos = Vector2(self.screenw // 2 - self.menusize[0] // 2, self.screenh // 2 - self.menusize[1] // 2)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.selected_color = (255, 255, 255)
		self.inactive_color = (155, 155, 155)
		self.menufont = font
		self.debugfont = font
		self.panelfont = pygame.freetype.Font(DEFAULTFONT, 16)
		self.font = font
		self.font_color = (255, 255, 255)
		self.panelfont_color = (255, 255, 255)
		self.menufont.fgcolor = self.selected_color
		self.bgcolor = pygame.Color("darkred")
		self.bordercolor = pygame.Color("black")
		# self.menufont.bgcolor = (44,55,66)
		self.menuitems = ['Start', 'Connect to server', 'Start server', 'Stop server', 'Pause', 'Restart', 'Quit']
		self.selected_item = 0

	def set_pos(self, newpos: Vector2):
		self.pos = newpos


	def draw_menubg(self, screen):
		self.bordercolor = pygame.Color("darkred")
		bordersize = 5
		menupos = [self.pos.x - bordersize, self.pos.y - bordersize]
		# pygame.draw.rect(screen, self.bgcolor, (menupos[0], menupos[1], self.menusize[0], self.menusize[1])) # background
		pygame.draw.line(screen, self.bordercolor, menupos, (menupos[0], menupos[1] + self.menusize[1]), bordersize)  # left border
		pygame.draw.line(screen, self.bordercolor, (menupos[0] + self.menusize[0], menupos[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize)  # right border
		pygame.draw.line(screen, self.bordercolor, menupos, (menupos[0] + self.menusize[0], menupos[1]), bordersize)  # top border
		pygame.draw.line(screen, self.bordercolor, (menupos[0], menupos[1] + self.menusize[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize)  # bottom border
		self.bordercolor = pygame.Color("black")

	# pass

	def draw_mainmenu(self, screen=None):
		screen = pygame.display.get_surface()
		self.draw_menubg(screen)
		pos_y = self.pos.y
		for item in enumerate(self.menuitems):
			if item[0] == self.selected_item:
				self.menufont.fgcolor = self.selected_color
			else:
				self.menufont.fgcolor = self.inactive_color
			self.menufont.render_to(screen, (self.pos.x, pos_y), item[1], self.menufont.fgcolor)
			pos_y += 25

	def draw_panel(self, blocks, particles, playerone, flames, screen, grid):
		screen = pygame.display.get_surface()
		pos = Vector2(len(grid)*BLOCK+10, 10)
		self.panelfont.render_to(screen, pos, text=f'id {playerone.client_id}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, pos, text=f'pos {playerone.pos} {playerone.gridpos}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, pos, text=f'{self.screenw} x {self.screenh}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, pos, text=f'score {playerone.score}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, pos, text=f'hearts {playerone.hearts}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, pos, text=f'bombs {playerone.bombs_left} power {playerone.bombpower}', fgcolor=(111,222,111))
		#pos = [10,10]
		for netp in playerone.netplayers:
			if netp != playerone.client_id:
				np = playerone.netplayers[netp]
				pos.y += 30
				self.panelfont.render_to(screen, pos, text=f'netplayer {netp}', fgcolor=(111,222,211))
				pos.y += 30
				self.panelfont.render_to(screen, pos, text=f'hearts {np.get("hearts")}', fgcolor=(211,222,111))
				pos.y += 30
				self.panelfont.render_to(screen, pos, text=f'score {np.get("score")}', fgcolor=(211,222,111))
				pos.y += 30



	def get_selection(self):
		return self.menuitems[self.selected_item]

	def menu_up(self):
		if self.selected_item > 0:
			self.selected_item -= 1
		else:
			self.selected_item = len(self.menuitems) - 1

	def menu_down(self):
		if self.selected_item < len(self.menuitems) - 1:
			self.selected_item += 1
		else:
			self.selected_item = 0

