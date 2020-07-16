import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS

class Powerup_Block(pg.sprite.Sprite):
    def __init__(self, x, y, screen):
        super().__init__()
        self.screen = screen
        self.x = x
        self.y = y
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x // BLOCKSIZE,y // BLOCKSIZE)
        self.pos = (self.x, self.y)
        self.block_color = random.choice(list(colordict.items()))[1]   #block_color
        self.image = pg.Surface((BLOCKSIZE // 2,BLOCKSIZE // 2))
        self.radius = BLOCKSIZE // 2
        pg.draw.circle(self.image, (255,0,0), (0,0), self.radius)
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.centerx = self.x
        self.rect.centery = self.y
        self.solid = False
        self.powerup_type = random.choice(list(POWERUPS.items()))
        self.timer = 600
        self.start_time = pg.time.get_ticks() / FPS
        # print(f'pb {self.rect.x} {self.rect.y} {self.powerup}')

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.timer:
            # print(f'bomb expl {self.bomb_timer} - dt {self.dt:.2f} = {self.dt - self.start_time:.2f} pos {self.rect.x} {self.rect.y} bid {self.bomber_id}')
            self.time_left = 0
            self.kill()
            #print(f'powerup dead dt {self.dt} start {self.start_time} timer {self.timer}')

    def draw_outlines(self):
        pass
        # pg.draw.rect(self.screen, (0,255,0), [self.rect.centerx, self.rect.centery, 2,2])
        # pg.draw.line(self.screen, (5,25,55), (self.x, self.y), (self.x + BLOCKSIZE, self.y))
        # pg.draw.line(self.screen, (5,25,55), (self.x, self.y), (self.x, self.y + BLOCKSIZE))
        # pg.draw.line(self.screen, (5,25,55), (self.x + BLOCKSIZE, self.y), (self.x + BLOCKSIZE, self.y + BLOCKSIZE))
        # pg.draw.line(self.screen, (5,25,55), (self.x + BLOCKSIZE, self.y + BLOCKSIZE), (self.x, self.y + BLOCKSIZE))
        # pg.draw.circle(self.screen, (255,255,255), (self.rect.centerx, self.rect.centery), self.radius)
        # print(f'dddd')


class BlockBomb(pg.sprite.Sprite):
    def __init__(self, x, y, bomber_id, block_color, screen):
        super().__init__()
        self.screen = screen
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x // BLOCKSIZE,y // BLOCKSIZE)
        self.x = x  # + (BLOCKSIZE//2)
        self.y = y  # + (BLOCKSIZE//2)
        self.bomber_id = bomber_id
        self.block_color = block_color
        self.start_time = pg.time.get_ticks() / FPS
        # self.pos = (self.x, self.y)
        self.image = pg.Surface((BLOCKSIZE // 2,BLOCKSIZE // 2))
        # todo fix exact placement on grid
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, BLOCKSIZE // 2 ,BLOCKSIZE // 2])
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.centerx = self.x
        self.rect.centery = self.y
        self.bomb_timer = 100
        self.time_left = 3
        self.exploding = False
        self.exp_steps = 20
        self.exp_radius = 4
        self.done = False
        self.flame_len = 2
        self.flame_power = 2

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.bomb_timer:
            # print(f'bomb expl {self.bomb_timer} - dt {self.dt:.2f} = {self.dt - self.start_time:.2f} pos {self.rect.x} {self.rect.y} bid {self.bomber_id}')
            self.time_left = 0

    def update_map(self, game_map):
        # do stuff with map after explotion...
        return game_map

    def explode(self, game_map):
        # cetner explotion
        pg.draw.circle(self.screen, (255,255,255), (self.rect.centerx, self.rect.centery), self.exp_radius,1)
        # flame from top
        start_pos = self.rect.midtop
        end_pos = (start_pos[0], start_pos[1] - self.flame_len)
        pg.draw.line(self.screen, (255,255,255), start_pos, end_pos, width=2)
        x = end_pos[0] // BLOCKSIZE
        y = end_pos[1] // BLOCKSIZE
        try:
            if 1 <= game_map[x][y] <= 3:
                game_map[x][y] = 9
        except:
            pass
        # flame from bottom
        start_pos = self.rect.midbottom
        end_pos = (start_pos[0], start_pos[1] + self.flame_len)
        pg.draw.line(self.screen, (255,255,255), start_pos, end_pos, width=2)
        x = end_pos[0] // BLOCKSIZE
        y = end_pos[1] // BLOCKSIZE
        try:
            if 2 <= game_map[x][y] <= 3:
                game_map[x][y] = 9
        except:
            pass
            # print(f'killed block {x} {y} {game_map[x][y]}')
        # flame from rightside
        start_pos = self.rect.midright
        end_pos = (start_pos[0] + self.flame_len, start_pos[1])
        pg.draw.line(self.screen, (255,255,255), start_pos, end_pos, width=2)
        # flame from leftside
        x = end_pos[0] // BLOCKSIZE
        y = end_pos[1] // BLOCKSIZE
        try:
            if 2 <= game_map[x][y] <= 3:
                game_map[x][y] = 9
        except:
            pass
        start_pos = self.rect.midleft
        end_pos = (start_pos[0] - self.flame_len, start_pos[1])
        pg.draw.line(self.screen, (255,255,255), start_pos, end_pos, width=2)
        x = end_pos[0] // BLOCKSIZE
        y = end_pos[1] // BLOCKSIZE
        try:
            if 2 <= game_map[x][y] <= 3:
                game_map[x][y] = 9
        except:
            pass
        # pg.draw.circle(screen, (255,255,255), (250, 250), 100,2)
        self.exp_radius += self.flame_power // 2
        self.flame_len += self.flame_power
        self.exp_steps -= 1
        # print(f'bomb anim {self.exp_steps} r {self.exp_radius} pos {self.rect.x} {self.rect.y}')
        if self.exp_steps <= 0:
            self.exploding = False
            self.done = True
        return game_map

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
            
