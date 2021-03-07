# bomberdude
# TODO
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import random
import pygame
from pygame.math import Vector2

from debug import (
    draw_debug_sprite,
    draw_debug_block
)
from globals import BLOCKSIZE, FPS, GRIDSIZE, SCREENSIZE, DEFAULTFONT
from globals import Block, Bomb, Player, Gamemap, Powerup
from globals import DEBUG
from globals import get_angle
from menus import Menu
from random import randint
import time
from net.bombclient import BombClient

class Game:
    def __init__(self, screen=None, game_dt=None):
        # pygame.display.set_mode((GRIDSIZE[0] * BLOCKSIZE + BLOCKSIZE, GRIDSIZE[1] * BLOCKSIZE + panelsize), 0, 32)
        self.dt = game_dt
        self.screen = screen
        self.gameloop = asyncio.get_event_loop()
        self.bg_color = pygame.Color("black")
        self.show_mainmenu = True
        self.running = False
        self.show_panel = True
        self.gamemap = Gamemap()
        self.gamemap.grid = self.gamemap.generate()
        self.blocks = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.players = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.powerups = pygame.sprite.Group()
        self.bombs = pygame.sprite.Group()
        self.flames = pygame.sprite.Group()
        self.game_menu = Menu(self.screen)
        self.player1 = Player(pos=self.gamemap.place_player(location=0), player_id=33, dt=self.dt, image='player1.png', bot=False)
        self.player2 = Player(pos=self.gamemap.place_player(location=1), player_id=50, dt=self.dt, image='player2.png', bot=True)
        _ = [self.blocks.add(Block(gridpos=(j, k), dt=self.dt, block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRIDSIZE[0] + 1) for j in range(0, GRIDSIZE[1] + 1)]
        self.players.add(self.player1)
        self.players.add(self.player2)
        self.font = pygame.freetype.Font(DEFAULTFONT, 12)
        self.connected = False
        self.client = BombClient(player=self.player1)

    def network_update(self, data=None):
        data = self.player1.pos
        # print(f'[n] send {data}')
        self.client.Send(data)

    def update(self):
        # todo network things
        # [player.update(self.blocks) for player in self.players]
        self.players.update(self.blocks)
        _ = [player.move(self.blocks, dt) for player in self.players]
        _ = [player.bot_move(self.blocks, dt) for player in self.players if player.bot]
        self.bombs.update()
        for bomb in self.bombs:
            bomb.dt = pygame.time.get_ticks() / 1000
            if bomb.dt - bomb.start_time >= bomb.bomb_fuse:
                bomb.gen_flames()
                self.flames.add(bomb.flames)
                bomb.kill()
                self.player1.bombs_left += 1
        self.flames.update()
        for flame in self.flames:
            flame_coll = pygame.sprite.spritecollide(flame, self.blocks, False)
            for block in flame_coll:
                if block.block_type == '1' or block.block_type == "2":  # or block.block_type == '3' or block.block_type == '4':
                    powerup = Powerup(pos=block.rect.center, dt=dt)
                    self.powerups.add(powerup)
                    draw_debug_block(self.screen, block)
                if block.solid:
                    block.hit()
                    block.gen_particles(flame)
                    self.particles.add(block.particles)
                    flame.kill()

        for particle in self.particles:
            blocks = pygame.sprite.spritecollide(particle, self.blocks, dokill=False)
            for block in blocks:
                if block.solid:
                    particle.kill()
        powerblock_coll = pygame.sprite.spritecollide(self.player1, self.powerups, False)
        for pc in powerblock_coll:
            self.player1.take_powerup(powerup=random.choice([1, 2, 3]))
            pc.kill()

        self.particles.update(self.blocks)
        self.blocks.update(self.blocks)
        self.powerups.update()

    def set_block(self, x, y, value):
        self.gamemap.grid[x][y] = value

    def bombdrop(self, player):
        if player.bombs_left > 0:
            bombpos = Vector2((player.rect.centerx, player.rect.centery))
            bomb = Bomb(pos=bombpos, dt=self.dt, bomber_id=player.player_id, bomb_power=player.bomb_power)
            self.bombs.add(bomb)
            player.bombs_left -= 1

    def draw(self):
        # draw on screen
        pygame.display.flip()
        self.screen.fill(self.bg_color)
        self.blocks.draw(self.screen)
        self.bombs.draw(self.screen)
        self.powerups.draw(self.screen)
        self.particles.draw(self.screen)
        self.players.draw(self.screen)
        self.flames.draw(self.screen)

        if self.show_mainmenu:
            self.game_menu.draw_mainmenu(self.screen)
        self.game_menu.draw_panel(gamemap=self.gamemap, blocks=self.blocks, particles=self.particles,
                                  player1=self.player1, flames=self.flames)
        if DEBUG:
            draw_debug_sprite(self.screen, self.players)


    def handle_menu(self, selection):
        # mainmenu
        if selection == "Quit":
            self.running = False
        if selection == "Pause":
            self.show_mainmenu ^= True
        if selection == "Start":
            self.show_mainmenu ^= True
        if selection == "Restart":
            self.show_mainmenu ^= True
        if selection == "Start server":
            pass
        if selection == "Connect to server":
            if self.client.Connect():
                auth = self.client.authenticate()
                self.connected = True
            else:
                self.connected = False

    def handle_input(self):
        # get player input
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                    if self.show_mainmenu:  # or self.paused:
                        selection = self.game_menu.get_selection()
                        self.handle_menu(selection)
                    else:
                        self.bombdrop(self.player1)
                if event.key == pygame.K_ESCAPE:
                    if not self.show_mainmenu:
                        self.running = False
                    else:
                        self.show_mainmenu ^= True
                if event.key == pygame.K_1:
                    _ = [particle.stop() for particle in self.particles]
                if event.key == pygame.K_2:
                    _ = [particle.move() for particle in self.particles]
                if event.key == pygame.K_3:
                    _ = [particle.set_vel() for particle in self.particles]
                if event.key == pygame.K_4:
                    _ = [particle.set_vel(Vector2(1, 1)) for particle in self.particles]
                if event.key == pygame.K_5:
                    _ = [particle.kill() for particle in self.particles]
                if event.key == pygame.K_c:
                    self.player1.bomb_power = 100
                    self.player1.max_bombs = 10
                    self.player1.bombs_left = 10
                    self.player1.speed = 7
                if event.key == pygame.K_p:
                    self.show_panel ^= True
                if event.key == pygame.K_m:
                    pass
                if event.key == pygame.K_q:
                    pass
                if event.key == pygame.K_g:
                    pass
                if event.key == pygame.K_r:
                    pass
                if event.key in {pygame.K_DOWN, pygame.K_s}:
                    if self.show_mainmenu:
                        self.game_menu.menu_down()
                    else:
                        self.player1.vel.y = self.player1.speed
                if event.key in {pygame.K_UP, pygame.K_w}:
                    if self.show_mainmenu:
                        self.game_menu.menu_up()
                    else:
                        self.player1.vel.y = -self.player1.speed
                if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
                    # if not self.show_mainmenu:
                    self.player1.vel.x = self.player1.speed
                if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
                    # if not self.show_mainmenu:
                    self.player1.vel.x = -self.player1.speed
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_a:
                    pass
                if event.key == pygame.K_d:
                    pass
                if event.key in {pygame.K_DOWN, pygame.K_s} and not self.show_mainmenu:
                    self.player1.vel.y = 0
                if event.key in {pygame.K_UP, pygame.K_w} and not self.show_mainmenu:
                    self.player1.vel.y = 0
                if event.key in {pygame.K_RIGHT, pygame.K_d} and not self.show_mainmenu:
                    self.player1.vel.x = 0
                if event.key in {pygame.K_LEFT, pygame.K_a} and not self.show_mainmenu:
                    self.player1.vel.x = 0
            #if event.type == pygame.MOUSEBUTTONDOWN:
                # mousex, mousey = pygame.mouse.get_pos()
                # gridx = mousex // BLOCKSIZE[0]
                # gridy = mousey // BLOCKSIZE[1]
                # angle = get_angle(self.player1.pos, pygame.mouse.get_pos())
                # angle2 = get_angle(pygame.mouse.get_pos(), self.player1.pos)
            # blockinf = self.gamemap.get_block_real(mousex, mousey)
            # print(f"mouse x:{mousex} y:{mousey} [gx:{gridx} gy:{gridy}] |  b:{self.gamemap.get_block(gridx, gridy)} a:{angle:.1f} a2:{angle2:.1f}")
            # print(f"mouse x:{mousex} y:{mousey} [x:{mousex//BLOCKSIZE[0]} y:{mousey//BLOCKSIZE[1]}]|  b:{self.gamemap.get_block(mousex // GRIDSIZE[0], mousey // GRIDSIZE[1])} ")
            if event.type == pygame.QUIT:
                self.running = False


if __name__ == "__main__":
    pygame.init()
    pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
    game = Game(screen=pyscreen)
    mainClock = pygame.time.Clock()
    dt = mainClock.tick(FPS) / 1000
    game.running = True
    while game.running:
        # main game loop logic stuff
        game.handle_input()
        pygame.event.pump()
        game.update()
        game.draw()
        if game.connected:
            game.network_update()
        # print(f'{game.client}')
    pygame.quit()
