import pygame
import pygame.freetype
from pygame.color import THECOLORS
import math
from globals import Bomb, Block, Particle, BasicThing
from globals import DEFAULTFONT, BLOCKSIZE
from globals import get_angle


def draw_debug_sprite(screen, sprites):
    # DEBUGFONTCOLOR = (255, 255, 255)
    # DEBUGFONT.fgcolor
    DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
    DEBUGFONTCOLOR = (123, 123, 123)
    for sprite in sprites:
        # screen.set_at(sprite.rect.center, (255,255,255))
        # screen.set_at(sprite.rect.topleft, (255,255,255))
        # screen.set_at(sprite.rect.topright, (255,255,255))
        # screen.set_at(sprite.rect.bottomright, (255,255,255))
        # screen.set_at(sprite.rect.bottomleft, (255,255,255))
        if isinstance(sprite, Particle):
            try:
                DEBUGFONT.render_to(
                    screen,
                    sprite.rect.center,
                    f"xv:{sprite.vel.x:.0f} yv:{sprite.vel.y:.0f}",
                    DEBUGFONTCOLOR,
                )
            except TypeError as e:
                print(f"[DP] {e} {sprite.rect} {math.degrees(sprite.angle)}")
    # font.render_to(screen,(player.rect.x, player.rect.y),f"player pos x:{player.rect}",DEBUGFONTCOLOR)
    # font.render_to(screen,player.rect.topleft,f"{player.rect.x}",DEBUGFONTCOLOR)
    # font.render_to(screen,player.rect.topright,f"{player.rect.y}",DEBUGFONTCOLOR)
    # font.render_to(screen,player.rect.bottomleft,f"{player.rect.y}",DEBUGFONTCOLOR)
    # font.render_to(screen,player.rect.bottomright,f"{player.rect.y}",DEBUGFONTCOLOR)
    # font.render_to(screen,player.pos,f"player pos x:{player.rect}",DEBUGFONTCOLOR)


def debug_mouse_particles(screen, particles):
    DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
    DEBUGFONTCOLOR = (123, 123, 123)
    mousepos = pygame.mouse.get_pos()
    for particle in particles:
        angle = get_angle(mousepos, particle.rect.center)
        DEBUGFONT.render_to(
            screen, particle.rect.center, f"{angle:.1f}", (255, 255, 255)
        )
        if -3 <= angle <= -2.5:
            pygame.draw.line(screen, (255, 255, 255), mousepos, particle.rect.midright)
        if -2.5 <= angle <= -1.5:
            pygame.draw.line(screen, (255, 255, 255), mousepos, particle.rect.midbottom)
        # pygame.draw.line(screen, (255,255,255), mousepos, particle.rect.bottomleft)
        if -1.5 <= angle <= -0.5:
            pygame.draw.line(screen, (255, 255, 255), mousepos, particle.rect.midleft)
        # pygame.draw.line(screen, (255,255,255), mousepos, particle.rect.bottomleft)
        if -0.5 <= angle <= -0.0:
            pygame.draw.line(screen, (255, 255, 255), mousepos, particle.rect.midleft)
        if 0.0 <= angle <= 0.5:
            # pygame.draw.line(screen, (255,255,255), mousepos, particle.rect.topleft)
            pygame.draw.line(screen, (255, 255, 255), mousepos, particle.rect.midleft)
        if 0.5 <= angle <= 3:
            pygame.draw.line(screen, (255, 255, 255), mousepos, particle.rect.midtop)
        # pygame.draw.line(screen, (255,255,255), mousepos, particle.rect.topleft)
        # pygame.draw.line(screen, (255,255,255), mousepos, particle.rect.topright)
        if 3 <= angle <= 3.5:
            # pygame.draw.line(screen, (255,255,225), mousepos, particle.rect.topleft)
            # pygame.draw.line(screen, (255,255,225), mousepos, particle.rect.topright)
            pygame.draw.line(screen, (255, 255, 225), mousepos, particle.rect.midright)


def debug_draw_mouseangle(self, screen, player):
    DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
    DEBUGFONTCOLOR = (123, 123, 123)
    mousepos = pygame.mouse.get_pos()
    angle = get_angle(mousepos, player.rect.center)
    DEBUGFONT.render_to(screen, mousepos, f"{angle:.1f}", (255, 255, 255))
    if -3 <= angle <= -2.5:
        pygame.draw.line(screen, (255, 255, 255), mousepos, player.rect.midright)
    if -2.5 <= angle <= -1.5:
        pygame.draw.line(screen, (255, 255, 255), mousepos, player.rect.midbottom)
    # pygame.draw.line(screen, (255,255,255), mousepos, player.rect.bottomleft)
    if -1.5 <= angle <= -0.5:
        pygame.draw.line(screen, (255, 255, 255), mousepos, player.rect.midleft)
    # pygame.draw.line(screen, (255,255,255), mousepos, player.rect.bottomleft)
    if -0.5 <= angle <= -0.0:
        pygame.draw.line(screen, (255, 255, 255), mousepos, player.rect.midleft)
    if 0.0 <= angle <= 0.5:
        # pygame.draw.line(screen, (255,255,255), mousepos, player.rect.topleft)
        pygame.draw.line(screen, (255, 255, 255), mousepos, player.rect.midleft)
    if 0.5 <= angle <= 3:
        pygame.draw.line(screen, (255, 255, 255), mousepos, player.rect.midtop)
    # pygame.draw.line(screen, (255,255,255), mousepos, player.rect.topleft)
    # pygame.draw.line(screen, (255,255,255), mousepos, player.rect.topright)
    if 3 <= angle <= 3.5:
        # pygame.draw.line(screen, (255,255,225), mousepos, player.rect.topleft)
        # pygame.draw.line(screen, (255,255,225), mousepos, player.rect.topright)
        pygame.draw.line(screen, (255, 255, 225), mousepos, player.rect.midright)


# pygame.mouse.set_visible(True)


def draw_debug_particles(screen, particles, blocks):
    pass


def draw_debug_particles_1(screen, particles, blocks):
    DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
    DEBUGFONTCOLOR = (123, 123, 123)
    for particle in particles:
        if particle.vel.y < 0:
            linecolor = (255, 0, 0)
        elif particle.vel.y > 0:
            linecolor = (255, 255, 0)
        elif particle.vel.x < 0:
            linecolor = (0, 255, 0)
        elif particle.vel.x > 0:
            linecolor = (0, 0, 255)
        elif particle.vel.x > 0 and particle.vel.y > 0:
            linecolor = (255, 22, 22)
        elif particle.vel.x < 0 and particle.vel.y < 0:
            linecolor = (255, 22, 22)
        else:
            linecolor = (255, 255, 255)
        for block in blocks:
            if int(block.block_type) in range(1, 11):
                angle = get_angle(particle.pos, block.pos)
                distance = block.pos.distance_to(particle.pos)
                if distance < 40:
                    # pygame.draw.circle(screen, (0,255,110), block.rect.center, 3)
                    if -3 <= angle <= -2.5:
                        pygame.draw.line(screen, THECOLORS["firebrick1"], particle.rect.center, block.rect.midright)
                        DEBUGFONT.render_to(screen, block.rect.midright, f"R {angle:.1f}", DEBUGFONTCOLOR)
                    if -2.5 <= angle <= -1.5:
                        pygame.draw.line(screen, THECOLORS["skyblue1"], particle.rect.center, block.rect.midbottom)
                        DEBUGFONT.render_to(screen, block.rect.midbottom, f"B {angle:.1f}", DEBUGFONTCOLOR)
                    if -1.5 <= angle <= -0.5:
                        pygame.draw.line(screen, THECOLORS["skyblue1"], particle.rect.center, block.rect.midleft)
                        DEBUGFONT.render_to(screen, block.rect.midleft, f"L1 {angle:.1f}", DEBUGFONTCOLOR)
                    if -0.5 <= angle <= -0.0:
                        pygame.draw.line(screen, THECOLORS["skyblue1"], particle.rect.center, block.rect.midleft)
                        DEBUGFONT.render_to(screen, block.rect.midleft, f"L2 {angle:.1f}", DEBUGFONTCOLOR)
                    if 0.0 <= angle <= 0.5:
                        pygame.draw.line(screen, THECOLORS["skyblue1"], particle.rect.center, block.rect.midleft)
                        DEBUGFONT.render_to(screen, block.rect.midleft, f"L3 {angle:.1f}", DEBUGFONTCOLOR)
                    if 0.5 <= angle <= 3:
                        pygame.draw.line(screen, THECOLORS["skyblue1"], particle.rect.center, block.rect.midtop)
                        DEBUGFONT.render_to(screen, block.rect.midtop, f"T {angle:.1f}", DEBUGFONTCOLOR)
                    if 3 <= angle <= 3.5:
                        pygame.draw.line(screen, (255, 255, 225), particle.rect.center, block.rect.midright)
                        DEBUGFONT.render_to(screen, block.rect.midtop, f"R {angle:.1f}", DEBUGFONTCOLOR)


def draw_debug_block(screen=None, block=None):
    DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 14)
    outlinecolor = (255, 255, 255)
    # DEBUGFONT.render_to(screen,(block.rect.x, block.rect.y),f"{block.gridpos}",DEBUGFONTCOLOR)
    # DEBUGFONT.render_to(screen,(block.rect.x, block.rect.y+14),f"x:{block.rect.x:.0f}",DEBUGFONTCOLOR)
    # DEBUGFONT.render_to(screen,(block.rect.x, block.rect.y+14+14),f"x:{block.rect.y:.0f}",DEBUGFONTCOLOR)
    pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y), (block.pos.x + BLOCKSIZE[0], block.pos.y))
    pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y), (block.pos.x, block.pos.y + BLOCKSIZE[1]))
    pygame.draw.line(screen, outlinecolor, (block.pos.x + BLOCKSIZE[0], block.pos.y),
                     (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]))
    pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y + BLOCKSIZE[1]),
                     (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]))


def draw_debug_blocks(screen=None, blocks=None, grid=None, particles=None):
    DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 14)
    DEBUGFONTCOLOR = (33, 3, 33)
    for block in blocks:
        outlinecolor = (1, 22, 33)
        # DEBUGFONT.render_to(screen,(block.rect.x, block.rect.y),f"{block.gridpos}",DEBUGFONTCOLOR)
        # DEBUGFONT.render_to(screen,(block.rect.x, block.rect.y+14),f"x:{block.rect.x:.0f}",DEBUGFONTCOLOR)
        # DEBUGFONT.render_to(screen,(block.rect.x, block.rect.y+14+14),f"x:{block.rect.y:.0f}",DEBUGFONTCOLOR)
        # DEBUGFONT.render_to(screen,(block.rect.centerx-5, block.rect.centery),f"{block.block_type}/{grid.get_block_real(block.rect.centerx, block.rect.centery)}",DEBUGFONTCOLOR)
        pygame.draw.line(
            screen,
            outlinecolor,
            (block.pos.x, block.pos.y),
            (block.pos.x + BLOCKSIZE[0], block.pos.y),
        )
        pygame.draw.line(
            screen,
            outlinecolor,
            (block.pos.x, block.pos.y),
            (block.pos.x, block.pos.y + BLOCKSIZE[1]),
        )
        pygame.draw.line(
            screen,
            outlinecolor,
            (block.pos.x + BLOCKSIZE[0], block.pos.y),
            (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]),
        )
        pygame.draw.line(
            screen,
            outlinecolor,
            (block.pos.x, block.pos.y + BLOCKSIZE[1]),
            (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]),
        )
        for particle in particles:
            if (
                    particle.distance(block) < 55
                    and int(block.block_type) in range(1, 11)
                    and block.solid
            ):
                d2 = math.degrees(get_angle(particle.pos, block.pos))
                angle = get_angle(particle.pos, block.pos)
                angle2 = get_angle(block.pos, particle.pos)
                pygame.draw.line(
                    screen,
                    THECOLORS["skyblue1"],
                    particle.rect.center,
                    block.rect.center,
                )
                try:
                    DEBUGFONT.render_to(screen, particle.rect.center, f"{d2:.1f}", (255, 255, 0))
                except TypeError as e:
                    print(f'[E] {e}')
            # DEBUGFONT.regander_to(screen, block.rect.center, f"{angle2:.1f}",(255,0,255))

# 			else:
# 				DEBUGFONT.render_to(screen,block.rect,f"X",DEBUGFONTCOLOR)
# def draw_debug_pl
def debug_coll(screen, item1, item2):
    screen.set_at(item1.rect.center, (255, 55, 255))
    screen.set_at(item2.rect.center, (255, 255, 55))

