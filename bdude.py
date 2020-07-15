import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG
from player import Player as Player
# colors
# C:\python\lib\site-packages\pygame\colordict.py


class Block(pg.sprite.Sprite):
    def __init__(self, x, y, block_color):
        super().__init__()
        self.x = x
        self.y = y
        self.pos = (self.x, self.y)
        self.block_color = block_color
        self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE))
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.x = self.x
        self.rect.y = self.y


class Game_Data():
    def __init__(self):
        # super().__init__()
        # make a random grid map
        # self.screen = SCREEN
        # make a random map
        self.game_map = [[random.randint(0,10) for k in range(GRID_Y)] for j in range(GRID_X)]

        self.bombs = pg.sprite.Group()
        self.blocks = pg.sprite.Group()
        # set edges to solid blocks, 0 = solid block
        for x in range(GRID_X):
            self.game_map[x][0] = 0
            self.game_map[x][GRID_Y-1] = 0
        for y in range(GRID_Y):
            self.game_map[0][y] = 0
            self.game_map[GRID_X-1][y] = 0

    def draw_map(self):
        self.blocks = pg.sprite.Group()
        for k in range(GRID_X):
            for j in range(GRID_Y):
                if self.game_map[k][j] == 0:
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('darkseagreen')))
                if self.game_map[k][j] == 30:
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE, block_color=pg.Color('gray32')))
            
def place_player(game_map):
    # place player somewhere where there is no block
    placed = False
    while not placed:
        x = random.randint(1,GRID_X-1)
        y = random.randint(1,GRID_Y-1)
        if game_map[x][y] > 0:
            placed = True
            print(f'player placed x:{x} y:{y} screen x:{x*BLOCKSIZE} y:{y*BLOCKSIZE} ')
            return (x*BLOCKSIZE,y*BLOCKSIZE)

class Game():
    def __init__(self):
        # self.width = GRID_X * BLOCKSIZE
        # self.height = GRID_Y * BLOCKSIZE
        # self.FPS = 30
        self.mainClock = pg.time.Clock()
        self.dt = self.mainClock.tick(FPS) / 100
        self.screen = SCREEN  # pg.display.set_mode((self.width, self.height),0,32)
        self.bg_color = pg.Color('gray12')
        self.running = True
        pg.init()
        self.game_data = Game_Data()

        self.players = pg.sprite.Group()
        player_pos = place_player(self.game_data.game_map)
        self.player1 = Player(x=player_pos[0], y=player_pos[1], player_id=33, screen=SCREEN)
        self.players.add(self.player1)
        self.font = pg.font.SysFont('calibri', 33, True)
    def run(self):
        # self.draw_map()
        while self.running:
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
                if event.key == pg.K_DOWN:
                    self.player1.changespeed(0,1)
                if event.key == pg.K_UP:
                    self.player1.changespeed(0,-1)
                if event.key == pg.K_RIGHT:
                    self.player1.changespeed(1,0)
                if event.key == pg.K_LEFT:
                    self.player1.changespeed(-1,0)
            if event.type == pg.KEYUP:
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
                if event.key == pg.K_DOWN:
                    self.player1.changespeed(0,-1)
                if event.key == pg.K_UP:
                    self.player1.changespeed(0,1)
                if event.key == pg.K_RIGHT:
                    self.player1.changespeed(-1,0)
                if event.key == pg.K_LEFT:
                    self.player1.changespeed(1,0)
            if event.type == pg.MOUSEBUTTONDOWN:
                pass
            if event.type == pg.QUIT:
                self.running = False

    def main_logic(self):
        for bomb in self.game_data.bombs:
            # print(f'bombs on map {len(self.bombs)}')
            if bomb.time_left <= 0: 
                print(f'bx dt {bomb.dt:.2f} tl {bomb.time_left} {bomb.bomber_id} gridpos {bomb.gridpos} griddata: {self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]]}')
                self.game_data.game_map[bomb.gridpos[0]][bomb.gridpos[1]] = 30  # set grid location where bomb was placed to 30 when it explodes
                bomb.exploding = True  # bomb explotion 'animation'
                # bomb.kill() # remove bomb from sprite group
                # self.game_data.bombs.remove(bomb)
            if bomb.done:
                self.player1.bombs_left += 1  # update bombs_left for player1
                bomb.kill()

        self.game_data.bombs.update()
        self.players.update(self.game_data.blocks)


    def draw(self):
        SCREEN.fill(self.bg_color)
        self.game_data.draw_map()

        self.game_data.blocks.draw(SCREEN)
        self.game_data.bombs.draw(SCREEN)
        for bomb in self.game_data.bombs:
            if bomb.exploding:
                bomb.draw_expl(SCREEN)
        self.players.draw(SCREEN)
        text = self.font.render(f'x {self.player1.rect.x} y {self.player1.rect.y}', 1, (255,255,255))
        self.screen.blit(text, (10,10))
        pg.display.flip()
        

if __name__ == '__main__':
    main_game = Game
    SCREEN = pg.display.set_mode((GRID_X * BLOCKSIZE, GRID_Y * BLOCKSIZE),0,32)
    main_game().run()
