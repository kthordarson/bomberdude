import random
from loguru import logger
from constants import BLOCK, BLOCKTYPES, DEBUG, POWERUPSIZE, PARTICLESIZE, FLAMESIZE, BOMBSIZE, BLOCKSIZE

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
			self.grid = self.generate_custom(gridsize=10)
		self.gridsize = (len(self.grid), len(self.grid))

	def generate_custom(self, gridsize):
		# generate a custom map, gridsize is max blocks x and y
		# players = list of players, clear spot around each player
		# grid = [[random.choice([1,1,2,3,4,5,11,11,11,10]) for k in range(gridsize)] for j in range(gridsize)]
		grid = [[{'blktype':random.choice([1,2,3,4,5,11]), 'bomb':False} for k in range(gridsize)] for j in range(gridsize)]
		# set edges to solid blocks, 10 = solid blockwalkk
		gridsize = len(grid)
		for x in range(gridsize):
			grid[x][0] = {'blktype':10, 'bomb':False}
			grid[0][x] = {'blktype':10, 'bomb':False}
			grid[-1][x] = {'blktype':10, 'bomb':False}
			grid[x][-1] = {'blktype':10, 'bomb':False}
		# self.grid = grid
		return grid

		# self.grid = grid
		# [f'gridpos=({k},{j}) blk={grid[k][j]}' for k in range(gridsize) for j in range(gridsize)]

	def placeplayer(self, grid=None, pos=None, randpos=True):
		#self.grid = grid
		# logger.debug(f'[map] placeplayer g:{len(grid)}  pos={pos} randpos={randpos} sg={len(self.grid)}')
		validpos = False
		invcnt = 0
		while not validpos:
			# find a random spot on the map to place the player
			gpx = random.randint(1, len(grid)-1)
			gpy = random.randint(1, len(grid)-1)
			try:
				if grid[gpx][gpy].get("blktype") == 11:
					validpos = True
					logger.info(f'valid {invcnt} pos gpx:{gpx} gpy:{gpy} grid={grid[gpx][gpy]}')
					break
			except (IndexError, ValueError) as e:
				logger.error(f'Err: {e} gl={len(grid)} pos={pos} gpx={gpx} gpy={gpy} ')

		# clear spot aound player
		nx = int(gpx * BLOCK)
		ny = int(gpy * BLOCK)
		logger.info(f'[placeplayer] pos={pos} gpx:{gpx} gpy:{gpy} xp:{ny} yp:{ny}')
		grid[gpx][gpy] = {'blktype':11, 'bomb':False}
		grid[gpx-1][gpy] = {'blktype':11, 'bomb':False}
		grid[gpx+1][gpy] = {'blktype':11, 'bomb':False}
		grid[gpx][gpy-1] = {'blktype':11, 'bomb':False}
		grid[gpx][gpy+1] = {'blktype':11, 'bomb':False}
		grid[gpx-1][gpy-1] = {'blktype':11, 'bomb':False}
		grid[gpx+1][gpy+1] = {'blktype':11, 'bomb':False}
		for x in range(len(grid)):
			grid[x][0] = {'blktype':10, 'bomb':False}
			grid[0][x] = {'blktype':10, 'bomb':False}
			grid[-1][x] = {'blktype':10, 'bomb':False}
			grid[x][-1] = {'blktype':10, 'bomb':False}
		#self.grid = grid
		return grid, (nx, ny), (gpx, gpy)

	def is_empty(self):
		cnt = 0
		try:
			for x in range(len(self.grid)):
				for y in range(len(self.grid)):
					if self.grid[x][y].get("blktype") in range(1,9):
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
	
	def get_block(self, gridpos):
		return self.grid[gridpos[0]][gridpos[1]]
