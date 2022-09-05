import math
import pygame
import pygame.freetype
from globals import Particle
from constants import DEFAULTFONT, BLOCKSIZE, DEBUGFONTCOLOR
from loguru import logger


def draw_debug_sprite(screen, sprites, DEBUGFONT):
	pass
	# DEBUGFONTCOLOR = (123, 123, 123)
	# for sprite in sprites:
	# 	if isinstance(sprite, Particle):
	# 		try:
	# 			DEBUGFONT.render_to(screen,sprite.rect.center,f"s:{sprite} xv:{sprite.vel.x:.0f} yv:{sprite.vel.y:.0f}",DEBUGFONTCOLOR)
	# 		except TypeError as e:
	# 			logger.error(f"[DP] {e} {sprite.rect} {math.degrees(sprite.angle)}")


def draw_debug_block(screen=None, block=None):
	pass
	# outlinecolor = (123, 255, 123)
	# pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y), (block.pos.x + BLOCKSIZE[0], block.pos.y))
	# pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y), (block.pos.x, block.pos.y + BLOCKSIZE[1]))
	# pygame.draw.line(screen, outlinecolor, (block.pos.x + BLOCKSIZE[0], block.pos.y), (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]))
	# pygame.draw.line(screen, outlinecolor, (block.pos.x, block.pos.y + BLOCKSIZE[1]), (block.pos.x + BLOCKSIZE[0], block.pos.y + BLOCKSIZE[1]))
