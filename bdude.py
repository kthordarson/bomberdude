# bomberdude
# TODO
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import os
import random

import pygame

from globals import Block, Particle, BlockBomb, Player, Gamemap, Bomb_Flame
from globals import BLOCKSIZE, FPS, GRID_X, GRID_Y, SCREENSIZE
from globals import get_angle, get_entity_angle
from menus import Menu

DEBUG = True


class Game:
	def __init__(self, screen=None):
		# pygame.display.set_mode((GRID_X * BLOCKSIZE + BLOCKSIZE, GRID_Y * BLOCKSIZE + panelsize), 0, 32)
		self.screen = screen
		self.gameloop = asyncio.get_event_loop()
		self.bg_color = pygame.Color("gray12")
		self.show_mainmenu = True
		self.running = False
		self.show_panel = True
		self.gamemap = Gamemap()
		self.blocks = pygame.sprite.Group()
		self.players = pygame.sprite.Group()
		self.blocksparticles = pygame.sprite.Group()
		self.powerblocks = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.bombsflames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.player1 = Player(pos=self.gamemap.place_player(), player_id=33)

	def init(self):
		self.gamemap = Gamemap()	
		self.gamemap.generate()
		self.blocks = pygame.sprite.Group()
		self.players = pygame.sprite.Group()
		self.blocksparticles = pygame.sprite.Group()
		self.powerblocks = pygame.sprite.Group()
		self.bombs = pygame.sprite.Group()
		self.bombsflames = pygame.sprite.Group()
		self.game_menu = Menu(self.screen)
		self.player1 = Player(pos=self.gamemap.place_player(), player_id=33)
		[self.blocks.add(Block(gridpos=(k, j),block_type=str(self.gamemap.grid[j][k]))) for k in range(0, GRID_X + 1) for j in range(0, GRID_Y + 1)]
		self.players.add(self.player1)

	def update(self):
		# todo network things
		#[player.update(self.blocks) for player in self.players]
		self.players.update(self.blocks)
		self.update_bombs()
		self.update_blocks()

	def set_block(self, x, y, value):
		self.gamemap.grid[x][y] = value

	def terminate(self):
		os._exit(1)

	def bombdrop(self, player):
		bomb = BlockBomb(pos=(player.rect.centerx, player.rect.centery), bomber_id=player.player_id, bomb_power=player.bomb_power)
		flame = Bomb_Flame(rect=bomb.rect,flame_length=bomb.flame_len,vel=(-1, 0),direction="left")
		self.bombsflames.add(flame)
		flame = Bomb_Flame(rect=bomb.rect, flame_length=bomb.flame_len, vel=(1, 0), direction="right")
		self.bombsflames.add(flame)
		flame = Bomb_Flame(rect=bomb.rect, flame_length=bomb.flame_len, vel=(0, 1), direction="down")
		self.bombsflames.add(flame)
		flame = Bomb_Flame(rect=bomb.rect, flame_length=bomb.flame_len, vel=(0, -1), direction="up")
		self.bombsflames.add(flame)
		self.bombs.add(bomb)
		player.bombs_left -= 1

	def update_blocks(self):
		for block in self.blocks:
			block.update()
			block_coll = block.collide(self.players)  # for particle in block.particles
			for item in block_coll:
				if isinstance(item, Player) and block.solid:
					if item.vel.x < 0: # moving left
						item.rect.left = block.rect.right
						item.vel.x = 0
						# print(f'[coll-left] {type(item)} {type(block)} {block.solid} {block.rect}')
					elif item.vel.x > 0: # moving right
						item.rect.left = block.rect.right
						item.vel.x = 0
					elif item.vel.y > 0: # moving up
						item.rect.top = block.rect.bottom
						item.vel.y = 0
					elif item.vel.y < 0: # moving up
						item.rect.bottom = block.rect.top
						item.vel.y = 0
				elif isinstance(item, Particle) and block.solid:
					pass

						# print(f'[coll-right] {type(item)} {type(block)} {block.solid} {block.rect}')
					# print(f'{type(item)} {type(block)} {block.solid} {block.rect}')
				# if isinstance(particle, Particle) and block.solid:
				# # 	# math.degrees(get_angle(pygame.math.Vector2(4,4), pygame.math.Vector2(4,5)))
				# 	angle = get_angle(particle.rect, block.rect)
				# 	# angle = get_entity_angle(particle.rect, block.rect)
				# 	if 0 < angle < 90:
				# 		particle.vel.x = -particle.vel.x
				# 		# print('90')
				# 	if 90 < angle < 180:
				# 		particle.vel.x = -particle.vel.x
				# 	if 180 < angle < 270:
				# 		particle.vel.y = -particle.vel.y
				# 	else:
				# 		particle.vel.y = -particle.vel.y
					# particle.vel.x += random.choice([-0.5, 0.5])
					# particle.vel.y += random.choice([-0.5, 0.5])

	def update_bombs(self):
		self.bombs.update()
		self.bombsflames.update()
		for bomb in self.bombs:
			if bomb.exploding:
				for flame in self.bombsflames:
					blocks = pygame.sprite.spritecollide(
						flame, self.blocks, False)
					for block in blocks:
						if int(block.block_type) >= 1:
							# block.take_damage(self.screen,  flame)  #  = True		# block particles
							gengja = [self.blocksparticles.add(Particle(block, flame.direction)) for k in range(1, 10) if not block.hit ]
							block.hit = True
							flame.stop()
						if (int(block.block_type) >=
								3):  # block_type 1,2,3 = solid orange
							block.drop_powerblock(
							)  # make block drop the powerup
							self.player1.add_score()  # give player some score
							# self.game_data.grid[bomb.gridpos[0]][bomb.gridpos[1]] = 0

			if bomb.done:
				self.player1.bombs_left += 1  # return bomb to owner when done
				bomb.kill()

	def draw(self):
		# draw on screen
		pygame.display.flip()
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
		self.players.draw(self.screen)
		self.bombs.draw(self.screen)
		self.bombsflames.draw(self.screen)
		self.powerblocks.draw(self.screen)
		self.blocksparticles.draw(self.screen)
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu(self.screen)
		if DEBUG:
			self.game_menu.draw_debug_blocks(self.screen, self.blocks)
		# self.game_menu.draw_panel(
		# 	gamemap=self.gamemap,
		# 	blocks=self.blocks,
		# 	particles=self.blocksparticles,
		# 	player1=self.player1,
		# )

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Quit":
			self.running = False
			self.terminate()
		if selection == "Pause":
			self.show_mainmenu ^= True
		if selection == "Start":
			self.show_mainmenu ^= True
		if selection == "Restart":
			self.show_mainmenu ^= True
		if selection == "Start server":
			pass
		if selection == "Connect to server":
			pass

	def handle_input(self):
		# get player input
		for event in pygame.event.get():
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.show_mainmenu:  # or self.paused:
						selection = self.game_menu.get_selection()
						self.handle_menu(selection)
					else:
						self.bombdrop(self.player1)
				if event.key == pygame.K_ESCAPE:
					if not self.show_mainmenu:
						self.running = False
						# break
						self.terminate()
					else:
						self.show_mainmenu ^= True
				if event.key == pygame.K_c:
					self.player1.bomb_power = 100
					self.player1.max_bombs = 10
					self.player1.bombs_left = 10
					self.player1.speed = 10
				if event.key == pygame.K_p:
					self.show_panel ^= True
				if event.key == pygame.K_m:
					pass
					# self.paused ^= True
				if event.key == pygame.K_q:
					pass
					# DEBUG ^= True
				if event.key == pygame.K_g:
					pass
					# DEBUG = False
					# DEBUG_GRID ^= True
				if event.key == pygame.K_r:
					pass
					# game_init()
				if event.key in set([pygame.K_DOWN, pygame.K_s]):
					if self.show_mainmenu:
						self.game_menu.menu_down()
					else:
						self.player1.vel.y = self.player1.speed
				if event.key in set([pygame.K_UP, pygame.K_w]):
					if self.show_mainmenu:
						self.game_menu.menu_up()
					else:
						self.player1.vel.y = -self.player1.speed
				if event.key in set([pygame.K_RIGHT, pygame.K_d]):
					if not self.show_mainmenu:
						self.player1.vel.x = self.player1.speed
				if event.key in set([pygame.K_LEFT, pygame.K_a]):
					if not self.show_mainmenu:
						self.player1.vel.x = -self.player1.speed
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in set([pygame.K_DOWN, pygame.K_s]):
					if not self.show_mainmenu:
						self.player1.vel.y = 0
				if event.key in set([pygame.K_UP, pygame.K_w]):
					if not self.show_mainmenu:
						self.player1.vel.y = 0
				if event.key in set([pygame.K_RIGHT, pygame.K_d]):
					if not self.show_mainmenu:
						self.player1.vel.x = 0
				if event.key in set([pygame.K_LEFT, pygame.K_a]):
					if not self.show_mainmenu:
						self.player1.vel.x = 0
			if event.type == pygame.MOUSEBUTTONDOWN:
				mousex, mousey = pygame.mouse.get_pos()
				blockinf = self.gamemap.get_block_real(mousex, mousey)
				print(f"mouse x:{mousex} y:{mousey} |  b:{blockinf}")
			if event.type == pygame.QUIT:
				self.running = False


async def main_loop(game):
	mainClock = pygame.time.Clock()
	while True:
		# main game loop logic stuff
		dt = mainClock.tick(FPS) / 1000
		pygame.event.pump()
		game.handle_input()
		game.update()
		game.draw()

if __name__ == "__main__":
	pygame.init()
	pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)	
	game = Game(screen=pyscreen)
	game.init()
	game_task = asyncio.Task(main_loop(game))
	try:
		game.gameloop.run_until_complete(game_task)
	finally:
		pygame.quit()
