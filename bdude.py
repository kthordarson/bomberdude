import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
import pdb

BLOCKSIZE = 15
GRID_X = 50
GRID_Y = 50

class Block(pg.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.pos = (self.x, self.y)
        self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE))
        pg.draw.rect(self.image, (255,0,255), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        self.rect = self.image.get_rect()
        self.image.fill((255,255,0), self.rect)
        # self.rect.center = (50,50)
        self.rect.x = self.x
        self.rect.y = self.y

class Player(pg.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.pos = (self.x, self.y)
        self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE))
        pg.draw.rect(self.image, (255,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        self.rect = self.image.get_rect()
        self.image.fill((255,0,0), self.rect)
        self.rect.x = self.x
        self.rect.y = self.y
        self.moving_down = False
        self.moving_up = False
        self.moving_right = False
        self.moving_left = False
        self.change_x = 0
        self.change_y = 0


    def stop_moving(self):
        # self.changespeed(0,0)
        self.moving_down = False
        self.moving_up = False
        self.moving_left = False
        self.moving_right = False

    def move_down(self):
        self.rect.y += 1
    def move_up(self):
        self.rect.y -= 1
    def move_right(self):
        self.rect.x += 1
    def move_left(self):
        self.rect.x -= 1
    def changespeed(self, x, y):
        self.change_x += x
        self.change_y += y
    def update(self, blocks):
        # Move left/right
        self.rect.x += self.change_x 
        # Did this update cause us to hit a wall?
        block_hit_list = pg.sprite.spritecollide(self, blocks, False)
        for block in block_hit_list:
            # If we are moving right, set our right side to the left side of
            # the item we hit
            if self.change_x > 0:
                self.rect.right = block.rect.left
            else:
                # Otherwise if we are moving left, do the opposite.
                self.rect.left = block.rect.right
 
        # Move up/down
        self.rect.y += self.change_y
 
        # Check and see if we hit anything
        block_hit_list = pg.sprite.spritecollide(self, blocks, False)
        for block in block_hit_list: 
            # Reset our position based on the top/bottom of the object.
            if self.change_y > 0:
                self.rect.bottom = block.rect.top
            else:
                self.rect.top = block.rect.bottom

    def update1(self, blocks):
        self.rect.x += self.change_x
        blockscoll = pg.sprite.spritecollide(self, blocks, False)
        if len(blockscoll) >+ 1:
            for block in blockscoll:
                if self.moving_down:
                    self.rect.bottom = block.rect.top
                    # self.rect.y += 1
                if self.moving_up:
                    self.rect.top = block.rect.bottom
                    # self.rect.y -= 1
                if self.moving_right:
                    self.rect.right = block.rect.left
                    # self.rect.x += 1
                if self.moving_left:
                    self.rect.left = block.rect.right
                    # self.rect.x -= 1
        else:
            if self.moving_down:
                # self.rect.bottom = block.rect.top
                self.rect.y += 1
            if self.moving_up:
                # self.rect.top = block.rect.bottom
                self.rect.y -= 1
            if self.moving_right:
                # self.rect.right = block.rect.left
                self.rect.x += 1
            if self.moving_left:
                # self.rect.left = block.rect.right
                self.rect.x -= 1


def place_player(game_map):
    placed = False
    while not placed:
        x = random.randint(1,GRID_X-1)
        y = random.randint(1,GRID_Y-1)
        if game_map[x][y] == 0:
            placed = True
            return (x*BLOCKSIZE,y*BLOCKSIZE)

class Game():
    def __init__(self):
        self.width = 750 # GRID_X * 10
        self.height = 750 # GRID_Y * 10
        self.FPS = 30
        self.mainClock = pg.time.Clock()
        self.dt = self.mainClock.tick(self.FPS) / 1000
        self.screen = pg.display.set_mode((self.width, self.height),0,32)
        self.bg_color = pg.Color('gray12')
        self.running = True
        # self.width, self.height = pg.display.get_surface().get_size()
        pg.init()
        
        self.game_map = [[random.randint(0,10) for k in range(GRID_Y)] for j in range(GRID_X)]
        for x in range(GRID_X):
            self.game_map[x][0] = 1
            self.game_map[x][GRID_Y-1] = 1 
        for y in range(GRID_Y):
            self.game_map[0][y] = 1
            self.game_map[GRID_X-1][y] = 1
        self.players = pg.sprite.Group()
        player_pos = place_player(self.game_map)
        self.player1 = Player(x=player_pos[0], y=player_pos[1])
        self.players.add(self.player1)

    def run(self):
        self.blocks = pg.sprite.Group()
        for k in range(GRID_X):
            for j in range(GRID_Y):
                if self.game_map[k][j] == 1:
                    self.blocks.add(Block(k*BLOCKSIZE, j*BLOCKSIZE))
                    # print(f'b {k} {j}')
        while self.running:            
            self.handle_events()
            self.main_logic()
            self.draw()

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    self.running = False
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
                if event.key == pg.K_DOWN:
                    self.player1.moving_down = True
                    self.player1.changespeed(0,1)
                    # self.player1.move_down()                    
                if event.key == pg.K_UP:
                    self.player1.moving_up = True
                    self.player1.changespeed(0,-1)
                    # self.player1.move_up()
                if event.key == pg.K_RIGHT:
                    self.player1.moving_right = True
                    self.player1.changespeed(1,0)
                    # self.player1.move_right()
                if event.key == pg.K_LEFT:
                    self.player1.moving_left = True
                    self.player1.changespeed(-1,0)
                    # self.player1.move_left()
            if event.type == pg.KEYUP:
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
                if event.key == pg.K_DOWN:
                    self.player1.stop_moving()
                    self.player1.changespeed(0,-1)
                if event.key == pg.K_UP:
                    self.player1.stop_moving()
                    self.player1.changespeed(0,1)
                if event.key == pg.K_RIGHT:
                    self.player1.stop_moving()
                    self.player1.changespeed(-1,0)
                if event.key == pg.K_LEFT:
                    self.player1.stop_moving()
                    self.player1.changespeed(1,0)
            if event.type == pg.MOUSEBUTTONDOWN:
                pass
            if event.type == pg.QUIT:
                self.running = False

    def main_logic(self):
        # coll = pg.sprite.spritecollide(self.player1, self.blocks, False)
        # if coll != []:
        #     print(f'{coll}')
        mouse_press = pg.mouse.get_pressed()
        if mouse_press[0]:
            x, y = pg.mouse.get_pos()
            # self.things.add(Thing(x,y))
        # coll = pg.sprite.groupcollide(self.blocks, self.things, False, False)
    def draw(self):
        # d_time = self.mainClock.tick(60) / 1000
        self.screen.fill(self.bg_color)
        self.blocks.update()
        self.blocks.draw(self.screen)
        self.players.update(self.blocks)
        self.players.draw(self.screen)
        pg.display.flip()
        

if __name__ == '__main__':
    main_game = Game
    main_game().run()
