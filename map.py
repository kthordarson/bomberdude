import random
from loguru import logger
from constants import BLOCK, BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID,DEFAULTGRID3,DEFAULTGRID4,DEFAULTGRID1,DEFAULTGRID0

def inside_circle(radius, pos_x, pos_y):
	x = round(radius)  # radius is the radius
	for x in range(-x, x + 1):
		y = round((radius * radius - x * x) ** 0.5)  # bound for y given x
		for y in range(-y, y + 1):
			yield x + pos_x, y + pos_y

class Gamemap:
	def __init__(self, genmap=False):
		self.grid = []
		if genmap:
			self.grid = self.generate_custom(gridsize=15)
		self.gridsize = (len(self.grid), len(self.grid))

	def generate(self, gridsize):
		grid = [[random.choice([1,2,3,4,5,11]) for k in range(gridsize)] for j in range(gridsize)]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(gridsize):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		self.grid = grid
		return self.grid

	def generate_custom(self, gridsize):
		# generate a custom map, gridsize is max blocks x and y
		# players = list of players, clear spot around each player
		grid = [[random.choice([1,1,2,3,4,5,11,11,11,10]) for k in range(gridsize)] for j in range(gridsize)]
		# set edges to solid blocks, 10 = solid blockwalkk
		#grid = DEFAULTGRID
		gridsize = len(grid)
		for x in range(gridsize):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		# self.grid = grid
		return grid

		# self.grid = grid
		# [f'gridpos=({k},{j}) blk={grid[k][j]}' for k in range(gridsize) for j in range(gridsize)]

	def placeplayer(self, grid=None, pos=None, randpos=True):
		#grid = DEFAULTGRID
		#self.grid = grid
		# logger.debug(f'[map] placeplayer g:{len(grid)}  pos={pos} randpos={randpos} sg={len(self.grid)}')
		if randpos:
			# find a random spot on the map to place the player
			try:
				gpx = random.randint(1, len(grid)-1)
				gpy = random.randint(1, len(grid)-1)
				nx = round(gpx * BLOCK)
				ny = round(gpy * BLOCK)
			except ValueError as e:
				logger.error(f'[map] ValueError {e} gl={len(grid)} pos={pos} randpos={randpos} grid={grid}')
				gpx = 2
				gpy = 2
				nx = round(gpx * BLOCK)
				ny = round(gpy * BLOCK)
		else:
			# gridpos from pos			
			gpx = round(pos[0] // BLOCK)
			gpy = round(pos[1] // BLOCK)
			nx = pos[0]
			ny = pos[1]
		# logger.info(f'[map] placeplayer pos={pos} x={xpos} y={ypos}')
#		if gpx == 0 or gpy == 0 or gpx == 1 or gpy == 1:
			#logger.warning(f'[map] placeplayer gpx:{gpx} gpy:{gpy} grid={grid}')
		if gpx == 0 or gpx == 1:
			gpx += 1
		if gpx == len(grid) or gpx == len(grid) -1 or gpx == len(grid) -2:
			gpx -= 1
		if gpy == len(grid) or gpy == len(grid) -1 or gpy == len(grid) -2:
			gpy -= 1
		if gpy == 0  or gpy == 1:
			gpy += 1
		# clear spot aound player
		logger.info(f'[placeplayer] pos={pos} randpos:{randpos} gpx:{gpx} gpy:{gpy} xp:{ny} yp:{ny}')
		grid[gpx][gpy] = 11
		grid[gpx-1][gpy] = 11
		grid[gpx+1][gpy] = 11
		grid[gpx][gpy-1] = 11
		grid[gpx][gpy+1] = 11
		grid[gpx-1][gpy-1] = 11
		grid[gpx+1][gpy+1] = 11
		for x in range(len(grid)):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		#self.grid = grid
		return grid, (nx, ny), (gpx, gpy)

	def is_empty(self):
		cnt = 0
		try:
			for x in range(len(self.grid)):
				for y in range(len(self.grid)):
					if self.grid[x][y] in range(1,9):
						cnt += 1
			if cnt == 0:
				return True
			else:
				return False
		except TypeError as e:
			logger.error(f'[map] is_empty {e} {self.grid}')

	def get_bcount(self, cval=0):
		cnt = 0
		return cnt

def gengrid(gridx=10, gridy=10):
	# generate a custom map, gridsize is max blocks x and y
	# grid = [[random.choice([1,2,3,4,5,11]) for k in range(gridx)] for j in range(gridy)]
	grid = [[0 for k in range(gridx)] for j in range(gridy)]
	# set edges to solid blocks, 10 = solid blockwalk, 11=walkable
	gridsize = (gridx, gridy)
	for x in range(gridsize[0]):
		grid[x][0] = 10
		grid[0][x] = 10
		grid[-1][x] = 10
		grid[x][-1] = 10
	return grid
