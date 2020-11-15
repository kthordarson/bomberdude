# bomberdude
# TODO
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import os
import random

import pygame as pg

from globals import Block, Particle, BlockBomb, Player, Gamemap
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y
from globals import get_angle, get_entity_angle
from menus import Info_panel
from menus import Menu

DEBUG = False


class Game():
    def __init__(self, gamemap, screen):
        self.gamemap = gamemap
        self.gamemap.generate()
        self.screen = screen  # pg.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize), 0, 32)
        self.gameloop = asyncio.get_event_loop()
        self.bg_color = pg.Color('gray12')
        self.show_mainmenu = True
        self.running = False
        self.players = pg.sprite.Group()
        self.player1 = Player(pos=self.gamemap.place_player(), player_id=33)
        self.players.add(self.player1)
        self.blocksparticles = pg.sprite.Group()
        self.powerblocks = pg.sprite.Group()
        self.blocks = pg.sprite.Group()
        donk = [self.blocks.add(Block(screen=self.screen,  gridpos=(k, j), blocktype=str(self.gamemap.grid[j][k]))) for k in range(0, GRID_X+1) for j in range(0, GRID_Y+1)]
        self.bombs = pg.sprite.Group()
        self.bombs.flames = pg.sprite.Group()
        self.game_menu = Menu(self.screen)
        self.info_panel = Info_panel(BLOCKSIZE, GRID_Y * BLOCKSIZE + BLOCKSIZE, self.screen)
        self.show_panel = True

    def set_block(self, x, y, value):
        self.gamemap.grid[x][y] = value

    def terminate(self):
        os._exit(1)

    def bombdrop(self, player):
        # get grid pos of player
        x = player.gridpos[0]
        y = player.gridpos[1]
        if player.bombs_left > 0:  # and game_data.grid[x][y] == 0:  # only place bombs if we have bombs... and on free spot...
            # create bomb at gridpos xy, multiply by BLOCKSIZE for screen coordinates
            bomb = BlockBomb(pos=(player.rect.centerx, player.rect.centery), bomber_id=player.player_id, color=pg.Color('yellow'), bomb_power=player.bomb_power, gridpos=player.gridpos)
            self.bombs.add(bomb)
            player.bombs_left -= 1
        # else:
        #	print(f'cannot drop bomb')

    def update(self):
        # todo network things
        self.player1.update(self.blocks)
        self.update_bombs()
        # self.update_powerblock()
        self.update_blocks()
        donk = [particle.update() for particle in self.blocksparticles]

    def update_blocks(self):
        for block in self.blocks:
            block.update()
            partcoll = block.collide(self.blocksparticles)  # for particle in block.particles
            if len(partcoll) > 0:
                for particle in partcoll:
                    if isinstance(particle, Particle) and block.solid:
                        # math.degrees(get_angle(pg.math.Vector2(4,4), pg.math.Vector2(4,5)))
                        angle = get_angle(particle.rect, block.rect)
                        # angle = get_entity_angle(particle.rect, block.rect)
                        if 0 < angle < 90:
                            particle.vel.x = -particle.vel.x
                        if 90 < angle < 180:
                            particle.vel.x = -particle.vel.x
                        if 180 < angle < 270:
                            particle.vel.y = -particle.vel.y
                        else:
                            particle.vel.y = -particle.vel.y
                        #particle.vel.x += random.choice([-0.5, 0.5])
                        #particle.vel.y += random.choice([-0.5, 0.5])

    def update_bombs(self):
        self.bombs.update()
        self.bombs.flames.update()
        for bomb in self.bombs:
            if bomb.exploding:
                for flame in bomb.flames:
                    blocks = pg.sprite.spritecollide(flame, self.blocks, False)
                    for block in blocks:
                        if int(block.block_type) >= 1:
                            # block.take_damage(self.screen,  flame)  #  = True		# block particles
                            gengja = [self.blocksparticles.add(Particle(block, flame.direction)) for k in range(1, 10) if not block.hit]
                            block.hit = True
                            flame.stop()
                        if int(block.block_type) >= 3: 		# block_type 1,2,3 = solid orange
                            block.drop_powerblock()		# make block drop the powerup
                            self.player1.add_score()  # give player some score
                            # self.game_data.grid[bomb.gridpos[0]][bomb.gridpos[1]] = 0

            if bomb.done:
                self.player1.bombs_left += 1  # return bomb to owner when done
                bomb.kill()

    def draw(self):
        # draw on screen
        pg.display.flip()
        self.screen.fill(self.bg_color)
        [block.draw(self.screen) for block in self.blocks]
        [bomb.draw(self.screen) for bomb in self.bombs]
        [flame.draw(self.screen) for flame in self.bombs.flames]
        [powerblock.draw(self.screen) for powerblock in self.powerblocks]
        # for block in self.blocks:
        [particle.draw(self.screen) for particle in self.blocksparticles]
        self.players.draw(self.screen)
        if self.show_mainmenu:
            self.game_menu.draw_mainmenu(self.screen)
        if self.show_panel:
            self.info_panel.draw_panel(gamemap=self.gamemap, blocks=self.blocks, particles=self.blocksparticles, player1=self.player1)

    def handle_menu(self, selection):
        # mainmenu
        if selection == 'Quit':
            self.running = False
            self.terminate()
        if selection == 'Pause':
            self.show_mainmenu ^= True
        if selection == 'Start':
            self.show_mainmenu ^= True
        if selection == 'Restart':
            self.show_mainmenu ^= True
        if selection == 'Start server':
            pass
        if selection == 'Connect to server':
            pass

    def handle_input(self):
        # get player input
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_SPACE or event.key == pg.K_RETURN:
                    if self.show_mainmenu:  # or self.paused:
                        selection = self.game_menu.get_selection()
                        self.handle_menu(selection)
                    else:
                        self.bombdrop(self.player1)
                if event.key == pg.K_ESCAPE:
                    if not self.show_mainmenu:
                        self.running = False
                        # break
                        self.terminate()
                    else:
                        self.show_mainmenu ^= True
                if event.key == pg.K_c:
                    self.player1.bomb_power = 100
                    self.player1.max_bombs = 10
                    self.player1.bombs_left = 10
                    self.player1.speed = 10
                if event.key == pg.K_p:
                    self.show_panel ^= True
                if event.key == pg.K_m:
                    pass
                    # self.paused ^= True
                if event.key == pg.K_q:
                    pass
                    # DEBUG ^= True
                if event.key == pg.K_g:
                    pass
                    # DEBUG = False
                    # DEBUG_GRID ^= True
                if event.key == pg.K_r:
                    pass
                    # game_init()
                if event.key in set([pg.K_DOWN, pg.K_s]):
                    if self.show_mainmenu:
                        self.game_menu.menu_down()
                    else:
                        self.player1.vel.y = self.player1.speed
                if event.key in set([pg.K_UP, pg.K_w]):
                    if self.show_mainmenu:
                        self.game_menu.menu_up()
                    else:
                        self.player1.vel.y = -self.player1.speed
                if event.key in set([pg.K_RIGHT, pg.K_d]):
                    if not self.show_mainmenu:
                        self.player1.vel.x = self.player1.speed
                if event.key in set([pg.K_LEFT, pg.K_a]):
                    if not self.show_mainmenu:
                        self.player1.vel.x = -self.player1.speed
            if event.type == pg.KEYUP:
                if event.key == pg.K_a:
                    pass
                if event.key == pg.K_d:
                    pass
                if event.key in set([pg.K_DOWN, pg.K_s]):
                    if not self.show_mainmenu:
                        self.player1.vel.y = 0
                if event.key in set([pg.K_UP, pg.K_w]):
                    if not self.show_mainmenu:
                        self.player1.vel.y = 0
                if event.key in set([pg.K_RIGHT, pg.K_d]):
                    if not self.show_mainmenu:
                        self.player1.vel.x = 0
                if event.key in set([pg.K_LEFT, pg.K_a]):
                    if not self.show_mainmenu:
                        self.player1.vel.x = 0
            if event.type == pg.MOUSEBUTTONDOWN:
                mousex, mousey = pg.mouse.get_pos()
                blockinf = self.gamemap.get_block_real(mousex, mousey)
                gx = mousex // BLOCKSIZE
                gy = mousey // BLOCKSIZE
                print(f'mouse x:{mousex} y:{mousey} | gx:{gx} gy:{gy} | b:{blockinf}')
            if event.type == pg.QUIT:
                self.running = False


async def main_loop(game):
    mainClock = pg.time.Clock()
    # game.game_init(game)
    while True:
        # main game loop logic stuff
        dt = mainClock.tick(FPS)
        pg.event.pump()
        game.handle_input()
        game.update()
        game.draw()


def main():
    panelsize = BLOCKSIZE * 5
    screen = pg.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize), 0, 32)
    gamemap = Gamemap()
    game = Game(gamemap=gamemap, screen=screen)
    game_task = asyncio.Task(main_loop(game))
    game.gameloop.run_until_complete(game_task)


if __name__ == "__main__":
    pg.init()
    try:
        main()
    finally:
        pg.quit()
