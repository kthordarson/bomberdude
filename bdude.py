# bomberdude
# 07102022 todo fix mapsync, limit one bomb per grid on map,
#  		   remove killed netplayers when server sends killnpevent
# 17102022 todo fix fps drops
from argparse import ArgumentParser
from pygame.sprite import Group, spritecollide
from pygame.math import Vector2
from pygame.event import Event
from pygame import USEREVENT
import pygame
from loguru import logger
from globals import Block, Bomb, ResourceHandler
from constants import BLOCK, DEBUG, DEFAULTFONT, NETPLAYERSIZE,FPS
from menus import Menu
from player import Player
from threading import Thread
import threading
# from queue import Queue, Empty

class GameGUI:
	def __init__(self, screen):
		self.screen = screen
		self.show_mainmenu = True
		self.blocks = Group()
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.game_menu = Menu(self.screen, self.font)
		self.font_color = (255, 255, 255)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
	# self.debugfont = pygame.freetype.Font(DEFAULTFONT, 10)

class Game(Thread):
	def __init__(self, args=None):
		Thread.__init__(self, name='game')
		self.rm = ResourceHandler()
		self.args = args
		self.gameclock = pygame.time.Clock()
		self.name = 'game'
		self.kill = False
		self.bg_color = pygame.Color("black")
		self.running = False
		self.blocks = Group()
		self.particles = Group()
		self.bombs = Group()
		self.flames = Group()
		self.lostblocks = Group()
		self.playerone = Player(dummy=True, serverargs=self.args)
		self.authkey = 'foobar'
		self.extradebug = False
		self.screensize = (800, 600)
		self.updategridcnt = 0

	def __str__(self):
		return f'[G] run:{self.running} updategridcnt={self.updategridcnt} p1 p1conn:{self.playerone.connected} p1ready:{self.playerone.ready} p1gotmap:{self.playerone.gotmap} p1gotpos:{self.playerone.gotpos} np:{len(self.playerone.netplayers)} '
	
	def run(self):
		# pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP, pygame.USEREVENT])
		pygame.display.set_mode(size=(800,800), flags=pygame.DOUBLEBUF, vsync=1)
		self.screen = pygame.display.get_surface() #  pygame.display.set_mode(SCREENSIZE, 0, vsync=0)  # pygame.display.get_surface()#  pygame.display.set_mode(SCREENSIZE, 0, 32)
		self.font = pygame.freetype.Font(DEFAULTFONT, 12)
		self.screenw, self.screenh = pygame.display.get_surface().get_size()
		self.gui = GameGUI(self.screen)
		# self.bgimage = pygame.transform.scale(pygame.image.load('data/blackfloor.png').convert(), (1000,900))
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
			mouse_events = [event for event in events_ if event.type == pygame.MOUSEBUTTONDOWN]
			input_events = [event for event in events_ if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT)]
			user_events = [event for event in events_ if event.type == pygame.USEREVENT]
			
			# [self.handle_mainq(gamemsg=event.payload) for event in events_ if event.type == pygame.USEREVENT]
			# [self.handle_mainq(gamemsg=event.payload) for event in userevents]
			for event in user_events:
				self.handle_mainq(gamemsg=event.payload)
			for event in input_events:
				if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
					keypressed = None
					if event.type == pygame.KEYDOWN:
						keypressed = event.key
						self.handle_input(keypressed)
			for event in mouse_events:
				if event.type == pygame.MOUSEBUTTONDOWN:
					mx,my = pygame.mouse.get_pos()
					gx = mx // BLOCK
					gy = my // BLOCK
					try:
						logger.debug(f'[mouse] {mx},{my} grid={gx},{gy} {self.playerone.gamemap.grid[gx][gy]}')
					except IndexError as e:
						logger.error(f'indexerror:{e} mouse {mx},{my} grid={gx},{gy} ')

			self.update_bombs()
			self.update_flames()
			self.update_blocks()
			self.update_particles()

			# check map grids...
			# needrefresh = False
			# for b in self.blocks:
			# 	x,y = b.gridpos
			# 	try:
			# 		if self.playerone.gamemap.grid[x][y].get("blktype") != b.block_type:
			# 			needrefresh = True
			# 	except (IndexError, AttributeError) as e:
			# 		logger.error(f'{e} bcheck {b} btype={b.block_type} != p1grid={self.playerone.gamemap.grid}')
			# 		needrefresh = True
			# 		break
			# 	try:
			# 		self.playerone.gamemap.grid[x][y] = {'blktype':b.block_type, 'bomb':False}
			# 	except (IndexError, AttributeError) as e:
			# 		logger.error(f'{e} x={x} y={y} b={b} p1gridlen={len(self.playerone.gamemap.grid)} grid={self.playerone.gamemap.grid}')
			# 		needrefresh = True
			# 		break
			# 		#logger.warning(f'bcheck: mismatch {b} btype={b.block_type} != client={self.playerone.gamemap.grid[x][y].get("blktype")}')
			# if needrefresh:
			# 	self.updategrid(self.playerone.gamemap.grid)
			# 	#self.playerone.send_refreshgrid()
	
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
			newbomb = Bomb(pos=bombpos, bomber_id=bomber_id, gridpos=bombgridpos, bombpower=bombpower, rm=self.rm)
			bx,by = newbomb.gridpos
			self.playerone.gamemap.grid[bx][by] = {'blktype':11, 'bomb':False}
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
				logger.warning(f'newnetpos clid mismatch clid={client_id} != {self.playerone.client_id} ') # np={newpos} ngp={newgridpos} posdata={posdata} ')
			self.playerone.pos = posdata.get('newpos')
			self.playerone.gridpos = posdata.get('newgridpos')

			#self.playerone.pos = Vector2(newpos[0], newpos[1])
			self.playerone.rect.x = self.playerone.pos[0]
			self.playerone.rect.y = self.playerone.pos[1]
			grid_data = posdata.get('griddata')

			if len(self.blocks) != len(self.playerone.gamemap.grid[0])**2 or len(self.blocks) == 0 or not self.playerone.gotmap or len(self.playerone.gamemap.grid) == 0:
				if len(self.blocks) == 0 or not self.playerone.gotmap:
					pass
				else:
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
			self.playerone.gamemap.grid[x][y] = {'blktype':11, 'bomb':False}
			self.blocks.add(nb)

		elif msgtype == 'poweruppickup':
			nb = gamemsg.get('blockdata')
			x,y = nb.gridpos
			self.playerone.gamemap.grid[x][y] = {'blktype':11, 'bomb':False}
			self.blocks.add(nb)

		elif msgtype == 'newblock':
			nb = gamemsg.get('blockdata')
			ob = gamemsg.get('oldblock')
			ox,oy = ob.gridpos
			x,y = nb.gridpos
			self.playerone.gamemap.grid[x][y] = {'blktype':nb.block_type, 'bomb':False}
			self.blocks.add(nb)
			# self.updategrid(self.playerone.gamemap.grid)

		elif msgtype == 'c_ngu':
			old_blkcnt = len(self.blocks)
			gridpos = gamemsg.get('blkgridpos')
			x,y = gridpos
			blktype = gamemsg.get("blktype")
			bclid = gamemsg.get('bclid')
			clientid = gamemsg.get('client_id')
			newblock = Block(pos=(x*BLOCK, y*BLOCK), gridpos=gridpos, block_type=blktype, client_id=bclid, rm=self.rm)
			if self.playerone.client_id == bclid or self.playerone.client_id == clientid:
				pass
				# logger.warning(f'netgridupdate from self {self.playerone.client_id} gamemsg={gamemsg}')
			else:
				logger.info(f'{msgtype} from netplayer b={bclid} bc={clientid} p1={self.playerone.client_id} gamemsg={gamemsg}')
			if self.playerone.gamemap.grid[x][y].get("blktype") != blktype:
				logger.warning(f'{msgtype} mismatch {self.playerone.client_id} gamemsg={gamemsg}')
			self.playerone.gamemap.grid[x][y] = {'blktype':blktype, 'bomb':False}
			for b in self.blocks:
				if b.gridpos == newblock.gridpos:
					logger.warning(f'{msgtype} block already exists b={b.block_type} nb={newblock.block_type}')
					b.kill()
			self.blocks.add(newblock)
			blkcnt = len(self.blocks)
			logger.info(f'{msgtype} bclid={bclid} clientid={clientid} newblock={newblock} {self.playerone.gamemap.grid[x][y].get("blktype")} blkcnt={blkcnt}/{old_blkcnt}')

		elif msgtype == 's_gamemapgrid':
			grid = gamemsg.get('grid', None)
			newpos = gamemsg.get('newpos')
			newgridpos = gamemsg.get('newgridpos')
			self.updategrid(grid)
			logger.debug(f's_gamemapgrid np={newpos} ngp={newgridpos} p1={self.playerone}')
	
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
					blktype =  self.playerone.gamemap.grid[j][k].get("blktype")
				except (IndexError, TypeError) as e:
					logger.error(f'updategrid: {e} blktype={blktype} j={j} k={k} idx={idx} p1gridlen={len(self.playerone.gamemap.grid)}') # gmg={self.playerone.gamemap.grid[j][k]}
					logger.error(f'grid={self.playerone.gamemap.grid}')
					break

				if not blktype:
					logger.error(f'updategrid: blktype={blktype} j={j} k={k} idx={idx} p1gridlen={len(self.playerone.gamemap.grid)}')
					logger.error(f'grid={self.playerone.gamemap.grid}')
					break
				try:
					newblock = Block(Vector2(j * BLOCK, k * BLOCK), (j, k), block_type=blktype, client_id=self.playerone.client_id, rm=self.rm)
					newblks.add(newblock)
					idx += 1
				except Exception as e:
					logger.error(f'updategrid: {e} blktype={blktype} j={j} k={k} idx={idx} p1gridlen={len(self.playerone.gamemap.grid)}')
					logger.error(f'grid={self.playerone.gamemap.grid}')
		self.blocks.empty()
		self.blocks = newblks
		blkchk = len(self.playerone.gamemap.grid) ** 2
		if blkchk == len(self.blocks) or old_blkcnt == 0:
			logger.debug(f'gridlen={len(self.playerone.gamemap.grid)} block count was {old_blkcnt} now={len(self.blocks)} idx:{idx} self.updategridcnt={self.updategridcnt}')
		else:
			logger.error(f'gridlen={len(self.playerone.gamemap.grid)} block count mismatch was {old_blkcnt} now={len(self.blocks)} idx:{idx} self.updategridcnt={self.updategridcnt}')
	
	def update_blocks(self):
		# self.particles.update(self.blocks, self.screen)
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
					self.playerone.gamemap.grid[x][y] = {'blktype':11, 'bomb':False}
					nb = Block(b.pos, b.gridpos, block_type=11, client_id=b.client_id, rm=self.rm)
					logger.debug(f'p1={self.playerone} poweruppickup b={b} nb={nb} grid[x][y].get("blktype")={self.playerone.gamemap.grid[x][y].get("blktype")} bgridpos={b.gridpos} timer:{pygame.time.get_ticks() - b.start_time} >= {b.timer}')
					pygame.event.post(Event(USEREVENT, payload={'msgtype': 'poweruppickup', 'blockdata': nb}))
					b.kill()
				# if block is powerup, check timer
				if pygame.time.get_ticks() - b.start_time >= b.timer:
					nx = b.gridpos[0]
					ny = b.gridpos[1]
					self.playerone.gamemap.grid[nx][ny] = {'blktype':11, 'bomb':False}
					nb = Block(b.pos, b.gridpos, block_type=11, client_id=b.client_id, rm=self.rm)
					logger.debug(f'poweruptimeout b={b} nb={nb} grid[x][y].get("blktype")={self.playerone.gamemap.grid[nx][ny]} bgridpos={b.gridpos} timer:{pygame.time.get_ticks() - b.start_time} >= {b.timer}')
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
				nb = Block(pos=pos, gridpos=bomb.gridpos, block_type=11, client_id=bomb.bomber_id, rm=self.rm)
				pygame.event.post(Event(USEREVENT, payload={'msgtype': 'newblock', 'blockdata': nb, 'oldblock':bomb}))
				self.playerone.gamemap.grid[bx][by] = {'blktype':nb.block_type, 'bomb':False}
				flames = bomb.exploder()
				flamemsg = Event(USEREVENT, payload={'msgtype': 'flames', 'flamedata': flames})
				pygame.event.post(flamemsg)
				bomb.kill()
	
	def update_flames(self):
		if len(self.flames) == 0:
			return
		self.flames.update(surface=self.screen)
		for flame in self.flames:			
			# for player in spritecollide(flame, self.playerone, False):
			# 	if pygame.Rect.colliderect(flame.rect, player.rect):
			# 		player.flame_hit(flame)
			# 		flame.kill()
			# 		if player.hearts <= 0:
			# 			logger.info(f'{player} killed by {flame}')
			# 			player.kill = True
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
						self.playerone.gamemap.grid[x][y] = {'blktype':newblock.block_type, 'bomb':False}
						blockmsg = Event(USEREVENT, payload={'msgtype': 'newblock', 'blockdata': newblock, 'oldblock':block})
						pygame.event.post(blockmsg)
						flame.kill()
						block.kill()
	
	def update_particles(self):
		self.particles.update(self.blocks)
	
	def draw(self):
		try:
			pygame.display.update()
		except:
			pass
		self.gameclock.tick(FPS)
		self.screen.fill(self.bg_color)
		self.blocks.draw(self.screen)
		self.bombs.draw(self.screen)
		self.flames.draw(self.screen)
		self.particles.draw(self.screen)
		if self.playerone.gotpos and self.playerone.ready:
			self.playerone.draw(self.screen)
			self.gui.game_menu.draw_panel(screen=self.screen, blocks=self.blocks, particles=self.particles, playerone=self.playerone, flames=self.flames, grid=self.playerone.gamemap.grid)
		for npid in self.playerone.netplayers:
			npitem = self.playerone.netplayers[npid]
			x,y = self.playerone.netplayers[npid].get('pos', None)
			pos = [x,y]
			if self.playerone.client_id != npid:
				pygame.draw.circle(self.screen, color=(0,0,255), center=pos, radius=10)
		# 	try:
		# 		x,y = self.playerone.netplayers[npid].get('pos', None)
		# 	except TypeError as e:
		# 		logger.error(f'err:{e} np={npid} npitem={npitem} ')
		# 		break
		# 	pos = [x,y]
		# 	gpos = self.playerone.netplayers[npid].get('gridpos', None)
		# 	if self.playerone.client_id != npid:
		# 		#pos -= (0,5)
		# 		#pos[1] -=10
		# 		# self.font.render_to(self.screen, pos, f'{np}', (255, 255, 255))
		# 		pos[0] += 15
		# 		pos[1] += 15
		# 		pygame.draw.circle(self.screen, color=(0,0,255), center=pos, radius=10)
		# 		#pos = self.playerone.netplayers[npid].get('pos')
		# 		#self.font.render_to(self.screen, pos, f'{np}', (255, 55, 55))
		# 	if npid == self.playerone.client_id:
		# 		pos[0] += 15
		# 		pos[1] += 15
		# 		pygame.draw.circle(self.screen, color=(0,255,0), center=pos, radius=2)
				#self.font.render_to(self.screen, pos , f'{np}', (123, 123, 255))

		if self.gui.show_mainmenu:
			self.gui.game_menu.draw_mainmenu(self.screen)
	
	def draw_debug(self):
		pos = Vector2(10, self.screenh - 100)
		self.font.render_to(self.screen, pos, f"blklen:{len(self.blocks)} b:{len(self.bombs)} fl:{len(self.flames)} p:{len(self.particles)}  ", (173, 173, 173))
		pos += (0, 15)
		self.font.render_to(self.screen, pos, f"fps={self.gameclock.get_fps():.2f} threads:{threading.active_count()}  p1 np:{len(self.playerone.netplayers)} ", (183, 183, 183))
		pos += (0, 15)
		self.font.render_to(self.screen, pos, f"p1 pos {self.playerone.pos} {self.playerone.gridpos} cpos {self.playerone.pos} {self.playerone.gridpos}", (183, 183, 183))
		pos += (0, 15)
		try:
			self.font.render_to(self.screen, pos, f"client {self.playerone} clt={self.playerone.cl_timer} sendq={self.playerone.sender.queue.qsize()} pq={self.playerone.payloadqueue.qsize()}", (183, 183, 183))
		except:
			pass
		if self.extradebug:
			pos = self.playerone.pos
			self.font.render_to(self.screen, pos, f'{self.playerone.gridpos}', (255,255,255))
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
				else:
					self.font.render_to(self .screen, (textpos[0]+12, textpos[1]+12), f"{b.block_type}", (255, 1, 255))
	
	def handle_menu(self, selection):
		# mainmenu
		if selection == "Start":
			self.gui.show_mainmenu ^= True
			self.playerone = Player(dummy=False, serverargs=self.args)
			conn = self.playerone.connect_to_server()
			logger.debug(f'p1conn={conn}')
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
	
	def handle_input(self, keypressed):
		#events = pygame.event.get()
		#for event in events:
		if keypressed in (pygame.K_SPACE, pygame.K_RETURN,32,13,r'\r'):
			if self.gui.show_mainmenu:  # or self.paused:
				selection = self.gui.game_menu.get_selection()
				print(selection)
				self.handle_menu(selection)
			elif not self.gui.show_mainmenu:
				self.playerone.send_bomb()
		elif keypressed in  (pygame.K_ESCAPE, 27):
			self.gui.show_mainmenu ^= True
		elif keypressed in(pygame.K_q, 113,'q','Q'):
			# quit game
			self.playerone.disconnect()
			self.kill = True
			self.running = False
		elif keypressed == pygame.K_1:
			self.playerone.send_maprequest(gridsize=15)
		elif keypressed == pygame.K_2:
			self.playerone.send_maprequest(gridsize=10)
		elif keypressed == pygame.K_3:
			self.playerone.send_maprequest(gridsize=13)
		elif keypressed == pygame.K_4:
			self.playerone.send_maprequest(gridsize=18)
		elif keypressed == pygame.K_5:
			self.playerone.send_maprequest(gridsize=22)
		elif keypressed == pygame.K_6:
			self.playerone.send_refreshgrid()
			# logger.debug(f'send_refreshgrid p1gz={self.playerone.gamemap.gridsize} p1={self.playerone}')
		elif keypressed == pygame.K_0:
			self.extradebug ^= True
			logger.info(f'{self} extradebug={self.extradebug}')
		elif keypressed == pygame.K_f:
			pass
		elif keypressed == pygame.K_e:
			pass
		elif keypressed == pygame.K_p:
			logger.info(f'p1={self.playerone} cltimer={self.playerone.cl_timer} st={self.playerone.start_time} pytick={pygame.time.get_ticks()}')
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
		elif keypressed == pygame.K_n:
			self.playerone.bombs_left += 3
			self.playerone.hearts += 3
			self.playerone.bombpower += 30
		elif keypressed == pygame.K_g:
			pass
		elif keypressed == pygame.K_r:
			pass
		elif keypressed in {pygame.K_DOWN, pygame.K_s, 's',115}:
			if self.gui.show_mainmenu:
				self.gui.game_menu.menu_down()
			else:
				try:
					self.playerone.move("down")
				except IndexError as e:
					logger.warning(f'err={e} {self.playerone} {self.playerone}')
				#self.playerone.vel.y = self.playerone.speed
				#self.playerone.vel.x = 0
		elif keypressed in {pygame.K_UP, pygame.K_w, 'w',119}:
			if self.gui.show_mainmenu:
				self.gui.game_menu.menu_up()
			else:
				try:
					self.playerone.move("up")
				except IndexError as e:
					logger.warning(f'err={e} {self.playerone} {self.playerone}')
				#self.playerone.vel.y = -self.playerone.speed
				#self.playerone.vel.x = 0
		elif keypressed in {pygame.K_RIGHT, pygame.K_d, 'd', 100}:
			if not self.gui.show_mainmenu:
				try:
					self.playerone.move("right")
				except IndexError as e:
					logger.warning(f'err={e} {self.playerone} {self.playerone}')
				#self.playerone.vel.x = self.playerone.speed
				#self.playerone.vel.y = 0
		elif keypressed in {pygame.K_LEFT, pygame.K_a, 'a', 97}:
			if not self.gui.show_mainmenu:
				try:
					self.playerone.move("left")
				except IndexError as e:
					logger.warning(f'err={e} {self.playerone} {self.playerone}')
				#self.playerone.vel.x = -self.playerone.speed
				#self.playerone.vel.y = 0
		else:
			logger.warning(f'unhandled key keypressed={keypressed} {type(keypressed)}')

def main(args):
	pygame.init()
	game = Game(args)
	game.daemon = True
	game.running = True
	game.run()
	while game.running:
		if game.kill:
			game.running = False
			break
	pygame.quit()


if __name__ == "__main__":
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--server',  action='store', dest='server', default='localhost')
	parser.add_argument('--port',  action='store', dest='port', default=9696)
	args = parser.parse_args()
	if args.testclient:
		pass

	#pygame.display.set_mode((800,600), 0, 8)
	main(args)


