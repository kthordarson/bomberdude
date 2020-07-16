import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS
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
        self.game_map = [[random.randint(0,8) for k in range(GRID_Y)] for j in range(GRID_X)]

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
                if self.game_map[k][j] == 9:   # 9 = blasted block
                    powerblock = Powerup_Block(k*BLOCKSIZE, j*BLOCKSIZE, screen=self.screen)
                    self.powerblocks.add(powerblock)
                    self.game_map[k][j] = powerblock.powerup_type[1]
            
def place_player(game_map):
    # place player somewhere where there is no block
    placed = False
    while not placed:
        x = random.randint(1,GRID_X-1)
        y = random.randint(1,GRID_Y-1)
        if game_map[x][y] > 3:
            placed = True
            print(f'player placed x:{x} y:{y} screen x:{x*BLOCKSIZE} y:{y*BLOCKSIZE} ')
            return (x*BLOCKSIZE,y*BLOCKSIZE)

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

    def game_init(self):
        self.game_data = Game_Data(screen=self.screen)
        self.players = pg.sprite.Group()
        player_pos = place_player(self.game_data.game_map)
        self.player1 = Player(x=player_pos[0], y=player_pos[1], player_id=33, screen=self.screen)
        self.players.add(self.player1)

    def run(self):
        # self.draw_map()
        self.game_init()
        self.game_data.place_blocks()
        while self.running:
            self.dt = self.mainClock.tick(FPS)
            #self.draw_map_with_bombs()
            self.handle_events()  # keyboard input stuff
            self.main_logic()     # update game_data, bombs and player stuff
            self.draw()           # draw

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_SPACE:
                    # print(f'space')
                    self.game_data = self.player1.drop_bomb(self.game_data)
                if event.key == pg.K_ESCAPE:
                    self.running = False
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
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
            # print(f'bombs on map {len(self.bombs)}')
            if bomb.time_left <= 0: 
                self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]] = 30  # set grid location where bomb was placed to 30 when it explodes
                bomb.exploding = True  # bomb explotion 'animation'
                # bomb.kill() # remove bomb from sprite group
                # self.game_data.bombs.remove(bomb)
            if bomb.done:
                # print(f'bx dt {bomb.dt:.2f} tl {bomb.time_left} {bomb.bomber_id} gridpos {bomb.gridpos} griddata: {self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]]}')
                self.player1.bombs_left += 1  # update bombs_left for player1
                bomb.kill()
        for powerblock in self.game_data.powerblocks:
            if powerblock.timer <= 0:
                self.game_data.game_map[powerblock.gridpos[0]][powerblock.gridpos[1]] = 0
                # powerblock.kill()
                print(f'powerblock kill')
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
                self.game_data.game_map = bomb.explode(self.game_data.game_map)
                self.game_data.place_blocks()
        self.players.draw(self.screen)
        player_pos = self.font.render(f'x:{self.player1.rect.x} y:{self.player1.rect.y}', 1, [255,255,255], [10,10,10])
        self.screen.blit(player_pos, (10,10))
        player_info = self.font.render(f'mb {self.player1.max_bombs} bl {self.player1.bombs_left} bp {self.player1.bomb_power} sp {self.player1.speed}', 1, [255,255,255], [10,10,10])
        self.screen.blit(player_info, (10,25))
        pg.display.flip()
        

if __name__ == '__main__':
    main_game = Game
    screen = pg.display.set_mode((GRID_X * BLOCKSIZE, GRID_Y * BLOCKSIZE),0,32)
    # main_game(screen=screen).game_init()
    main_game(screen=screen).run()
