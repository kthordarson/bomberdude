import pygame as pg
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS, PLAYERSIZE, BOMBSIZE, CHEAT
from globals import inside_circle as inside_circle

class Info_panel():
    def __init__ (self, x, y, screen):
        self.screen = screen
        self.x = x
        self.y = y
        self.panelitems = []        
        self.font = pg.font.SysFont('calibri', 15, True)
        self.font_color = [255,255,255]
    def add_panel_item(self, item):
        self.panelitems.append(item)
    def draw_panel(self, player1):
        text1 = self.font.render(f'player pos x:{player1.rect.x} y:{player1.rect.y} grid {player1.gridpos}', 1, [255,255,255], [10,10,10])
        text2 = self.font.render(f'player health: {player1.health} max bombs {player1.max_bombs} bombs left {player1.bombs_left} bomb power: {player1.bomb_power} speed: {player1.speed}', 1, [255,255,255], [10,10,10])
        text3 = self.font.render(f'score: {player1.score}', 1, [255,255,255], [10,10,10])
        self.screen.blit(text1, (self.x, self.y))
        self.screen.blit(text2, (self.x, self.y+text1.get_height()))
        self.screen.blit(text3, (self.x, self.y+text1.get_height()++text2.get_height()))
    def update(self, game_data):
        pass
class Menu():
    def __init__(self, screen):
        self.screen = screen
        self.menu_pos = [100,100]
        self.selected_color = [255,255,255]
        self.inactive_color = [55,55,55]
        self.menufont = pg.font.SysFont('calibri', 35, True)
        self.menuitems = []
        self.menuitems.append('Start')
        self.menuitems.append('Pause')
        self.menuitems.append('Restart')
        self.menuitems.append('Quit')
        self.selected_item = 0

    def draw_mainmenu(self):
        global DEBUG
        pos_y = self.menu_pos[1]
        for item in enumerate(self.menuitems):
            if item[0] == self.selected_item:
                text_color = self.selected_color
            else:
                text_color = self.inactive_color
            text = self.menufont.render(item[1], 1, text_color, [1,1,1])
            self.screen.blit(text, (self.menu_pos[0], pos_y))
            pos_y += self.menufont.get_height()
#            if DEBUG:
#                print(f'mm s:{self.selected_item} l:{len(self.menuitems)}')
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
