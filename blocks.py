import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS, PLAYERSIZE, BOMBSIZE
from globals import limit as limit

class Block(pg.sprite.Sprite):
    def __init__(self, x, y, block_color, screen, solid, block_type=0, permanent=False):
        super().__init__()
        self.screen = screen
        self.x = x
        self.y = y
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x // BLOCKSIZE,y // BLOCKSIZE)
        self.pos = (self.x, self.y)
        self.block_color = block_color
        self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE))
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.x = self.x
        self.rect.y = self.y
        self.solid = solid
        self.font = pg.font.SysFont('calibri', 7, True)
        self.permanent = permanent
        self.block_type = block_type
        # self.debugtext = self.font.render(f'x:{self.gridpos}', 1, [255,255,255], [10,10,10])


    def draw_debug(self):
        global DEBUG
        if DEBUG:            
            if self.y == 0:
                debugtext = self.font.render(f'{self.gridpos[0]}', 1, [255,0,255], [10,10,10])
                self.screen.blit(debugtext, (self.rect.x, self.rect.centery))
            if self.x == 0:
                debugtext = self.font.render(f'{self.gridpos[1]}', 1, [255,0,255], [10,10,10])
                self.screen.blit(debugtext, (self.rect.x, self.rect.centery))
            #if self.permanent:
            #    debugtext = self.font.render(f'p', 1, [255,0,0], [10,10,10])
            #    self.screen.blit(debugtext, (self.rect.x, self.rect.centery))
            if not self.solid:
                debugtext = self.font.render(f'{self.block_type}', 1, [255,255,255], [10,10,10])
                self.screen.blit(debugtext, (self.rect.centerx, self.rect.centery))

    def update(self):
        if self.block_type == 0:
            self.solid = False
            self.permanent = False
        # global DEBUG
        # if DEBUG:
        #     self.debugtext = self.font.render(f'x:{self.gridpos}', 1, [255,255,255], [10,10,10])

    def draw_outlines(self):
        # pg.draw.rect(self.screen, (0,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        pg.draw.line(self.screen, (55,55,55), (self.x, self.y), (self.x + BLOCKSIZE, self.y))
        pg.draw.line(self.screen, (55,55,55), (self.x, self.y), (self.x, self.y + BLOCKSIZE))
        pg.draw.line(self.screen, (55,55,55), (self.x + BLOCKSIZE, self.y), (self.x + BLOCKSIZE, self.y + BLOCKSIZE))
        pg.draw.line(self.screen, (55,55,55), (self.x + BLOCKSIZE, self.y + BLOCKSIZE), (self.x, self.y + BLOCKSIZE))
        # pg.draw.circle(self.screen, (255,255,255), (self.x, self.y), 300)

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

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.timer:
            self.time_left = 0
            self.kill()

    def draw_outlines(self):
        pass

class BlockBomb(pg.sprite.Sprite):
    def __init__(self, x, y, bomber_id, block_color, screen, bomb_power):
        super().__init__()
        self.screen = screen
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x // BLOCKSIZE,y // BLOCKSIZE)
        self.x = x  # + (BOMBSIZE//2)
        self.y = y  # + (BOMBSIZE//2)
        self.bomber_id = bomber_id
        self.block_color = block_color
        self.start_time = pg.time.get_ticks() / FPS
        # self.pos = (self.x, self.y)
        self.image = pg.Surface((BOMBSIZE // 2,BOMBSIZE // 2))
        # todo fix exact placement on grid
        pg.draw.rect(self.image, (0,0,0), [self.x, self.y, BOMBSIZE // 2 ,BOMBSIZE // 2])
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.centerx = self.x
        self.rect.centery = self.y
        self.bomb_timer = 100
        self.time_left = 3
        self.exploding = False
        self.exp_steps = 20
        self.exp_radius = 1
        self.done = False
        self.flame_len = bomb_power
        self.flame_power = bomb_power
        self.flame_width = 10
        self.expand_up = True
        self.expand_down = True
        self.expand_right = True
        self.expand_left = True
    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.bomb_timer:
            self.time_left = 0

    def update_map(self, game_map):
        # do stuff with map after explotion...
        return game_map

    def explode(self, game_map):
        # todo convert explosion flames to Sprites
        # todo return only information about destroyed blocks (gridxy cords)
        destroyed_blocks = []
        # cetner explotion
        pg.draw.circle(self.screen, (255,255,255), (self.rect.centerx, self.rect.centery), self.exp_radius,1)

        # flame from top
        if self.expand_up:            
            start_pos = self.rect.midtop
            # end_pos = (start_pos[0], start_pos[1] - self.flame_len)
            end_pos = (start_pos[0], limit((start_pos[1] - self.flame_len),1, (GRID_Y*BLOCKSIZE)-1))
            pg.draw.line(self.screen, (0,0,255), self.rect.midtop, end_pos, width=self.flame_width)
            x = end_pos[0] // BLOCKSIZE
            y = end_pos[1] // BLOCKSIZE
            if game_map[x][y] >= 1:
                if game_map[x][y] >= 3:
                    destroyed_blocks.append((x,y))
                self.expand_up = False

        # flame from bottom
        if self.expand_down:
            start_pos = self.rect.midbottom
            # end_pos = (start_pos[0], start_pos[1] + self.flame_len)
            end_pos = (start_pos[0], limit((start_pos[1] + self.flame_len),1, (GRID_Y*BLOCKSIZE)-1))
            pg.draw.line(self.screen, (0,0,0), start_pos, end_pos, width=self.flame_width)
            x = end_pos[0] // BLOCKSIZE
            y = end_pos[1] // BLOCKSIZE
            if game_map[x][y] >= 1:
                if game_map[x][y] >= 3:
                    destroyed_blocks.append((x,y))
                self.expand_down = False
                

        # flame from rightside
        if self.expand_right:
            start_pos = self.rect.midright
            # end_pos = (start_pos[0] + self.flame_len, start_pos[1])
            end_pos = (limit((start_pos[0] + self.flame_len), 1, (GRID_X*BLOCKSIZE)-1), start_pos[1])
            pg.draw.line(self.screen, (255,255,255), start_pos, end_pos, width=self.flame_width)
            # flame from leftside
            x = end_pos[0] // BLOCKSIZE
            y = end_pos[1] // BLOCKSIZE
            if game_map[x][y] >= 1:
                if game_map[x][y] >= 3:
                    destroyed_blocks.append((x,y))
                self.expand_right = False

        # flame from leftside
        if self.expand_left:
            start_pos = self.rect.midleft
            # end_pos = (start_pos[0] - self.flame_len, start_pos[1])
            end_pos = (limit((start_pos[0] - self.flame_len),1, (GRID_X*BLOCKSIZE)-1), start_pos[1])
            pg.draw.line(self.screen, (255,0,0), start_pos, end_pos, width=self.flame_width)
            x = end_pos[0] // BLOCKSIZE
            y = end_pos[1] // BLOCKSIZE
            if game_map[x][y] >= 1:
                if game_map[x][y] >= 3:
                    destroyed_blocks.append((x,y))
                self.expand_left = False
        # pg.draw.circle(screen, (255,255,255), (250, 250), 100,2)
        self.exp_radius += 1
        if self.exp_radius >= BLOCKSIZE:
            self.exp_radius = BLOCKSIZE
        self.flame_len += self.flame_power
        self.exp_steps -= 1
        if DEBUG:
            if len(destroyed_blocks) >= 1:
                print(f'bomb step {self.exp_steps} gp {self.gridpos} sp {self.screen_pos} db {len(destroyed_blocks)}')
        if self.exp_steps <= 0:
            self.exploding = False
            self.done = True
            if DEBUG:
                print(f'bomb done gp {self.gridpos} sp {self.screen_pos}')
        self.flame_width -= 1
        if self.flame_width <= 1:
            self.flame_width = 1
        return destroyed_blocks
