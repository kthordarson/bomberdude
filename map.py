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

	def generate_custom(self, squaresize):
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

	def placeplayer(self, grid):
		# find a random spot on the map to place the player
		xpos = random.randint(2, len(grid[0])-2)
		ypos = random.randint(2, len(grid[1])-2)
		# clear spot aound player
		grid[xpos][ypos] = 0
		grid[xpos-1][ypos] = 0
		grid[xpos+1][ypos] = 0
		grid[xpos][ypos-1] = 0
		grid[xpos][ypos+1] = 0
		grid[xpos-1][ypos-1] = 0
		grid[xpos+1][ypos+1] = 0
		xp = xpos * BLOCK
		yp = ypos * BLOCK
		for x in range(len(grid[0])):
			grid[x][0] = 10
			grid[0][x] = 10
			grid[-1][x] = 10
			grid[x][-1] = 10
		logger.debug(f'[placeplayer] xpos:{xpos} ypos:{ypos} xp:{xp} yp:{yp}')
		self.grid = grid
		return grid, xp, yp

	def place_player(self, grid, location=0):
		# place player somewhere where there is no block
		# returns the (x,y) coordinate where player is to be placed
		# random starting point from gridgamemap
		if len(grid) == 0:
			logger.error(f'[place_player] grid is empty')
			return None
		if location == 0:  # center pos
			x = int(self.gridsize[0] // 2)  # random.randint(2, self.gridsize[0] - 2)
			y = int(self.gridsize[1] // 2)  # random.randint(2, self.gridsize[1] - 2)
			# x = int(x)
			try:
				grid[x][y] = 0
			except IndexError as e:
				logger.error(f'IndexError {e} x:{x} y:{y} gz:{self.gridsize} g:{type(grid)} {len(grid)}')
				return None
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.error(f"[e] place_player {block} {e}")
					return None
			return grid
		# return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))
		if location == 1:  # top left
			x = 5
			y = 5
			# x = int(x)
			grid[x][y] = 0
			# make a clear radius around spawn point
			for block in list(inside_circle(3, x, y)):
				try:
					# if self.grid[clear_bl[0]][clear_bl[1]] > 1:
					grid[block[0]][block[1]] = 0
				except Exception as e:
					logger.error(f"[e] place_player {block} {e}")
					return None
			return grid

	# return Vector2((x * BLOCKSIZE[0], y * BLOCKSIZE[1]))

	def get_block(self, x, y):
		# get block inf from grid
		try:
			value = self.grid[x][y]
		except IndexError as e:
			logger.error(f"[get_block] {e} x:{x} y:{y}")
			return -1
		return value

	def is_empty(self):
		cnt = 0
		for row in self.grid:
			for item in row:
				if item in range(1,9):
					cnt += 1
		if cnt == 0:
			return True
		else:
			return False

	def get_bcount(self, cval=0):
		cnt = 0
		for row in self.grid:
			for item in row:
				if item == cval:
					cnt += 1
		return cnt

	def get_block_real(self, x, y):
		x = x // BLOCKSIZE[0]
		y = y // BLOCKSIZE[1]
		try:
			value = self.grid[x][y]
		except IndexError as e:
			logger.error(f"[get_block] {e} x:{x} y:{y}")
			return -1
		return value

	def set_block(self, x, y, value):
		self.grid[x][y] = value

	def set_grid(self, newgrid):
		logger.debug(f'[map] setting newgrid')
		self.grid = newgrid
