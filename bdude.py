import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
import time
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS, PLAYERSIZE, BOMBSIZE, CHEAT
from globals import inside_circle as inside_circle
from player import Player as Player
from blocks import Block, Powerup_Block, BlockBomb
# colors
# C:\python\lib\site-packages\pygame\colordict.py

class Game_Data():
    def __init__(self, screen):
        # super().__init__()
        # make a random grid map
        self.screen = screen
        # make a random map
        self.game_map = [[random.randint(0,9) for k in range(GRID_Y+1)] for j in range(GRID_X+1)]

        self.bombs = pg.sprite.Group()
        self.blocks = pg.sprite.Group()
        self.powerblocks = pg.sprite.Group()
        # set edges to solid blocks, 0 = solid block
        for x in range(GRID_X+1):
            self.game_map[x][0] = 1
            self.game_map[x][GRID_Y] = 1
        for y in range(GRID_Y+1):
            self.game_map[0][y] = 1
            self.game_map[GRID_X][y] = 1

    def get_block(self, x, y):
        # get block inf from grid
        return self.game_map[x][y]

    def kill_block(self, x, y):
        # remove block at gridpos x,y
        for block in self.blocks:
            if block.gridpos[0] == x and block.gridpos[1] == y:
                block.kill()
                self.game_map[x][y] = 0
                block = Block(x,y, screen=self.screen, block_type=0)
                self.blocks.add(block)

    def place_blocks(self):
        global DEBUG
        if DEBUG:
            t1 = time.time()
            # print(f'place_blocks: start')
        self.blocks = pg.sprite.Group()
        # self.powerblocks = pg.sprite.Group()
        for k in range(0,GRID_X+1):
            for j in range(0, GRID_Y+1):
                block = Block(k,j, screen=self.screen, block_type=self.game_map[k][j])
                self.blocks.add(block)
        if DEBUG:
            print(f'place_blocks: done time {time.time() - t1:.2f}')

    def update_map(self, mapinfo):
        global DEBUG
        for item in mapinfo:
            if DEBUG:
                print(f'update_map items: {len(mapinfo)} item: {item}')
            gridpos = [item[0], item[1]]
            block_id = self.game_map[gridpos[0]][gridpos[1]]
            if 3 <= block_id <= 9:
                # powerblock = Powerup_Block(gridpos[0], gridpos[1], screen=self.screen)
                # self.powerblocks.add(powerblock)
                self.game_map[item[0]][item[1]] = powerblock.powerup_type[1]
                self.kill_block(item[0], item[1])
                if DEBUG:
                    print(f'update_map: powerupdrop on {gridpos} bid {block_id} p {powerblock.powerup_type[1]} newbid: {self.game_map[item[0]][item[1]]}')
            # self.game_map[item[0]][item[1]] = 30

    def destroy_blocks(self, block_list):
        pass
class Menu():
    def __init__(self, screen):
        self.screen = screen
        super().__init__()
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

            

class Game():
    def __init__(self, screen):
        self.mainClock = pg.time.Clock()
        self.screen = screen  # pg.display.set_mode((self.width, self.height),0,32)
        self.bg_color = pg.Color('gray12')
        self.running = True
        pg.init()
        self.font = pg.font.SysFont('calibri', 15, True)

        self.show_mainmenu = True
        self.paused = True
    def place_player(self):
        # place player somewhere where there is no block
        placed = False
        while not placed:
            x = 5 # random.randint(1,GRID_X-1)
            y = 5 # random.randint(1,GRID_Y-1)
            self.game_data.game_map[x][y] = 0
            # make a clear radius around spawn point
            for clear_bl in list(inside_circle(3,x,y)):
                try:
                    if self.game_data.game_map[clear_bl[0]][clear_bl[1]] > 1:
                        self.game_data.game_map[clear_bl[0]][clear_bl[1]] = 0
                except:
                    print(f'exception in place_player {clear_bl}')
            placed = True
            if DEBUG:
                print(f'player placed x:{x} y:{y} screen x:{x*BLOCKSIZE} y:{y*BLOCKSIZE} ')
            return (x*BLOCKSIZE,y*BLOCKSIZE)

    def game_init(self):
        global DEBUG
        if DEBUG:
            t1 = time.time()
            # print(f'game_init: start')

        # data and classes for Game
        self.game_data = Game_Data(screen=self.screen)
        # menus
        self.game_menu = Menu(self.screen)
        # players
        self.players = pg.sprite.Group()
        player_pos = self.place_player()
        self.player1 = Player(x=player_pos[0], y=player_pos[1], player_id=33, screen=self.screen)
        self.players.add(self.player1)

        if DEBUG:
            print(f'game_init: done time {time.time() - t1:.2f}')

    def run(self):
        # self.draw_map()
        self.game_init()
        self.game_data.place_blocks()
        while self.running:
            self.dt = self.mainClock.tick(FPS)
            #self.draw_map_with_bombs()
            self.handle_events()  # keyboard input stuff
            if not self.paused:
                self.main_logic()     # update game_data, bombs and player stuff
            self.draw()           # draw

    def handle_menu(self, selection):
        if selection == 'Quit':
            self.running = False
        if selection == 'Pause':
            self.paused^= True
            self.show_mainmenu^= True
        if selection == 'Start':
            self.paused^= True
            self.show_mainmenu^= True
        if selection == 'Restart':
            self.paused^= True
            self.show_mainmenu^= True
            self.game_init()
            self.run()

    def handle_events(self):
        global CHEAT
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_SPACE or event.key == pg.K_RETURN:
                    if not self.paused:
                        self.game_data = self.player1.drop_bomb(self.game_data)
                    if self.show_mainmenu or self.paused:
                        selection = self.game_menu.get_selection()
                        self.handle_menu(selection)
                if event.key == pg.K_ESCAPE:
                    if not self.paused:
                        self.running = False
                    else:
                        self.paused^= True
                        self.show_mainmenu^= True

                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_c:
                    self.player1.bomb_power = 100
                    self.player1.max_bombs = 10
                    self.player1.bombs_left = 10
                    self.player1.speed = 10
                    CHEAT = True
                if event.key == pg.K_p:
                    self.paused^= True
                    self.show_mainmenu^= True
                if event.key == pg.K_m:
                    self.show_mainmenu^= True
                    self.paused^= True
                if event.key == pg.K_d:
                    global DEBUG
                    DEBUG^= True
                if event.key == pg.K_r:
                    self.game_init()
                    self.run()
                if event.key == pg.K_DOWN:
                    if not self.paused:
                        self.player1.changespeed(0,self.player1.speed)
                    if self.show_mainmenu:
                        self.game_menu.menu_down()
                if event.key == pg.K_UP:
                    if not self.paused:
                        self.player1.changespeed(0,-self.player1.speed)
                    if self.show_mainmenu:
                        self.game_menu.menu_up()
                if event.key == pg.K_RIGHT:
                    if not self.paused:
                        self.player1.changespeed(self.player1.speed,0)
                if event.key == pg.K_LEFT:
                    if not self.paused:
                        self.player1.changespeed(-self.player1.speed,0)
            if event.type == pg.KEYUP:
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
                if event.key == pg.K_DOWN:
                    if not self.paused:
                        self.player1.changespeed(0,0)
                        self.player1.change_y = 0
                if event.key == pg.K_UP:
                    if not self.paused:
                        self.player1.changespeed(0,0)
                        self.player1.change_y = 0
                if event.key == pg.K_RIGHT:
                    if not self.paused:
                        self.player1.changespeed(0,0)
                        self.player1.change_x = 0
                if event.key == pg.K_LEFT:
                    if not self.paused:
                        self.player1.changespeed(0,0)
                        self.player1.change_x = 0
            if event.type == pg.MOUSEBUTTONDOWN:
                pass
            if event.type == pg.QUIT:
                self.running = False

    def main_logic(self):
        global DEBUG
        for bomb in self.game_data.bombs:
            if bomb.exploding:
                bomb.explode(self.game_data.game_map)
                for flame in bomb.flames:
                    flame.update()
                    flame_hits = pg.sprite.spritecollide(flame, self.game_data.blocks, False)  # get blocks that flames touch
                    for block in flame_hits:
                        if block.block_type > 0:  # if block_type is larger than 0, stop expanding flame, else keep expanding until solid is hit
                            flame.set_adder(0)
                            flame.stop_expander()
                            flame.kill()
                        if block.block_type > 2: # if block_type is larger than 2 (less than 2 are permanent blocks)
                            block.kill()
                            powerblock = Powerup_Block(block.gridpos[0], block.gridpos[1], screen=self.screen)  # drop powerup where destroyed block was before
                            self.game_data.powerblocks.add(powerblock)
                            newblock = Block(block.gridpos[0], block.gridpos[1], screen=self.screen, block_type=0)  # make a new type 0 block....
                            self.game_data.blocks.add(newblock)
                            if DEBUG:
                                print(f'blhit: {block.gridpos} x:{block.x} y:{block.y} {block.block_type} fl: dir: {flame.dir} u:{flame.l_up} d:{flame.l_dn} r:{flame.l_r} l:{flame.l_l} a:{flame.flame_adder} fl:{flame.flame_length} fe:{flame.expand}')
            if bomb.done:
                self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]] = 0
                self.player1.bombs_left += 1  # update bombs_left for player1
                for flame in bomb.flames:
                    flame.kill()
                bomb.kill()
        for powerblock in self.game_data.powerblocks:
            if powerblock.timer <= 0:
                powerblock.kill()
                # self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]] = 0
                # powerblock.kill()
        self.game_data.blocks.update()
        self.game_data.powerblocks.update()
        self.game_data.bombs.update()
        self.players.update(self.game_data)


    def draw(self):
        self.screen.fill(self.bg_color)
        # self.game_data.draw_map()

        self.game_data.blocks.draw(self.screen)
        self.game_data.powerblocks.draw(self.screen)
        self.game_data.bombs.draw(self.screen)
        for bomb in self.game_data.bombs:
            if bomb.exploding:
                bomb.draw_explotion()                                
                for flame in bomb.flames:
                    flame.draw_flame()
        self.players.draw(self.screen)
        if self.show_mainmenu:
            self.game_menu.draw_mainmenu()
        if DEBUG:
            player_pos = self.font.render(f'x:{self.player1.rect.x} y:{self.player1.rect.y}', 1, [255,255,255], [10,10,10])
            self.screen.blit(player_pos, (10,10))
            player_info = self.font.render(f'mb {self.player1.max_bombs} bl {self.player1.bombs_left} bp {self.player1.bomb_power} sp {self.player1.speed}', 1, [255,255,255], [10,10,10])
            self.screen.blit(player_info, (10,25))
            for block in self.game_data.blocks:
                block.draw_id()
                # block.draw_outlines()
        pg.display.flip()


if __name__ == '__main__':
    main_game = Game
    screen = pg.display.set_mode((GRID_X * BLOCKSIZE + 20 , GRID_Y * BLOCKSIZE + 20),0,32)
    # main_game(screen=screen).game_init()
    main_game(screen=screen).run()
