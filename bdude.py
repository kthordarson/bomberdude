# bomberdude
# 07102022 todo fix mapsync, limit one bomb per grid on map, 
#  		   remove killed netplayers when server sends killnpevent
import socket
import time
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
from pygame.event import Event
from pygame import USEREVENT
import pygame
from loguru import logger
from globals import Block, Bomb
from constants import BLOCK, DEBUG, DEFAULTFONT, NETPLAYERSIZE,FPS
from menus import Menu, DebugDialog
from player import Player
from threading import Thread
import threading
from queue import Queue, Empty

			
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
	def __init__(self):
		Thread.__init__(self, name='game')
		# todo make this work
		
		self.gameclock = pygame.time.Clock()
		self.name = 'game'
		self.kill = False
		self.bg_color = pygame.Color("black")
		self.running = False
		self.blocks = Group()
		self.players = Group()
		self.particles = Group()
		self.bombs = Group()
		self.flames = Group()
		self.lostblocks = Group()
		self.playerone = Player(dummy=True)
		# self.players.add(self.playerone)
		self.authkey = 'foobar'
		self.extradebug = False
		self.screensize = (800, 600)
		self.updategridcnt = 0

	def __str__(self):
		return f'[G] run:{self.running} updategridcnt={self.updategridcnt} p1 p1conn:{self.playerone.connected} p1ready:{self.playerone.ready} p1gotmap:{self.playerone.gotmap} p1gotpos:{self.playerone.gotpos} np:{len(self.playerone.netplayers)} '

	def run(self):
		pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP, pygame.USEREVENT])
		pygame.display.set_mode((800,800), 0, 8)
		self.screen = pygame.display.get_surface() #  pygame.display.set_mode(SCREENSIZE, 0, vsync=0)  # pygame.display.get_surface()#  pygame.display.set_mode(SCREENSIZE, 0, 32)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.gui = GameGUI(self.screen)
		self.bgimage = pygame.transform.scale(pygame.image.load('data/blackfloor.png').convert(), (1000,900))
		logger.debug(f'{self}  started ')
		
		while True:
			if self.kill:
				logger.warning(f'{self}  game kill')
				self.kill = True
				self.playerone.kill = True
				break			
			self.draw()
			if DEBUG:
				self.draw_debug()
			events_ = pygame.event.get()
			events = [event for event in events_ if event.type != pygame.USEREVENT]
			userevents = [event for event in events_ if event.type == pygame.USEREVENT]
			[self.handle_mainq(gamemsg=event.payload) for event in userevents]
			for event in events:
				if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP or event.type == pygame.TEXTINPUT:
					self.handle_input(event)
				elif event.type == pygame.USEREVENT:
					logger.warning(f'events in queue={len(events)} {event}')
					# self.handle_mainq(gamemsg=event.payload)
					# if len(events)>=3:
					# 	logger.warning(f'events in queue={len(events)}')
				elif event.type == pygame.MOUSEMOTION:
					pass
				elif event.type == pygame.MOUSEBUTTONDOWN:
					mx,my = pygame.mouse.get_pos()
					gx = mx // BLOCK
					gy = my // BLOCK
					logger.debug(f'[mouse] {mx},{my} grid={gx},{gy} {self.playerone.gamemap.grid[gx][gy]}')
				elif event.type == pygame.MOUSEBUTTONUP:
					pass
				elif event.type == pygame.AUDIODEVICEADDED or event.type == pygame.AUDIODEVICEREMOVED:
					pass
				elif event.type == pygame.WINDOWSHOWN or event.type == pygame.WINDOWHIDDEN or event.type == pygame.WINDOWMOVED or event.type == pygame.WINDOWEXPOSED or event.type == pygame.ACTIVEEVENT:
					pass
				elif event.type == pygame.WINDOWENTER or event.type == pygame.WINDOWTAKEFOCUS:
					pass
				elif event.type == pygame.WINDOWFOCUSGAINED or event.type == pygame.WINDOWFOCUSLOST or event.type == pygame.WINDOWLEAVE:
					pass
				elif event.type == pygame.VIDEOEXPOSE:
					pass
				elif event.type == 772:
					pass
				else:
					#pass
					logger.warning(f'unhandled event events={len(events)} event={event}')
			#self.blocks.update()			
			if self.playerone.ready:
				self.playerone.update(self.blocks)
				self.gui.show_mainmenu = False
			#else:
			self.font.render_to(self.screen, (10, 10), f'p1status={self.playerone.status}', (255, 255, 255))
			#self.players.update(blocks=self.blocks, screen=self.screen)
			self.update_bombs()
			self.update_flames()
			self.update_blocks()
			self.update_particles()

			# check map grids...
			needrefresh = False
			for b in self.blocks:
				x,y = b.gridpos
				try:
					if self.playerone.gamemap.grid[x][y] != b.block_type:
						logger.warning(f'bcheck: mismatch {b} btype={b.block_type} != client={self.playerone.gamemap.grid[x][y]}')
						self.playerone.gamemap.grid[x][y] = b.block_type
						needrefresh = True
				except IndexError as e:
					logger.warning(f'indexerror {e} x={x} y={y} b={b} p1gridlen={len(self.playerone.gamemap.grid)}')
					needrefresh = True
					#logger.warning(f'bcheck: mismatch {b} btype={b.block_type} != client={self.playerone.gamemap.grid[x][y]}')
			if needrefresh:
				self.updategrid(self.playerone.gamemap.grid)
				#self.playerone.send_refreshgrid()
				
	def handle_mainq(self, gamemsg):
		msgtype = gamemsg.get('msgtype')
		if msgtype == 'playerpos':
			logger.debug(f'{self}  gamemsg={gamemsg}')
		if msgtype == 'bombdrop' or msgtype == 'netbomb':
			bomber_id = gamemsg.get('bombdata').get('client_id')
			if bomber_id == self.playerone.client_id:
				self.playerone.bombs_left -= 1
			bombpos = gamemsg.get('bombdata').get('bombpos')
			bombgridpos = gamemsg.get('bombdata').get('bombgridpos')

			bombpower = gamemsg.get('bombdata').get('bombpower')
			newbomb = Bomb(pos=bombpos, bomber_id=bomber_id, gridpos=bombgridpos, bombpower=bombpower)
			bx,by = newbomb.gridpos
			self.playerone.gamemap.grid[bx][by] = 11
			self.bombs.add(newbomb)
			logger.debug(f'bombpos = gridpos:{bombgridpos} pos:{bombpos} {newbomb.pos} bl={self.playerone.bombs_left} b:{len(self.bombs)}  mt:{msgtype} ')

		elif msgtype == 'newnetpos':
			posdata = gamemsg.get('posdata')
			# blkcnt = len(self.blocks)
			client_id = posdata.get('client_id')
			if client_id == self.playerone.client_id:
				pass
				#logger.info(f'newnetpos np={newpos} ngp={newgridpos} posdata={posdata} ')
			else:
				logger.warning(f'newnetpos clid mismatch clid={client_id} != {self.playerone.client_id} np={newpos} ngp={newgridpos} posdata={posdata} ')
			self.playerone.pos = posdata.get('newpos')
			self.playerone.gridpos = posdata.get('newgridpos')

			#self.playerone.pos = Vector2(newpos[0], newpos[1])
			self.playerone.rect.x = self.playerone.pos[0]
			self.playerone.rect.y = self.playerone.pos[1]
			grid_data = posdata.get('griddata')
			
			if len(self.blocks) != len(self.playerone.gamemap.grid[0])**2 or len(self.blocks) == 0 or not self.playerone.gotmap or len(self.playerone.gamemap.grid) == 0:
				logger.warning(f'{self} block count mismatch! grid_data={len(grid_data)} p1g={len(self.playerone.gamemap.grid)} p1g2={len(self.playerone.gamemap.grid[0])**2} p1gotpos={self.playerone.gotpos} p1gotmap={self.playerone.gotmap} p1r={self.playerone.ready} blkc={len(self.blocks)}   ')
				self.playerone.gamemap.grid = grid_data
				self.updategrid(self.playerone.gamemap.grid)
				self.playerone.gotpos = True
				self.playerone.gotmap = True
				self.playerone.ready = True

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

		elif msgtype == 'poweruptimeout':
			nb = gamemsg.get('blockdata')
			x,y = nb.gridpos
			self.playerone.gamemap.grid[x][y] = 11
			self.blocks.add(nb)

		elif msgtype == 'poweruppickup':
			nb = gamemsg.get('blockdata')
			x,y = nb.gridpos
			self.playerone.gamemap.grid[x][y] = 11
			self.blocks.add(nb)
			#logger.debug(f'{msgtype} nb={nb} self.playerone.gamemap.grid[x][y]={self.playerone.gamemap.grid[x][y]} x={x} y={y}')
			#self.blocks.add(nb)

		elif msgtype == 'newblock':
			nb = gamemsg.get('blockdata')
			ob = gamemsg.get('oldblock')
			ox,oy = ob.gridpos
			x,y = nb.gridpos
			#y = nb.gridpos[1]
			# if self.playerone.gamemap.grid[x][y] != nb.block_type:
			# 	logger.warning(f'{msgtype} mismatch {nb} btype={nb.block_type} != client={self.playerone.gamemap.grid[x][y]}')
			# elif self.playerone.gamemap.grid[x][y] == nb.block_type:
			# 	logger.info(f'{msgtype} {nb} btype={nb.block_type} == client={self.playerone.gamemap.grid[x][y]}')
			#logger.debug(f'ob = {ob} newblock={nb}')
			self.playerone.gamemap.grid[x][y] = nb.block_type
			self.blocks.add(nb)
			# self.updategrid(self.playerone.gamemap.grid)

		elif msgtype == 'netgridupdate':
			old_blkcnt = len(self.blocks)
			gridpos = gamemsg.get('blkgridpos')
			x,y = gridpos
			blktype = gamemsg.get('blktype')
			bclid = gamemsg.get('bclid')
			clientid = gamemsg.get('client_id')
			newblock = Block(pos=(x*BLOCK, y*BLOCK), gridpos=gridpos, block_type=blktype, client_id=bclid)
			if self.playerone.client_id == bclid or self.playerone.client_id == clientid:
				pass
				# logger.warning(f'netgridupdate from self {self.playerone.client_id} gamemsg={gamemsg}')
			else:
				logger.info(f'NGU from netplayer b={bclid} bc={clientid} p1={self.playerone.client_id} gamemsg={gamemsg}')
			if self.playerone.gamemap.grid[x][y] != blktype:
				logger.warning(f'NGU mismatch {self.playerone.client_id} gamemsg={gamemsg}')
			self.playerone.gamemap.grid[x][y] = blktype
			for b in self.blocks:
				if b.gridpos == newblock.gridpos:
					logger.warning(f'NGU: block already exists b={b.block_type} nb={newblock.block_type}')
					b.kill()
			self.blocks.add(newblock)
			blkcnt = len(self.blocks)
			logger.info(f'NGU bclid={bclid} clientid={clientid} newblock={newblock} {self.playerone.gamemap.grid[x][y]} blkcnt={blkcnt}/{old_blkcnt}')

		elif msgtype == 's_gamemapgrid':
			self.playerone.ready = False
			grid = gamemsg.get('grid', None)
			newpos = gamemsg.get('newpos')
			newgridpos = gamemsg.get('newgridpos')
			logger.debug(f'{self} gamemapgrid np={newpos} ngp={newgridpos} p1={self.playerone}')
			self.updategrid(grid)
			self.playerone.ready = True
			self.playerone.gotmap = True
			self.playerone.gotpos = True
			self.playerone.gamemap.grid = grid
			self.playerone.pos = newpos

	def updategrid(self, gamemapgrid):
		self.updategridcnt += 1
		if not gamemapgrid:
			logger.error(f'updategrid: no gamemapgrid')
			return
		else:
			self.playerone.gamemap.grid = gamemapgrid
		old_blkcnt = len(self.blocks)
		# self.blocks.empty()
		newblks = Group()
		idx = 0
		for k in range(0, len(self.playerone.gamemap.grid)):
			for j in range(0, len(self.playerone.gamemap.grid)):				
				try:
					blktype =  self.playerone.gamemap.grid[j][k]
				except (IndexError, TypeError) as e:
					logger.error(f'updategrid: {e} blktype={blktype} j={j} k={k} idx={idx} p1gridlen={len(self.playerone.gamemap.grid)}') # gmg={self.playerone.gamemap.grid[j][k]}				
					return
				newblock = Block(Vector2(j * BLOCK, k * BLOCK), (j, k), block_type=blktype, client_id=self.playerone.client_id)
				newblks.add(newblock)
				idx += 1
		self.blocks.empty()
		self.blocks = newblks
		blkchk = len(self.playerone.gamemap.grid) ** 2
		if blkchk == len(self.blocks) or old_blkcnt == 0:
			logger.debug(f'gridlen={len(self.playerone.gamemap.grid)} block count was {old_blkcnt} now={len(self.blocks)} idx:{idx} self.updategridcnt={self.updategridcnt}')
		else:
			logger.error(f'gridlen={len(self.playerone.gamemap.grid)} block count mismatch was {old_blkcnt} now={len(self.blocks)} idx:{idx} self.updategridcnt={self.updategridcnt}')

	def update_blocks(self):
		# self.particles.update(self.blocks, self.screen)
		if len(self.blocks) == 0:
			return
		for b in self.blocks:
			if b.block_type in range(20,29):
				#powerups are between 20 and 29
				if pygame.Rect.colliderect(self.playerone.rect, b.rect):
					self.playerone.score += 2
					if b.block_type == 20:
						self.playerone.hearts += 1
					if b.block_type == 21:
						self.playerone.bombs_left += 1
					if b.block_type == 22:
						self.playerone.bombpower += 5
					x,y = b.gridpos
					self.playerone.gamemap.grid[x][y] = 11
					nb = Block(b.pos, b.gridpos, block_type=11, client_id=b.client_id)					
					logger.debug(f'p1={self.playerone} poweruppickup b={b} nb={nb} grid[x][y]={self.playerone.gamemap.grid[x][y]} bgridpos={b.gridpos} timer:{pygame.time.get_ticks() - b.start_time} >= {b.timer}')
					pygame.event.post(Event(USEREVENT, payload={'msgtype': 'poweruppickup', 'blockdata': nb}))
					b.kill()
				# if block is powerup, check timer				
				if pygame.time.get_ticks() - b.start_time >= b.timer:
					nx = b.gridpos[0]
					ny = b.gridpos[1]
					self.playerone.gamemap.grid[nx][ny] = 11
					nb = Block(b.pos, b.gridpos, block_type=11, client_id=b.client_id)
					logger.debug(f'poweruptimeout b={b} nb={nb} grid[x][y]={self.playerone.gamemap.grid[nx][ny]} bgridpos={b.gridpos} timer:{pygame.time.get_ticks() - b.start_time} >= {b.timer}')
					pygame.event.post(Event(USEREVENT, payload={'msgtype': 'poweruptimeout', 'blockdata': nb}))
					b.kill()

	def update_bombs(self):
		#self.bombs.update()
		if len(self.bombs) == 0:
			return
		for bomb in self.bombs:
			bomb.update()
			if pygame.time.get_ticks() - bomb.start_time >= bomb.timer:
				if bomb.bomber_id == self.playerone.client_id:
					self.playerone.bombs_left += 1
				bx,by = bomb.gridpos
				pos = (bx * BLOCK, by * BLOCK)
				nb = Block(pos=pos, gridpos=bomb.gridpos, block_type=11, client_id=bomb.bomber_id)
				pygame.event.post(Event(USEREVENT, payload={'msgtype': 'newblock', 'blockdata': nb, 'oldblock':bomb}))
				self.playerone.gamemap.grid[bx][by] = nb.block_type
				flames = bomb.exploder()
				flamemsg = Event(USEREVENT, payload={'msgtype': 'flames', 'flamedata': flames})
				pygame.event.post(flamemsg)
				bomb.kill()

	def update_flames(self):
		if len(self.flames) == 0:
			return
		#self.flames.update(surface=self.screen)
		for flame in self.flames:
			flame.update(surface=self.screen)
			for player in spritecollide(flame, self.players, False):
				if pygame.Rect.colliderect(flame.rect, player.rect):
					player.flame_hit(flame)
					flame.kill()
					if player.hearts <= 0:
						logger.info(f'{player} killed by {flame}')
						player.kill = True
			# check if flame collides with blocks
			for block in spritecollide(flame, self.blocks, False):
				if pygame.Rect.colliderect(flame.rect, block.rect):
					x,y = block.gridpos
					if block.block_type == 10:
						# kill flame on wallhit
						flame.kill()
					elif block.block_type == 11:
						# flames cann pass type 11
						pass
					elif 1 <= block.block_type < 40:
						# flames kills block
						if flame.client_id == self.playerone.client_id:
							# add player score if flame from bomb was by playerone
							if 1 <= block.block_type < 10:
								self.playerone.score += 1
						# block hits return particles and a new block
						particles, newblock = block.hit(flame)
						particlemsg = Event(USEREVENT, payload={'msgtype': 'particles', 'particledata': particles})
						pygame.event.post(particlemsg)
						#if newblock:
						self.playerone.gamemap.grid[x][y] = newblock.block_type
						blockmsg = Event(USEREVENT, payload={'msgtype': 'newblock', 'blockdata': newblock, 'oldblock':block})
						pygame.event.post(blockmsg)
						flame.kill()
						block.kill()

	def update_particles(self):
		for p in self.particles:
			p.update(self.blocks)
			# if pygame.time.get_ticks() - p.start_time >= p.timer:
			# 	logger.info(f'particles={p} timeout')
			# 	p.kill()

	def draw(self):
		# draw on screen
		if pygame.display.get_init():
			try:
				pygame.display.update()
			except pygame.error as e:
				logger.error(f'{self}  err:{e} getinit:{pygame.display.get_init()}')
				pygame.display.set_mode((800,800), 0, 8)
				#pygame.display.set_mode(self.screensize, 0, 8)
				#self.screen = pygame.display.get_surface()
				return
		self.gameclock.tick(FPS)
		#self.blocks.draw(self.screen)
		#if self.playerone.ready:
		self.screen.fill(self.bg_color)		
		self.screen.blit(self.bgimage, (0,0))
		self.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.flames.draw(self.screen)
		self.particles.draw(self.screen)
		if self.playerone.gotpos and self.playerone.ready:
			self.players.draw(self.screen)
		#self.playerone.draw(self.screen)
		for npid in self.playerone.netplayers:
			npitem = self.playerone.netplayers[npid]
			if not npitem.get('pos'):
				logger.error(f'nopos np={npid} npitem={npitem} ')
			np = f'{npitem["gridpos"]}'
			try:
				x,y = self.playerone.netplayers[npid].get('pos', None)
			except TypeError as e:
				logger.error(f'err:{e} np={npid} npitem={npitem} ')
				break
			pos = [x,y]
			gpos = self.playerone.netplayers[npid].get('gridpos', None)
			if self.playerone.client_id != npid:
				#pos -= (0,5)
				#pos[1] -=10
				# self.font.render_to(self.screen, pos, f'{np}', (255, 255, 255))
				pos[0] += 15
				pos[1] += 15
				pygame.draw.circle(self.screen, color=(0,0,255), center=pos, radius=10)
				#pos = self.playerone.netplayers[npid].get('pos')
				#self.font.render_to(self.screen, pos, f'{np}', (255, 55, 55))
			if npid == self.playerone.client_id:
				pos[0] += 15
				pos[1] += 15
				pygame.draw.circle(self.screen, color=(0,255,0), center=pos, radius=2)
				#self.font.render_to(self.screen, pos , f'{np}', (123, 123, 255))

		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
		if self.playerone.ready:
			self.gui.game_menu.draw_panel(screen=self.screen, blocks=self.blocks, particles=self.particles, playerone=self.playerone, flames=self.flames, grid=self.playerone.gamemap.grid)

	def draw_debug(self):
		pos = Vector2(10, self.screenh - 100)
		self.font.render_to(self.screen, pos, f"blklen:{len(self.blocks)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)}  ", (173, 173, 173))
		pos += (0, 15)
		self.font.render_to(self.screen, pos, f"fps={self.gameclock.get_fps():.2f} threads:{threading.active_count()}  p1 np:{len(self.playerone.netplayers)} p1eventq={self.playerone.eventqueue.qsize()} p1u={len(self.playerone.updates)}", (183, 183, 183))
		pos += (0, 15)
		self.font.render_to(self.screen, pos, f"p1 pos {self.playerone.pos} {self.playerone.gridpos} cpos {self.playerone.pos} {self.playerone.gridpos}", (183, 183, 183))
		pos += (0, 15)
		self.font.render_to(self.screen, pos, f"client {self.playerone}", (183, 183, 183))
		pos = self.playerone.pos
		self.font.render_to(self.screen, pos, f'{self.playerone.gridpos}', (255,255,255))
		if self.extradebug:
			for b in self.blocks:
				gx, gy = b.gridpos
				plg1item = self.playerone.gamemap.grid[gx][gy]
				textpos = [b.rect.topleft[0]+3, b.rect.topleft[1]]
				if b.block_type != plg1item:
					fcol1 = (255,0,0)
					fcol2 = (255,1,255)
					pygame.draw.rect(self.screen, color=(255,0,0), rect=b.rect, width=1)
					self.font.render_to(self.screen, (textpos[0]+5, textpos[1]+25), f"{plg1item}", fcol2)
					self.font.render_to(self.screen, b.pos, f"{b.block_type}", (255, 255, 255))
					#self.font.render_to(self.screen, b.pos, f"{b.block_type}", (183, 183, 183))
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
			# self.gui.show_mainmenu ^= True
			self.playerone.kill = True
			self.playerone = Player(dummy=False)
			self.players.add(self.playerone)
			self.playerone.start()

		if selection == "Connect to server":
			pass

		if selection == "Quit":
			self.running = False
			self.kill = True

		if selection == "Pause":
			self.gui.show_mainmenu ^= True

		if selection == "Restart":
			self.gui.show_mainmenu ^= True

		if selection == "Start server":
			pass

	def handle_input(self, event):
		#events = pygame.event.get()
		#for event in events:
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
					if self.gui.show_mainmenu:  # or self.paused:
						selection = self.gui.game_menu.get_selection()
						self.handle_menu(selection)
					elif not self.gui.show_mainmenu:
						self.playerone.send_bomb()
				if event.key == pygame.K_ESCAPE:
					self.gui.show_mainmenu ^= True
				if event.key == pygame.K_q:
					# quit game
					self.playerone.disconnect()
					self.kill = True
					self.running = False
				if event.key == pygame.K_1:
					self.blocks.empty()
					self.playerone.send_maprequest(gridsize=15)
				if event.key == pygame.K_2:
					self.blocks.empty()
					self.playerone.send_maprequest(gridsize=10)
				if event.key == pygame.K_3:
					self.blocks.empty()
					self.playerone.send_maprequest(gridsize=13)
				if event.key == pygame.K_4:
					self.blocks.empty()
					self.playerone.send_maprequest(gridsize=18)
				if event.key == pygame.K_5:
					self.blocks.empty()
					self.playerone.send_maprequest(gridsize=22)
				if event.key == pygame.K_6:
					self.blocks.empty()
					self.playerone.send_refreshgrid()
					# logger.debug(f'send_refreshgrid p1gz={self.playerone.gamemap.gridsize} p1={self.playerone}')
				if event.key == pygame.K_0:
					self.extradebug ^= True
					logger.info(f'{self} extradebug={self.extradebug}')
				if event.key == pygame.K_f:
					pass
				if event.key == pygame.K_e:
					if not self.playerone.eventqueue.empty():
						evs=[]
						print(f'{self} p1evqsize={self.playerone.eventqueue.qsize()}')
						try:
							evs = self.playerone.eventqueue.get_nowait()
						except Empty:
							pass
						for ev in evs:
							print(ev)
				if event.key == pygame.K_p:
					print(f'-'*80)
					print(self)
					print(f'-'*80)
					print('client netplayers:')
					for np in self.playerone.netplayers:
						print(f'\t{np} {self.playerone.netplayers[np]}')
						print(f'-'*80)
					# for tempg in tempgrids:
					# 	for tx in range(len(tempg)):
					# 		if len(tempg[tx]) != len(tempg):
					# 			logger.error(f'grid1 x={tx} len={len(tx)}')
				if event.key == pygame.K_m:
					print(f'pl={self.playerone.gamemap.grid}')
				if event.key == pygame.K_n:
					self.playerone.bombs_left += 3
					self.playerone.bombpower += 30
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
							logger.warning(f'err={e} {self.playerone} {self.playerone}')
						#self.playerone.vel.y = self.playerone.speed
						#self.playerone.vel.x = 0
				if event.key in {pygame.K_UP, pygame.K_w}:
					if self.gui.show_mainmenu:
						self.gui.game_menu.menu_up()
					else:
						try:
							self.playerone.move("up")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone}')
						#self.playerone.vel.y = -self.playerone.speed
						#self.playerone.vel.x = 0
				if event.key in {pygame.K_RIGHT, pygame.K_d}:
					if not self.gui.show_mainmenu:
						try:
							self.playerone.move("right")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone}')
						#self.playerone.vel.x = self.playerone.speed
						#self.playerone.vel.y = 0
				if event.key in {pygame.K_LEFT, pygame.K_a}:
					if not self.gui.show_mainmenu:
						try:
							self.playerone.move("left")
						except IndexError as e:
							logger.warning(f'err={e} {self.playerone} {self.playerone}')
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
				logger.warning(f'{self}  quit {event.type}')
				self.kill = True
				self.running = False



if __name__ == "__main__":

	#pygame.display.set_mode((800,600), 0, 8)
	pygame.init()
	game = Game()
	game.daemon = True
	game.running = True
	game.run()
	while game.running:
		if game.kill:
			game.running = False
			break
	pygame.quit()


