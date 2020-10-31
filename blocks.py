import pygame as pg
from pygame.locals import *
from pygame.colordict import THECOLORS as colordict
import random
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, DEBUG, POWERUPS, PLAYERSIZE, BOMBSIZE, CHEAT, DEBUG_GRID
from globals import limit as limit

class Bomb_Flame(pg.sprite.Sprite):
    def __init__(self, x, y, screen, dir, flame_length):
        super().__init__()
        self.screen = screen
        self.x = x
        self.y = y
        self.dir = dir
        self.flame_length = flame_length
        self.color = pg.Color('red')
        self.image = pg.Surface((2,2), pg.SRCALPHA)
        pg.draw.rect(self.image, (0,0,0), (self.x, self.y, 0, 0))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.image.fill(self.color, self.rect)
        self.max_length = 10
        self.length = 1
        self.l_up = 1
        self.step_up = 1
        self.l_dn = 1
        self.step_down = 1
        self.l_r = 1
        self.step_right = 1
        self.l_l = 1
        self.step_left = 1
        self.flame_adder = 1
        self.expand = True

    def update(self):
        if self.dir == 'u' and self.flame_adder == 1 and self.l_up <= self.flame_length:
            if self.expand:
                self.l_up += self.flame_adder
        elif self.dir == 'd' and self.flame_adder == 1 and self.l_dn <= self.flame_length:
            if self.expand:
                self.l_dn += self.flame_adder
        elif self.dir == 'r' and self.flame_adder == 1 and self.l_r <= self.flame_length:
            if self.expand:
                self.l_r += self.flame_adder
        elif self.dir == 'l' and self.flame_adder == 1 and self.l_l <= self.flame_length:
            if self.expand:
                self.l_l += self.flame_adder
        else:
            pass

    def update_old(self):
        if self.l_up <= 10 and self.dir == 'u':
            self.l_up += self.flame_adder
        elif self.l_dn <= 10 and self.dir == 'd':
            self.l_dn += self.flame_adder
        elif self.l_r <= 10 and self.dir == 'r':
            self.l_r += self.flame_adder
        elif self.l_l <= 10 and self.dir == 'l':
            self.l_l += self.flame_adder
        else:
            pass

    def set_adder(self, adder):
        self.flame_adder = adder
    
    def stop_expander(self):
        self.expand = False

    def draw_flame(self):
        if self.dir == 'u':
            self.rect = pg.Rect(self.x, self.y-self.l_up, 2,2+self.l_up)
            pg.draw.rect(self.screen, (255,0,0), self.rect,0)
        if self.dir == 'd':
            self.rect = pg.Rect(self.x, self.y+self.l_dn, 2,2+self.l_dn)
            pg.draw.rect(self.screen, (255,0,0), self.rect,0)
        if self.dir == 'r':
            self.rect = pg.Rect(self.x+self.l_r, self.y, 2+self.l_r,2)
            pg.draw.rect(self.screen, (255,0,0), self.rect,0)
        if self.dir == 'l':
            self.rect = pg.Rect(self.x-self.l_l, self.y, 2+self.l_l,2)
            pg.draw.rect(self.screen, (255,0,0), self.rect,0)
        return 0

class Block(pg.sprite.Sprite):
    def __init__(self, x, y, screen, block_type):
        super().__init__()
        self.screen = screen
        self.block_type = block_type
        self.x = x * BLOCKSIZE
        self.y = y * BLOCKSIZE
        self.screen_pos = [x * BLOCKSIZE, y * BLOCKSIZE]
        self.gridpos = [x,y]
        self.pos = [self.x, self.y]
        # self.block_color = (255,255,0)
        if self.block_type == 0:
            self.solid = False
            self.permanent = False
            self.block_color = pg.Color('black')
            self.bordercolor = (255,255,255)
        elif self.block_type == 1:
            self.solid = True
            self.permanent = True
            self.block_color = pg.Color('orangered4')
            self.bordercolor = (0,255,0)
        elif self.block_type == 2:
            self.solid = True
            self.permanent = True
            self.block_color = pg.Color('orangered4')
            self.bordercolor = (244,20,44)
        elif 2 < self.block_type <= 9:
            self.solid = True
            self.permanent = False
            self.block_color = pg.Color('gray31')
            self.bordercolor = (44,0,44)
        elif self.block_type == 99:
            self.solid = False
            self.permanent = False
            self.block_color = pg.Color('black')
            self.bordercolor = (4,123,44)
        else:
            self.solid = False
            self.permanent = False
            self.block_color = pg.Color('white')
            self.bordercolor = (55,55,244)

        self.image = pg.Surface((BLOCKSIZE,BLOCKSIZE), pg.SRCALPHA)
        pg.draw.rect(self.image, (0,0,0), (self.screen_pos[0], self.screen_pos[1], BLOCKSIZE, BLOCKSIZE))
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.x = self.screen_pos[0]
        self.rect.y = self.screen_pos[1]
        # self.solid = solid
        self.font = pg.font.SysFont('calibri', 10, True)

    def draw_id(self):
        global DEBUG
        if DEBUG:            
            debugtext = self.font.render(f'{self.block_type}', 1, [255,255,255], [0,0,0])
            self.screen.blit(debugtext, (self.rect.x+3, self.rect.centery-3))

    def draw_grid_id(self):
        global DEBUG_GRID
        if DEBUG_GRID:
            debugtext = self.font.render(f'{self.gridpos[0]}', 1, [0,255,0], [0,0,0])
            self.screen.blit(debugtext, (self.rect.x+3, self.rect.centery-3))
            debugtext = self.font.render(f':{self.gridpos[1]}', 1, [0,255,0], [0,0,0])
            self.screen.blit(debugtext, (self.rect.x+8, self.rect.centery-3))

    def update(self):
        pass            

    def draw_outlines(self):
        # pg.draw.rect(self.screen, (0,0,0), [self.x, self.y, BLOCKSIZE,BLOCKSIZE])
        pg.draw.line(self.screen, self.bordercolor, (self.x, self.y), (self.x + BLOCKSIZE, self.y))
        pg.draw.line(self.screen, self.bordercolor, (self.x, self.y), (self.x, self.y + BLOCKSIZE))
        pg.draw.line(self.screen, self.bordercolor, (self.x + BLOCKSIZE, self.y), (self.x + BLOCKSIZE, self.y + BLOCKSIZE))
        pg.draw.line(self.screen, self.bordercolor, (self.x + BLOCKSIZE, self.y + BLOCKSIZE), (self.x, self.y + BLOCKSIZE))
        # pg.draw.circle(self.screen, (255,255,255), (self.x, self.y), 300)

class Powerup_Block(pg.sprite.Sprite):
    def __init__(self, x, y, screen):
        super().__init__()
        self.screen = screen
        self.x = x * BLOCKSIZE
        self.y = y * BLOCKSIZE
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x, y)
        self.pos = (self.x, self.y)
        self.block_color = random.choice(list(colordict.items()))[1]   #block_color
        self.image = pg.Surface((BLOCKSIZE // 2,BLOCKSIZE // 2), pg.SRCALPHA)
        self.radius = BLOCKSIZE // 2
        pg.draw.rect(self.image, (0,0,0), (self.x, self.y, BLOCKSIZE // 2 , BLOCKSIZE // 2))
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        self.rect.centerx = self.x + BLOCKSIZE // 2
        self.rect.centery = self.y + BLOCKSIZE // 2
        self.solid = False
        self.powerup_type = random.choice(list(POWERUPS.items()))
        self.timer = 400
        self.time_left = self.timer
        self.ending_soon = False
        self.taken = False
        self.start_time = pg.time.get_ticks() / FPS

    def flash(self):
        self.block_color = random.choice(list(colordict.items()))[1]   #block_color
        self.image = pg.Surface((BLOCKSIZE // 2,BLOCKSIZE // 2), pg.SRCALPHA)
        pg.draw.rect(self.image, (0,0,0), (self.x, self.y, BLOCKSIZE // 2 , BLOCKSIZE // 2))
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        self.rect.centerx = self.x + BLOCKSIZE // 2
        self.rect.centery = self.y + BLOCKSIZE // 2

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.timer:
            self.time_left = 0
            # self.kill()
        if self.dt - self.start_time >= self.timer // 3:
            self.ending_soon = True

    def draw_outlines(self):
        pass

class BlockBomb(pg.sprite.Sprite):
    def __init__(self, x, y, bomber_id, block_color, screen, bomb_power):
        global DEBUG, CHEAT
        super().__init__()
        self.screen = screen
        self.screen_pos = (x * BLOCKSIZE, y * BLOCKSIZE)
        self.gridpos = (x,y)
        self.x = x * BLOCKSIZE
        self.y = y * BLOCKSIZE
        self.bomber_id = bomber_id
        self.block_color = block_color
        self.start_time = pg.time.get_ticks() / FPS
        # self.pos = (self.x, self.y)
        self.image = pg.Surface((BOMBSIZE,BOMBSIZE ), pg.SRCALPHA)
        # todo fix exact placement on grid
        pg.draw.rect(self.image, (0,0,0), [self.x,self.y, BOMBSIZE,BOMBSIZE])
        self.rect = self.image.get_rect()
        self.image.fill(self.block_color, self.rect)
        # self.rect.center = (50,50)
        self.rect.centerx = self.x + BLOCKSIZE // 2
        self.rect.centery = self.y + BLOCKSIZE // 2
        self.font = pg.font.SysFont('calibri', 10, True)
        self.bomb_timer = 100
        self.time_left = 3
        self.exploding = False
        self.exp_steps = 50
        self.exp_radius = 1
        self.done = False
        self.flame_len = 1
        self.flame_power = bomb_power
        self.flame_width = 10
        self.expand_up = True
        self.expand_down = True
        self.expand_right = True
        self.expand_left = True
        self.flames = []
        self.flame_up = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, dir='u', flame_length=self.flame_len)
        self.flames.append(self.flame_up)
        self.flame_down = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, dir='d', flame_length=self.flame_len)
        self.flames.append(self.flame_down)
        self.flame_right = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, dir='r', flame_length=self.flame_len)
        self.flames.append(self.flame_right)
        self.flame_left = Bomb_Flame(self.rect.centerx, self.rect.centery, self.screen, dir='l', flame_length=self.flame_len)
        self.flames.append(self.flame_left)
        # self.flames = [Bomb_Flame(self.x, self.y, self.screen) for k in range(4)]

    def update(self):
        global DEBUG
        self.dt = pg.time.get_ticks() / FPS
        if self.dt - self.start_time >= self.bomb_timer:
            self.time_left = 0
            self.exploding = True
            # if DEBUG:
            #    print(f'bombtimer expired....')
    def update_map(self, game_map):
        # do stuff with map after explotion...
        return game_map

    def draw_explotion(self):
        if self.exploding:
            pg.draw.circle(self.screen, (255,255,255), (self.rect.centerx, self.rect.centery), self.exp_radius,1)

    def explode(self, game_map):
        self.exp_radius += 1
        if self.exp_radius >= BLOCKSIZE:
            self.exp_radius = BLOCKSIZE
        for flame in self.flames:
            if flame.expand:
                flame.flame_length += self.flame_power
        self.exp_steps -= 1
        if self.exp_steps <= 0:
            self.exploding = False
            self.done = True
            if DEBUG:
                pass
            self.kill()
        self.flame_width -= 1
        if self.flame_width <= 1:
            self.flame_width = 1
        
        return []

    def draw_id(self):
        global DEBUG
        if DEBUG:            
            debugtext = self.font.render(f'{self.bomber_id}', 1, [255,255,255], [0,0,0])
            self.screen.blit(debugtext, (self.rect.x+3, self.rect.centery-3))
