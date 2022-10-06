import random
from loguru import logger
from constants import BLOCK, BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID

def inside_circle(radius, pos_x, pos_y):
	x = int(radius)  # radius is the radius
	for x in range(-x, x + 1):
		y = int((radius * radius - x * x) ** 0.5)  # bound for y given x
		for y in range(-y, y + 1):
			yield x + pos_x, y + pos_y

class Gamemap:
	def __init__(self, genmap=False):
		self.grid = []
		if genmap:
			self.grid = self.generate_custom()
		self.gridsize = (len(self.grid), len(self.grid))

	def generate(self):
		grid = [[random.choice([1,2,3,4,5,11]) for k in range(self.gridsize[1])] for j in range(self.gridsize[0])]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(self.gridsize[0]):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		self.grid = grid
		return self.grid

	def generate_custom(self, squaresize=15):
		# generate a custom map, squaresize is max blocks x and y
		# players = list of players, clear spot around each player
		self.grid = [[random.choice([1,2,3,4,5,11]) for k in range(squaresize)] for j in range(squaresize)]
		# set edges to solid blocks, 10 = solid blockwalkk
		#grid = DEFAULTGRID
		self.gridsize = len(self.grid)
		for x in range(self.gridsize):
			self.grid[x][0] = 10
			self.grid[0][x] = 10
			self.grid[-1][x] = 10
			self.grid[x][-1] = 10
		# self.grid = grid
		return self.grid

	def clear_center(self):
		x = int(self.gridsize[0] // 2)  # random.randint(2, self.gridsize[0] - 2)
		y = int(self.gridsize[1] // 2)  # random.randint(2, self.gridsize[1] - 2)
		# x = int(x)
		self.grid[x][y] = 0
		# make a clear radius around spawn point
		for block in list(inside_circle(3, x, y)):
			self.grid[block[0]][block[1]] = 0

	def placeplayer(self, grid=None, pos=None, randpos=True):
		# logger.debug(f'[map] placeplayer g:{len(grid)} {len(grid[0])} pos={pos} randpos={randpos}')
		if randpos:
			# find a random spot on the map to place the player			
			gpx = random.randint(2, len(grid[0])-2)
			gpy = random.randint(2, len(grid[0])-2)
			nx = int(gpx * BLOCK)
			ny = int(gpy * BLOCK)
		else:
			# gridpos from pos			
			gpx = int(pos[0] // BLOCK)
			gpy = int(pos[1] // BLOCK)
			nx = pos[0]
			ny = pos[1]
		# logger.info(f'[map] placeplayer pos={pos} x={xpos} y={ypos}')
		if gpx == 0 or gpy == 0:
			logger.warning(f'[map] placeplayer xpos:{gpx} ypos:{gpy} grid={grid}')
		# clear spot aound player
		self.grid[gpx][gpy] = 11
		self.grid[gpx-1][gpy] = 11
		self.grid[gpx+1][gpy] = 11
		self.grid[gpx][gpy-1] = 11
		self.grid[gpx][gpy+1] = 11
		self.grid[gpx-1][gpy-1] = 11
		self.grid[gpx+1][gpy+1] = 11
		for x in range(len(self.grid[0])):
			self.grid[x][0] = 10
			self.grid[0][x] = 10
			self.grid[-1][x] = 10
			self.grid[x][-1] = 10
		logger.info(f'[placeplayer] pos={pos} randpos:{randpos} xpos:{gpx} ypos:{gpy} xp:{ny} yp:{ny}')
		#self.grid = grid
		return self.grid, (nx, ny), (gpx, gpy)


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

