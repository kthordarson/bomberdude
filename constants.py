DEBUG = True
DEFAULTFONT = "data/DejaVuSans.ttf"
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
		"powerup": False,
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
		"bitmap": "data/black.png",
		"bgbitmap": "data/black.png",
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
