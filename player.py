import pygame as pg
import pygame.gfxdraw as gfxdraw
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS, PLAYERSIZE, BOMBSIZE, CHEAT

from blocks import Block, Powerup_Block, BlockBomb
class Player(pg.sprite.Sprite):
    def __init__(self, x, y, player_id, screen):
        super().__init__()
        self.screen = screen
        self.x = x
        self.y = y
        self.image = pg.Surface((PLAYERSIZE,PLAYERSIZE)) # , pg.SRCALPHA, 32)
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, PLAYERSIZE,PLAYERSIZE])
        # pg.draw.circle(self.image, (0,0,0), (self.x, self.y), 2)
        #gfxdraw.aacircle(self.image, self.x, self.y, 15, (255,255,255))
        #pg.gfxdraw.filled_circle(self.image, self.x, self.y, 15, (255,255,255))
        self.rect = self.image.get_rect()
        self.image.fill((0,0,255), self.rect)
        self.rect.x = self.x
        self.rect.y = self.y
        self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
        self.change_x = 0
        self.change_y = 0
        self.max_bombs = 3
        self.bombs_left = self.max_bombs
        self.bomb_power = 1
        self.speed = 1
        self.player_id = player_id
        self.health = 100
        self.dead = False
        self.clock = pg.time.Clock()
        

    def drop_bomb(self, game_data):
        global DEBUG
        # get grid pos of player
        x = self.gridpos[0]
        y = self.gridpos[1]
        if self.bombs_left > 0:  # only place bombs if we have bombs...
            game_data.game_map[x][y] = self.player_id
            # create bomb at gridpos xy
            bomb = BlockBomb(x=x, y=y, bomber_id=self.player_id, block_color=pg.Color('yellow'), screen=self.screen, bomb_power=self.bomb_power)
            game_data.bombs.add(bomb)
            self.bombs_left -= 1
            if DEBUG:
                print(f'dropdrop {x} {y} {game_data.game_map[x][y]} bl {self.bombs_left} mb {self.max_bombs} bp {self.bomb_power}')
        elif self.bombs_left <= 0:
            if DEBUG:
                print(f'nodrop {x} {y} {game_data.game_map[x][y]} bl {self.bombs_left} mb {self.max_bombs}')
        else:
            if DEBUG:
                print(f'nodrop {x} {y} {game_data.game_map[x][y]} cannot drop bomb')
        return game_data

    def changespeed(self, x, y):
        self.change_x += x
        self.change_y += y
    def take_damage(self, amount=25):
        global DEBUG
        self.health -= amount
        if self.health <= 0:
            self.dead = True
            if DEBUG:
                print(f'player DEAD {amount} {self.health}')
        if DEBUG:
            print(f'player damage {amount} {self.health}')
    def update(self, game_data):
        # Move left/right
        self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
        self.rect.x += self.change_x 
        # Did this update cause us to hit a wall?
        block_hit_list = pg.sprite.spritecollide(self, game_data.blocks, False)
        for block in block_hit_list:
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

        # pick up powerups...
        powerup_hits = pg.sprite.spritecollide(self, game_data.powerblocks, False)
        for powerup in powerup_hits:
            #if DEBUG:
            #    print(f'powerup {powerup.powerup_type}')
            if powerup.powerup_type[0] == 'addbomb':
                if self.max_bombs < 10:
                    self.max_bombs += 1
                    self.bombs_left += 1
            if powerup.powerup_type[0] == 'bombpower':
                if self.bomb_power < 10:
                    self.bomb_power += 1
            if powerup.powerup_type[0] == 'speedup':
                if self.speed < 10:
                    self.speed += 1
            if powerup.powerup_type[0] == 'healthup':
                    self.health += 10
            powerup.kill()
            
