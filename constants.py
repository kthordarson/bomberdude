import pygame
from pygame import Color
from pygame import USEREVENT
PKTHEADER = 64
PKTLEN = 1024*2
FORMAT = 'utf8'
DEBUG = True
DEFAULTFONT = "data/DejaVuSans.ttf"
COLOR_INACTIVE = Color('lightskyblue3')
COLOR_ACTIVE = Color('dodgerblue2')

DEBUGFONTCOLOR = (123, 123, 123)
SQUARESIZE=13
BLOCK = 32
BLOCKSIZE = (BLOCK, BLOCK)
PLAYERSIZE = [round(x // 1.3) for x in BLOCKSIZE]
NETPLAYERSIZE = [round(x // 1.4) for x in PLAYERSIZE]
DUMMYSIZE = [round(x // 2) for x in BLOCKSIZE]
POWERUPSIZE = [round(x // 2) for x in BLOCKSIZE]
BOMBSIZE = [round(x // 2.5) for x in BLOCKSIZE]
PARTICLESIZE = [round(x // 4) for x in BLOCKSIZE]
FLAMESIZE = [10, 10]
MAXPARTICLES = 5
GRIDSIZE = 20

FPS = 30
POWERUPS = {
	"bombpower": 11,
	"speedup": 12,
	"addbomb": 13,
	"healthup": 40
}

BLOCKTYPES = {
	1: {
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite5a.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
		'timer': 1,
	},
	2: {
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite3b.png",
		"bgbitmap": "data/black.png",
		"powerup": True,
		'timer': 1,
	},
	3: {
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite6.png",
		"bgbitmap": "data/black.png",
		"powerup": True,
		'timer': 1,
	},
	4: {
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite3.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
		'timer': 1,
	},
	5: {
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1b.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
		'timer': 1,
	},
	10: {
		"size": BLOCKSIZE,
		"bitmap": "data/blocksprite1.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
		'timer': 1,
	},
	11: {
		"size": BLOCKSIZE,
		"bitmap": "data/blackfloor.png",
		"bgbitmap": "data/black.png",
		"powerup": False,
		'timer': 1,
	},
	20: {
		"size": POWERUPSIZE,
		"bitmap": "data/heart.png", # bmargo
		"bgbitmap": "data/blackfloor.png",
		"powerup": False,
		'timer': 4300,
	},
	21: {
		"size": POWERUPSIZE,
		"bitmap": "data/newbomb.png",
		"bgbitmap": "data/blackfloor.png",
		"powerup": False,
		'timer': 3700,
	},
	22: {
		"size": POWERUPSIZE,
		"bitmap": "data/newbomb2.png",
		"bgbitmap": "data/blackfloor.png",
		"powerup": False,
		'timer': 4000,
	},
	30: {
		"size": POWERUPSIZE,
		"bitmap": "data/newbomb.png",
		"bgbitmap": "data/blackfloor.png",
		"powerup": False,
		'timer': 4100,
	},
}
