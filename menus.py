import pygame as pg
import pygame.freetype
from functools import reduce
from operator import mul


class Info_panel():
    def __init__(self, x, y, screen):
        self.screen = screen
        self.pos = pg.math.Vector2(x, y)
        self.panelitems = []
        self.font = pg.freetype.Font("DejaVuSans.ttf", 12)
        self.font_color = (255, 255, 255)

    def add_panel_item(self, item):
        self.panelitems.append(item)

    def draw_panel(self, gamemap, blocks, particles, player1):
        # todo fix this shit
        self.font.render_to(
            self.screen, self.pos,
            f'player pos x:{player1.rect.x} y:{player1.rect.y} grid:{player1.gridpos} vel:{player1.vel} gamemap:{gamemap.grid[player1.gridpos[0]][player1.gridpos[1]]}', self.font_color)
        self.font.render_to(self.screen, (self.pos.x, self.pos.y+12), f'bombs: {player1.bombs_left} score: {player1.score}', self.font_color)
        self.font.render_to(self.screen, (self.pos.x, self.pos.y+25), f'blocks: {len(blocks)} particles {len(particles)}', self.font_color)


class Menu():
    def __init__(self, screen):
        self.screen = screen
        w, h = pg.display.get_surface().get_size()
        self.menusize = [250, 180]
        self.pos = pg.math.Vector2(w // 2 - self.menusize[0] // 2, h // 2 - self.menusize[1] // 2)
        self.selected_color = (255, 255, 255)
        self.inactive_color = (155, 155, 155)
        self.menufont = pg.freetype.Font("DejaVuSans.ttf", 24)
        self.menufont.fgcolor = self.selected_color
        self.bgcolor = pg.Color('darkred')
        self.bordercolor = pg.Color('black')
        # self.menufont.bgcolor = (44,55,66)
        self.menuitems = []
        self.menuitems.append('Start')
        self.menuitems.append('Start server')
        self.menuitems.append('Connect to server')
        self.menuitems.append('Pause')
        self.menuitems.append('Restart')
        self.menuitems.append('Quit')
        self.selected_item = 0

    def draw_menubg(self, screen):

        bordersize = 5
        menupos = [self.pos.x - bordersize, self.pos.y - bordersize]
        pg.draw.rect(screen, self.bgcolor, (menupos[0], menupos[1], self.menusize[0], self.menusize[1]))  # background
        pg.draw.line(screen, self.bordercolor, menupos, (menupos[0], menupos[1] + self.menusize[1]), bordersize)  # left border
        pg.draw.line(screen, self.bordercolor, (menupos[0] + self.menusize[0], menupos[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize)  # right border
        pg.draw.line(screen, self.bordercolor, menupos, (menupos[0] + self.menusize[0], menupos[1]), bordersize)  # top border
        pg.draw.line(screen, self.bordercolor, (menupos[0], menupos[1] + self.menusize[1]), (menupos[0] + self.menusize[0], menupos[1] + self.menusize[1]), bordersize)  # bottom border

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
