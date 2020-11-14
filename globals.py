# global constants
BLOCKSIZE = 20
PLAYERSIZE = 15
GRID_X = 30
GRID_Y = 30
FPS = 30
# FONT = pg.font.SysFont('calibri', 13, True)
POWERUPS = {
	'bombpower' : 11,
	'speedup'   : 12,
	'addbomb'   : 13,
	'healthup'   : 14,
}
# block = Block(k, j, screen=self.screen, block_type=block_type, solid=False, permanent=False, block_color=pg.Color('black'))
BLOCKTYPE = {
	'block_type' : 10,
}
def limit(num, minimum=1, maximum=255):
	return max(min(num, maximum), minimum)

def inside_circle(R, pos_x, pos_y):
	X = int(R) # R is the radius
	for x in range(-X,X+1):
		Y = int((R*R-x*x)**0.5) # bound for y given x
		for y in range(-Y,Y+1):
			yield (x+pos_x,y+pos_y)
			

