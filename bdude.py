#!/usr/bin/python
# bomberdude
# todo:
# make map 10xbigger and scrollable, with minimap
# create gamemodes; with timelimit, most kills or highest score wins
# move network things from player.py to bdude or somewhere else...?
# add more upgrades, like speed, kick, punch, etc
# fix player.move logic
# upgrade blocks should not be part of grid
# - grid from server should only show non-upgrade and non-killable blocks
# - upgrade blocks should be added to a separate group

import os
import sys
import time
import random
from argparse import ArgumentParser
import threading
from threading import Thread
from threading import Event as TEvent
from threading import current_thread, Timer, active_count, _enumerate
import socket
from queue import Queue
import pygame
from loguru import logger
from pygame.event import Event
from pygame.sprite import Group, spritecollide, Sprite, collide_rect
from pygame import USEREVENT
from constants import BLOCK
from constants import DEFAULTFONT
from globals import ResourceHandler, NewBlock, UpgradeBlock, NewBomb, NewFlame, get_bomb_flames, Particle
from globals import RepeatedTimer
from menus import GameMenu
from player import  NewPlayer
from bombserver import Gameserver, NewHandler
FPS = 60

class Game(Thread):
	def __init__ (self, args=None):
		Thread.__init__(self, name='Gamethread')
		self._stop = TEvent()
		self.server_running = False
		self.args = args
		self.killed = False
		self.running = False
		self.display = pygame.display.set_mode((800,800)) # pygame.display.set_mode(size=(800,800), flags=pygame.DOUBLEBUF, vsync=1).get_surface()
		# self.display = pygame.display.get_surface()
		# self.displayw, self.displayh = pygame.display.get_surface().get_size()
		self.game_menu = GameMenu(self.display)
		self.show_mainmenu = True
		self.clock = pygame.time.Clock()
		self.game_started = False
		self.rh = ResourceHandler()
		self.player = NewPlayer(image=self.rh.get_image('data/playerone.png'), rh=self.rh, serveraddress=(self.args.server, self.args.port))
		self.bombs = Group()
		self.flames = Group()
		self.particles = Group()
		self.blocks = Group()
		self.upgradeblocks = Group()
		# self.sprites = Group()
		# self.sprites.add(self.bombs)
		# self.sprites.add(self.flames)
		# self.sprites.add(self.blocks)
		self.debugfont = pygame.freetype.Font(DEFAULTFONT, 8)
		self.font = pygame.freetype.Font(DEFAULTFONT, 22)
		self.debugmode = self.args.debug
		self.blockdebug = False

	def __repr__(self):
		return f'bdude ( p:{self.player} pl:{len(self.player.playerlist)} s:{self.server_running} )'

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	def handle_events(self, payload):
		msgtype = payload.get('msgtype')
		# logger.debug(f'{msgtype}')
		match msgtype:
			case 'startgame':
				self.start_game()
			case 'start_server':
				self.start_server()
			case 'connect_to_server':
				self.connect_to_server()
			case 'bombxplode':
				# create flames from bomb
				# logger.debug(f'{msgtype} {payload}')
				image = self.rh.get_image(f'data/flame1.png')
				newflames = get_bomb_flames(payload.get("gridpos"), payload.get("bomberid"), image)
				self.flames.add(newflames)
				if payload.get("bomberid") == self.player.client_id:
					self.player.bombsleft += 1
			case 'sv_gridupdate':
				logger.debug(f'{msgtype} blks: {len(self.blocks)}')
				self.update_screen()
				#self.create_blocks_from_grid()

			case 'trigger_newplayer_grid': # triggered for new player, update gridblocks
				newgrid = payload.get('grid', None)
				if newgrid:
					self.update_screen()
					# self.create_blocks_from_grid()
					logger.debug(f'{msgtype} blks: {len(self.blocks)} p: {self.player}')
				else:
					logger.error(f'{msgtype} gotgrid: {self.player.gotgrid} : {payload} ')

			case 'newgridfromserver':
				if self.show_mainmenu:
					self.show_mainmenu = False
				newgrid = payload.get('grid', None)
				if newgrid:
					self.update_screen()
					# self.create_blocks_from_grid()
					logger.debug(f'{msgtype} p1gg: {self.player.gotgrid} blks: {len(self.blocks)}')
				else:
					logger.error(f'{msgtype} gotgrid: {self.player.gotgrid} : {payload} ')

			case 'ackplrbmb':
				# create bomb with timer and add to sprites
				bombimg = self.rh.get_image(filename='data/bomb1.png', force=False)
				bid = payload.get('client_id')
				bpos = payload.get('pos')
				gpos = payload.get('gridpos')
				clbombpos = payload.get('clbombpos')
				# logger.info(f'{msgtype} {bid} {bpos} {gpos} {clbombpos}')
				try:
					newbomb = NewBomb(bombimg, bomberid=bid, gridpos=clbombpos,  bombtimer=2000)
					self.bombs.add(newbomb)
				except TypeError as e:
					logger.warning(f'{e} {type(e)} msgtype:{msgtype} payload: {payload}')
				except Exception as e:
					logger.error(f'{e} {type(e)} msgtype:{msgtype} payload: {payload}')
			case _ :
				logger.warning(f'unknown event {payload}')

	def check_coll(self):
		# flames = Group([k for k in self.sprites if isinstance(k, NewFlame)])
		# blocks = Group([k for k in self.sprites if isinstance(k, NewBlock)])
		self.player_collide()
		self.flame_collide()
		self.particle_collide()
		for block in self.upgradeblocks: # check block collisions with player
			match block.blocktype:
				case 40: # extrabomb
					if collide_rect(block, self.player):
						self.player.bombsleft += 1 # todo fix this, server should keep track of this
						logger.info(f'extrabomb t:{block.blocktype} player: {self.player}')
						block.kill()
				case 44: # healthup
					if collide_rect(block, self.player):
						self.player.health += 1  # todo fix this, server should keep track of this
						logger.info(f'healthup t:{block.blocktype} player: {self.player}')
						block.kill()

	def particle_collide(self):
		for p in self.particles:
			colls = spritecollide(p, self.blocks, dokill=False)
			for c in colls:
				if c.blocktype != 2:
					p.bounce(c)
					# p.vel[0] = - p.vel[0]
					# p.vel[1] = - p.vel[1]
			# [p.kill() for c in colls if c.blocktype != 2]

	def player_collide(self):
		for f in self.flames: # check flame collisions with player
			if collide_rect(f, self.player):
				f.kill()
				self.player.health -= f.damage # todo fix this, server should keep track of this
				if self.player.health <= 0: # dead
					self.player.playerlist[f.bomberid]['score'] += 1 # increase score of bomber
					logger.warning(f'playerkilled {self.player.client_id} by f: {f.bomberid} ') # pl:{self.player.playerlist[f.bomberid]}
					# todo restart game and reset player or whatever
					self.player.playerlist[self.player.client_id]['health'] = 100
					self.player.health = 100
					self.player.playerlist[self.player.client_id]['score'] = 0
					self.player.score = 0
					self.player.playerlist[self.player.client_id]['bombsleft'] = 3
					self.player.bombsleft = 3
					# update server
					payload = {'msgtype' : 'cl_playerkilled', 'client_id': self.player.client_id, 'playerlist' :self.player.playerlist }
					self.player.send_queue.put(payload, block=True)
				else:
					logger.info(f'playerflamedamage f: {f.bomberid} ph: {self.player.health}')


	def flame_collide(self): # check flame collisions with blocks, creates particles
		for f in self.flames:
			colls = spritecollide(f, self.blocks, dokill=False)
			for c in colls:
				fgpos = (f.pos[0] // BLOCK, f.pos[1] // BLOCK)
				if c.blocktype != 2:
					particles = [Particle(gridpos=fgpos, vel=[random.uniform(-1.5,1.5),random.uniform(-1.5,1.5)] )for k in range(15)]
					self.particles.add(particles)
				match c.blocktype:
					case 1: # edge solid unkillable
						f.kill()
					case 2: # backgroundblock
						pass
					case 3: # killable block, no upgrade, turns into backgroundblock
						x = c.gridpos[0]
						y = c.gridpos[1]
						self.player.grid[x][y] = 2 # background
						image = self.rh.get_image(f'data/blocksprite2.png')
						self.blocks.add(NewBlock(gridpos=fgpos, image=image, blocktype=2))
						payload = {'msgtype' : 'cl_gridupdate', 'gridpos': c.gridpos, 'blocktype':2, 'client_id': self.player.client_id, 'grid' :self.player.grid }
						self.player.send_queue.put(payload, block=True) # tell server
						c.kill() # kill block and flame
						f.kill()
					case 4: # solid killable creates upgradeblock type 40/44
						# todo make server decide on upgrades....
						x = c.gridpos[0]
						y = c.gridpos[1]
						self.player.grid[x][y] = 2 # background
						upgrade_type = random.choice([40,44])
						# self.player.grid[x][y] = upgrade_type
						if upgrade_type == 40:
							image = self.rh.get_image(f'data/newbomb.png')
						if upgrade_type == 44:
							image = self.rh.get_image(f'data/heart.png')
						# image = self.rh.get_image(f'data/blocksprite2.png')
						self.upgradeblocks.add(UpgradeBlock(gridpos=fgpos, image=image, blocktype=upgrade_type)) # type 44 = heart
						payload = {'msgtype' : 'cl_gridupdate', 'gridpos': c.gridpos, 'blocktype':upgrade_type, 'client_id': self.player.client_id, 'grid' :self.player.grid }
						self.player.send_queue.put(payload, block=True) # tell server and kill block and flame
						c.kill()
						f.kill()
					case 5: # solid unkillable
						f.kill()
					case _:
						logger.warning(f'unknown blocktype {c}')

	def run_updates(self):
		try:
			self.check_coll()
		except KeyError as e:
			logger.error(e)
		self.bombs.update()
		self.flames.update()
		self.particles.update()
		self.blocks.update()
		self.upgradeblocks.update()
		self.player.update()

	def drawblocks(self):
		#draws the grid
		# block=BLOCK
		x = 0
		y = 0
		# blks = Group()
		newsurf = pygame.Surface((len(self.player.grid[0])*BLOCK,len(self.player.grid)*BLOCK))
		for row in self.player.grid:
			x=0
			for k in row:
				k = int(k)
				image = self.rh.get_image(f'data/blocksprite{k}.png')
				b = NewBlock(gridpos=(y,x), image=image, blocktype=k)
				b.draw(newsurf)
				#self.blocks.add(NewBlock(gridpos=(y,x), image=image, blocktype=k)) # swap x,y for gridpos
				x += 1 # BLOCK
			y += 1 # BLOCK
		self.display.blit(newsurf, (0,0))

	def update_screen(self):
		#draws the grid
		# block=BLOCK
		x = 0
		y = 0
		# blks = Group()
		self.blocks.empty()
		for row in self.player.grid:
			x=0
			for k in row:
				k = int(k)
				image = self.rh.get_image(f'data/blocksprite{k}.png')
				self.blocks.add(NewBlock(gridpos=(y,x), image=image, blocktype=k)) # swap x,y for gridpos
				x += 1 # BLOCK
			y += 1 # BLOCK
		# self.display.blit(newsurf, (0,0))

	def _update_screen(self):
		self.display = pygame.Surface((len(self.player.grid[0])*BLOCK,len(self.player.grid)*BLOCK))
		x,y = 0,0
		for row in self.player.grid:
			for tile in row:
				if tile == 1:
					pygame.draw.rect(self.display,(0,155,0),((x,y),(BLOCK,BLOCK)))
				elif tile == 2:
					pygame.draw.rect(self.display,(125,125,125),((x,y),(BLOCK,BLOCK)))
				else:
					pygame.draw.rect(self.display,(255,128,122),((x,y),(BLOCK,BLOCK)))
				x += BLOCK
			y += BLOCK
			x = 0

	def drawblocks_debug(self):
		for b in self.blocks:
			blktxt = self.debugfont.render(f'{self.player.grid[b.gridpos[0]][b.gridpos[1]]}', (55,155,55))
			self.display.blit(blktxt[0], (b.rect.x+5, b.rect.y+3))
			# blktxt = self.debugfont.render(f'{b.rect.x}.{b.rect.y}', (75,165,155)) # self.debugfont.render(f'{b.gridpos}', (75,165,155))
			blktxt = self.debugfont.render(f'{b.gridpos}', (75,165,155)) # self.debugfont.render(f'{b.gridpos}', (75,165,155))
			self.display.blit(blktxt[0], (b.rect.x+2, b.rect.y+15))
		# 	try:
		# 		self.debugfont.render_to(self.display, (b.rect.x+5, b.rect.y+3),blktxt, (55,155,55))
		# 	except TypeError as e:
		# 		logger.warning(f'{e} b:{b} {type(b)} blktxt: {blktxt} ')
		# for b in self.upgradeblocks:
		# 	blktxt = f'{self.player.grid[b.gridpos[0]][b.gridpos[1]]}'
		# 	self.debugfont.render_to(self.display, (b.rect.x+7, b.rect.y+7),blktxt, (255,255,255))
		# 	blktxt = f'{b.gridpos}'
		# 	self.debugfont.render_to(self.display, (b.rect.x+15, b.rect.y+13),blktxt, (255,255,255))

	def request_debug_info(self):
		payload = {'msgtype' : 'cl_serverdebug',} # request serverdebuginfo when in debugmode
		self.player.send_queue.put(payload, block=True) # tell server and kill block and flame

	def draw_debug_info(self):
		w,h = self.display.get_size()
		txtpos = [10,h]
		dbgitems = []
		dbgitems.append(self.debugfont.render(f'fps: {self.clock.get_fps():.2f} blks:{len(self.blocks)} b:{len(self.bombs)} f:{len(self.flames)} p:{len(self.particles)} ub:{len(self.upgradeblocks)}  ', (255,255,255)))
		dbgitems.append(self.debugfont.render(f'pc: {self.player.updcntr} rc: {self.player.runcounter} s: {self.player.sendcounter} r: {self.player.recvcounter} rq: {self.player.receiverq.qsize()} sq: {self.player.send_queue.qsize()} mq: {self.player.msg_queue.qsize()}', (255,255,255)))
		dbgitems.append(self.debugfont.render(f'threads: {active_count()} server: {self.server_running}  ', (255,255,255)))
		if len(self.player.debuginfo['server']) > 0:
			dbgitems.append(self.debugfont.render(f'sv_updcntr: {self.player.debuginfo["server"].get("sv_updcntr")}', (255,255,255)))
			for k in self.player.debuginfo.get('server').get('clients'):
				dbgitems.append(self.debugfont.render(f'id: {k.get("client_id")} handlerq: {k.get("handlerq")}', (255,255,255)))
		for d in dbgitems:
			txtpos[1] -= 10
			self.display.blit(d[0], txtpos)

	def draw_game_info(self):
		surf, rect1 = self.font.render(f'h: {self.player.health} bombs: {self.player.bombsleft} score: {self.player.score}', (255,255,255))
		self.display.blit(surf, (10,10))
		surf, rect = self.font.render(f'{self.player.health} ', (5,255,55)) # {self.player.playerlist[self.player.client_id]["health"]}
		self.display.blit(surf, (self.player.pos))
		for np in self.player.playerlist:
			if np != self.player.client_id:
				surf, rect = self.font.render(f'h: {self.player.playerlist[np]["health"]} bombs: {self.player.playerlist[np]["bombsleft"]} score: {self.player.playerlist[np]["score"]}', (155,255,255))
				self.display.blit(surf, (rect1.width+30,10))
				surf, rect = self.font.render(f'{self.player.playerlist[np]["health"]} ', (255,5,55))
				self.display.blit(surf, (self.player.playerlist[np]["pos"]))

	def run_draw(self):
		pygame.display.flip()
		if self.show_mainmenu:
			self.game_menu.draw_mainmenu()
			return
		elif self.player.gotpos and self.player.gotgrid:
			# self.blocks.draw(self.display)
			self.display.fill((0,0,0))
			self.drawblocks()
			self.draw_game_info()
			if self.blockdebug:
				self.drawblocks_debug()
			if self.debugmode:
				self.draw_debug_info()

			self.bombs.draw(self.display)
			self.flames.draw(self.display)
			self.upgradeblocks.draw(self.display)
			self.particles.draw(self.display)
			self.player.draw(self.display)

	def run(self):
		while True:
			if self.stopped():
				logger.debug(f'{self} stopped')
				return
			self.clock.tick(FPS)
			if self.player.gotpos and self.player.gotgrid:
				self.run_updates()
			self.run_draw()
			events_ = pygame.event.get()
			for event in events_:
				# USEREVENT
				e_type = int(event.type)
				maxe = pygame.USEREVENT+1000
				match e_type:
					case int(e_type) if maxe >= e_type >= pygame.USEREVENT:
						# logger.debug(f'{event.payload}')
						self.handle_events(event.payload)
					case pygame.KEYDOWN:
						try:
							self.handle_input_events(event)
						except IndexError as e:
							logger.error(f'{e} {type(e)}')
					case pygame.MOUSEBUTTONDOWN:
						self.handle_mouse_event(event)
					case pygame.QUIT:
						self.stop()
						self.player.stop()
						self.player.receiver_t.kill = True
						self.running = False
						self.killed = True
						self.player.kill = True
						self.player.connected = False
						self.killed = True
						logger.info(f'{self} pygameeventquit {event.type} events: {len(events_)}')
						return

	def start_game(self):
		if self.game_started:
			logger.warning(f'{self} game already started')
			# return
		logger.info(f'{self} startgame')
		self.display.fill((0,0,0))
		self.player.start()
		logger.debug(f'{self.player} started')
		self.game_started = True
		self.show_mainmenu = False

	def server_thread(self): # todo threading.lock for this
		mainsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		mainsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		connq = Queue()
		server = Gameserver(connq, mainsocket, None)
		server.start()
		logger.info(f'{self} server: {server}')
		server.tui.start()
		logger.info(f'{self} server: {server} {server.tui}')
		try:
			mainsocket.bind((self.args.listen,self.args.port))
		except OSError as e:
			logger.error(e)
		conncounter = 0
		self.server_running = True
		while True:
			mainsocket.listen()
			try:
				conn, addr = mainsocket.accept()
			except KeyboardInterrupt as e:
				logger.warning(f'{e}')
				break
			except Exception as e:
				logger.warning(f'{e} {type(e)}')
				break
			thread = NewHandler(conn,addr, server.dataq, name=f'clthrd{conncounter}')
			server.clients.append(thread)
			thread.start()
			conncounter += 1
			logger.info(f'{self} {server} NewHandler started {thread} conn: {conncounter} clients: {len(server.clients)}')
			server.trigger_newplayer()

	def connect_to_server(self):
		logger.info(f'{self}')

	def start_server(self): # start a local server thread ....
		logger.info(f'{self} ')
		ts = Thread(target=self.server_thread, name='serverthread', daemon=True)
		logger.debug(f'starting {ts}')
		ts.start()

	def handle_input_events(self, event):
		keypressed = event.key
		if keypressed in(pygame.K_q, 113,'q','Q'):
			logger.info(f'keyquit {keypressed} ')
			pygame.event.post(Event(pygame.QUIT))
		elif keypressed in {pygame.K_DOWN, pygame.K_s}:
			if self.show_mainmenu:
				self.game_menu.menu_down()
				logger.debug(f'item: {self.game_menu.active_item}')
			else:
				self.player.move('d')
		elif keypressed in {pygame.K_UP, pygame.K_w}:
			if self.show_mainmenu:
				self.game_menu.menu_up()
				logger.debug(f'item: {self.game_menu.active_item}')
			else:
				self.player.move('u')
		elif keypressed in {pygame.K_RIGHT, pygame.K_d}:
			if not self.show_mainmenu:
				self.player.move('r')
		elif keypressed in {pygame.K_LEFT, pygame.K_a}:
			if not self.show_mainmenu:
				self.player.move('l')
		elif keypressed == pygame.K_SPACE:
			# handle menu selection
			if not self.show_mainmenu:
				if self.player.bombsleft > 0:
					self.player.sendbomb()
				else:
					logger.warning(f'no bombs left player: {self.player}')
			else:
				if self.game_menu.active_item == 'Start':
					if not self.game_started:
						ev = Event(USEREVENT, payload={'msgtype': 'startgame',})
						pygame.event.post(ev)
						# logger.debug(f'e:{event} k:{keypressed} K_SPACE item: {self.game_menu.active_item} ev: {ev}')
					else:
						logger.warning(f'game already started') # todo handle this
						ev = Event(USEREVENT, payload={'msgtype': 'startgame',})
						pygame.event.post(ev)
				if self.game_menu.active_item == 'Connect to server':
					pygame.event.post(Event(USEREVENT, payload={'msgtype': 'connect_to_server',}))
				if self.game_menu.active_item == 'Start server':
					pygame.event.post(Event(USEREVENT, payload={'msgtype': 'start_server',}))
				if self.game_menu.active_item == 'Quit':
					pygame.event.post(Event(pygame.QUIT))
		elif keypressed == pygame.K_F1:
			# toggle debug
			self.debugmode = not self.debugmode
			dbgtimer = RepeatedTimer(interval=1, function=self.request_debug_info)
			logger.debug(f'toggledebug')
		elif keypressed == pygame.K_F2:
			# toggle blockdebug
			self.blockdebug = not self.blockdebug
			logger.debug(f'blockdebug')
		elif keypressed == pygame.K_F10:
			# send newgrid request
			logger.debug(f'requestnewgrid')
			self.player.do_send({'msgtype': 'requestnewgrid'})
		elif keypressed == pygame.K_ESCAPE:
			# escape show/hide menu
			logger.debug(f'K_ESCAPE item: {self.game_menu.active_item} show: {self.show_mainmenu}')
			self.show_mainmenu = not self.show_mainmenu
		else:
			logger.debug(f'keypressed {keypressed} ')

	def handle_mouse_event(self, event):
		if event.type == pygame.MOUSEBUTTONDOWN:
			mx,my = pygame.mouse.get_pos()
			logger.debug(f'[mouse] {mx},{my} ')

def locker_thread(lock):
    logger.debug('locker_thread Starting')
    while True:
        lock.acquire()
        try:
            # logger.debug('locker_thread Locking')
            time.sleep(0.05)
        finally:
            # logger.debug('locker_thread Not locking')
            lock.release()
        time.sleep(0.05)
    return

def main(args):
	# lock = threading.Lock()
	# lt = Thread(target=locker_thread, args=(lock,), daemon=True)
	lock = None
	game = Game(args=args)
	logger.debug(f'main game: {game}')
	game.daemon = True
	game.running = True
	game.run()
	logger.info(f'g:{game} killed')
	for t in threading.enumerate():
		try:
			logger.debug(f'killing {t}')
			t.join(timeout=0)
		except (TypeError, RuntimeError) as e:
			pass
			#logger.error(f'{t} error: {e} {type(e)}')
	logger.debug(f'threadskilled')
	game.stop()
	logger.debug(f'gamestop')


def run_testclient(args):
	pass

if __name__ == "__main__":
	pygame.init()
	# pygame.key.set_repeat(1000,3000)
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--listen', action='store', dest='listen', default='localhost')
	parser.add_argument('--server', action='store', dest='server', default='localhost')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()
	if args.testclient:
		run_testclient(args)
	else:
		main(args)
	pygame.quit()

