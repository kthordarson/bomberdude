import pygame
DEBUG = True
#DEFAULTFONT = "data/DejaVuSans.ttf"
from pygame import Color
COLOR_INACTIVE = Color('lightskyblue3')
COLOR_ACTIVE = Color('dodgerblue2')

DEBUGFONTCOLOR = (123, 123, 123)
# global constants
# GRIDSIZE[0] = 15
# GRIDSIZE[1] = 15
GRIDSIZE = (20, 20)
BLOCK = 30
BLOCKSIZE = (BLOCK, BLOCK)
PLAYERSIZE = [int(x // 1.5) for x in BLOCKSIZE]
DUMMYSIZE = [int(x // 2) for x in BLOCKSIZE]
POWERUPSIZE = [int(x // 2) for x in BLOCKSIZE]
BOMBSIZE = [int(x // 2.5) for x in BLOCKSIZE]
PARTICLESIZE = [int(x // 4) for x in BLOCKSIZE]
FLAMESIZE = [10, 10]
# FLAMESIZE = [int(x // 6) for x in BLOCKSIZE]
MAXPARTICLES = 5
# POWERUPSIZE = (12, 12)
# BOMBSIZE = (16, 16)
# FLAMESIZE = (8,8)
# FLAMELENGTH = 20
# PARTICLESIZE = (3,3)
SCREENSIZE = (BLOCKSIZE[0] * (GRIDSIZE[0] + 1), BLOCKSIZE[1] * GRIDSIZE[1] + 100)
#SCREENSIZE = (700, 700)
FPS = 30
POWERUPS = {
	"bombpower": 11,
	"speedup": 12,
	"addbomb": 13,
	"healthup": 14,
}

BLOCKTYPES = {
	0: {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "data/blackfloor.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	1: {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite5a.png",
		"bgbitmap": "data/black.png",
		"powerup": True,
	},
	2: {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite3b.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	3: {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite6.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	4: {
		"solid": True,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite3.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	5: {
		"solid": True,
		"permanent": True,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1b.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	10: {
		"solid": True,
		"permanent": True,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	11: {
		"solid": False,
		"permanent": False,
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1c.png",
		"bgbitmap": "data/blackfloor.png",
		"powerup": False,
	},
	20: {
		"solid": False,
		"permanent": False,
		"size": POWERUPSIZE,
		"bitmap": "data/heart.png",
		"bgbitmap": "data/blackfloor.png",
		"powerup": True,
	},
}

# noinspection PyPep8
DEFAULTGRID=[
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10],
	[10, 2, 5, 5, 2, 4, 3, 5, 4, 5, 2, 2, 5, 5, 0, 0, 2, 3, 3, 10],
	[10, 5, 1, 3, 4, 1, 0, 1, 5, 2, 2, 0, 5, 2, 3, 2, 0, 2, 2, 10],
	[10, 5, 0, 0, 4, 4, 0, 1, 5, 4, 2, 4, 5, 1, 2, 3, 4, 1, 2, 10],
	[10, 4, 4, 5, 0, 5, 0, 4, 5, 5, 0, 0, 5, 2, 5, 3, 0, 3, 0, 10],
	[10, 0, 5, 2, 5, 1, 5, 1, 1, 5, 0, 5, 5, 3, 1, 2, 1, 3, 3, 10],
	[10, 0, 3, 5, 3, 5, 0, 0, 0, 0, 1, 5, 5, 1, 5, 2, 1, 1, 4, 10],
	[10, 0, 4, 2, 1, 1, 0, 0, 0, 0, 0, 0, 5, 1, 3, 1, 2, 2, 0, 10],
	[10, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 3, 1, 1, 4, 10],
	[10, 0, 5, 1, 1, 1, 0, 0, 0, 0, 0, 3, 5, 0, 1, 1, 1, 1, 1, 10],
	[10, 1, 4, 3, 5, 5, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 10],
	[10, 2, 5, 3, 5, 0, 0, 0, 0, 0, 3, 3, 5, 1, 3, 5, 5, 2, 1, 10],
	[10, 4, 2, 4, 1, 5, 5, 1, 5, 0, 3, 0, 5, 2, 4, 0, 5, 2, 4, 10],
	[10, 3, 1, 3, 5, 3, 5, 0, 1, 0, 3, 4, 5, 3, 2, 2, 2, 3, 5, 10],
	[10, 4, 0, 1, 0, 4, 0, 0, 1, 0, 3, 4, 4, 0, 5, 2, 2, 0, 1, 10],
	[10, 4, 4, 2, 4, 3, 5, 5, 2, 2, 3, 5, 4, 5, 3, 2, 3, 1, 0, 10],
	[10, 0, 2, 1, 1, 2, 1, 2, 3, 2, 3, 1, 4, 0, 5, 5, 3, 4, 5, 10],
	[10, 0, 1, 5, 4, 3, 3, 5, 5, 2, 3, 3, 4, 4, 2, 4, 4, 2, 2, 10],
	[10, 3, 1, 5, 0, 3, 1, 2, 0, 2, 3, 4, 5, 5, 5, 4, 1, 5, 3, 10],
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10]]
