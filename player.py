import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG

class BlockBomb(pg.sprite.Sprite):
    def __init__(self, x, y, bomber_id, block_color, screen):
        super().__init__()
        self.screen = screen
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x // BLOCKSIZE,y // BLOCKSIZE)
        self.x = x + (BLOCKSIZE//2)
        self.y = y + (BLOCKSIZE//2)
        self.bomber_id = bomber_id
        self.block_color = block_color
        self.start_time = pg.time.get_ticks() / FPS
        # self.pos = (self.x, self.y)
        self.image = pg.Surface((BLOCKSIZE//2,BLOCKSIZE//2))
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, BLOCKSIZE//2,BLOCKSIZE//2])
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.x = self.x
        self.rect.y = self.y
        self.bomb_timer = 100
        self.time_left = 3
        self.exploding = False
        self.exp_steps = 5
        self.exp_radius = 2
        self.done = False

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.bomb_timer:
            # print(f'bomb expl {self.bomb_timer} dt {self.dt:.2f} pos {self.rect.x} {self.rect.y} bid {self.bomber_id}')
            self.time_left = 0 
            # self.kill()
            # self.exploding = True
#        if self.exploding:
#            self.explode_animation()
            # pg.draw.circle(self.screen, (255,255,255), (self.rect.x, self.rect.y), 20,2)
            # pg.draw.circle(SCREEN, (255,255,255), (100,100), 100,2)
            # self.exploding = False
    def draw_expl(self, screen):
        pg.draw.circle(screen, (255,255,255), (self.rect.x, self.rect.y), self.exp_radius,2)
        # pg.draw.circle(screen, (255,255,255), (250, 250), 100,2)
        self.exp_radius += 3
        self.exp_steps -= 1
        print(f'bomb anim {self.exp_steps} r {self.exp_radius} pos {self.rect.x} {self.rect.y}')
        if self.exp_steps <= 0:
            self.exploding = False
            print(f'b expl finish')
            self.done = True

class Player(pg.sprite.Sprite):
    def __init__(self, x, y, player_id, screen):
        super().__init__()
        self.screen = screen
        self.x = x
        self.y = y
        self.pos = (self.x, self.y)
        self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE))
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        self.rect = self.image.get_rect()
        self.image.fill((0,0,255), self.rect)
        self.rect.x = self.x
        self.rect.y = self.y
        self.change_x = 0
        self.change_y = 0
        self.bombs_left = 3
        self.player_id = player_id
        

    def drop_bomb(self, game_data):
        x = self.rect.x // BLOCKSIZE
        y = self.rect.y // BLOCKSIZE
        if 1 <= game_data.game_map[x][y] < 30 and self.bombs_left > 0:  # only place bombs on free tiles
            game_data.game_map[x][y] = self.player_id
            bomb = BlockBomb(self.rect.x, self.rect.y, 33, pg.Color('red'), self.screen)
            game_data.bombs.add(bomb)
            self.bombs_left -= 1
            print(f'drop gridpos {x} {y} {game_data.game_map[x][y]} bl {self.bombs_left}')
        elif self.bombs_left <= 0:
            print(f'nodrop {x} {y} {game_data.game_map[x][y]} no bombs left {self.bombs_left}')
        else:
            print(f'nodrop {x} {y} {game_data.game_map[x][y]} cannot drop bomb')
        return game_data

    def changespeed(self, x, y):
        self.change_x += x
        self.change_y += y

    def update(self, blocks):
        # Move left/right
        self.rect.x += self.change_x 
        # Did this update cause us to hit a wall?
        block_hit_list = pg.sprite.spritecollide(self, blocks, False)
        for block in block_hit_list:
            # print(f'blcol {block.block_color}')
            # If we are moving right, set our right side to the left side of the item we hit
            if self.change_x > 0 and block.block_color == (143, 188, 143, 255):
                self.rect.right = block.rect.left
            else:
                # Otherwise if we are moving left, do the opposite.
                if block.block_color == (143, 188, 143, 255):
                    self.rect.left = block.rect.right 
        # Move up/down
        self.rect.y += self.change_y
        # Check and see if we hit anything
        block_hit_list = pg.sprite.spritecollide(self, blocks, False)
        for block in block_hit_list: 
            # Reset our position based on the top/bottom of the object.
            if self.change_y > 0 and block.block_color == (143, 188, 143, 255):
                self.rect.bottom = block.rect.top
            else:
                if block.block_color == (143, 188, 143, 255):
                    self.rect.top = block.rect.bottom
        # text = self.font.render(f'x {self.rect.x} y {self.rect.y}', 1, (255,255,255))
        # self.screen.blit(text, (10,10))
