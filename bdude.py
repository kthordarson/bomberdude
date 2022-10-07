#!/bin/python3.9
# bomberdude
# 07102022 todo fix mapsync, limit one bomb per grid on map, win/mac not worky, remove killed netplayers when server sends killnpevent
import socket
import time
import random
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
from globals import Block, Powerup, Bomb
from constants import DEFAULTGRID,SQUARESIZE, BLOCK, DEBUG, DEBUGFONTCOLOR, BLOCKSIZE, PLAYERSIZE, DEFAULTFONT, NETPLAYERSIZE
from menus import Menu, DebugDialog
from player import Player
from threading import Thread, Event
import threading
from queue import Queue
from map import Gamemap


class GameGUI:
	def __init__(self, screen):
		self.screen = screen
		self.show_mainmenu = True
		self.blocks = Group()
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.game_menu = Menu(self.screen, self.font)
		self.debug_dialog = DebugDialog(self.screen, self.font)
		self.font_color = (255, 255, 255)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
	# self.debugfont = pygame.freetype.Font(DEFAULTFONT, 10)
	def draw(self):
		pass


class Game(Thread):
	def __init__(self, mainqueue=None, conn=None, sendq=None, netqueue=None):
		Thread.__init__(self, name='game')
		pygame.display.set_mode((800,600), 0, 8)
		self.gameclock = pygame.time.Clock()
		self.fps = self.gameclock.get_fps()
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.conn = conn
		self.name = 'game'
		self.mainqueue = Queue()
		self.sendq = sendq
		self.netqueue = netqueue
		self.kill = False
		self.screen = pygame.display.get_surface() #  pygame.display.set_mode(SCREENSIZE, 0, vsync=0)  # pygame.display.get_surface()#  pygame.display.set_mode(SCREENSIZE, 0, 32)
		self.bg_color = pygame.Color("black")
		self.running = False
		self.blocks = Group()
		self.players = Group()
		self.particles = Group()
		self.powerups = Group()
		self.bombs = Group()
		self.flames = Group()
		self.lostblocks = Group()
		self.playerone = Player(mainqueue=self.mainqueue)
		self.players.add(self.playerone)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.authkey = 'foobar'
		self.gotgamemapgrid = False
		self.extradebug = False
		self.screensize = (800, 600)
		self.gui = GameGUI(self.screen)

	def __str__(self):
		return f'[G] run:{self.running} p1 p1conn:{self.playerone.connected} p1clientconn:{self.playerone.client.connected} p1ready:{self.playerone.ready} p1gotmap:{self.playerone.gotmap} p1gotpos:{self.playerone.gotpos} np:{len(self.playerone.client.netplayers)} gmg:{self.gotgamemapgrid} '

	def get_block_count(self):
		# get number of killable blocks on map
		bcnt = 0
		pcnt = 0
		wcnt = 0
		ocnt = 0
		for block in self.blocks:
			if block.block_type in range(1,9) or block.block_type == 11:
				bcnt += 1
			elif block.block_type == 10:
				wcnt += 1
			elif block.block_type == 20:
				pcnt += 1
			else:
				logger.warning(f'lostblock {block}')
				ocnt += 1

		return {'bcnt': bcnt, 'pcnt': pcnt, 'wcnt': wcnt, 'ocnt': ocnt}

	def run(self):
		logger.debug(f'[ {self} ] started mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
		while True:
			if self.kill:
				logger.warning(f'[ {self} ] game kill')
				break
			if self.playerone.kill:
				logger.warning(f'[ {self} ] playerone kill {self.playerone}')
				self.kill = True
				break
			self.draw()
			self.draw_debug()
			self.handle_input()
			#self.blocks.update()
			self.playerone.update(self.blocks)
			#self.players.update(blocks=self.blocks, screen=self.screen)
			self.update_bombs()
			self.update_flames()
			self.update_particles()
			self.update_powerups(self.playerone)
			self.update_blocks()
			gamemsg = None
			if not self.mainqueue.empty():
				gamemsg = self.mainqueue.get()
			if gamemsg:
				self.handle_mainq(gamemsg)
				self.mainqueue.task_done()

			# check map grids...
			needrefresh = False
			for b in self.blocks:
				x,y = b.gridpos
				if self.playerone.client.gamemap.grid[x][y] != b.block_type:
					logger.warning(f'bcheck: mismatch {b} btype={b.block_type} != client={self.playerone.client.gamemap.grid[x][y]}')
					needrefresh = True
			if needrefresh:
				#self.playerone.client.send_refreshgrid()
				self.updategrid(self.playerone.client.gamemap.grid)


	def handle_mainq(self, gamemsg):
		msgtype = gamemsg.get('msgtype')
		if type == 'playerpos':
			logger.debug(f'[ {self} ] gamemsg={gamemsg}')
		if msgtype == 'bombdrop' or msgtype == 'netbomb':
			bomber_id = gamemsg.get('bombdata').get('client_id')
			if bomber_id == self.playerone.client_id:
				self.playerone.client.bombs_left -= 1
			bombpos = gamemsg.get('bombdata').get('bombpos')
			newbomb = Bomb(pos=bombpos, bomber_id=bomber_id)
			self.bombs.add(newbomb)
			logger.debug(f'bomb:{newbomb.pos} bl={self.playerone.client.bombs_left} b:{len(self.bombs)} mq={self.mainqueue.qsize()} sq={self.sendq.qsize()} mt:{msgtype} ')
		elif msgtype == 'newnetpos':
			posdata = gamemsg.get('posdata')
			client_id = posdata.get('client_id')
			newpos = posdata.get('newpos')
			newgridpos = posdata.get('newgridpos')
			if newgridpos[0] > 100 or newgridpos[1] > 100 or self.playerone.gridpos[0]>1000 or self.playerone.client.gridpos[1]>1000:
				logger.error(f'{self} gridpos out of range {newgridpos} pgridpos={self.playerone.gridpos} cgridpos={self.playerone.client.gridpos}')

			if client_id == self.playerone.client_id:
				logger.info(f'newnetpos np={newpos} ngp={newgridpos} posdata={posdata} ')
				self.playerone.setpos(newpos, newgridpos)
		elif msgtype == 'flames':
			flames = gamemsg.get('flamedata')
			for fl in flames:
				self.flames.add(fl)
		elif msgtype == 'particles':
			particles = gamemsg.get('particledata')
			for p in particles:
				self.particles.add(p)
		elif msgtype == 'powerup':
			logger.info(f'powerup gamemsg={gamemsg}')
			pwrup = gamemsg.get('powerupdata')
			for b in self.blocks:
				if b.gridpos == pwrup.gridpos:
					logger.warning(f'powerupdata: block already exists b={b.block_type} nb={newblock.block_type}')
					b.kill()
			self.blocks.add(pwrup)
		elif msgtype == 'newblock':
			newblock = gamemsg.get('blockdata')
			for b in self.blocks:
				if b.gridpos == newblock.gridpos:
					logger.warning(f'newblock: block already exists b={b.block_type} nb={newblock.block_type}')
					b.kill()
			if newblock.block_type == 20:
				logger.warning(f'newblock: {newblock} wrong queue ')
			else:
				self.blocks.add(newblock)
				self.playerone.client.send_gridupdate(gridpos=newblock.gridpos, blktype=newblock.block_type)
				logger.debug(f'self.blocks:{len(self.blocks)} newblk={newblock} newblock.gridpos={newblock.gridpos} newblock.block_type={newblock.block_type}')

		elif msgtype == 'poweruptimeout':
			nb = gamemsg.get('blockdata')
			x,y = nb.gridpos
			self.playerone.client.gamemap.grid[x][y] = 11
			self.blocks.add(nb)
			logger.debug(f'{msgtype} {nb}')
			#self.blocks.add(nb)

		elif msgtype == 'newpowerup':
			nb = gamemsg.get('blockdata')
			x = nb.gridpos[0]
			y = nb.gridpos[1]
			if self.playerone.client.gamemap.grid[x][y] != nb.block_type:
				logger.warning(f'{msgtype} mismatch {nb} btype={nb.block_type} != client={self.playerone.client.gamemap.grid[x][y]}')
			elif self.playerone.client.gamemap.grid[x][y] == nb.block_type:
				logger.info(f'{msgtype} {nb} btype={nb.block_type} == client={self.playerone.client.gamemap.grid[x][y]}')
				self.playerone.client.gamemap.grid[x][y] = nb.block_type
				self.blocks.add(nb)
			#logger.debug(f'{msgtype} {nb}')


		elif msgtype == 'netgridupdate':
			gridpos = gamemsg.get('blkgridpos')
			x = gridpos[0]
			y = gridpos[1]
			blktype = gamemsg.get('blktype')
			bclid = gamemsg.get('bclid')
			clientid = gamemsg.get('client_id')
			newblock = Block(pos=(gridpos[0]*BLOCK, gridpos[1]*BLOCK), gridpos=gridpos, block_type=blktype, client_id=bclid)
			if self.playerone.client_id == bclid or self.playerone.client_id == clientid:
				pass
				# logger.warning(f'netgridupdate from self {self.playerone.client_id} gamemsg={gamemsg}')
			else:
				logger.info(f'netgridupdate from netplayer b={bclid} bc={clientid} p1={self.playerone.client_id} gamemsg={gamemsg}')
			if self.playerone.client.gamemap.grid[x][y] != blktype:
				logger.warning(f'netgridupdate mismatch {self.playerone.client_id} gamemsg={gamemsg}')
			self.playerone.client.gamemap.grid[x][y] = blktype
			for b in self.blocks:
				if b.gridpos == newblock.gridpos:
					logger.warning(f'netgridupdate: block already exists b={b.block_type} nb={newblock.block_type}')
					b.kill()
			if newblock.block_type == 20:
				if DEBUG:
					pygame.draw.rect(self.screen, (255, 0, 0), newblock.rect)
			elif 1 <= newblock.block_type <= 11:
				if DEBUG:
					pygame.draw.rect(self.screen, (2, 255, 0), newblock.rect)
			self.blocks.add(newblock)
			# logger.info(f'ngu bclid={bclid} clientid={clientid} newblock={newblock} {self.playerone.client.gamemap.grid[x][y]} ')

		elif msgtype == 'gamemapgrid':
			gamemapgrid = gamemsg.get('gamemapgrid')
			newpos = gamemsg.get('newpos')
			newgridpos = gamemsg.get('newgridpos')
			if newgridpos[0] > 100 or newgridpos[1] > 100:
				logger.error(f'{self} gridpos out of range {newgridpos} pgridpos={self.playerone.gridpos} cgridpos={self.playerone.client.gridpos}')

			self.updategrid(gamemapgrid)
			if not self.playerone.gotpos:
				self.playerone.setpos(newpos, newgridpos)
			logger.debug(f'gamemapgrid np={newpos} ngp={newgridpos}')

	def updategrid(self, gamemapgrid):
		if not self.gotgamemapgrid:
			self.gotgamemapgrid = True
		else:
			pass
		newblocks = Group()
		oldlen = len(self.blocks)
		self.blocks.empty()
		idx = 0
		for k in range(0, len(gamemapgrid)):
			for j in range(0, len(gamemapgrid)):
				blktype = gamemapgrid[j][k]
				newblock = Block(Vector2(j * BLOCK, k * BLOCK), (j, k), block_type=blktype, client_id=self.playerone.client_id)
				self.blocks.add(newblock)
				idx += 1
		self.playerone.client.gamemap.grid = gamemapgrid
		logger.debug(f'gamemapgrid:{len(gamemapgrid)} blocks:{len(self.blocks)} oldlen:{oldlen} idx:{idx}')

	def update_blocks(self):
		for b in self.blocks:
			if b.block_type == 20:
				# if block is powerup, check timer
				dt = pygame.time.get_ticks()
				if dt - b.start_time >= b.timer:
					nx = b.gridpos[0] * BLOCK
					ny = b.gridpos[1] * BLOCK
					nb = Block((nx,ny), b.gridpos, block_type=11, client_id=b.client_id)
					b.kill()
					blockmsg = {'msgtype': 'poweruptimeout', 'blockdata': nb}
					self.mainqueue.put(blockmsg)

	def update_bombs(self):
		self.bombs.update()
		for bomb in self.bombs:
			dt = pygame.time.get_ticks()
			if dt - bomb.start_time >= bomb.timer:
				if bomb.bomber_id == self.playerone.client_id:
					self.playerone.client.bombs_left += 1
				flames = bomb.exploder()
				flamemsg = {'msgtype': 'flames', 'flamedata': flames}
				self.mainqueue.put(flamemsg)
				bomb.kill()

	def update_flames(self):
		self.flames.update(surface=self.screen)
		for flame in self.flames:
			# check if flame collides with blocks
			for block in spritecollide(flame, self.blocks, False):
				if pygame.Rect.colliderect(flame.rect, block.rect):
					if block.block_type == 10:
						# kill flame on wallhit
						flame.kill()
					elif block.block_type == 11:
						# flames cann pass type 11
						pass
					elif 1 <= block.block_type < 10:
						# flames kills self and block
						if flame.client_id == self.playerone.client_id:
							# add player score if flame from bomb was by playerone
							self.playerone.add_score()
						# block hits return particles and a new block
						particles, newblock = block.hit(flame)
						particlemsg = {'msgtype': 'particles', 'particledata': particles}
						self.mainqueue.put(particlemsg)
						if newblock.block_type == 20:
							blockmsg = {'msgtype': 'newpowerup', 'blockdata': newblock}
							self.mainqueue.put(blockmsg)
						else:
							blockmsg = {'msgtype': 'newblock', 'blockdata': newblock}
							self.mainqueue.put(blockmsg)
						flame.kill()
						block.kill()
						x,y = newblock.gridpos
						self.playerone.client.gamemap.grid[x][y] = newblock.block_type
					elif block.block_type == 20:
						# flame kills self and powerup
						x = block.gridpos[0]
						y = block.gridpos[1]
						self.playerone.client.gamemap.grid[x][y] = 11
						flame.kill()
						block.kill()

	def update_particles(self):
		self.particles.update(self.blocks, self.screen)

	def update_powerups(self, playerone):
		for p in self.powerups:
			if pygame.time.get_ticks() - p.start_time >= p.timer:
				logger.info(f'powerup={p} timeout')
				p.kill()


	def draw(self):
		# draw on screen
		if pygame.display.get_init():
			try:
				pygame.display.update()
			except pygame.error as e:
				logger.error(f'[ {self} ] err:{e} getinit:{pygame.display.get_init()}')
				pygame.display.set_mode(self.screensize, 0, 8)
				self.screen = pygame.display.get_surface()
				return
		self.gameclock.tick(30)
		#self.blocks.draw(self.screen)
		#if self.playerone.ready:
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
		self.particles.draw(self.screen)
		self.bombs.draw(self.screen)
		self.flames.draw(self.screen)
		self.powerups.draw(self.screen)
		if self.playerone.client.gotpos and self.playerone.ready:
			self.players.draw(self.screen)
		#self.playerone.draw(self.screen)
		for npid in self.playerone.client.netplayers:
			if npid == 0 or npid == '0':
				pass
				#logger.warning(f'npid:{npid} {self.playerone.client.netplayers[npid]}')
			else:
				npitem = self.playerone.client.netplayers[npid]
				np = f'{npitem["gridpos"]}'
				x,y = self.playerone.client.netplayers[npid].get('pos', None)
				pos = [x,y]
				gpos = self.playerone.client.netplayers[npid].get('gridpos', None)
				if gpos[0] > 100 or gpos[1] > 100:
					pass
					#logger.error(f'{self} gridpos out of range np={np} g={gpos} p={pos} netplayer={npitem} ')
				if self.playerone.client_id != npid:
					#pos -= (0,5)
					#pos[1] -=10
					self.font.render_to(self.screen, pos, f'{np}', (255, 255, 255))
					pos[0] += 20
					pos[1] += 20
					pygame.draw.circle(self.screen, color=(1,0,255), center=pos, radius=10)
					#pos = self.playerone.client.netplayers[npid].get('pos')
					#self.font.render_to(self.screen, pos, f'{np}', (255, 55, 55))
				if npid == self.playerone.client_id:
					#pos += (5,20)
					pass
					#self.font.render_to(self.screen, pos , f'{np}', (123, 123, 255))

		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
		self.gui.game_menu.draw_panel(screen=self.screen, blocks=self.blocks, particles=self.particles, playerone=self.playerone, flames=self.flames, grid=self.playerone.client.gamemap.grid)
		self.fps = self.gameclock.get_fps()

	def draw_debug(self):
		if DEBUG:
			pos = Vector2(10, self.screenh - 100)
			self.font.render_to(self.screen, pos, f"blklen:{len(self.blocks)} pups:{len(self.powerups)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)} bcounts:{self.get_block_count()} ", (173, 173, 173))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"fps={self.fps} threads:{threading.active_count()} mainq:{self.mainqueue.qsize()} sendq:{self.sendq.qsize()} netq:{self.netqueue.qsize()} p1 np:{len(self.playerone.client.netplayers)}", (183, 183, 183))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"p1 pos {self.playerone.pos} {self.playerone.gridpos} cpos {self.playerone.client.pos} {self.playerone.client.gridpos}", (183, 183, 183))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"client {self.playerone.client}", (183, 183, 183))
		if self.extradebug:
			for b in self.blocks:
				gx, gy = b.gridpos
				plg1item = self.playerone.client.gamemap.grid[gx][gy]
				textpos = [b.rect.topleft[0]+3, b.rect.topleft[1]]
				if b.block_type != plg1item:
					fcol1 = (255,0,0)
					fcol2 = (255,1,255)
					pygame.draw.rect(self.screen, color=(255,0,0), rect=b.rect, width=1)
					self.font.render_to(self.screen, (textpos[0]+5, textpos[1]+25), f"{plg1item}", fcol2)
					self.font.render_to(self.screen, b.pos, f"{b.block_type}", (255, 255, 255))

					#self.font.render_to(self.screen, b.pos, f"{b.block_type}", (183, 183, 183))
				elif b.block_type == 20:
					#
					#pygame.draw.rect(self.screen, color=(255,0,0), rect=b.rect, width=1)
					#self.font.render_to(self.screen, b.pos, f"{b.block_type} {b.gridpos} {b.pos}", (183, 18, 183))
					pass
				else:
					self.font.render_to(self .screen, (textpos[0]+12, textpos[1]+12), f"{b.block_type}", (255, 1, 255))
					#self.font.render_to(self.screen, (textpos[0], textpos[1]+15), f"{selfgitem} {plg1item}", (55, 211, 123))
					#self.font.render_to(self.screen, b.pos, f"{b.block_type}", (183, 23, 23))

					#textpos[0] -= 5
					#textpos[1] -= 10
					#self.font.render_to(self.screen, textpos, f"b {b.block_type}", (183, 255, 183))
					#textpos += (15, 15)
						#self.font.render_to(self.screen, (textpos[0], textpos[1]+25), f"b {plg1item} ", (183, 211, 183))
					#textpos += (5, 5)
					#self.font.render_to(self.screen, textpos, f"p={plg1item} ", (0, 183, 183))

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			# self.playerone.run()
			#self.gui.show_mainmenu ^= True
			if self.playerone.client.connect_to_server():
				self.playerone.connected = True
				self.playerone.start_client()
				mapreqcnt = 0
				while not self.playerone.client.gotmap and not self.playerone.client.gotpos:
					self.playerone.client.send_mapreq()
					mapreqcnt += 1
					logger.debug(f'playeone={self.playerone} waiting for map mapreqcnt:{mapreqcnt} cgotmap={self.playerone.client.gotmap} cgotpos={self.playerone.client.gotpos}')
					time.sleep(1)
					if mapreqcnt >= 5:
						logger.warning(f'mapreqcnt:{mapreqcnt}  pc:{self.playerone.connected} pcc:{self.playerone.client.connected} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
						self.playerone.connected = False
						self.playerone.client.connected = False
						self.playerone.client.socket.close()
						self.playerone.client.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						self.playerone.ready = False
						self.gui.show_mainmenu = True
						break
				self.gui.show_mainmenu ^= True
			else:
				logger.warning(f'p1 not connected  pc:{self.playerone.connected} pcc:{self.playerone.client.connected} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
				self.gui.show_mainmenu ^= True

		if selection == "Connect to server":
			pass

		if selection == "Quit":
			self.running = False

		if selection == "Pause":
			self.gui.show_mainmenu ^= True
			# self.pause_game()

		if selection == "Restart":
			self.gui.show_mainmenu ^= True
			# self.restart_game()

		if selection == "Start server":
			pass
			#self.gameserver.run()
			#self.is_server = True

	def handle_input(self):
		events = pygame.event.get()
		for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.gui.show_mainmenu:  # or self.paused:
						selection = self.gui.game_menu.get_selection()
						self.handle_menu(selection)
					elif not self.gui.show_mainmenu:
						#bombmsg = {'msgtype': 'bombdrop', 'client_id': self.playerone.client_id, 'bombpos': self.playerone.pos}
						#self.mainqueue.put_nowait(bombmsg)
						if self.playerone.client.bombs_left >= 0:
							self.playerone.client.send_bomb(pos=self.playerone.rect.center)
						else:
							logger.warning(f'no bombs left {self.playerone.client.bombs_left}')
				if event.key == pygame.K_ESCAPE:
					self.gui.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.playerone.client.disconnect()
					self.kill = True
					self.running = False
				if event.key == pygame.K_1:
					self.playerone.client.send_mapreq()
				if event.key == pygame.K_2:
					self.playerone.client.req_mapreset()
				if event.key == pygame.K_3:
					self.playerone.client.send_bomb(pos=self.playerone.rect.center)
				if event.key == pygame.K_4:
					self.extradebug ^= True
				if event.key == pygame.K_5:
					self.playerone.client.send_refreshgrid()
				if event.key == pygame.K_f:
					pass
				if event.key == pygame.K_p:
					print('client netplayers:')
					for np in self.playerone.client.netplayers:
						print(f'\t{np} {self.playerone.client.netplayers[np]}')
					# for tempg in tempgrids:
					# 	for tx in range(len(tempg)):
					# 		if len(tempg[tx]) != len(tempg):
					# 			logger.error(f'grid1 x={tx} len={len(tx)}')
				if event.key == pygame.K_m:
					print(f'pl={self.playerone.client.gamemap.grid}')
					if len(self.lostblocks) > 0:
						print(f'lostblocks {len(self.lostblocks)}: ')
						for b in self.lostblocks:
							print(f'\tlostblock: {b}')
					if len(self.powerups) > 0:
						for b in self.powerups:
							print(f'\power {len(self.powerups)}: {b}')
				if event.key == pygame.K_n:
					pass
				if event.key == pygame.K_g:
					pass
				if event.key == pygame.K_r:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s}:
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_down()
					else:
						try:
							self.playerone.move("down")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone.client}')
						#self.playerone.vel.y = self.playerone.speed
						#self.playerone.vel.x = 0
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_up()
					else:
						try:
							self.playerone.move("up")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone.client}')
						#self.playerone.vel.y = -self.playerone.speed
						#self.playerone.vel.x = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					if not self.gui.show_mainmenu:
						try:
							self.playerone.move("right")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone.client}')
						#self.playerone.vel.x = self.playerone.speed
						#self.playerone.vel.y = 0
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					if not self.gui.show_mainmenu:
						try:
							self.playerone.move("left")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone.client}')
						#self.playerone.vel.x = -self.playerone.speed
						#self.playerone.vel.y = 0
			if event.type == pygame.KEYUP:
				if event.key == pygame.K_a:
					pass
				if event.key == pygame.K_d:
					pass
				if event.key in {pygame.K_DOWN, pygame.K_s}:
					self.playerone.vel.y = 0
				if event.key in {pygame.K_UP, pygame.K_w}:
					self.playerone.vel.y = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					self.playerone.vel.x = 0
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					self.playerone.vel.x = 0
			if event.type == pygame.MOUSEBUTTONDOWN:
				mx, my = pygame.mouse.get_pos()
				logger.info(f'mouse click at {mx}, {my}')
			if event.type == pygame.QUIT:
				logger.warning(f'[ {self} ] quit {event.type}')
				self.running = False



if __name__ == "__main__":
	pygame.init()
	pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])

	#pygame.display.set_mode((800,600), 0, 8)
	mainqueue = Queue()
	netqueue = Queue()
	sendq = Queue()
	stop_event = Event()
	#mainqueue = OldQueue()#  multiprocessing.Manager().Queue()
	# engine = Engine(stop_event=stop_event, name='engine')
	game = Game(mainqueue=mainqueue, sendq=sendq, netqueue=netqueue)
	game.daemon = True
	game.start()
	game.running = True
	while game.running:
		if game.kill:
			game.running = False
			break
		try:
			t1 = time.time()
		except KeyboardInterrupt as e:
			logger.warning(f'[kb] {e}')
			# game.kill_engine(killmsg=f'killed by {e}')
			break
	pygame.quit()


