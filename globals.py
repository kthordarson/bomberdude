import random
import math
import pygame as pg
from pygame.colordict import THECOLORS as colordict

# global constants
BOMBSIZE = 5
BLOCKSIZE = 20
PLAYERSIZE = 15
GRID_X = 30
GRID_Y = 30
FPS = 30
POWERUPS = {
    'bombpower': 11,
    'speedup': 12,
    'addbomb': 13,
    'healthup': 14,
}

BLOCKTYPES = {
    '0':  {'solid': False, 'permanent': False, 'color': pg.Color('black')},
    '1':  {'solid': True, 'permanent': True, 'color': pg.Color('orangered1')},
    '2':  {'solid': True, 'permanent': True, 'color': pg.Color('orangered2')},
    '3':  {'solid': True, 'permanent': True, 'color': pg.Color('orangered3')},
    '4':  {'solid': True, 'permanent': False, 'color': pg.Color('gray31')},
    '10':  {'solid': True, 'permanent': True, 'color': pg.Color('steelblue4')},
}


def get_entity_angle(e_1, e_2):
    dif_x = e_2.x-e_1.x
    dif_y = e_2.y-e_1.y
    return math.atan2(dif_y, dif_x)


def get_angle(pos_1, pos_2):
    dif_x = pos_2[0]-pos_1[0]
    dif_y = pos_2[1]-pos_1[1]
    return math.atan2(dif_y, dif_x)


def limit(num, minimum=1,  maximum=255):
    return max(min(num, maximum), minimum)


def inside_circle(R, pos_x, pos_y):
    X = int(R)  # R is the radius
    for x in range(-X, X+1):
        Y = int((R*R-x*x)**0.5)  # bound for y given x
        for y in range(-Y, Y+1):
            yield (x+pos_x, y+pos_y)


class BasicThing(pg.sprite.Sprite):
    def __init__(self, screen=None,  gridpos=(0, 0), color=(33, 44, 55, 255)):
        super().__init__()
        self.screen = screen
        self.pos = pg.math.Vector2(gridpos[0] * BLOCKSIZE, gridpos[1] * BLOCKSIZE)
        self.gridpos = gridpos
        self.size = BLOCKSIZE
        self.color = color
        self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)
        pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, self.size, self.size))  # self.image.get_rect()
        self.image.set_alpha(255)
        self.rect = self.image.get_rect()
        self.image.fill(self.color, self.rect)
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y
        self.font = pg.freetype.Font("DejaVuSans.ttf", 12)
        self.font_color = (255, 255, 255)

    def collide(self, items):
        return pg.sprite.spritecollide(self, items, False)


class Block(BasicThing):
    def __init__(self, screen=None, gridpos=(0, 0), blocktype=0):
        super().__init__(screen, gridpos)
        self.block_type = blocktype
        self.solid = BLOCKTYPES.get(blocktype)['solid']
        self.permanent = BLOCKTYPES.get(blocktype)['permanent']
        self.color = BLOCKTYPES.get(blocktype)['color']
        self.explode = False
        self.ending_soon = False
        self.powerblock = False
        self.hit = False
        self.dt = pg.time.get_ticks() / FPS
        self.timer = 100
        self.time_left = self.timer
        self.start_time = pg.time.get_ticks() / FPS

    def update(self):
        if self.powerblock:
            self.dt = pg.time.get_ticks() / FPS
            if self.dt - self.start_time >= self.timer:
                self.time_left = 0
                self.color = pg.Color('black')
                self.block_type = 0
                self.solid = False
                self.powerblock = False
                self.size = BLOCKSIZE
                self.pos.x -= 5
                self.pos.y -= 5
                self.kill()
            if self.dt - self.start_time >= self.timer // 3:
                self.ending_soon = True

    def draw(self, screen):
        pg.draw.rect(screen, self.color, (self.pos.x, self.pos.y, self.size, self.size))

    def set_zero(self):
        pass

    def drop_powerblock(self):
        if not self.powerblock:
            self.start_time = pg.time.get_ticks() / FPS
            self.color = pg.Color('firebrick4')
            # self.dt = pg.time.get_ticks() / FPS
            self.size = BLOCKSIZE // 2
            self.solid = False
            self.permanent = False
            self.pos.x += 5
            self.pos.y += 5
            self.powerblock = True
            print(f'[powerblock] {self.pos} {self.gridpos} {self.powerblock} ')
            self.hit = False


class Particle(pg.sprite.Sprite):
    def __init__(self, block, direction=None):
        super().__init__()
        self.color = random.choice(list(colordict.items()))[
            1]  # (255, 155, 55)
        self.image = pg.Surface((3, 3), pg.SRCALPHA)
        self.direction = direction
        self.alpha = 0
        self.alpha_mod = 13
        self.image.set_alpha(self.alpha)
        # pg.draw.rect(self.image, self.color, (self.pos.x, self.pos.y, 1, 1))
        self.rect = self.image.get_rect()
        self.image.set_alpha(self.alpha)
        self.image.fill(self.color, self.rect)
        self.vel = pg.math.Vector2(
            random.uniform(-2, 2), random.uniform(-2, 2))  # pg.math.Vector2(0, 0)
        if self.direction == 'up':
            self.rect.midtop = block.rect.midbottom
        if self.direction == 'down':  # and self.vel.y >= 0:
            self.rect.midbottom = block.rect.midtop
        if self.direction == 'right':  # and self.vel.x >= 0:
            self.rect.x = block.rect.midright[1]
        if self.direction == 'left':  # and self.vel.x <= 0:
            self.rect.midright = block.rect.midleft
        self.pos = self.rect.center
        self.move = False
        self.radius = 1
        self.dt = pg.time.get_ticks() / FPS
        self.timer = 100
        self.time_left = self.timer
        self.start_time = pg.time.get_ticks() / FPS

    def collide(self, blocks):
        return pg.sprite.spritecollide(self, blocks, False)

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        w, h = pg.display.get_surface().get_size()
        if self.dt - self.start_time >= self.timer:
            self.kill()
        self.pos += self.vel
        self.alpha += self.alpha_mod
        if self.alpha <= 0:
            self.alpha = 0
        self.image.set_alpha(self.alpha)
        if self.pos.x >= w or self.pos.x <= 0 or self.pos.y >= h or self.pos.y <= 0:
            self.kill()
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y

    def draw(self, screen):
        pg.draw.circle(self.image, self.color, (int(
            self.pos.x), int(self.pos.y)), self.radius)
        screen.blit(self.image, self.pos)


class Bomb_Flame(pg.sprite.Sprite):
    def __init__(self, direction, rect, vel, flame_length):
        super().__init__()
        self.direction = direction
        self.flame_length = flame_length
        self.color = pg.Color('red')
        self.pos = pg.math.Vector2(rect.centerx, rect.centery)
        self.endpos = pg.math.Vector2(self.pos.x, self.pos.y)
        self.vel = pg.math.Vector2(vel[0], vel[1])  # flame direction
        self.image = pg.Surface([1, 1])
        self.rect = self.image.get_rect()  # self.rect = pg.draw.line(self.image, self.color, self.pos, self.endpos, 1)
        self.startrect = rect
        self.max_length = 13
        self.length = 1
        self.flame_adder = 1
        self.expand = True

    def stop(self):
        self.vel = pg.math.Vector2(0, 0)

    def update(self):
        self.endpos += self.vel
        self.rect.x = self.endpos.x
        self.rect.y = self.endpos.y

    def draw(self, screen):
        pg.draw.line(screen, self.color, self.pos, self.endpos, 1)
        if self.vel[0] > 0:  # flame direction = right
            pg.draw.line(screen, (255, 255, 55), self.startrect.topright, self.endpos, 1)
            pg.draw.line(screen, (255, 255, 55), self.startrect.bottomright, self.endpos, 1)
        if self.vel[0] < 0:  # flame direction = left
            pg.draw.line(screen, (255, 255, 55), self.startrect.topleft, self.endpos, 1)
            pg.draw.line(screen, (255, 255, 55), self.startrect.bottomleft, self.endpos, 1)
        if self.vel[1] < 0:  # flame direction = up
            pg.draw.line(screen, (255, 255, 55), self.startrect.topleft, self.endpos, 1)
            pg.draw.line(screen, (255, 255, 55), self.startrect.topright, self.endpos, 1)
        if self.vel[1] > 0:  # flame direction = down
            pg.draw.line(screen, (255, 255, 55), self.startrect.bottomleft, self.endpos, 1)
            pg.draw.line(screen, (255, 255, 55), self.startrect.bottomright, self.endpos, 1)


class BlockBomb(pg.sprite.Sprite):
    def __init__(self, pos, bomber_id, color, bomb_power, gridpos):
        super().__init__()
        self.flames = pg.sprite.Group()
# 		self.screen = screen
        self.pos = pg.math.Vector2(pos[0], pos[1])
        self.gridpos = gridpos
        self.bomber_id = bomber_id
        self.color = color
        self.start_time = pg.time.get_ticks() / FPS
        self.image = pg.Surface((BOMBSIZE, BOMBSIZE), pg.SRCALPHA)
        # todo fix exact placement on grid
        self.rect = self.image.get_rect()  # pg.draw.circle(self.screen, self.block_color, (int(self.pos.x), int(self.pos.y)), BOMBSIZE) # self.image.get_rect()
        self.rect.centerx = self.pos.x
        self.rect.centery = self.pos.y
        self.font = pg.font.SysFont('calibri', 10, True)
        self.bomb_timer = 100
        self.exploding = False
        self.exp_steps = 50
        self.exp_radius = 1
        self.done = False
        self.flame_len = 1
        self.flame_power = bomb_power
        self.flame_width = 10
        self.dt = pg.time.get_ticks() / FPS
        # each bomb has four flames for each side
        self.flames = pg.sprite.Group()
        # screen, direction, pos, vel, flame_length
        flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(-1, 0), direction='left')
        self.flames.add(flame)
        flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(1, 0), direction='right')
        self.flames.add(flame)
        flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(0, 1), direction='down')
        self.flames.add(flame)
        flame = Bomb_Flame(rect=self.rect, flame_length=self.flame_len, vel=(0, -1), direction='up')
        self.flames.add(flame)

    def update(self):
        self.dt = pg.time.get_ticks() / FPS
        # I will start exploding after xxx seconds....
        if self.dt - self.start_time >= self.bomb_timer:
            self.exploding = True
        if self.exploding:
            self.exp_radius += 1     # make it bigger
            if self.exp_radius >= BLOCKSIZE:
                self.exp_radius = BLOCKSIZE  # not too big
            # update flame animation, flames do player damage and destroy most blocks
            spliff = [flame.update() for flame in self.flames]
            self.exp_steps -= 1  # animation steps ?
            if self.exp_steps <= 0:  # stop animation and kill bomb
                self.done = True

    def draw(self, screen):
        # pg.draw.rect(screen, self.block_color, [self.pos.x,self.pos.y, BOMBSIZE, BOMBSIZE])
        pg.draw.circle(screen, self.color, (int(self.pos.x), int(self.pos.y)), BOMBSIZE)
        if self.exploding:
            pg.draw.circle(screen, (255, 255, 255), (self.rect.centerx, self.rect.centery), self.exp_radius, 1)
            krem = [flame.draw(screen) for flame in self.flames]


class Player(pg.sprite.Sprite):
    def __init__(self, pos, player_id):
        super().__init__()
        # self.screen = screen
        self.pos = pg.math.Vector2(pos[0], pos[1])
        self.vel = pg.math.Vector2(0, 0)
        self.image = pg.Surface((PLAYERSIZE, PLAYERSIZE), pg.SRCALPHA)  # , pg.SRCALPHA, 32)
        self.color = pg.Color('blue')
        pg.draw.rect(self.image, self.color, [self.pos.x, self.pos.y, PLAYERSIZE, PLAYERSIZE])
        self.image.set_alpha(255)
        self.rect = self.image.get_rect()
        self.image.fill(self.color, self.rect)
        self.rect.centerx = self.pos.x
        self.rect.centery = self.pos.y
        self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
        self.max_bombs = 3
        self.bombs_left = self.max_bombs
        self.bomb_power = 1
        self.speed = 3
        self.player_id = player_id
        self.health = 100
        self.dead = False
        self.clock = pg.time.Clock()
        self.score = 0
        self.font = pg.font.SysFont('calibri', 10, True)

    def drop_bomb(self, game_data):
        # get grid pos of player
        x = self.gridpos[0]
        y = self.gridpos[1]
        if self.bombs_left > 0:  # and game_data.grid[x][y] == 0:  # only place bombs if we have bombs... and on free spot...
            game_data.grid[x][y] = self.player_id
            # create bomb at gridpos xy, multiply by BLOCKSIZE for screen coordinates
            bomb = BlockBomb(pos=(self.rect.centerx, self.rect.centery), bomber_id=self.player_id, color=pg.Color('yellow'), bomb_power=self.bomb_power, gridpos=self.gridpos)
            game_data.bombs.add(bomb)
            self.bombs_left -= 1
        else:
            print(f'cannot drop bomb on gridpos: {x} {y} bl:{self.bombs_left} griddata: {game_data.grid[x][y]}')
        return game_data

    def take_damage(self, amount=25):
        self.health -= amount
        if self.health <= 0:
            self.dead = True

    def update(self, blocks):
        # Move left/right
        self.rect.centerx += self.vel.x
        self.gridpos = (self.rect.centerx//BLOCKSIZE, self.rect.centery//BLOCKSIZE)
        block_hit_list = pg.sprite.spritecollide(self, blocks, False)
        for block in block_hit_list:
            # If we are moving right, set our right side to the left side of the item we hit
            if self.vel[0] > 0 and block.solid:
                self.rect.right = block.rect.left
                self.vel = pg.math.Vector2(0, 0)
            else:
                # Otherwise if we are moving left, do the opposite.
                if self.vel[0] < 0 and block.solid:
                    self.rect.left = block.rect.right
                    self.vel = pg.math.Vector2(0, 0)

        # Move up/down
        self.rect.centery += self.vel.y
        # Check and see if we hit anything
        block_hit_list = pg.sprite.spritecollide(self, blocks, False)
        for block in block_hit_list:
            # Reset our position based on the top/bottom of the object.
            if self.vel[1] > 0 and block.solid:
                self.rect.bottom = block.rect.top
                self.vel = pg.math.Vector2(0, 0)
            else:
                if self.vel[1] < 0 and block.solid:
                    self.rect.top = block.rect.bottom
                    self.vel = pg.math.Vector2(0, 0)
        self.pos = pg.math.Vector2(self.rect.x, self.rect.y)

    def take_powerup(self, powerup):
        # pick up powerups...
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

    def add_score(self):
        self.score += 1


class Gamemap:
    def __init__(self):
        self.grid = self.generate()  # None # [[random.randint(0, 9) for k in range(GRID_Y + 1)] for j in range(GRID_X + 1)]

    def generate(self):
        grid = [[random.randint(0, 4) for k in range(GRID_Y + 1)] for j in range(GRID_X + 1)]
        # set edges to solid blocks, 10 = solid blockwalkk
        for x in range(GRID_X + 1):
            grid[x][0] = 10
            grid[x][GRID_Y] = 10
        for y in range(GRID_Y + 1):
            grid[0][y] = 10
            grid[GRID_X][y] = 10
        return grid

    def place_player(self):
        # place player somewhere where there is no block
        # returns the (x,y) coordinate where player is to be placed
        # random starting point from gridgamemap
        x = int(GRID_X // 2)  # random.randint(2, GRID_X - 2)
        y = int(GRID_Y // 2)  # random.randint(2, GRID_Y - 2)
        self.grid[x][y] = 0
        # make a clear radius around spawn point
        for block in list(inside_circle(3, x, y)):
            try:
                # if self.grid[clear_bl[0]][clear_bl[1]] > 1:
                self.grid[block[0]][block[1]] = 0
            except Exception as e:
                print(f'exception in place_player {block} {e}')
        return (x * BLOCKSIZE, y * BLOCKSIZE)

    def get_block(self, x, y):
        # get block inf from grid
        return self.grid[x][y]

    def get_block_real(self, x, y):
        # get block inf from grid
        gamemapx = x // BLOCKSIZE
        gamemapy = y // BLOCKSIZE
        return self.grid[gamemapx][gamemapy]

    def set_block(self, x, y, value):
        self.grid[x][y] = value
