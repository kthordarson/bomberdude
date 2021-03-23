import random
import math
import pygame
from pygame.math import Vector2
import os
from net.bombclient import gen_randid
# from pygame.colordict import THECOLORS as colordict

DEBUG = True
DEFAULTFONT = "DejaVuSans.ttf"

# global constants
# GRIDSIZE[0] = 15
# GRIDSIZE[1] = 15
GRIDSIZE = (20, 20)
BLOCK = 40
BLOCKSIZE = (BLOCK, BLOCK)
PLAYERSIZE = [int(x // 1.5) for x in BLOCKSIZE]
POWERUPSIZE = [int(x // 2) for x in BLOCKSIZE]
BOMBSIZE = [int(x // 2.5) for x in BLOCKSIZE]
PARTICLESIZE = [int(x // 6) for x in BLOCKSIZE]
FLAMESIZE = [10, 5]
# FLAMESIZE = [int(x // 6) for x in BLOCKSIZE]

# POWERUPSIZE = (12, 12)
# BOMBSIZE = (16, 16)
# FLAMESIZE = (8,8)
# FLAMELENGTH = 20
# PARTICLESIZE = (3,3)
SCREENSIZE = (BLOCKSIZE[0] * (GRIDSIZE[0] + 1), BLOCKSIZE[1] * GRIDSIZE[1] + 100)
# SCREENSIZE = (700, 700)
FPS = 30
POWERUPS = {
    "bombpower": 11,
    "speedup": 12,
    "addbomb": 13,
    "healthup": 14,
}

BLOCKTYPES = {
    "0": {
        "solid": False,
        "permanent": False,
        "size": BLOCKSIZE,
        "bitmap": "blackfloor.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "1": {
        "solid": True,
        "permanent": False,
        "size": BLOCKSIZE,
        "bitmap": "blocksprite5a.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "11": {
        "solid": False,
        "permanent": False,
        "size": BLOCKSIZE,
        "bitmap": "black.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "2": {
        "solid": True,
        "permanent": False,
        "size": BLOCKSIZE,
        "bitmap": "blocksprite3b.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "3": {
        "solid": True,
        "permanent": False,
        "size": BLOCKSIZE,
        "bitmap": "blocksprite6.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "4": {
        "solid": True,
        "permanent": False,
        "size": BLOCKSIZE,
        "bitmap": "blocksprite3.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "5": {
        "solid": True,
        "permanent": True,
        "size": BLOCKSIZE,
        "bitmap": "blocksprite1b.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "10": {
        "solid": True,
        "permanent": True,
        "size": BLOCKSIZE,
        "bitmap": "blocksprite1.png",
        "bgbitmap": "black.png",
        "powerup": False,
    },
    "20": {
        "solid": False,
        "permanent": False,
        "size": POWERUPSIZE,
        "bitmap": "heart.png",
        "bgbitmap": "blackfloor.png",
        "powerup": True,
    },
}

# def gen_randid(seed=None):
#     randid = []
#     for k in range(0,7):
#         n = random.randint(1,99)
#         randid.append(n)
#     return randid


def random_velocity(direction=None):
    while True:
        vel = Vector2(
            (random.uniform(-2.0, 2.0), random.uniform(-2.0, 2.0))
        )
        if direction == "left":
            vel.x = random.uniform(-3.0, 0.3)
        if direction == "right":
            vel.x = random.uniform(0.3, 3.0)
        if direction == "down":
            vel.y = random.uniform(0.3, 3.0)
        if direction == "up":
            vel.y = random.uniform(-3.0, 0.3)
        if vel.y != 0 and vel.x != 0:
            return vel
        else:
            print(f"[vel] {vel}")


def rot_center(image, rect, angle):
    """rotate an image while keeping its center"""
    rot_image = pygame.transform.rotate(image, angle)
    rot_rect = rot_image.get_rect(center=rect.center)
    return rot_image, rot_rect


def get_entity_angle(e_1, e_2):
    dif_x = e_2.x - e_1.x
    dif_y = e_2.y - e_1.y
    return math.atan2(dif_y, dif_x)


def get_angle(pos_1, pos_2):
    dif_x = pos_2[0] - pos_1[0]
    dif_y = pos_2[1] - pos_1[1]
    return math.atan2(dif_y, dif_x)


def limit(num, minimum=1, maximum=255):
    return max(min(num, maximum), minimum)


def inside_circle(radius, pos_x, pos_y):
    x = int(radius)  # radius is the radius
    for x in range(-x, x + 1):
        y = int((radius * radius - x * x) ** 0.5)  # bound for y given x
        for y in range(-y, y + 1):
            yield x + pos_x, y + pos_y


def load_image(name, colorkey=None):
    fullname = os.path.join("data", name)
    try:
        image = pygame.image.load(fullname)
        image = image.convert()
        if colorkey is not None:
            if colorkey == -1:
                colorkey = image.get_at((0, 0))
            image.set_colorkey(colorkey)
        return image, image.get_rect()
    except FileNotFoundError as e:
        print(f"[load_image] {name} {e}")


def dot_product(v1, v2):
    r = 0.0
    for a, b in zip(v1, v2):
        r += a * b
    return r


def scalar_product(v, n):
    return [i * n for i in v]


def normalize(v):
    m = 0.0
    for spam in v:
        m += spam ** 2.0
    m = m ** 0.5
    return [spam / m for spam in v]


class BasicThing(pygame.sprite.Sprite):
    def __init__(self, screen=None, gridpos=None, color=None, vel=Vector2(), accel=Vector2(),
                 dt=None):
        pygame.sprite.Sprite.__init__(self)
        self.color = color
        self.screen = screen
        self.vel = vel
        self.dt = dt
        self.accel = accel
        self.mass = 3
        self.radius = 3
        self.gridpos = gridpos
        # self.size = BLOCKSIZE
        self.font = pygame.freetype.Font(DEFAULTFONT, 12)
        self.font_color = (255, 255, 255)
        self.collisions = []
        self.start_time = pygame.time.get_ticks() / 1000
        self.screenw, self.screenh = pygame.display.get_surface().get_size()

    def collide(self, items=None, dt=None):
        self.collisions = pygame.sprite.spritecollide(self, items, False)
        return self.collisions

    def set_vel(self, vel):
        self.vel = vel

    def set_screen(self, screen):
        self.screen = screen


class Block(BasicThing):
    def __init__(self, gridpos=None, block_type=None, blockid=None, pos=None, dt=None):
        BasicThing.__init__(self)
        pygame.sprite.Sprite.__init__(self)
        self.gridpos = gridpos
        self.block_type = block_type
        self.blockid = blockid
        self.start_time = pygame.time.get_ticks() / 1000
        self.particles = pygame.sprite.Group()
        self.dt = dt
        self.start_time = pygame.time.get_ticks() / 1000
        self.explode = False
        # self.hit = False
        self.timer = 10
        self.bomb_timer = 1
        self.poweruptime = 10
        self.pos = Vector2((BLOCKSIZE[0] * self.gridpos[0], BLOCKSIZE[1] * self.gridpos[1]))
        self.gridpos = Vector2((self.pos.x // BLOCKSIZE[0], self.pos.y // BLOCKSIZE[1]))
        self.solid = BLOCKTYPES.get(block_type)["solid"]
        self.permanent = BLOCKTYPES.get(block_type)["permanent"]
        self.size = BLOCKTYPES.get(block_type)["size"]
        self.bitmap = BLOCKTYPES.get(block_type)["bitmap"]
        self.powerup = BLOCKTYPES.get(block_type)["powerup"]
        self.image, self.rect = load_image(self.bitmap, -1)
        self.image = pygame.transform.scale(self.image, self.size)
        self.rect = self.image.get_rect(topleft=self.pos)
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y
        self.image.set_alpha(255)
        self.image.set_colorkey((0, 0, 0))

    def hit(self):
        if not self.permanent:
            self.block_type = '0'
            self.solid = False
            self.image, self.rect = load_image('blackfloor.png', -1)
            self.image = pygame.transform.scale(self.image, self.size)
            self.image.set_alpha(255)
            self.image.set_colorkey((0, 0, 0))
            self.rect = self.image.get_rect(topleft=self.pos)
            self.rect.x = self.pos.x
            self.rect.y = self.pos.y
            # self.rect = self.image.get_rect()

    def get_type(self):
        return self.block_type

    def set_type(self, block_type="0"):
        pass

    def update(self, items=None):
        pass
        # if len(self.particles) <= 0:
        #   self.hit = False

    def get_particles(self):
        return self.particles

    def gen_particles(self, flame):
        # called when block is hit by a flame
        # generate particles and set initial velocity based on direction of flame impact
        self.particles = pygame.sprite.Group()
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y
        # flame.vel = Vector2(flame.vel[0], flame.vel[1])
        for k in range(1, 10):
            if flame.vel.x < 0:  # flame come from left
                self.particles.add(
                    Particle(pos=flame.rect.midright, vel=random_velocity(direction="right")))  # make particle go right
            elif flame.vel.x > 0:  # right
                self.particles.add(
                    Particle(pos=flame.rect.midleft, vel=random_velocity(direction="left")))  # for k in range(1,2)]
            elif flame.vel.y > 0:  # down
                self.particles.add(Particle(pos=flame.rect.midtop, vel=random_velocity(
                    direction="up")))  # flame.vel.y+random.uniform(-1.31,1.85))))   #for k in range(1,2)]
            elif flame.vel.y < 0:  # up
                self.particles.add(Particle(pos=flame.rect.midbottom, vel=random_velocity(
                    direction="down")))  # flame.vel.y+random.uniform(-1.31,1.85))))   #for k in range(1,2)]
        return self.particles


class Powerup(BasicThing):
    def __init__(self, pos=None, vel=None, dt=None):
        # super().__init__()
        BasicThing.__init__(self)
        pygame.sprite.Sprite.__init__(self)
        self.dt = dt
        self.image, self.rect = load_image("heart.png", -1)
        self.size = POWERUPSIZE
        self.image = pygame.transform.scale(self.image, self.size)
        self.rect = self.image.get_rect()
        self.rect.center = pos
        self.pos = Vector2(pos)
        self.alpha = 255
        self.image.set_alpha(self.alpha)
        self.timer = 5
        self.start_time = pygame.time.get_ticks() / 1000

    def update(self, items=None):
        self.dt = pygame.time.get_ticks() / 1000
        # print(f'[pu] {dt  - self.start_time} {self.timer}')
        if self.dt - self.start_time >= self.timer:
            self.kill()


class Particle(BasicThing):
    def __init__(self, pos=None, vel=None, dt=None):
        # super().__init__()
        BasicThing.__init__(self)
        pygame.sprite.Sprite.__init__(self)
        self.dt = dt
        self.pos = Vector2(pos)
        self.image, self.rect = load_image("greenorb.png", -1)
        self.size = PARTICLESIZE
        self.image = pygame.transform.scale(self.image, self.size)
        self.alpha = 255
        self.image.set_alpha(self.alpha)
        self.rect = self.image.get_rect(topleft=self.pos)
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y
        self.start_time = 1  # pygame.time.get_ticks() // 1000
        self.timer = 10
        self.hits = 0
        self.maxhits = 10
        self.start_time = pygame.time.get_ticks() / 1000
        self.angle = math.degrees(0)
        self.mass = 11
        self.vel = vel  # Vector2(random.uniform(-2, 2), random.uniform(-2, 2))  # Vector2(0, 0)

    # self.accel = Vector2(0.05,0.05)

    def stop(self):
        print(f"[stop] {self.vel}")
        self.vel = Vector2(0, 0)
        print(f"[stop] {self.vel}")

    def move(self):
        print(f"[move] {self.vel}")

    def update(self, items=None):
        self.dt = pygame.time.get_ticks() / 1000
        if self.dt - self.start_time >= self.timer:
            self.kill()
        if self.rect.top <= 0 or self.rect.left <= 0:
            self.kill()
        self.alpha -= random.randrange(1, 5)
        if self.alpha <= 0:
            self.kill()
        else:
            self.image.set_alpha(self.alpha)
        self.vel -= self.accel
        self.pos += self.vel
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y

    def collide_blocks(self, blocks, dt):
        pass
    # for block in blocks:
    #     if self.surface_distance(block, dt) <= 0:
    #         collision_vector = self.pos - block.pos
    #         collision_vector.normalize()
    #         print(f'{self.surface_distance(block, dt)}')
    #         self.vel = self.vel.reflect(collision_vector)
    #         block.vel = block.vel.reflect(collision_vector)


class Flame(BasicThing):
    def __init__(self, pos=None, vel=None, direction=None, dt=None, flame_length=None):
        # super().__init__()
        BasicThing.__init__(self)
        pygame.sprite.Sprite.__init__(self)
        self.dt = dt
        if vel[0] == -1 or vel[0] == 1:
            self.image, self.rect = load_image("flame4.png", -1)
        elif vel[1] == -1 or vel[1] == 1:
            self.image, self.rect = load_image("flame3.png", -1)
        self.image = pygame.transform.scale(self.image, FLAMESIZE)
        # dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
        self.size = FLAMESIZE
        self.pos = Vector2(pos)
        self.rect.x = self.pos.x
        self.rect.y = self.pos.y
        self.start_pos = Vector2(pos)
        self.vel = Vector2(vel[0], vel[1])  # flame direction
        self.timer = 10
        self.start_time = pygame.time.get_ticks() / 1000
        self.flame_length = flame_length
        self.stopped = False

    def check_time(self):
        pass

    def stop(self):
        self.vel = Vector2((0, 0))
        self.stopped = True
        self.kill()

    def draw(self, screen):
        screen.blit(self.image, self.pos)

    def update(self):
        if not self.stopped:
            self.dt = pygame.time.get_ticks() / 1000
            self.pos += self.vel
            distance = abs(int(self.pos.distance_to(self.start_pos)))
            center = self.rect.center
            if self.vel[0] == -1 or self.vel[0] == 1:
                self.image = pygame.transform.scale(self.image, (self.size[0] + distance, self.size[1]))
            if self.vel[1] == -1 or self.vel[1] == 1:
                self.image = pygame.transform.scale(self.image, (self.size[0], self.size[1] + distance))
            self.rect = self.image.get_rect()
            self.rect = self.image.get_rect(topleft=self.pos)
            self.rect.center = center
            self.rect.x = self.pos.x
            self.rect.y = self.pos.y
            # print(f'{self.pos.x} {self.start_pos.x} {self.pos.distance_to(self.start_pos)}')
            if distance >= self.flame_length:  # or (self.dt - self.start_time >= self.timer):
                # print(f'[flame] dist {distance} max {self.flame_length}')
                self.kill()
            if self.dt - self.start_time >= self.timer:
                pass
                # print(f'[flame] time {self.dt - self.start_time} >= {self.timer}')
                # self.kill()


class Bomb(BasicThing):
    def __init__(self, pos=None, bomber_id=None, bomb_power=None, dt=None):
        pygame.sprite.Sprite.__init__(self)
        self.dt = dt
        self.pos = pos
        self.image, self.rect = load_image("bomb.png", -1)
        self.image = pygame.transform.scale(self.image, BOMBSIZE)
        # self.gridpos = gridpos
        self.bomber_id = bomber_id
        self.rect = self.image.get_rect(topleft=self.pos)
        self.rect.centerx = self.pos.x
        self.rect.centery = self.pos.y
        self.font = pygame.font.SysFont("calibri", 10, True)
        self.start_time = pygame.time.get_ticks() / 1000
        self.bomb_timer = 1
        self.bomb_fuse = 1
        self.bomb_end = 2
        self.bomb_size = 5
        self.explode = False
        self.exp_radius = 1
        self.done = False
        self.flame_power = bomb_power
        self.flame_len = bomb_power
        self.flame_width = 10
        self.flamesout = False
        self.flames = pygame.sprite.Group()

    def gen_flames(self):
        if not self.flamesout:
            self.flames = pygame.sprite.Group()
            dirs = [(-1, 0), (1, 0), (0, 1), (0, -1)]
            flex = [Flame(pos=Vector2(self.pos), vel=k, dt=self.dt, flame_length=self.flame_len) for k in
                    dirs]
            for f in flex:
                self.flames.add(f)
            self.flamesout = True
        return self.flames


class Player(BasicThing):
    def __init__(self, pos=None, dt=None, image='player1.png', bot=False):
        BasicThing.__init__(self)
        pygame.sprite.Sprite.__init__(self)
        self.dt = dt
        self.image, self.rect = load_image(image, -1)
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.size = PLAYERSIZE
        self.image = pygame.transform.scale(self.image, self.size)
        self.rect = self.image.get_rect(topleft=self.pos)
        self.rect.centerx = self.pos.x
        self.rect.centery = self.pos.y
        self.max_bombs = 3
        self.bombs_left = self.max_bombs
        self.bomb_power = 15
        self.speed = 1
        self.health = 100
        self.dead = False
        self.score = 0
        self.font = pygame.font.SysFont("calibri", 10, True)
        self.bot = bot
        self.bot_chdir = False
        self.client_id = ''.join([''.join(str(k)) for k in gen_randid()])

    def bot_move(self, blocks, dt):
        pass
        # if self.bot_chdir:
        #     botdir = random.choice([1,2,3,4])
        #     if botdir == 1:
        #         self.vel.x = -self.speed
        #     if botdir == 2:
        #         self.vel.x = abs(self.speed)
        #     if botdir == 3:
        #         self.vel.y = -self.speed
        #     if botdir == 4:
        #         self.vel.y = abs(self.speed)
        #     self.bot_chdir = False

    def move(self, blocks, dt):
        self.vel += self.accel
        self.pos.x += self.vel.x
        self.rect.x = int(self.pos.x)
        block_hit_list = self.collide(blocks, dt)
        for block in block_hit_list:
            if isinstance(block, Block):
                if self.vel.x > 0 and block.solid:
                    self.rect.right = block.rect.left
                    self.bot_chdir = True
                elif self.vel.x < 0 and block.solid:
                    self.rect.left = block.rect.right
                    self.bot_chdir = True
                self.pos.x = self.rect.x
            # self.vel.x = 0
        self.pos.y += self.vel.y
        self.rect.y = int(self.pos.y)
        block_hit_list = self.collide(blocks)
        for block in block_hit_list:
            self.bot_chdir = True
            if self.vel.y > 0 and block.solid:
                self.rect.bottom = block.rect.top
                self.bot_chdir = True
            elif self.vel.y < 0 and block.solid:
                self.rect.top = block.rect.bottom
                self.bot_chdir = True
            # self.change_y = 0
            self.pos.y = self.rect.y
        # self.vel.y = 0

    def take_powerup(self, powerup=None):
        # pick up powerups...
        if powerup == 1:
            if self.max_bombs < 10:
                self.max_bombs += 1
                self.bombs_left += 1
        if powerup == 2:
            self.speed += 1
        if powerup == 3:
            self.bomb_power += 10

    def add_score(self):
        self.score += 1


class Gamemap:
    def __init__(self):
        self.grid = []

    @staticmethod
    def generate():
        grid = [[random.randint(0, 5) for k in range(GRIDSIZE[1] + 1)] for j in range(GRIDSIZE[0] + 1)]
        # set edges to solid blocks, 10 = solid blockwalkk
        for x in range(GRIDSIZE[0] + 1):
            grid[x][0] = 10
            grid[x][GRIDSIZE[1]] = 10
        for y in range(GRIDSIZE[1] + 1):
            grid[0][y] = 10
            grid[GRIDSIZE[0]][y] = 10
        return grid

    def place_player(self, location=0):
        # place player somewhere where there is no block
        # returns the (x,y) coordinate where player is to be placed
        # random starting point from gridgamemap
        if location == 0:  # center pos
            x = int(GRIDSIZE[0] // 2)  # random.randint(2, GRIDSIZE[0] - 2)
            y = int(GRIDSIZE[1] // 2)  # random.randint(2, GRIDSIZE[1] - 2)
            # x = int(x)
            self.grid[x][y] = 0
            # make a clear radius around spawn point
            for block in list(inside_circle(3, x, y)):
                try:
                    # if self.grid[clear_bl[0]][clear_bl[1]] > 1:
                    self.grid[block[0]][block[1]] = 0
                except Exception as e:
                    print(f"exception in place_player {block} {e}")
            return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))
        if location == 1:  # top left
            x = 5
            y = 5
            # x = int(x)
            self.grid[x][y] = 0
            # make a clear radius around spawn point
            for block in list(inside_circle(3, x, y)):
                try:
                    # if self.grid[clear_bl[0]][clear_bl[1]] > 1:
                    self.grid[block[0]][block[1]] = 0
                except Exception as e:
                    print(f"exception in place_player {block} {e}")
            return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))

    def get_block(self, x, y):
        # get block inf from grid
        try:
            value = self.grid[x][y]
        except IndexError as e:
            print(f"[get_block] {e} x:{x} y:{y}")
            return -1
        return value

    def get_block_real(self, x, y):
        x = x // BLOCKSIZE[0]
        y = y // BLOCKSIZE[1]
        try:
            value = self.grid[x][y]
        except IndexError as e:
            print(f"[get_block] {e} x:{x} y:{y}")
            return -1
        return value

    def set_block(self, x, y, value):
        self.grid[x][y] = value
