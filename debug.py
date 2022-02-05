import math
import pygame
import pygame.freetype
from globals import Particle
from globals import DEFAULTFONT, BLOCKSIZE
from loguru import logger
from player import DummyPlayer


def debug_dummies(screen, dummies):
	DEBUGFONT = pygame.freetype.Font(DEFAULTFONT, 10)
	DEBUGFONTCOLOR = (123, 123, 123)
	if isinstance(dummies, DummyPlayer):
		DEBUGFONT.render_to(screen, dummies.rect.center, f"xv:{dummies.pos.x:.0f} yv:{dummies.pos.y:.0f}", DEBUGFONTCOLOR, )
	else:
		for dummy in dummies:
			DEBUGFONT.render_to(screen, dummy.rect.center, f"xv:{dummy.pos.x:.0f} yv:{dummy.pos.y:.0f}", DEBUGFONTCOLOR, )


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
