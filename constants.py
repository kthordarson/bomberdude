import pygame
DEBUG = True
DEFAULTFONT = "data/DejaVuSans.ttf"
from pygame import Color
COLOR_INACTIVE = Color('lightskyblue3')
COLOR_ACTIVE = Color('dodgerblue2')

DEBUGFONTCOLOR = (123, 123, 123)
SQUARESIZE=13
BLOCK = 50
BLOCKSIZE = (BLOCK, BLOCK)
PLAYERSIZE = [int(x // 1.3) for x in BLOCKSIZE]
NETPLAYERSIZE = [int(x // 1.4) for x in PLAYERSIZE]
DUMMYSIZE = [int(x // 2) for x in BLOCKSIZE]
POWERUPSIZE = [int(x // 2) for x in BLOCKSIZE]
BOMBSIZE = [int(x // 2.5) for x in BLOCKSIZE]
PARTICLESIZE = [int(x // 4) for x in BLOCKSIZE]
FLAMESIZE = [10, 10]
MAXPARTICLES = 5
#screenx = len(DEFAULTGRID) * BLOCK + 300
#screeny = len(DEFAULTGRID) * BLOCK + 100
#SCREENSIZE = (screenx, screeny)

FPS = 30
POWERUPS = {
	"bombpower": 11,
	"speedup": 12,
	"addbomb": 13,
	"healthup": 14,
}

BLOCKTYPES = {
	1: {			
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite5a.png",
		"bgbitmap": "data/black.png",
		"powerup": True,
	},
	2: {		
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite3b.png",
		"bgbitmap": "data/black.png",
		"powerup": True,
	},
	3: {		
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite6.png",
		"bgbitmap": "data/black.png",
		"powerup": True,
	},
	4: {		
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite3.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	5: {		
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1b.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	10: {		
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	11: {		
		"size": BLOCKSIZE,
		"bitmap": "data/blackfloor.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
	},
	20: {		
		"size": POWERUPSIZE,
		"bitmap": "data/heart.png",
		"bgbitmap": "data/blackfloor.png",
		"powerup": False,
	},
}


DEFAULTGRID0=[
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10],
	[10, 2, 5, 5, 2, 4, 3, 5, 4, 5, 2, 2, 5, 5, 11, 11, 2, 3, 3, 10],
	[10, 5, 1, 3, 4, 1, 11, 1, 5, 2, 2, 11, 5, 2, 3, 2, 11, 2, 2, 10],
	[10, 5, 11, 11, 4, 4, 11, 1, 5, 4, 2, 4, 5, 1, 2, 3, 4, 1, 2, 10],
	[10, 4, 4, 5, 11, 5, 11, 4, 5, 5, 11, 11, 5, 2, 5, 3, 11, 3, 11, 10],
	[10, 11, 5, 2, 5, 1, 5, 1, 1, 5, 11, 5, 5, 3, 1, 2, 1, 3, 3, 10],
	[10, 11, 3, 5, 3, 5, 11, 11, 11, 11, 9, 9, 5, 1, 5, 2, 1, 1, 4, 10],
	[10, 11, 4, 2, 1, 1, 11, 11, 11, 11, 11, 11, 5, 1, 3, 1, 2, 2, 11, 10],
	[10, 2, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 1, 11, 3, 1, 1, 4, 10],
	[10, 11, 5, 1, 1, 1, 11, 11, 11, 11, 11, 11, 11, 11, 1, 1, 1, 1, 1, 10],
	[10, 1, 4, 3, 5, 5, 11, 11, 11, 11, 11, 11, 11, 1, 1, 1, 1, 1, 1, 10],
	[10, 2, 5, 3, 5, 11, 11, 11, 11, 11, 11, 11, 11, 1, 3, 5, 5, 2, 1, 10],
	[10, 4, 2, 4, 1, 11, 11, 11, 11, 11, 11, 11, 11, 2, 4, 11, 5, 2, 4, 10],
	[10, 3, 1, 3, 5, 3, 5, 11, 11, 11, 11, 11, 11, 3, 2, 2, 2, 3, 5, 10],
	[10, 4, 11, 1, 11, 4, 11, 11, 11, 11, 3, 4, 4, 11, 5, 2, 2, 11, 1, 10],
	[10, 4, 4, 2, 4, 3, 5, 5, 2, 2, 3, 5, 4, 5, 3, 2, 3, 1, 11, 10],
	[10, 11, 2, 1, 1, 2, 1, 2, 3, 2, 3, 1, 4, 11, 5, 5, 3, 4, 5, 10],
	[10, 11, 1, 5, 4, 3, 3, 5, 5, 2, 3, 3, 4, 4, 2, 4, 4, 2, 2, 10],
	[10, 3, 1, 5, 11, 3, 1, 2, 11, 2, 3, 4, 5, 5, 5, 4, 1, 5, 3, 10],
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10]]

DEFAULTGRID1=[
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10],
	[10, 2, 5, 5, 2, 4, 3, 5, 4, 5, 2, 2, 5, 5, 11, 11, 2, 3, 3, 10],
	[10, 5, 1, 3, 4, 1, 11, 1, 5, 2, 2, 11, 5, 2, 3, 2, 11, 2, 2, 10],
	[10, 5, 11, 11, 4, 4, 11, 1, 5, 4, 2, 4, 5, 1, 2, 3, 4, 1, 2, 10],
	[10, 4, 4, 5, 11, 5, 11, 4, 5, 5, 11, 11, 5, 2, 5, 3, 11, 3, 11, 10],
	[10, 11, 5, 2, 5, 1, 5, 1, 1, 5, 11, 5, 5, 3, 1, 2, 1, 3, 3, 10],
	[10, 11, 3, 5, 3, 5, 11, 11, 11, 11, 1, 5, 5, 1, 5, 2, 1, 1, 4, 10],
	[10, 11, 4, 2, 1, 1, 11, 11, 11, 11, 11, 11, 5, 1, 3, 1, 2, 2, 11, 10],
	[10, 2, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 1, 11, 3, 1, 1, 4, 10],
	[10, 11, 5, 1, 1, 1, 11, 11, 11, 11, 11, 11, 11, 11, 1, 1, 1, 1, 1, 10],
	[10, 1, 4, 3, 5, 5, 11, 11, 11, 11, 11, 11, 1, 1, 1, 1, 1, 1, 1, 10],
	[10, 2, 5, 3, 5, 11, 11, 11, 11, 11, 11, 11, 5, 1, 3, 5, 5, 2, 1, 10],
	[10, 4, 2, 4, 1, 5, 5, 11, 11, 11, 11, 11, 5, 2, 4, 11, 5, 2, 4, 10],
	[10, 3, 1, 3, 5, 3, 5, 11, 11, 11, 11, 11, 5, 3, 2, 2, 2, 3, 5, 10],
	[10, 4, 11, 1, 11, 4, 11, 11, 11, 11, 11, 11, 4, 11, 5, 2, 2, 11, 1, 10],
	[10, 4, 4, 2, 4, 3, 5, 5, 2, 2, 3, 5, 4, 5, 3, 2, 3, 1, 11, 10],
	[10, 11, 2, 1, 1, 2, 1, 2, 3, 2, 3, 1, 4, 11, 5, 5, 3, 4, 5, 10],
	[10, 11, 1, 5, 4, 3, 3, 5, 5, 2, 3, 3, 4, 4, 2, 4, 4, 2, 2, 10],
	[10, 3, 1, 5, 11, 3, 1, 2, 11, 2, 3, 4, 5, 5, 5, 4, 1, 5, 3, 10],
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10]]

DEFAULTGRID2=[
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10],
	[10, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 10],
	[10, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 10],
	[10, 2, 3, 4, 11, 4, 11, 1, 5, 4, 2, 4, 5, 1, 11, 11, 11, 11, 2, 10],
	[10, 2, 3, 4, 11, 4, 11, 4, 5, 5, 11, 11, 5, 2, 11, 3, 11, 11, 11, 10],
	[10, 2, 3, 4, 11, 4, 5, 1, 1, 5, 11, 5, 5, 3, 11, 2, 1, 11, 3, 10],
	[10, 2, 3, 4, 11, 4, 11, 11, 11, 11, 1, 5, 5, 1, 11, 2, 1, 11, 4, 10],
	[10, 2, 2, 4, 11, 4, 11, 11, 11, 11, 11, 11, 5, 1, 11, 1, 2, 11, 11, 10],
	[10, 2, 2, 4, 11, 4, 11, 11, 11, 11, 11, 11, 11, 1, 11, 3, 1, 11, 4, 10],
	[10, 2, 2, 5, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 1, 1, 11, 1, 10],
	[10, 2, 2, 5, 11, 11, 11, 11, 11, 11, 11, 11, 1, 1, 11, 1, 1, 11, 1, 10],
	[10, 2, 2, 5, 11, 11, 11, 11, 11, 11, 11, 11, 5, 1, 11, 5, 5, 11, 1, 10],
	[10, 2, 2, 5, 11, 11, 11, 11, 11, 11, 11, 11, 5, 2, 11, 11, 5, 11, 4, 10],
	[10, 2, 1, 5, 11, 11, 11, 11, 11, 11, 11, 11, 5, 3, 11, 2, 2, 11, 5, 10],
	[10, 2, 1, 5, 11, 11, 11, 11, 11, 11, 11, 11, 4, 11, 11, 2, 2, 11, 1, 10],
	[10, 2, 1, 5, 11, 11, 5, 5, 2, 2, 3, 5, 4, 5, 11, 11, 3, 11, 11, 10],
	[10, 2, 1, 5, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 3, 11, 5, 10],
	[10, 2, 1, 5, 11, 3, 3, 5, 5, 2, 3, 3, 4, 4, 2, 11, 11, 11, 2, 10],
	[10, 2, 1, 5, 11, 3, 1, 2, 11, 2, 3, 4, 5, 5, 5, 4, 1, 5, 3, 10],
	[10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10]]

DEFAULTGRID=[
	[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 1, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[111, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]]

DEFAULTGRID3=[
	[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
	[10, 1, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[10, 1, 1, 1, 1, 1, 1, 11, 1, 1, 1, 1, 1, 1, 10],
	[10, 1, 11, 11, 11, 11, 2, 11, 5, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 2, 11, 5, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 2, 11, 5, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[10, 1, 1, 1, 1, 1, 1, 11, 1, 1, 1, 1, 1, 1, 10],
	[10, 1, 11, 11, 11, 11, 2, 11, 5, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 2, 11, 5, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 2, 11, 5, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 2, 2, 2, 2, 11, 5, 5, 5, 5, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 11, 11, 11, 11, 11, 5, 11, 11, 10],
	[10, 1, 11, 3, 3, 3, 3, 11, 11, 11, 11, 5, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 3, 1, 11, 11, 11, 5, 11, 11, 10],
	[10, 1, 11, 4, 11, 11, 3, 11, 11, 11, 11, 5, 11, 11, 10],
	[10, 1, 11, 4, 11, 11, 3, 11, 11, 11, 11, 5, 11, 11, 10],
	[10, 1, 11, 4, 4, 4, 3, 11, 11, 11, 11, 11, 11, 11, 10],
	[10, 1, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 10],
	[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]]

DEFAULTGRID4=[
	[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
 	[10, 0, 2, 2, 0, 0, 10, 0, 0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0, 10],
	[10, 0, 10, 2, 0, 0, 10, 0, 0, 10, 0, 0, 0, 10, 0, 0, 10, 0, 0, 10],
	[10, 0, 10, 2, 0, 0, 10, 0, 0, 10, 0, 0, 0, 10, 0, 0, 10, 0, 0, 10],
	[10, 0, 10, 2, 0, 0, 10, 0, 0, 10, 0, 0, 0, 10, 0, 0, 10, 0, 0, 10],
	[10, 0, 10, 2, 0, 0, 10, 0, 0, 10, 0, 0, 0, 10, 0, 0, 10, 0, 0, 10],
	[10, 0, 0, 0, 0, 0, 10, 0, 0, 10, 0, 0, 0, 10, 0, 0, 10, 0, 0, 10],
	[10, 0, 10, 10, 10, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10],
	[10, 5, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10],
	[10, 4, 10, 1, 1, 1, 1, 1, 1, 0, 0, 0, 2, 2, 0, 0, 3, 4, 0, 10],
	[10, 5, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 3, 4, 0, 10],
	[10, 4, 10, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 10],
	[10, 5, 10, 10, 10, 10, 10, 10, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10],
	[10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10],
	[10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0, 10],
	[10, 0, 0, 10, 10, 10, 10, 10, 10, 10, 10, 10, 0, 10, 0, 0, 0, 0, 0, 10],
	[10, 0, 3, 3, 3, 0, 3, 0, 3, 0, 3, 0, 0, 10, 3, 3, 0, 0, 0, 10],
	[10, 0, 0, 10, 10, 10, 10, 10, 10, 10, 10, 10, 0, 10, 0, 0, 0, 0, 0, 10],
	[10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10],
 	[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]]