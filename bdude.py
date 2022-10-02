#!/bin/python3.9
# bomberdude
import time
import random
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
import pygame
from loguru import logger
from globals import Block, Powerup, Bomb
from constants import BLOCK, DEBUG, DEBUGFONTCOLOR, GRIDSIZE, BLOCKSIZE, PLAYERSIZE, SCREENSIZE ,DEFAULTFONT, NETPLAYERSIZE
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
	def __init__(self, mainqueue=None, conn=None, sendq=None, netqueue=None, args=None):
		Thread.__init__(self, name='game')
		self.args = args
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.conn = conn
		self.name = 'game'
		self.mainqueue = Queue()
		self.sendq = sendq
		self.netqueue = netqueue
		self.kill = False
		self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
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
		self.playerone = Player(pos=(1, 1), visible=False, mainqueue=self.mainqueue)
		self.p1connected = False
		self.players.add(self.playerone)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.authkey = 'foobar'
		self.netplayers = {}
		self.gamemapgrid = []
		self.gotgamemapgrid = False
		if self.args.testmode:
			g=Gamemap()
			grid,nx,ny = g.placeplayer(g.grid)
			self.playerone.setpos((nx,ny))
			self.gamemapgrid = grid
			self.gotgamemapgrid = True
			self.playerone.gotmap = True
			self.playerone.visible = True
			self.gui.show_mainmenu ^= True
			self.updategrid(self.gamemapgrid)
		# self.authresp = {}


	def __repr__(self):
		return f'[game] {self.name}'

	def run(self):
		logger.debug(f'[game] {self} started mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
		while True:
			# logger.debug(f'[game] {self}  mq:{self.mainqueue.qsize()} sq:{self.sendq.qsize()} nq:{self.netqueue.qsize()}')
			if self.kill:
				logger.warning(f'game kill')
				break
			if self.playerone.kill:
				logger.warning(f'{self} playerone kill {self.playerone}')
				self.kill = True
				break
			self.draw()
			self.handle_input()
			#self.playerone.update(self.blocks)
			if self.playerone.visible:
				self.players.update(blocks=self.blocks, screen=self.screen)
				self.update_bombs()
				self.update_flames()
				self.update_particles()
				self.update_powerups(self.playerone)
			gamemsg = None
			if not self.mainqueue.empty():
				gamemsg = self.mainqueue.get_nowait()
				# logger.debug(f'[game] gamemsg:{gamemsg}')
				# logger.warning(f'[game] {self.mainqueue.qsize()}')
			if gamemsg:
				# self.mainqueue.task_done()
				self.handle_mainq(gamemsg)


	def handle_mainq(self, gamemsg):
		#logger.debug(f'[game] {self} gamemsg:{gamemsg}')
		type = gamemsg.get('msgtype')
		# logger.debug(f"[e] type:{type} cl:{gamemsg.get('client_id')} pos:{gamemsg.get('pos')} resp:{resp}")
		#if type == 'playerpos':
		#	resp = {'msgtype':dataid["playerpos"], 'authkey':self.authkey, 'client_id': gamemsg.get('client_id'), 'pos': gamemsg.get('pos'), 'data_id': dataid['playerpos']}
		if type == 'bombdrop' or type == 'netbomb':
			#logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} gamemsg={gamemsg}')
			bomber_id = gamemsg.get('bombdata').get('client_id')
			bombpos = gamemsg.get('bombdata').get('bombpos')
			newbomb = Bomb(pos=bombpos, bomber_id=bomber_id)
			self.bombs.add(newbomb)
			logger.debug(f'[mainq] bombs:{len(self.bombs)} {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} bomb:{newbomb.pos}')
		elif type == 'newnetpos':
			# logger.debug(f'[mainq] gamemsg={gamemsg}')
			posdata = gamemsg.get('posdata')
			newgrid = posdata.get('newgrid')
			client_id = posdata.get('client_id')
			newpos = posdata.get('newpos')
			logger.debug(f'[mainq] posupdate {client_id} newpos={newpos} newgrid={len(newgrid)}')
			self.updategrid(newgrid)
			if client_id == self.playerone.client_id:
				if not self.playerone.visible:
					self.playerone.setpos(newpos)
					self.playerone.visible = True
		elif type == 'flames':
			flames = gamemsg.get('flamedata')
			for fl in flames:
				self.flames.add(fl)
			logger.debug(f'[bfl] self.flames:{len(self.flames)} nf:{len(flames)}')
		elif type == 'particles':
			particles = gamemsg.get('particledata')
			for p in particles:
				self.particles.add(p)
			logger.debug(f'[p] self.particles:{len(self.particles)} ')
		elif type == 'powerup':
			pwrup = gamemsg.get('powerupdata')
			self.powerups.add(pwrup)
			logger.debug(f'[p] self.powerups:{len(self.powerups)} pwr={pwrup.powertype} ')
		elif type == 'newblock':
			blk = gamemsg.get('blockdata')
			self.blocks.add(blk)
			self.gamemapgrid[blk.gridpos[0]][blk.gridpos[1]] = blk.block_type
			self.playerone.client.send_gridupdate(self.gamemapgrid)
			logger.debug(f'[blk] self.blocks:{len(self.blocks)} newblk={blk} ')
		elif type == 'gamemapgrid':
			gamemapgrid = gamemsg.get('gamemapgrid')
			logger.debug(f'[mainq] {self.mainqueue.qsize()} {self.sendq.qsize()} got type:{type} engmsg:{len(gamemsg)} gamemapgrid:{len(gamemapgrid)}')
			if len(gamemapgrid) > 1:
				self.updategrid(gamemapgrid)

	def updategrid(self, gamemapgrid):
		self.gamemapgrid = gamemapgrid
		self.gotgamemapgrid = True
		newblocks = Group()
		for k in range(0, GRIDSIZE[0]):
			for j in range(0, GRIDSIZE[1]):
				newblock = Block(pos=Vector2(j * BLOCKSIZE[0], k * BLOCKSIZE[1]), gridpos=(j, k), block_type=gamemapgrid[j][k])
				newblocks.add(newblock)
		self.blocks.empty()
		self.blocks.add(newblocks)

	def update_bombs(self):
		self.bombs.update()
		for bomb in self.bombs:
			# logger.debug(f'[btq] b:{bomb} q:{bomb.thingq.qsize()}')
			dt = pygame.time.get_ticks()
			if dt - bomb.start_time >= bomb.timer:
				flames = bomb.exploder()
				flamemsg = {'msgtype': 'flames', 'flamedata': flames}
				self.mainqueue.put(flamemsg)
				#for fl in flames:
				#	self.flames.add(fl)
					# logger.debug(f'[bombflames] fl:{fl} flv:{fl.vel} self.flames:{len(self.flames)} nf:{len(flames)}')
				bomb.kill()

	def update_flames(self):
		self.flames.update(surface=self.screen)
		for flame in self.flames:
			# check if flame collides with blocks
			flame_coll = spritecollide(flame, self.blocks, False)
			for block in flame_coll:
				if DEBUG:
					if block.block_type == 0:
						pygame.draw.rect(self.screen, (95,95,95), rect=block.rect, width=1)
					else:
						pygame.draw.rect(self.screen, (215,215,215), rect=block.rect, width=1)
				if block.block_type == 10:
					flame.kill()
				if block.block_type != 10:
					pos, gridpos, particles, newblock, powerblock = block.hit(flame)
					if particles:
						particlemsg = {'msgtype': 'particles', 'particledata': particles}
						self.mainqueue.put(particlemsg)
						#self.particles.add(particles)
					if newblock:
						# self.gamemap.set_block(gridpos[0], gridpos[1], 0)
						blockmsg = {'msgtype': 'newblock', 'blockdata': newblock}
						self.mainqueue.put(blockmsg)
						# self.blocks.add(newblock)
						if powerblock:
							powerupmsg = {'msgtype': 'powerup', 'powerupdata': powerblock}
							self.mainqueue.put(powerupmsg)
							#self.powerups.add(powerblock)
					#block.kill()

	def update_particles(self):
		self.particles.update(self.blocks, self.screen)
		for particle in self.particles:
			blocks = spritecollide(particle, self.blocks, dokill=False)
			for block in blocks:
				if block.solid:
					if DEBUG:
						pygame.draw.circle(self.screen, (111,111,111), particle.rect.center, 2)
						pygame.draw.rect(self.screen, (85,85,85), rect=block.rect, width=1)
					particle.hit(block)

	def update_powerups(self, playerone):
		self.powerups.update()
		if len(self.powerups) > 0:
			powerblock_coll = spritecollide(playerone, self.powerups, False)
			for pc in powerblock_coll:
				logger.debug(f'[pwrb] type:{pc.powertype} colls:{len(powerblock_coll)} sp:{len(self.powerups)}')
				playerone.take_powerup(pc.powertype)
				pc.kill()

		
	def draw(self):
		# draw on screen
		try:
			pygame.display.flip()
		except pygame.error as e:
			logger.error(f'[pg] err:{e}')
			self.screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
			return
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
		self.particles.draw(self.screen)
		self.bombs.draw(self.screen)
		self.flames.draw(self.screen)
		if self.playerone.visible:
			self.players.draw(self.screen)
		self.powerups.draw(self.screen)
		# for bomb in self.bombs:
		# 	bomb.draw(self.screen)
		# 	pygame.draw.circle(self.screen, (255, 0, 0), bomb.pos, 10, 0)
		for np in self.playerone.client.netplayers:
			if self.playerone.client_id != np:
				if not self.playerone.client.netplayers[np].get('kill'):
					ckill = self.playerone.client.netplayers[np].get('kill')
					cpos = Vector2(self.playerone.client.netplayers[np].get('centerpos'))
					rpos = Vector2(self.playerone.client.netplayers[np].get('pos'))
					nprect = pygame.Rect(rpos, NETPLAYERSIZE)
					surf = pygame.display.get_surface()
					surf.fill(color=(211,0,0), rect=nprect, special_flags=pygame.BLEND_ADD)
					#pygame.draw.rect(self.screen, (255, 0, 0), rect=nprect, width=1)
					#pygame.draw.circle(self.screen, (255, 0, 0), cpos, 10, 0)
					rpos.x -= 20
					self.font.render_to(self.screen, rpos, f'{np}', (255, 255, 255))
					#rpos += (0,15)
					#self.font.render_to(self.screen, rpos, f'{cpos} {rpos}', (255, 255, 255))
			if self.playerone.client_id == np:
				pass
				#pos = self.playerone.client.netplayers[np].get('pos')
				#pygame.draw.circle(self.screen, (255, 255, 255), pos, 5, 0)
				#self.font.render_to(self.screen, pos, str(np), (255, 155, 255))
				#self.font.render_to(self.screen, pos+(0,10), f'p1:{self.playerone.pos} np:{pos}', (255, 155, 255))
		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
		self.gui.game_menu.draw_panel(blocks=self.blocks, particles=self.particles, playerone=self.playerone, flames=self.flames)

		if DEBUG:
			pos = Vector2(10, self.screenh - 100)
			self.font.render_to(self.screen, pos, f"blk:{len(self.blocks)} pups:{len(self.powerups)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)} threads:{threading.active_count()}", (123, 123, 123))
			pos += (0, 15)
			self.font.render_to(self.screen, pos, f"threads:{threading.active_count()} mainq:{self.mainqueue.qsize()} sendq:{self.sendq.qsize()} netq:{self.netqueue.qsize()} p1c:{self.p1connected} np:{len(self.playerone.client.netplayers)}", (123, 123, 123))

	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			# self.playerone.start()
			self.gui.show_mainmenu ^= True
			self.p1connected = self.playerone.client.connect_to_server()
			if self.p1connected:
				self.playerone.connected = True
				logger.debug(f'[game] p1 connecting c:{self.p1connected} pc:{self.playerone.connected} pcc:{self.playerone.client.connected} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
				self.playerone.start_client()
				mapreqcnt = 0
				while not self.playerone.client.gotmap:
					self.playerone.client.send_mapreq()
					mapreqcnt += 1
					time.sleep(0.5)
					logger.debug(f'[game] p1 mapreqcnt:{mapreqcnt} c:{self.p1connected} pc:{self.playerone.connected} pcc:{self.playerone.client.connected} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
				
				# while not self.gotgamemapgrid:
				# 	time.sleep(0.5)
				# 	logger.debug(f'[game] waiting for grid pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')
				# p1pos = self.placeplayer()
				# self.playerone.setpos(p1pos)
				# logger.debug(f'[game] p1pos={p1pos} ppos={self.playerone.pos} pclpos={self.playerone.client.pos} pgm={self.playerone.gotmap} gg={self.gotgamemapgrid}')

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
						self.playerone.client.send_bomb(pos=self.playerone.rect.center)
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
					self.playerone.client.send_pos(pos=self.playerone.pos)
				if event.key == pygame.K_3:
					pass
					# logger.debug(f'[c] req serverinfo p1c:{self.playerone.bombclient.connected}')
					# self.playerone.get_server_info()
					# logger.debug(f'[c] req netplayers p1c:{self.playerone.bombclient.connected}')
					# self.playerone.refresh_netplayers()
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
						self.playerone.vel.y = self.playerone.speed
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_up()
					else:
						self.playerone.vel.y = -self.playerone.speed
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					if not self.gui.show_mainmenu:
						self.playerone.vel.x = self.playerone.speed
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					if not self.gui.show_mainmenu:
						self.playerone.vel.x = -self.playerone.speed
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
			if event.type == pygame.QUIT:
				logger.warning(f'[pgevent] quit {event.type}')
				self.running = False



if __name__ == "__main__":
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--testmode', default=False, action='store_true', dest='testmode')
	args = parser.parse_args()
	if args.testclient:
		pass

	else:
		pygame.init()
		#screen = pygame.display.set_mode(SCREENSIZE, 0, 32)
		dt = pygame.time.Clock()
		mainqueue = Queue()
		netqueue = Queue()
		sendq = Queue()
		stop_event = Event()
		#mainqueue = OldQueue()#  multiprocessing.Manager().Queue()
		# engine = Engine(stop_event=stop_event, name='engine')
		game = Game(mainqueue=mainqueue, sendq=sendq, netqueue=netqueue, args=args)
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


