# bomberdude
# TODO
# fix player placement
# fix restart game
# fix flames
# multiplayer

import asyncio
import os
import random
import math
import pygame

from globals import Block, Particle, Bomb, Player, Gamemap, Flame, Powerup
from globals import BLOCKSIZE, FPS, GRIDSIZE, GRIDSIZE, SCREENSIZE, DEFAULTFONT
from globals import get_angle, get_entity_angle
from globals import DEBUG
from menus import Menu
from debug import (
		draw_debug_blocks,
		draw_debug_particles,
		draw_debug_sprite,
		debug_draw_mouseangle,
		debug_draw_mouseangle,
)


def debug_coll(screen, item1, item2):
		screen.set_at(item1.rect.center, (255, 55, 255))
		screen.set_at(item2.rect.center, (255, 255, 55))


class Game:
		def __init__(self, screen=None, dt=None):
				# pygame.display.set_mode((GRIDSIZE[0] * BLOCKSIZE + BLOCKSIZE, GRIDSIZE[1] * BLOCKSIZE + panelsize), 0, 32)
				self.dt = dt
				self.screen = screen
				self.gameloop = asyncio.get_event_loop()
				self.bg_color = pygame.Color("black")
				self.show_mainmenu = True
				self.running = False
				self.show_panel = True
				self.gamemap = Gamemap()
				self.gamemap.grid = self.gamemap.generate()
				self.blocks = pygame.sprite.Group()
				self.particles = pygame.sprite.Group()
				self.players = pygame.sprite.Group()
				self.particles = pygame.sprite.Group()
				self.powerups = pygame.sprite.Group()
				self.bombs = pygame.sprite.Group()
				self.flames = pygame.sprite.Group()
				self.game_menu = Menu(self.screen)
				self.player1 = Player(pos=self.gamemap.place_player(), player_id=33, dt=self.dt)
				[self.blocks.add(Block(gridpos=(j, k), dt=self.dt, block_type=str(self.gamemap.grid[j][k])))for k in range(0, GRIDSIZE[0] + 1)for j in range(0, GRIDSIZE[1] + 1)]
				self.players.add(self.player1)
				self.font = pygame.freetype.Font(DEFAULTFONT, 12)

		def update(self):
				# todo network things
				# [player.update(self.blocks) for player in self.players]
				self.players.update(self.blocks)
				[player.move(self.blocks, dt) for player in self.players]
				self.bombs.update()
				for bomb in self.bombs:
					if bomb.explode:
						[self.flames.add(flames) for flames in bomb.flames]
				self.flames.update()
				flame_colls = pygame.sprite.groupcollide(self.blocks, self.flames, False, False)
				for block, flames in flame_colls.items():
					if int(block.block_type) in range(1, 10) and block.solid and not block.hit:
						if block.block_type == '1' or block.block_type == "2" or block.block_type == '3' or block.block_type == '4':
							powerup = Powerup(pos=block.rect.center, dt=dt)
							self.powerups.add(powerup)
							block.set_type("0")
							block.solid = False
							for flame in flames:
								if block.rect.colliderect(flame.rect):
										# if flame.rect.colliderect(block.rect):
										# pygame.draw.rect(self.screen, (0,123,33), block.rect)
										block.hit = True
										block.gen_particles(flame)
										self.particles.add(block.particles)  # for flame in flames]
										flame.kill()
				for particle in self.particles:
					blocks = pygame.sprite.spritecollide(particle, self.blocks, dokill=False)
					for block in blocks:
						if int(block.block_type) in range(1,11) and block.solid:
							particle.kill()

				self.particles.update(self.blocks)
				self.blocks.update(self.blocks)
				self.powerups.update()

		def set_block(self, x, y, value):
				self.gamemap.grid[x][y] = value

		def bombdrop(self, player):
				bombpos = pygame.math.Vector2((player.rect.centerx, player.rect.centery))
				bomb = Bomb(
						pos=bombpos, dt=self.dt, bomber_id=player.player_id, bomb_power=player.bomb_power
				)
				# print(f'[bombdrop] b:{bomb.rect} p:{player.rect} bp:{bombpos}')
				self.bombs.add(bomb)
				# player.bombs_left -= 1
				x = int(player.rect.centerx // BLOCKSIZE[0])
				y = int(player.rect.centery // BLOCKSIZE[1])
				# self.gamemap.set_block(x, y, 0)

		def draw(self):
				# draw on screen
				pygame.display.flip()
				self.screen.fill(self.bg_color)
				self.blocks.draw(self.screen)
				self.bombs.draw(self.screen)
				self.powerups.draw(self.screen)
				self.particles.draw(self.screen)
				self.players.draw(self.screen)
				for bomb in self.bombs:
						if bomb.explode:
								self.flames.draw(self.screen)
				# 		for block in self.blocks:

				if self.show_mainmenu:
						self.game_menu.draw_mainmenu(self.screen)
				self.game_menu.draw_panel(
						gamemap=self.gamemap,
						blocks=self.blocks,
						particles=self.particles,
						player1=self.player1,
				)
				if DEBUG:
						# debug_draw_mouseangle(self.screen, self.player1)
						# debug_mouse_particles(self.screen, self.particles)
						# draw_debug_sprite(self.screen, self.particles)
						draw_debug_sprite(self.screen, self.players)
						# draw_debug_sprite(self.screen, self.flames)
						#draw_debug_particles(self.screen, self.particles, self.blocks)
						# draw_debug_sprite(self.screen, self.bombs)
						#draw_debug_blocks(self.screen, self.blocks, self.gamemap, self.particles)

		def handle_menu(self, selection):
				# mainmenu
				if selection == "Quit":
						self.running = False
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
												# pygame.quit()
												# break
										else:
												self.show_mainmenu ^= True
								if event.key == pygame.K_1:
										[particle.stop() for particle in self.particles]
								if event.key == pygame.K_2:
										[particle.move() for particle in self.particles]
								if event.key == pygame.K_3:
										[particle.set_vel() for particle in self.particles]
								if event.key == pygame.K_4:
										[
												particle.set_vel(pygame.math.Vector2(1, 1))
												for particle in self.particles
										]
								if event.key == pygame.K_5:
										[particle.kill() for particle in self.particles]
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
								if (
										event.key in set([pygame.K_RIGHT, pygame.K_d])
										and not self.show_mainmenu
								):
										# if not self.show_mainmenu:
										self.player1.vel.x = self.player1.speed
								if (
										event.key in set([pygame.K_LEFT, pygame.K_a])
										and not self.show_mainmenu
								):
										# if not self.show_mainmenu:
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
								gridx = mousex // BLOCKSIZE[0]
								gridy = mousey // BLOCKSIZE[1]
								angle = get_angle(self.player1.pos, pygame.mouse.get_pos())
								angle2 = get_angle(pygame.mouse.get_pos(), self.player1.pos)
								# blockinf = self.gamemap.get_block_real(mousex, mousey)
								# print(f"mouse x:{mousex} y:{mousey} [gx:{gridx} gy:{gridy}] |  b:{self.gamemap.get_block(gridx, gridy)} a:{angle:.1f} a2:{angle2:.1f}")
								# print(f"mouse x:{mousex} y:{mousey} [x:{mousex//BLOCKSIZE[0]} y:{mousey//BLOCKSIZE[1]}]|  b:{self.gamemap.get_block(mousex // GRIDSIZE[0], mousey // GRIDSIZE[1])} ")
						if event.type == pygame.QUIT:
								self.running = False


def main_loop(game=None):
		game.running = True
		while game.running:
				# main game loop logic stuff
				game.handle_input()
				pygame.event.pump()
				game.update()
				game.draw()
		pygame.quit()


if __name__ == "__main__":
		pygame.init()
		pyscreen = pygame.display.set_mode(SCREENSIZE, 0, 32)
		game = Game(screen=pyscreen)
		mainClock = pygame.time.Clock()
		dt = mainClock.tick(FPS) / 1000
		main_loop(game=game)
