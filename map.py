import random
from loguru import logger
from constants import BLOCK, BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, BOMBSIZE, BLOCKSIZE, DEFAULTGRID, DEFAULTGRID2, DEFAULTGRID15

def inside_circle(radius, pos_x, pos_y):
	x = int(radius)  # radius is the radius
	for x in range(-x, x + 1):
		y = int((radius * radius - x * x) ** 0.5)  # bound for y given x
		for y in range(-y, y + 1):
			yield x + pos_x, y + pos_y

class Gamemap:
	def __init__(self, genmap=True):
		self.grid = DEFAULTGRID15
		self.gridsize = (len(self.grid[0]), len(self.grid[0]))

	def generate(self):
		grid = [[random.randint(0, 5) for k in range(self.gridsize[1])] for j in range(self.gridsize[0])]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(self.gridsize[0]):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		self.grid = grid
		return self.grid

	def generate_custom(self, squaresize=None):
		# generate a custom map, squaresize is max blocks x and y
		# players = list of players, clear spot around each player
		grid = [[random.randint(0, 5) for k in range(squaresize)] for j in range(squaresize)]
		# set edges to solid blocks, 10 = solid blockwalkk
		for x in range(squaresize):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		self.grid = grid
		return grid

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
			xpos = random.randint(2, len(grid[0])-2)
			ypos = random.randint(2, len(grid[0])-2)
		else:
			# clear spot around player
			xpos = int(pos[0] // BLOCK)
			ypos = int(pos[1] // BLOCK)
		# logger.info(f'[map] placeplayer pos={pos} x={xpos} y={ypos}')
		xp = xpos * BLOCK
		yp = ypos * BLOCK
		if xpos == 0 or ypos == 0:
			logger.warning(f'[map] placeplayer xpos:{xpos} ypos:{ypos} grid={grid}')
		# clear spot aound player
		try:
			grid[xpos][ypos] = 0
			grid[xpos-1][ypos] = 0
			grid[xpos+1][ypos] = 0
			grid[xpos][ypos-1] = 0
			grid[xpos][ypos+1] = 0
			grid[xpos-1][ypos-1] = 0
			grid[xpos+1][ypos+1] = 0
			for x in range(len(grid[0])):
				grid[x][0] = 10
				grid[0][x] = 10
				grid[-1][x] = 10
				grid[x][-1] = 10
		except IndexError as e:
			logger.warning(f'[map] placeplayer IndexError {e} pos={pos} xp:{xp} yp:{yp} xpos:{xpos} ypos:{ypos} grid={grid}')
		logger.info(f'[placeplayer] pos={pos} randpos:{randpos} xpos:{xpos} ypos:{ypos} xp:{xp} yp:{yp}')
		self.grid = grid
		return grid, (xp, yp)


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
		for row in self.grid:
			for item in row:
				if item == cval:
					cnt += 1
		return cnt

