# global constants
BLOCKSIZE = 15
PLAYERSIZE = 12
BOMBSIZE = 10
GRID_X = 50
GRID_Y = 50
FPS = 30
# FONT = pg.font.SysFont('calibri', 13, True)
DEBUG = True
CHEAT = False
POWERUPS = {
    'bombpower' : 11,
    'speedup'   : 12,
    'addbomb'   : 13,
    'healthup'   : 14,
}

#def limit(num, minimum=1, maximum=255):
#    return max(min(num, maximum), minimum)

def limit(num, minimum=1, maximum=255):
    return max(min(num, maximum), minimum)

def inside_circle(R, pos_x, pos_y):
    X = int(R) # R is the radius
    for x in range(-X,X+1):
        Y = int((R*R-x*x)**0.5) # bound for y given x
        for y in range(-Y,Y+1):
            yield (x+pos_x,y+pos_y)
            

