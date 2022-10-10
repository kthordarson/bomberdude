import pygame
import pygame.freetype
from pygame.math import Vector2
from loguru import logger
from constants import *
from threading import Thread

class DebugDialog:
	def __init__(self, screen, font):
		self.screen = pygame.display.get_surface()
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.menusize = (400, 80)
		self.image = pygame.Surface(self.menusize)
		self.font = font  # pygame.freetype.Font(font, 12)
		self.font_color = (255, 255, 255)
		# self.pos = Vector2(self.screenw-self.menusize[0],self.screenh-80)
		self.pos = Vector2(10, 500)
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

	def draw_panel(self, blocks=None, particles=None, playerone=None, flames=None, screen=None, grid=None):
		screen = pygame.display.get_surface()
		pos = Vector2(len(grid)*BLOCK+10, 10)
		self.panelfont.render_to(screen, dest=pos, text=f'id {playerone.client_id}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, dest=pos, text=f'pos {playerone.pos} {playerone.gridpos}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, dest=pos, text=f'{self.screenw} x {self.screenh}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, dest=pos, text=f'score {playerone.score}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, dest=pos, text=f'hearts {playerone.hearts}', fgcolor=(111,222,111))
		pos += (0,25)
		self.panelfont.render_to(screen, dest=pos, text=f'bombs {playerone.bombs_left} power {playerone.flame_len}', fgcolor=(111,222,111))


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

class ServerGUI(Thread):
	def __init__(self):
		super().__init__(daemon=True)
		self.screen =  pygame.display.set_mode((800,600), 0, 8)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.menusize = (250, 180)
		self.image = pygame.Surface(self.menusize)
		self.pos = Vector2(self.screenw // 2 - self.menusize[0] // 2, self.screenh // 2 - self.menusize[1] // 2)
		self.rect = self.image.get_rect(topleft=self.pos)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.font_color = (255, 255, 255)
		self.bg_color = pygame.Color("black")
		self.bombclients = []
		self.netplayers = {}
		self.guiclock = pygame.time.Clock()
		self.gamemapgrid = []

	def renderinfo(self):
			self.guiclock.tick(FPS)
			try:
				pygame.display.flip()
			except:
				self.screen = pygame.display.set_mode((800,600), 0, 8)
			self.screen.fill(self.bg_color)
			ctextpos = [10, 10]
			try:

				msgtxt = f'fps={self.guiclock.get_fps():2f} clients:{len(self.bombclients)} np:{len(self.netplayers)} '
			except TypeError as e:
				logger.warning(f'[ {self} ] TypeError:{e}')
				msgtxt = ''
			self.font.render_to(self.screen, ctextpos, msgtxt, (150,150,150))
			ctextpos = [15, 25]
			npidx = 1
			for np in self.netplayers:
				snp = self.netplayers[np]
				msgtxt = f"[{npidx}/{len(self.netplayers)}] servernp:{snp.get('client_id')} pos={snp.get('pos')} {snp.get('gridpos')} kill:{snp.get('kill')}"
				self.font.render_to(self.screen, (ctextpos[0]+13, ctextpos[1] ), msgtxt, (130,30,130))
				ctextpos[1] += 20
				npidx += 1
			bidx = 1
			plcolor = [255,0,0]
			for bc in self.bombclients:
				if bc.client_id:
					bctimer = pygame.time.get_ticks()-bc.lastupdate
					self.gamemapgrid = bc.gamemap.grid
					bcgridpos = (bc.gridpos[0], bc.gridpos[1])
					np = {'client_id':bc.client_id, 'pos':bc.pos, 'centerpos':bc.centerpos,'kill':round(bc.kill), 'gridpos':bcgridpos}
					self.netplayers[bc.client_id] = np
					bc.servercomm.netplayers[bc.client_id] = np
					textmsg = f'[{bidx}/{len(self.bombclients)}] bc={bc.client_id} pos={bc.pos} np:{len(bc.servercomm.netplayers)} t:{bctimer}'
					self.font.render_to(self.screen, ctextpos, textmsg, (130,130,130))
					ctextpos[1] += 20
					bidx += 1
					#self.font.render_to(self.screen, (ctextpos[0]+10, ctextpos[1]), f'np={np}', (140,140,140))
					#ctextpos[1] += 20
					npidx = 1
					for npitem in bc.servercomm.netplayers:
						bcnp = bc.servercomm.netplayers[npitem]
						msgstring = f'[{npidx}/{len(bc.servercomm.netplayers)}] bcnp={bcnp["client_id"]} pos={bcnp["pos"]} {bcnp["gridpos"]} kill={bcnp["kill"]} t:{bctimer}'
						if npitem != '0':
							self.font.render_to(self.screen, (ctextpos[0]+15, ctextpos[1]), msgstring, (145,245,145))
							npidx += 1
							ctextpos[1] += 20
						if npitem == '0':
							self.font.render_to(self.screen, (ctextpos[0]+15, ctextpos[1]), msgstring, (145,145,145))
							npidx += 1
							ctextpos[1] += 20
					pygame.draw.circle(self.screen, plcolor, center=bc.pos, radius=5)
					plcolor[1] += 60
					plcolor[2] += 60
