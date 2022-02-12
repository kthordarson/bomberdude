import pygame
import pygame.freetype
from pygame.math import Vector2
from globals import DEFAULTFONT
from loguru import logger

COLOR_INACTIVE = pygame.Color('lightskyblue3')
COLOR_ACTIVE = pygame.Color('dodgerblue2')


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
		self.panelfont = pygame.freetype.Font(DEFAULTFONT, 10)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.panelfont_color = (255, 255, 255)
		self.menufont.fgcolor = self.selected_color
		self.bgcolor = pygame.Color("darkred")
		self.bordercolor = pygame.Color("black")
		# self.menufont.bgcolor = (44,55,66)
		self.menuitems = []
		self.menuitems.append("Start")
		self.menuitems.append("Connect to server")
		self.menuitems.append("Start server")
		self.menuitems.append("Stop server")
		self.menuitems.append("Pause")
		self.menuitems.append("Restart")
		self.menuitems.append("Quit")
		self.selected_item = 0

	def draw_menubg(self, screen):
		pass

	# bordersize = 5
	# menupos = [self.pos.x - bordersize, self.pos.y - bordersize]
	# pygame.draw.rect(screen, self.bgcolor, (menupos[0], menupos[1], self.menusize[0], self.menusize[1]))  # background
	# pygame.draw.line(screen, self.bordercolor, menupos ,(menupos[0], menupos[1] + self.menusize[1]), bordersize)  # left border
	# pygame.draw.line(screen, self.bordercolor, (menupos[0] + self.menusize[0], menupos[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize)  # right border
	# pygame.draw.line(screen, self.bordercolor, menupos, (menupos[0] + self.menusize[0], menupos[1]), bordersize)  # top border
	# pygame.draw.line(screen, self.bordercolor, (menupos[0], menupos[1] + self.menusize[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize)  # bottom border

	def draw_mainmenu(self, screen):
		# self.draw_menubg(screen)
		pos_y = self.pos.y
		for item in enumerate(self.menuitems):
			if item[0] == self.selected_item:
				self.menufont.fgcolor = self.selected_color
			else:
				self.menufont.fgcolor = self.inactive_color
			self.menufont.render_to(screen, (self.pos.x, pos_y), item[1], self.menufont.fgcolor)
			pos_y += 25

	def draw_coll_debug(self, players, blocks, colls):
		pass

	def draw_server_debug(self, server=None):
		pos = self.screenh // 2
		pos = Vector2(pos, self.screenh - 50)
		server_text = f"players: {len(server.players)} "
		self.panelfont.render_to(self.screen, pos, server_text, self.panelfont_color)
		for player in server.players:
			pos.y += 12
			player_text = f'[C] id: {player} {player.pos} '
			self.panelfont.render_to(self.screen, (pos.x, pos.y), player_text, self.panelfont_color)
			

	def draw_panel(self, blocks, particles, player1, flames, dummies):
		pos = Vector2(10, self.screenh - 50)
		try:
			self.panelfont.render_to(self.screen, pos, f"playerid: {player1.client_id} pos x:{player1.rect} vel:{player1.vel} d:{len(dummies)} np:{len(player1.net_players)} conn:{player1.connected}/{player1.connecting} q:{player1.sq.qsize()}:{player1.rq.qsize()}", self.panelfont_color)
			self.panelfont.render_to(self.screen, (pos.x, pos.y + 12), f"s: {player1.speed} bombs: {player1.bombs_left}  bp: {player1.bomb_power} score: {player1.score}", self.panelfont_color)
			self.panelfont.render_to(self.screen, (pos.x, pos.y + 25), f"b: {len(blocks)} p: {len(particles)} f: {len(flames)}", self.panelfont_color)
			self.panelfont.render_to(self.screen, (pos.x, pos.y + 38), f"blocks: {player1.got_blocks} grid: {player1.got_gamemap}", self.panelfont_color)
		# self.screen.blit(self.image, self.rect)
		except IndexError as e:
			logger.error(f"[panel] {e} {player1.gridpos}")
		except TypeError as e:
			logger.error(f"[panel] {e} ")

	def draw_netpanel(self, net_players):
		logger.debug(f'draw_netpanel np: {len(net_players)}')
		pos = Vector2(100, self.screenh - 40)
		for player in net_players:
			# logger.debug(f'draw_netpanel np: {player}')
			try:
				self.panelfont.render_to(self.screen, pos, f"player: {player} ", self.panelfont_color)
				# self.panelfont.render_to(self.screen, (pos.x, pos.y + 12), f"s: {player.speed} bombs: {player.bombs_left}  bp: {player.bomb_power} score: {player.score}", self.panelfont_color)
			except IndexError as e:
				logger.error(f"[panel] {e} {player.gridpos}")
			except TypeError as e:
				logger.error(f"[panel] {e} ")

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
