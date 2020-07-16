import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS

from blocks import Block, Powerup_Block, BlockBomb
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
        self.max_bombs = 3
        self.bombs_left = self.max_bombs
        self.bomb_power = 3
        self.speed = 1
        self.player_id = player_id
        self.clock = pg.time.Clock()
        

    def drop_bomb(self, game_data):
        x = self.rect.x // BLOCKSIZE
        y = self.rect.y // BLOCKSIZE
        if 1 <= game_data.game_map[x][y] < 30 and self.bombs_left > 0:  # only place bombs on free tiles
            game_data.game_map[x][y] = self.player_id
            bomb = BlockBomb(self.rect.centerx, self.rect.centery, 33, pg.Color('red'), self.screen)
            game_data.bombs.add(bomb)
            self.bombs_left -= 1
            print(f'drop gridpos {x} {y} {game_data.game_map[x][y]} bl {self.bombs_left} mb {self.max_bombs}')
        elif self.bombs_left <= 0:
            print(f'nodrop {x} {y} {game_data.game_map[x][y]} no bombs left {self.bombs_left}  mb {self.max_bombs}')
        else:
            print(f'nodrop {x} {y} {game_data.game_map[x][y]} cannot drop bomb')
        return game_data

    def changespeed(self, x, y):
        self.change_x += x
        self.change_y += y

    def update(self, game_data):
        # Move left/right
        self.rect.x += self.change_x 
        # Did this update cause us to hit a wall?
        block_hit_list = pg.sprite.spritecollide(self, game_data.blocks, False)
        for block in block_hit_list:
            # print(f'blcol {block.block_color}')
            # If we are moving right, set our right side to the left side of the item we hit
            if self.change_x > 0 and block.solid:
                self.rect.right = block.rect.left
            else:
                # Otherwise if we are moving left, do the opposite.
                if block.solid:
                    self.rect.left = block.rect.right 
        # Move up/down
        self.rect.y += self.change_y
        # Check and see if we hit anything
        block_hit_list = pg.sprite.spritecollide(self, game_data.blocks, False)
        for block in block_hit_list: 
            # Reset our position based on the top/bottom of the object.
            if self.change_y > 0 and block.solid:
                self.rect.bottom = block.rect.top
            else:
                if block.solid:
                    self.rect.top = block.rect.bottom
        # text = self.font.render(f'x {self.rect.x} y {self.rect.y}', 1, (255,255,255))
        # self.screen.blit(text, (10,10))

        # pick up powerups...
        powerup_hits = pg.sprite.spritecollide(self, game_data.powerblocks, False)
        for powerup in powerup_hits:
            print(f'powerup {powerup.powerup_type}')
            if powerup.powerup_type[0] == 'addbomb':
                self.max_bombs += 1
            if powerup.powerup_type[0] == 'bombpower':
                self.bomb_power += 1
            if powerup.powerup_type[0] == 'speedup':
                self.speed += 1
            powerup.kill()
            
