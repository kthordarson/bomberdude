import random
import numpy as np
from loguru import logger
from constants import (BLOCK,GRIDSIZE, BLOCKSIZE, BLOCKTYPES, BOMBSIZE, DEBUG, FLAMESIZE, PARTICLESIZE, POWERUPSIZE)
from globals import BlockNotFoundError
TESTGRID1 = np.array(		[
	   [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 5, 2, 2, 2, 5, 2, 5, 2, 5, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]])

TESTGRID1 = np.array(		[
	   [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 5, 2, 2, 2, 5, 2, 5, 2, 5, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]])


TESTGRID = np.array(		[
	   [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 5, 2, 2, 2, 5, 2, 5, 2, 5, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1],
       [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]])

def oldgenerate_grid():
	oneline = [0 for k in range(0, GRIDSIZE)]
	grid = np.array([oneline for k in range(0, GRIDSIZE)])
	# edges
	for k in grid:
		k[0] = 1
		k[-1] = 1
	for k in range(len(grid[0])):
		grid[0][k] = 1
		grid[-1][k] = 1
	# random blocks
	for y in range(1, len(grid)-1):
		for x in range(1, len(grid)-1):
			grid[x][y] = random.choice([2,2,2,2,2,5])
	return TESTGRID

def generate_grid():
	# types
	# 1 = edges
	# 2 = background
	# 3 = block
	# 4 = creates upgrades
	# 5 = unkillable block
	# 44 = heart
	# 40 = extrabomb
	grid = [[random.choice([2,2,2,2,2,3,4,5]) for k in range(GRIDSIZE)] for j in range(GRIDSIZE)]
	gridsize = len(grid)
	for x in range(gridsize): # set grid edges to solid blocks type 1
		grid[x][0] = 1
		grid[0][x] = 1
		grid[-1][x] = 1
		grid[x][-1] = 1
	# self.grid = grid
	return grid

class Gamemap:
	def __init__(self, genmap=False):
		self.grid = [[]]
		if genmap:
			self.grid = self.generate_custom(gridsize=10)
		self.gridsize = (len(self.grid), len(self.grid))

	def generate_custom(self, gridsize) -> dict:
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

	def placeplayer(self, grid=[], pos=(0,0)):
		#self.grid = grid
		validpos = False
		invcnt = 0
		gpx, gpy = 0,0
		while not validpos:
			# find a random spot on the map to place the player
			gpx = random.randint(1, len(grid)-1)
			gpy = random.randint(1, len(grid)-1)
			try:
				if grid[gpx][gpy].get("blktype") == 11:
					validpos = True
					logger.info(f'valid {invcnt} pos gpx:{gpx} gpy:{gpy} grid={grid[gpx][gpy]}')
					break
			except (IndexError, ValueError, AttributeError) as e:
				logger.error(f'Err: {e} {type(e)} gl={len(grid)} pos={pos} gpx={gpx} gpy={gpy} ')

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
		return False
		# cnt = 0
		# try:
		# 	for x in range(len(self.grid)):
		# 		for y in range(len(self.grid)):
		# 			if self.grid[x][y].get("blktype") in range(1,9):
		# 				cnt += 1
		# 	if cnt == 0:
		# 		return True
		# 	else:
		# 		return False
		# except TypeError as e:
		# 	logger.error(f'[map] is_empty {e} {self.grid}')

	def get_bcount(self, cval=0):
		cnt = 0
		return cnt

	def get_block(self, gridpos) -> dict[int, int]:
		blk = -1
		try:
			blk = self.grid[gridpos[0]][gridpos[1]]
		except IndexError as e:
			errmsg = f'[M] {e} gridpos:{gridpos}'
			raise BlockNotFoundError(errmsg)
		return blk
