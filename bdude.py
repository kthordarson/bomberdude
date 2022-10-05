#!/bin/python3.9
# bomberdude
import socket
import time
import random
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
from globals import Block, Powerup, Bomb
from constants import BLOCK, DEBUG, DEBUGFONTCOLOR, BLOCKSIZE, PLAYERSIZE, SCREENSIZE ,DEFAULTFONT, NETPLAYERSIZE
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
		self.gameclock = pygame.time.Clock()
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.conn = conn
		self.name = 'game'
		self.mainqueue = Queue()
		self.sendq = sendq
		self.netqueue = netqueue
		self.kill = False
		self.screen = pygame.display.get_surface() #  pygame.display.set_mode(SCREENSIZE, 0, vsync=0)  # pygame.display.get_surface()#  pygame.display.set_mode(SCREENSIZE, 0, 32)
		self.gui = GameGUI(self.screen)
		self.bg_color = pygame.Color("black")
		self.running = False
		self.blocks = Group()
		self.players = Group()
		self.netplayers = Group()
		self.particles = Group()
		self.powerups = Group()
		self.bombs = Group()
		self.flames = Group()
		self.playerone = Player(mainqueue=self.mainqueue)
		self.players.add(self.playerone)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.authkey = 'foobar'
		self.netplayers = {}
		self.gamemapgrid = []
		self.gotgamemapgrid = False

	def __str__(self):
		return f'[G] run:{self.running} p1 p1conn:{self.playerone.connected} p1clientconn:{self.playerone.client.connected} p1ready:{self.playerone.ready} p1gotmap:{self.playerone.gotmap} p1gotpos:{self.playerone.gotpos} np:{len(self.netplayers)} gmg:{self.gotgamemapgrid} gg={len(self.gamemapgrid)}'

	def get_block_count(self):
		# get number of killable blocks on map
		cnt = 0
		for block in self.blocks:
			if block.block_type in range(1,9):
				cnt += 1
		return cnt

	def run(self):
		logger.debug(f'[ {self} ] started mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
		while True:
			# logger.debug(f'[ {self} ] {self}  mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
			if self.kill:
				logger.warning(f'[ {self} ] game kill')
				break
			if self.playerone.kill:
				logger.warning(f'[ {self} ] playerone kill {self.playerone}')
				self.kill = True
				break
			self.draw()
			self.handle_input()
			self.playerone.update(self.blocks)
			#self.players.update(blocks=self.blocks, screen=self.screen)
			self.update_bombs()
			self.update_flames()
			self.update_particles()
			self.update_powerups(self.playerone)
			gamemsg = None
			if not self.mainqueue.empty():
				gamemsg = self.mainqueue.get()
			if gamemsg:
				self.handle_mainq(gamemsg)
				self.mainqueue.task_done()


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
			logger.debug(f'[ {self} ] bombs:{len(self.bombs)} {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{msgtype} engmsg:{len(gamemsg)} bomb:{newbomb.pos}')
		elif msgtype == 'newnetpos':
			posdata = gamemsg.get('posdata')
			client_id = posdata.get('client_id')
			newpos = posdata.get('newpos')
			newgridpos = posdata.get('newgridpos')
			if client_id == self.playerone.client_id:
				logger.info(f'[ {self} ] newnetpos posdata={posdata} np={newpos} ngp={newgridpos}')
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
			pwrup = gamemsg.get('powerupdata')
			self.powerups.add(pwrup)
		elif msgtype == 'newblock':
			blk = gamemsg.get('blockdata')
			self.blocks.add(blk)
			# if not blk.block_type:
			# 	logger.error(f'self.blocks:{len(self.blocks)} newblk={blk} missing blktype')
			# 	blk.block_type = 0
			self.gamemapgrid[blk.gridpos[0]][blk.gridpos[1]] = blk.block_type
			self.playerone.client.send_gridupdate(gridpos=blk.gridpos, blktype=blk.block_type, grid_data=self.gamemapgrid)
			logger.debug(f'self.blocks:{len(self.blocks)} newblk={blk} ')
		elif msgtype == 'netgridupdate':
			gridpos = gamemsg.get('gridpos')
			blktype = gamemsg.get('blktype')
			self.gamemapgrid[gridpos[0]][gridpos[1]] = blktype
			logger.debug(f'[ {self} ] netgridupdate {gridpos} {blktype}')
		elif msgtype == 'gamemapgrid':
			gamemapgrid = gamemsg.get('gamemapgrid')
			newpos = gamemsg.get('newpos')
			newgridpos = gamemsg.get('newgridpos')
			self.updategrid(gamemapgrid)
			if not self.playerone.gotpos:
				self.playerone.setpos(newpos, newgridpos)
			logger.debug(f'gamemapgrid np={newpos} ngp={newgridpos}')

	def updategrid(self, gamemapgrid):
		if not gamemapgrid:
			logger.warning(f'[ {self} ] updategrid got empty gamemapgrid')
			return
		self.gamemapgrid = gamemapgrid
		self.gotgamemapgrid = True
		newblocks = Group()
		self.blocks.empty()
		for k in range(0, len(gamemapgrid)):
			for j in range(0, len(gamemapgrid)):
				if not gamemapgrid[j][k]:
					blktype = 0
					#logger.warning(f'[ {self} ] k={k} j={j} grid={gamemapgrid} selfgrid={self.gamemapgrid} blktype={blktype}')
				else:
					blktype = gamemapgrid[j][k]
				try:					
					newblock = Block(Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), (j, k), block_type=blktype)
				except TypeError as e:
					logger.error(f'[ {self} ] err:{e} k={k} j={j} grid={gamemapgrid} selfgrid={self.gamemapgrid} blktype={blktype}')
					newblock = Block(Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), (j, k), block_type=0)
				self.blocks.add(newblock)				
		logger.debug(f'mainq={self.mainqueue.qsize()} sendq={self.sendq.qsize()} gamemapgrid:{len(gamemapgrid)}')

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
				if pygame.Rect.colliderect(flame.rect, block.rect) and block.block_type != 0:
					if DEBUG:
						if block.block_type >= 10:
							pygame.draw.rect(self.screen, (215,215,215), rect=block.rect, width=1)
						elif block.block_type == 0:
							pygame.draw.rect(self.screen, (95,95,95), rect=block.rect, width=1)
						else:
							pygame.draw.rect(self.screen, (115,115,115), rect=block.rect, width=1)
					if 1 < block.block_type < 10:
						if flame.client_id == self.playerone.client_id:
							self.playerone.add_score()
						particles, newblock = block.hit(flame)
						particlemsg = {'msgtype': 'particles', 'particledata': particles}
						self.mainqueue.put(particlemsg)
						#self.particles.add(particles)
						blockmsg = {'msgtype': 'newblock', 'blockdata': newblock}
						self.mainqueue.put(blockmsg)
						block.kill()
						flame.kill()
					if block.block_type >= 10:
						flame.kill()
					if block.block_type == 0:
						pass
							# self.blocks.add(newblock)

	def update_particles(self):
		self.particles.update(self.blocks, self.screen)
		# for particle in self.particles:
		# 	blocks = spritecollide(particle, self.blocks, dokill=False)
		# 	for block in blocks:
		# 		pass
				# if block.block_type != 0 and pygame.Rect.colliderect(particle.rect, block.rect):
				# 	if DEBUG:
				# 		#pygame.draw.circle(self.screen, (111,111,111), particle.rect.center, 2)
				# 		pygame.draw.rect(self.screen, (85,85,85), rect=block.rect, width=1)
				# 	particle.hit(block)

	def update_powerups(self, playerone):
		self.powerups.update()
		if len(self.powerups) > 0:
			powerblock_coll = spritecollide(playerone, self.powerups, False)
			for pc in powerblock_coll:
				logger.debug(f'[ {self} ] type:{pc.powertype} colls:{len(powerblock_coll)} sp:{len(self.powerups)}')
				playerone.take_powerup(pc.powertype)
				pc.kill()


	def draw(self):
		# draw on screen
		fps = -1
		if pygame.display.get_init():
			try:
				pygame.display.update()
			except pygame.error as e:
				logger.error(f'[ {self} ] err:{e} getinit:{pygame.display.get_init()}')
				pygame.display.set_mode(SCREENSIZE, 0, 8)
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
			npitem = self.playerone.client.netplayers[npid]
			np = f'{npitem["gridpos"]} {npitem["client_id"]}'
			pos = self.playerone.client.netplayers[npid].get('pos')
			if npid == '0' or npid == 0:
				pass
			elif self.playerone.client_id != npid:
				#pos -= (0,5)
				#pos[1] -=10
				self.font.render_to(self.screen, pos, f'{np}', (255, 255, 255))
				#pos += (5,10)
				#pygame.draw.circle(self.screen, color=(123,123,123), center=pos, radius=10)
				#pos = self.playerone.client.netplayers[npid].get('pos')
				#self.font.render_to(self.screen, pos, f'{np}', (255, 55, 55))
			elif npid == self.playerone.client_id:
				#pos += (5,20)
				self.font.render_to(self.screen, pos , f'{np}', (123, 123, 255))

		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
		self.gui.game_menu.draw_panel(screen=self.screen, blocks=self.blocks, particles=self.particles, playerone=self.playerone, flames=self.flames)
		fps = self.gameclock.get_fps()
		if DEBUG:
			pos = Vector2(10, self.screenh - 100)
			self.font.render_to(self.screen, pos, f"blk:{len(self.blocks)} b:{self.get_block_count()} pups:{len(self.powerups)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)} threads:{threading.active_count()}", (173, 173, 173))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"fps={fps} threads:{threading.active_count()} mainq:{self.mainqueue.qsize()} sendq:{self.sendq.qsize()} netq:{self.netqueue.qsize()} p1 np:{len(self.playerone.client.netplayers)}", (183, 183, 183))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"p1 {self.playerone}", (183, 183, 183))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"client {self.playerone.client}", (183, 183, 183))

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			# self.playerone.start()
			#self.gui.show_mainmenu ^= True
			if self.playerone.client.connect_to_server():
				self.playerone.connected = True
				logger.debug(f'[ {self} ] p1 connecting ')
				self.playerone.start_client()
				mapreqcnt = 0
				while not self.playerone.client.gotmap and not self.playerone.client.gotpos:
					logger.debug(f'[ {self} ] playeone={self.playerone} waiting for map mapreqcnt:{mapreqcnt} ')
					self.playerone.client.send_mapreq()
					mapreqcnt += 1
					time.sleep(1)					
					if mapreqcnt >= 5:
						logger.warning(f'[ {self} ] mapreqcnt:{mapreqcnt}  pc:{self.playerone.connected} pcc:{self.playerone.client.connected} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
						self.playerone.connected = False
						self.playerone.client.connected = False
						self.playerone.client.socket.close()
						self.playerone.client.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						self.playerone.ready = False
						self.gui.show_mainmenu = True
						break
				self.gui.show_mainmenu ^= True
			else:
				logger.warning(f'[ {self} ] p1 not connected  pc:{self.playerone.connected} pcc:{self.playerone.client.connected} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
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
			#self.gameserver.start()
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
						if self.playerone.client.bombs_left > 0:
							self.playerone.client.send_bomb(pos=self.playerone.rect.center)
						else:
							logger.warning(f'[ {self} ] {self.playerone.client} no bombs left')
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
				if event.key == pygame.K_c:
					pass
				if event.key == pygame.K_f:
					pass
				if event.key == pygame.K_p:
					pass
				if event.key == pygame.K_m:
					pass
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
						self.playerone.move("down")
						#self.playerone.vel.y = self.playerone.speed
						#self.playerone.vel.x = 0
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_up()
					else:
						self.playerone.move("up")
						#self.playerone.vel.y = -self.playerone.speed
						#self.playerone.vel.x = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					if not self.gui.show_mainmenu:
						self.playerone.move("right")
						#self.playerone.vel.x = self.playerone.speed
						#self.playerone.vel.y = 0
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					if not self.gui.show_mainmenu:
						self.playerone.move("left")
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

	pygame.display.set_mode(SCREENSIZE, 0, 8)
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


