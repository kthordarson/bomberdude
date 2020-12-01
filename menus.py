import pygame
import pygame.freetype
from functools import reduce
from operator import mul
from globals import BLOCKSIZE
from globals import Particle
from globals import DEFAULTFONT
from globals import get_angle
import math


class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.screenw, self.screenh = pygame.display.get_surface().get_size()
        self.menusize = (250, 180)
        self.image = pygame.Surface(self.menusize)
        self.pos = pygame.math.Vector2(self.screenw // 2 - self.menusize[0] // 2,
                                       self.screenh // 2 - self.menusize[1] // 2)
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
        self.menuitems.append("Start server")
        self.menuitems.append("Connect to server")
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
            self.menufont.render_to(screen, (self.pos.x, pos_y), item[1],
                                    self.menufont.fgcolor)
            pos_y += 25

    def draw_coll_debug(self, players, blocks, colls):
        pass

    def draw_panel(self, gamemap, blocks, particles, player1, flames):
        # todo fix this shit
        pos = pygame.math.Vector2(10, self.screenh - 40)
        try:
            self.panelfont.render_to(self.screen, pos, f"player pos x:{player1.rect} vel:{player1.vel} ", self.panelfont_color)
            self.panelfont.render_to(self.screen, (pos.x, pos.y + 12), f"s: {player1.speed} bombs: {player1.bombs_left}  bp: {player1.bomb_power} score: {player1.score}", self.panelfont_color)
            self.panelfont.render_to(self.screen, (pos.x, pos.y + 25), f"b: {len(blocks)} p: {len(particles)} f: {len(flames)}", self.panelfont_color)
        # self.screen.blit(self.image, self.rect)
        except IndexError as e:
            print(f"[panel] {e} {player1.gridpos}")
        except TypeError as e:
            print(f"[panel] {e} ")

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
