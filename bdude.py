import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
import time
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS
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
        self.game_map = [[random.randint(2,8) for k in range(GRID_Y)] for j in range(GRID_X)]

        self.bombs = pg.sprite.Group()
        self.blocks = pg.sprite.Group()
        self.powerblocks = pg.sprite.Group()
        # set edges to solid blocks, 0 = solid block
        for x in range(GRID_X):
            self.game_map[x][0] = 1
            self.game_map[x][GRID_Y-1] = 1
        for y in range(GRID_Y):
            self.game_map[0][y] = 1
            self.game_map[GRID_X-1][y] = 1

    def place_blocks(self):
        global DEBUG
        if DEBUG:
            t1 = time.time()
            # print(f'place_blocks: start')
        self.blocks = pg.sprite.Group()
        # self.powerblocks = pg.sprite.Group()
        for k in range(GRID_X):
            for j in range(GRID_Y):
                if self.game_map[k][j] == 0:   # 0
                    pass
                    # self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('black'), screen=self.screen, solid=False))
                if self.game_map[k][j] == 1:   # 1 = solid block
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('orangered4'), screen=self.screen, solid=True, permanent=True))
                if self.game_map[k][j] == 2:   # 2 = solid block
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('grey39'), screen=self.screen, solid=True))
                if self.game_map[k][j] == 3:   # 3 = solid block
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('gray26'), screen=self.screen, solid=True))
                if self.game_map[k][j] == 4:   # 3 = solid block
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('gray31'), screen=self.screen, solid=True, permanent=True))
#                if self.game_map[k][j] == 9:   # 9 = blasted block
#                    powerblock = Powerup_Block(k*BLOCKSIZE, j*BLOCKSIZE, screen=self.screen)
#                    self.powerblocks.add(powerblock)
#                    self.game_map[k][j] = powerblock.powerup_type[1]
        if DEBUG:
            print(f'place_blocks: done time {time.time() - t1:.2f}')

    def update_map(self, mapinfo):
        global DEBUG
        for item in mapinfo:
            if DEBUG:
                print(f'updatemap items: {len(mapinfo)} item: {item}')
            powerblock = Powerup_Block(item[0]*BLOCKSIZE, item[1]*BLOCKSIZE, screen=self.screen)
            self.powerblocks.add(powerblock)
            self.game_map[item[0]][item[1]] = powerblock.powerup_type[1]
            # self.game_map[item[0]][item[1]] = 30
            
class Menu():
    def __init__(self, screen):
        self.screen = screen
        super().__init__()
        self.menu_pos = [100,100]
        self.selected_color = [255,255,255]
        self.inactive_color = [55,55,55]

        self.menuitems = []
        self.menuitems.append(self.menufont.render('Start', 1, selected_color, [10,10,10]))
        self.menuitems.append(self.menufont.render('Pause', 1, inactive_color, [10,10,10]))
        self.menuitems.append(self.menufont.render('Restart', 1, inactive_color, [10,10,10]))
        self.menuitems.append(self.menufont.render('Quit', 1, inactive_color, [10,10,10]))

    def draw_mainmenu(self):        
        for item in self.menuitems:
            self.screen.blit(item, self.menu_pos)
            self.menu_pos[1] += 35

class Game():
    def __init__(self, screen):
        # self.width = GRID_X * BLOCKSIZE
        # self.height = GRID_Y * BLOCKSIZE
        # self.FPS = 30
        self.mainClock = pg.time.Clock()
        # self.dt = self.mainClock.tick(FPS) / 1000
        self.screen = screen  # pg.display.set_mode((self.width, self.height),0,32)
        self.bg_color = pg.Color('gray12')
        self.running = True
        pg.init()
        self.font = pg.font.SysFont('calibri', 15, True)
        self.menufont = pg.font.SysFont('calibri', 35, True)
        self.show_mainmenu = True
        self.paused = True
    def place_player(self):
        # place player somewhere where there is no block
        placed = False
        while not placed:
            x = random.randint(1,GRID_X-1)
            y = random.randint(1,GRID_Y-1)
            if self.game_data.game_map[x][y] > 3:
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
        self.game_data = Game_Data(screen=self.screen)
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

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_SPACE:
                    if not self.paused:
                        self.game_data = self.player1.drop_bomb(self.game_data)
                if event.key == pg.K_ESCAPE:
                    self.running = False
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_p:
                    self.paused^= True
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
                    self.player1.changespeed(0,self.player1.speed)
                if event.key == pg.K_UP:
                    self.player1.changespeed(0,-self.player1.speed)
                if event.key == pg.K_RIGHT:
                    self.player1.changespeed(self.player1.speed,0)
                if event.key == pg.K_LEFT:
                    self.player1.changespeed(-self.player1.speed,0)
            if event.type == pg.KEYUP:
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
                if event.key == pg.K_DOWN:
                    self.player1.changespeed(0,0)
                    self.player1.change_y = 0
                if event.key == pg.K_UP:
                    self.player1.changespeed(0,0)
                    self.player1.change_y = 0
                if event.key == pg.K_RIGHT:
                    self.player1.changespeed(0,0)
                    self.player1.change_x = 0
                if event.key == pg.K_LEFT:
                    self.player1.changespeed(0,0)
                    self.player1.change_x = 0
            if event.type == pg.MOUSEBUTTONDOWN:
                pass
            if event.type == pg.QUIT:
                self.running = False

    def main_logic(self):
        for bomb in self.game_data.bombs:
            if bomb.time_left <= 0: 
                self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]] = 29  # set grid location where bomb was placed to 30 when it explodes
                bomb.exploding = True  # bomb explotion 'animation'
            if bomb.done:
                self.player1.bombs_left += 1  # update bombs_left for player1
                bomb.kill()
        for powerblock in self.game_data.powerblocks:
            if powerblock.timer <= 0:
                self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]] = 0
                # powerblock.kill()
        self.game_data.powerblocks.update()
        self.game_data.bombs.update()
        self.players.update(self.game_data)


    def draw(self):
        self.screen.fill(self.bg_color)
        # self.game_data.draw_map()

        self.game_data.blocks.draw(self.screen)
        self.game_data.powerblocks.draw(self.screen)
        # for block in self.game_data.blocks:
        #     block.draw_outlines()
        # for block in self.game_data.powerblocks:
        #     block.draw_outlines()
        self.game_data.bombs.draw(self.screen)
        for bomb in self.game_data.bombs:
            if bomb.exploding:
                # self.game_data.game_map = bomb.update_map(self.game_data.game_map)
                destroyed_blocks = bomb.explode(self.game_data.game_map)
                self.game_data.update_map(destroyed_blocks)
                # self.game_data.place_blocks()
        self.players.draw(self.screen)
        if self.show_mainmenu:
            self.mainmenu()
        if DEBUG:
            player_pos = self.font.render(f'x:{self.player1.rect.x} y:{self.player1.rect.y}', 1, [255,255,255], [10,10,10])
            self.screen.blit(player_pos, (10,10))
            player_info = self.font.render(f'mb {self.player1.max_bombs} bl {self.player1.bombs_left} bp {self.player1.bomb_power} sp {self.player1.speed}', 1, [255,255,255], [10,10,10])
            self.screen.blit(player_info, (10,25))
            for block in self.game_data.blocks:
                block.draw_debug()
        pg.display.flip()
        

if __name__ == '__main__':
    main_game = Game
    screen = pg.display.set_mode((GRID_X * BLOCKSIZE, GRID_Y * BLOCKSIZE),0,32)
    # main_game(screen=screen).game_init()
    main_game(screen=screen).run()
