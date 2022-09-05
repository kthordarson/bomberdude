import pygame
import pygame.freetype
from pygame.math import Vector2
from loguru import logger
from constants import *


class DebugDialog:
	def __init__(self, screen):
		self.screen = screen
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.menusize = (400, 80)
		self.image = pygame.Surface(self.menusize)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		# self.pos = Vector2(self.screenw-self.menusize[0],self.screenh-80)
		self.pos = Vector2(10,500)
		self.rect = self.image.get_rect(topleft=self.pos)
		
	def draw_menubg(self):
		pass
		# self.bordercolor = pygame.Color("white")
		# bordersize = 1
		# menupos = [self.pos.x - bordersize, self.pos.y - bordersize]
		# #pygame.draw.rect(screen, self.bgcolor, (menupos[0], menupos[1], self.menusize[0], self.menusize[1])) # background
		# pygame.draw.line(self.screen, self.bordercolor, menupos ,(menupos[0], menupos[1] + self.menusize[1]), bordersize) # left border
		# pygame.draw.line(self.screen, self.bordercolor, (menupos[0] + self.menusize[0], menupos[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize) # right border
		# pygame.draw.line(self.screen, self.bordercolor, menupos, (menupos[0] + self.menusize[0], menupos[1]), bordersize) # top border
		# pygame.draw.line(self.screen, self.bordercolor, (menupos[0], menupos[1] + self.menusize[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize) # bottom border
		# self.bordercolor = pygame.Color("black")


class Menu:
	def __init__(self, screen):
		self.screen = screen
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.menusize = (250, 180)
		self.image = pygame.Surface(self.menusize)
		self.pos = Vector2(self.screenw // 2 - self.menusize[0] // 2, self.screenh // 2 - self.menusize[1] // 2)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.selected_color = (255, 255, 255)
		self.inactive_color = (155, 155, 155)
		self.menufont = pygame.freetype.Font(DEFAULTFONT, 24)
		self.debugfont = pygame.freetype.Font(DEFAULTFONT, 10)
		self.panelfont = pygame.freetype.Font(DEFAULTFONT, 15)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.panelfont_color = (255, 255, 255)
		self.menufont.fgcolor = self.selected_color
		self.bgcolor = pygame.Color("darkred")
		self.bordercolor = pygame.Color("black")
		# self.menufont.bgcolor = (44,55,66)
		self.menuitems = ['Start','Connect to server','Start server','Stop server','Pause','Restart','Quit']
		self.selected_item = 0

	def set_pos(self, newpos: Vector2):
		self.pos = newpos

	def get_menuitems(self):
		return self.menuitems

	def insert_menuitems(self, menu_entry=None, entry_pos=0):
		if menu_entry in self.menuitems:
			self.menuitems.insert(entry_pos, menu_entry)

	def add_menuitem(self, menu_entry=None):
		if menu_entry not in self.menuitems:
			self.menuitems.append(menu_entry)

	def draw_menubg(self, screen):
		self.bordercolor = pygame.Color("darkred")
		bordersize = 5
		menupos = [self.pos.x - bordersize, self.pos.y - bordersize]
		#pygame.draw.rect(screen, self.bgcolor, (menupos[0], menupos[1], self.menusize[0], self.menusize[1])) # background
		pygame.draw.line(screen, self.bordercolor, menupos ,(menupos[0], menupos[1] + self.menusize[1]), bordersize) # left border
		pygame.draw.line(screen, self.bordercolor, (menupos[0] + self.menusize[0], menupos[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize) # right border
		pygame.draw.line(screen, self.bordercolor, menupos, (menupos[0] + self.menusize[0], menupos[1]), bordersize) # top border
		pygame.draw.line(screen, self.bordercolor, (menupos[0], menupos[1] + self.menusize[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize) # bottom border
		self.bordercolor = pygame.Color("black")
		#pass


	def draw_mainmenu(self, screen):
		self.draw_menubg(screen)
		pos_y = self.pos.y
		for item in enumerate(self.menuitems):
			if item[0] == self.selected_item:
				self.menufont.fgcolor = self.selected_color
			else:
				self.menufont.fgcolor = self.inactive_color
			self.menufont.render_to(screen, (self.pos.x, pos_y), item[1], self.menufont.fgcolor)
			pos_y += 25


	def draw_panel(self, blocks, particles, player1, flames):
		pos = Vector2(10, self.screenh - 90)
		idx = 0
		#self.panelfont.render_to(self.screen, pos, f"[{idx}/{len(list(player1.net_players))}] playerid: {player1.client_id} ", self.panelfont_color)
		self.panelfont.render_to(self.screen, pos, f"playerid: {player1.client_id} pos:{player1.rect} vel:{player1.vel} accel:{player1.accel} ", self.panelfont_color)
		self.panelfont.render_to(self.screen, (pos.x, pos.y + 15), f"speed: {player1.speed} bombs: {player1.bombs_left} bombpower: {player1.bomb_power} score: {player1.score}", self.panelfont_color)


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
