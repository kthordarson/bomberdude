import pygame as pg
import pygame.freetype
class Info_panel():
	def __init__ (self, x, y, screen):
		self.screen = screen
		self.pos = pg.math.Vector2(x,y)
		self.panelitems = []
		self.font = pg.freetype.Font("DejaVuSans.ttf", 12)
		self.font_color = (255,255,255)
	def add_panel_item(self, item):
		self.panelitems.append(item)
	def draw_panel(self, game_data, player1):
		# todo fix this shit
		self.font.render_to(self.screen, self.pos, f'player pos x:{player1.rect.x} y:{player1.rect.y} grid:{player1.gridpos} vel:{player1.vel} map:{game_data.game_map[player1.gridpos[0]][player1.gridpos[1]]}', self.font_color)
		self.font.render_to(self.screen, (self.pos.x, self.pos.y+12), f'bombs: {player1.bombs_left} score: {player1.score}', self.font_color)


class Menu():
	def __init__(self, screen):
		self.screen = screen
		self.pos = pg.math.Vector2(100,100)
		self.selected_color = (255,255,255)
		self.inactive_color = (55,55,55)
		self.menufont = pg.freetype.Font("DejaVuSans.ttf", 24)
		self.menufont.fgcolor = self.selected_color
		# self.menufont.bgcolor = (44,55,66)
		self.menuitems = []
		self.menuitems.append('Start')
		self.menuitems.append('Start server')
		self.menuitems.append('Connect to server')
		self.menuitems.append('Pause')
		self.menuitems.append('Restart')
		self.menuitems.append('Quit')
		self.selected_item = 0

	def draw_mainmenu(self, screen):
		pos_y = self.pos.y
		rect = pg.draw.rect(screen, (220, 0, 0), (self.pos.x, self.pos.y, 150, 160))
		for item in enumerate(self.menuitems):
			if item[0] == self.selected_item:
				self.menufont.fgcolor = self.selected_color
			else:
				self.menufont.fgcolor = self.inactive_color
			self.menufont.render_to(screen, (111, pos_y), item[1], self.menufont.fgcolor)
			pos_y += 25

	def get_selection(self):
		return self.menuitems[self.selected_item]
	def menu_up(self):
		if self.selected_item > 0:
			self.selected_item -= 1
		else:
			self.selected_item = len(self.menuitems)-1
	def menu_down(self):
		if self.selected_item < len(self.menuitems)-1:
			self.selected_item += 1
		else:
			self.selected_item = 0
