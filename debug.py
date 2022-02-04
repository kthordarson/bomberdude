import math
import pygame
import pygame.freetype
from pygame.color import THECOLORS
from globals import Particle
from globals import DEFAULTFONT, BLOCKSIZE
from globals import get_angle
from loguru import logger

def draw_debug_sprite(screen, sprites):
	# DEBUGFONTCOLOR = (255, 255, 255)
	# DEBUGFONT.fgcolor
	DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
	DEBUGFONTCOLOR = (123, 123, 123)
	for sprite in sprites:
		if isinstance(sprite, Particle):
			try:
				DEBUGFONT.render_to(
					screen,
					sprite.rect.center,
					f"xv:{sprite.vel.x:.0f} yv:{sprite.vel.y:.0f}",
					DEBUGFONTCOLOR,
				)
			except TypeError as e:
				logger.error(f"[DP] {e} {sprite.rect} {math.degrees(sprite.angle)}")


def draw_debug_block(screen=None, block=None):
	DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 14)
	outlinecolor = (255, 255, 255)
	pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y), (block.pos.x + BLOCKSIZE[0], block.pos.y))
	pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y), (block.pos.x, block.pos.y + BLOCKSIZE[1]))
	pygame.draw.line(screen, outlinecolor, (block.pos.x + BLOCKSIZE[0], block.pos.y), (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]))
	pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y + BLOCKSIZE[1]), (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]))

