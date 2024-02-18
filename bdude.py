#!/usr/bin/python
import sys
import copy
import asyncio
import json
from collections import deque
from threading import Thread
import time
from argparse import ArgumentParser
import random
from queue import Queue, Empty
import arcade
from arcade.gui import UIManager, UIBoxLayout, UITextArea,UIFlatButton,UIGridLayout
from arcade.gui.widgets.layout import UIAnchorLayout

from loguru import logger
from objects import Bomberplayer, Bomb, KeysPressed, PlayerEvent, PlayerState, GameState, gen_randid, Rectangle, UINumberLabel, UITextLabel, UIPlayerLabel
from constants import *

import zmq
from zmq.asyncio import Context, Socket
# todo get inital pos from server
# done draw netbombs
# done sync info bewteen Client and Bomberplayer
# done  update clients when new player connects
# task 1 send player input to server
# task 2 receive game state from server
# task 3 draw game

# task 1 accept connections
# taks 2 a. receive player input b. update game state
# task 3 send game state to clients

UPDATE_TICK = 60
RECT_WIDTH = 32
RECT_HEIGHT = 32


class MainMenu(arcade.View):
	def __init__(self, game):
		super().__init__()
		self.game = game
		self.manager = game.manager
		self.startbtn = UIFlatButton(text="Start New Game", width=150)
		self.connectb = UIFlatButton(text="Connect", width=150)
		self.exitbtn = UIFlatButton(text="Exit", width=150)
		self.grid = UIGridLayout(column_count=2, row_count=3, vertical_spacing=5)
		gridsb = self.grid.add(self.startbtn, col_num=0, row_num=0)
		gridcb = self.grid.add(self.connectb, col_num=0, row_num=1)
		grideb = self.grid.add(self.exitbtn, col_num=0, row_num=2)
		self.anchor = self.manager.add(UIAnchorLayout())
		self.anchor.add(anchor_x="center_x", anchor_y="center_y", child=self.grid,)

		@self.startbtn.event("on_click")
		def on_click_start_new_game_button(event):
			self.game.setup()
			self.startbtn.visible = False
			self.exitbtn.visible = False
			self.startbtn.disabled = True
			self.exitbtn.disabled = True
			self.connectb.disabled = True
			self.connectb.visible = False
			self.window.show_view(self.game)

		@self.exitbtn.event("on_click")
		def on_click_exit_button(event):
			arcade.exit()

		@self.connectb.event("on_click")
		def on_connect_to_server(event):
			self.game.setup()
			self.startbtn.visible = False
			self.exitbtn.visible = False
			self.startbtn.disabled = True
			self.exitbtn.disabled = True
			self.window.show_view(self.game)
			self.game.do_connect()
			self.game._connected = True
			self.connectb.text = f'{self.game.args.server}'
			self.connectb.disabled = True
			self.connectb.visible = False


	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_ASPARAGUS
		self.manager.enable()

	def on_draw(self):
		self.clear()
		self.manager.draw()

	def on_hide_view(self):
		self.manager.disable() # pass

class Bomberdude(arcade.View):
	def __init__(self, width, height, title='foobar', args=None):
		super().__init__()
		self.args = args
		self.debugmode = False
		self.manager = UIManager()
		self.window.center_window() # set_location(0,0)
		self.width = width
		self.height = height
		self.t = 0
		self.playerone = Bomberplayer(image="data/playerone.png",scale=0.9, client_id=gen_randid())
		self.keys_pressed = KeysPressed(self.playerone.client_id)
		self.hitlist = []
		self.player_event = PlayerEvent()
		self.game_state = GameState(game_seconds=0)
		self.ioctx = Context()
		self.sub_sock: Socket = self.ioctx.socket(zmq.SUB)
		self.push_sock: Socket = self.ioctx.socket(zmq.PUSH)
		self._connected = False
		self.physics_engine = None
		self.netplayers = []
		self.title = title
		self.eventq = Queue()
		self.graw_graphs = False
		self.poplist = []
		self.bomb_list = arcade.SpriteList(use_spatial_hash=True)
		self.particle_list = arcade.SpriteList(use_spatial_hash=True)
		self.flame_list = arcade.SpriteList(use_spatial_hash=True)
		self.netplayers = arcade.SpriteList(use_spatial_hash=True)
		self.scenewalls = arcade.SpriteList(use_spatial_hash=True)
		self.sceneblocks = arcade.SpriteList(use_spatial_hash=True)

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.game_state.players)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

	def connected(self):
		return self._connected

	def do_connect(self):
		logger.info(f'Connecting to {self.args.server}')
		self.sub_sock.connect(f'tcp://{self.args.server}:9696')
		self.sub_sock.subscribe('')
		self.push_sock.connect(f'tcp://{self.args.server}:9697')
		self._connected = True
		self.window.set_caption(f'{self.title} connected to {self.args.server} playerid: {self.playerone.client_id}')

	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_BLUE
		self.manager.enable()

	def on_hide_view(self):
		self.manager.disable()

	def setup(self):
		self.setup_panels()
		self.setup_perf()

		self.tile_map = arcade.load_tilemap('data/map3.json', layer_options={"Blocks": {"use_spatial_hash": True},}, scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)

		self.camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		self.background_color = arcade.color.AMAZON
		self.background_color = arcade.color.DARK_BLUE_GRAY
		self.scene.add_sprite_list_after("Player", "Walls")
		_ = [self.sceneblocks.append(k) for k in self.scene['Blocks'].sprite_list]
		_ = [self.scenewalls.append(k) for k in self.scene['Walls'].sprite_list]
		self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.scenewalls,platforms=self.sceneblocks, gravity_constant=GRAVITY)
		self.manager.enable()

	def setup_perf(self):
		# Create a sprite list to put the performance graphs into
		self.perf_graph_list = arcade.SpriteList()
		# Calculate position helpers for the row of 3 performance graphs
		row_y = self.height - GRAPH_HEIGHT / 2
		starting_x = GRAPH_WIDTH / 2
		step_x = GRAPH_WIDTH + GRAPH_MARGIN
		# Create the FPS performance graph
		graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="FPS")
		graph.position = starting_x, row_y
		self.perf_graph_list.append(graph)
		# Create the on_update graph
		graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="on_update")
		graph.position = starting_x + step_x, row_y
		self.perf_graph_list.append(graph)
		# Create the on_draw graph
		graph = arcade.PerfGraph(GRAPH_WIDTH, GRAPH_HEIGHT, graph_data="on_draw")
		graph.position = starting_x + step_x * 2, row_y
		self.perf_graph_list.append(graph)
		# Create a Text object to show the current FPS
		self.fps_text = arcade.Text(f"FPS: {arcade.get_fps(60):5.1f}",10, 10, arcade.color.BLACK, 22)

	def setup_panels(self):
		self.timer = UINumberLabel(value=1)
		self.status_label = UITextLabel(l_text='')
		self.pos_label = UITextLabel(l_text='')
		self.health_label = UITextLabel(l_text='')
		self.panel = UITextArea(text='panel')
		self.test_label = UITextLabel(l_text='')
		self.columns_list = [self.timer, self.status_label, self.pos_label, self.health_label, self.panel,self.test_label,]
		self.columns = UIBoxLayout(align='left',vertical=True,children=self.columns_list,)
		self.anchor = self.manager.add(UIAnchorLayout())#, anchor_y='top'))
		self.anchor.add(child=self.columns, anchor_x='left', anchor_y='top')

	def on_draw(self):
		self.clear()
		# self.draw_player_panel()
		self.camera.use()
		self.scene.draw()
		self.playerone.draw()
		self.netplayers.draw()
		self.bomb_list.draw()
		self.particle_list.draw()
		self.flame_list.draw()
		self.manager.draw()

		if self.graw_graphs:
			self.perf_graph_list.draw()
			# Get & draw the FPS for the last 60 frames
			if arcade.timings_enabled():
				self.fps_text.value = f"FPS: {arcade.get_fps(60):5.1f}"
				self.fps_text.draw()

	def dumpdebug(self):
		print('='*80)
		print(f'scenewalls:{len(self.scenewalls)} sceneblocks:{len(self.sceneblocks)} bombs:{len(self.bomb_list)} particles:{len(self.particle_list)} flames:{len(self.flame_list)}')
		print(f'playerone: {self.playerone} pos={self.playerone.position} ') #  gspos={self.game_state.players[self.playerone.client_id]}')
		print(f'self.game_state.players = {len(self.game_state.players)} gsge={len(self.game_state.game_events)}')
		print('='*80)
		for idx,p in enumerate(self.game_state.players):
			print(f"\t{idx}/{len(self.game_state.players)} p={p} | {self.game_state.players.get(p)} | {self.game_state.players}")
		print('='*80)
		for idx,e in enumerate(self.game_state.game_events):
			print(f"\t{idx}/{len(self.game_state.game_events)} event={e} ")
		# print('='*80)
		# arcade.print_timings()
		# print('='*80)

	def send_key_press(self, key, modifiers):
		pass

	def on_key_press(self, key, modifiers):
		# todo check collisions before sending keypress...
		sendmove = False
		# logger.debug(f'{key} {self} {self.client} {self.client.receiver}')
		if key == arcade.key.F1:
			self.debugmode = not self.debugmode
			logger.debug(f'debugmode: {self.debugmode}')
		if key == arcade.key.F2:
			self.game_state.debugmode = not self.game_state.debugmode
			logger.debug(f'gsdebugmode: {self.game_state.debugmode} debugmode: {self.debugmode}')
		elif key == arcade.key.F3:
			self.dumpdebug()
		elif key == arcade.key.F4:
			self.graw_graphs = not self.graw_graphs
		elif key == arcade.key.F5:
			arcade.clear_timings()
		elif key == arcade.key.ESCAPE or key == arcade.key.Q:
			logger.warning(f'quit')
			arcade.close_window()
			return
		if self.playerone.killed:
			logger.warning(f'playerone killed')
			return
		if key == arcade.key.SPACE:
			self.dropbomb(key)
		if len(self.hitlist) == 0:
			#self.player_event.keys[key] = True
			#self.keys_pressed.keys[key] = True
			if key == arcade.key.UP or key == arcade.key.W:
				self.playerone.change_y = PLAYER_MOVEMENT_SPEED
				sendmove = True
			elif key == arcade.key.DOWN or key == arcade.key.S:
				self.playerone.change_y = -PLAYER_MOVEMENT_SPEED
				sendmove = True
			elif key == arcade.key.LEFT or key == arcade.key.A:
				self.playerone.change_x = -PLAYER_MOVEMENT_SPEED
				sendmove = True
			elif key == arcade.key.RIGHT or key == arcade.key.D:
				self.playerone.change_x = PLAYER_MOVEMENT_SPEED
				sendmove = True
			# self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})

	def on_key_release(self, key, modifiers):
		if key == arcade.key.UP or key == arcade.key.DOWN or key == arcade.key.W or key == arcade.key.S:
			self.playerone.change_y = 0
		elif key == arcade.key.LEFT or key == arcade.key.RIGHT or key == arcade.key.A or key == arcade.key.D:
			self.playerone.change_x = 0
		self.player_event.keys[key] = False
		self.keys_pressed.keys[key] = False

	def handle_game_events(self, game_events):
		# gspcopy = copy.copy(self.game_state.game_events)
		# [self.game_state.game_events.remove(game_event) for game_event in self.game_state.game_events if game_event.get('handled')]
		for game_event in game_events:
			event_type = game_event.get('event_type')
			if self.debugmode:
				logger.info(f'{event_type=} {game_event=} {game_events=}')
			match event_type:
				case 'upgradeblock':
					if self.debugmode:
						logger.info(f'{event_type} upgradetype {game_event.get("upgradetype")}')
				case 'blkxplode':
					if self.debugmode:
						logger.info(f'{event_type} from {game_event.get("fbomber")}')
				case 'playerkilled' | 'dmgkill':
					#if self.debugmode:
					killer = game_event.get("killer")
					killed = game_event.get("killed")
					kill_score = 1
					[k.set_texture(arcade.load_texture('data/netplayerdead.png')) for k in self.netplayers if k.client_id == killed]#[0]
					[k.addscore(kill_score) for k in self.netplayers if k.client_id == killer]
					logger.info(f'{event_type} from {killer=}  {killed=}')
					if killed == self.playerone.client_id:
						kill_score += self.playerone.kill(killer)
						logger.debug(f'{event_type} from {killer=}  {killed=} {self.playerone=} {kill_score=}')
					if killer == self.playerone.client_id:
						self.playerone.score += kill_score
						logger.debug(f'{event_type} from {killer=}  {killed=} {self.playerone=} {kill_score=}')
					self.game_state.players[killed]['score'] += kill_score
				case 'takedamage':
					#if self.debugmode:
					killer = game_event.get("killer")
					killed = game_event.get("killed")
					damage = game_event.get("damage")
					score = sum([k.take_damage(damage, killer) for k in self.netplayers if k.client_id == killed])
					logger.info(f'{event_type} from {killer=}  {killed=} {score=}')
					if killed == self.playerone.client_id:
						score += self.playerone.take_damage(damage, killer)
						logger.debug(f'{event_type} from {killer=}  {killed=} {self.playerone=} {score=}')
					self.game_state.players[killed]['score'] += score
				case 'acktakedamage':
					#if self.debugmode:
					killer = game_event.get("killer")
					killed = game_event.get("killed")
					damage = game_event.get("damage")
					logger.info(f'{event_type} from {killer=}  {killed=} ')
					if killed == self.playerone.client_id:
						score = self.playerone.take_damage(damage, killer)
						logger.debug(f'{event_type} from {killer=}  {killed=} {self.playerone=} {score=}')
						self.game_state.players[killed]['score'] += score
				case 'bombdrop':
					bomber = game_event.get('bomber')
					bombpos = game_event.get('pos')
					bomb = Bomb("data/bomb.png",scale=1, bomber=bomber, timer=1500)
					bomb.center_x = bombpos[0]
					bomb.center_y = bombpos[1]
					self.bomb_list.append(bomb)
					if self.debugmode:
						logger.info(f'{game_event} from {bomber} pos {bombpos} ')
				case _:
					# game_events.remove(game_event)
					logger.warning(f'unknown type:{event_type} {game_events=} ')

	def update_gamestate_players(self):
		for pclid in self.game_state.players:
			if self.game_state.players[pclid].get('timeout'):
				logger.info(f'timeout ppclid={pclid} gsp={self.game_state.players}')
				self.poplist.append(pclid)

	def update_netplayers(self):
		# gspcopy = copy.copy(self.game_state.players)
		for pclid in self.game_state.players:
			# logger.info(f'pclid={pclid} gsp={self.game_state.players}')
			if pclid == self.playerone.client_id:
				continue
			if self.game_state.players[pclid].get('killed'): # add to pop list
				logger.info(f'killed pclid={pclid} gsp={self.game_state.players}')
			if pclid in [k.client_id for k in self.netplayers]:
				# logger.info(f'pclid={pclid} gsp={self.game_state.players}')
				if pclid != self.playerone.client_id:
					netplayer = [k for k in self.netplayers if k.client_id == pclid][0]
					npl = [k for k in self.columns.children if isinstance(k, UIPlayerLabel) and k.client_id == pclid][0]
					pclpos = self.game_state.players[pclid].get('position')
					score = self.game_state.players[pclid].get('score')
					npscore = netplayer.score
					npl.value = f'pos: {pclpos} score: {score} npscore: {npscore}'
					netplayer.position = pclpos
			else:
				pclpos = self.game_state.players[pclid].get('position')
				score = self.game_state.players[pclid].get('score')
				newplayer = Bomberplayer(image="data/netplayer.png",scale=0.9, client_id=pclid, position=pclpos)
				self.netplayers.append(newplayer)
				logger.info(f'newplayer: {newplayer} pos: {pclpos} players: {len(self.netplayers)}')
				playerlabel = UIPlayerLabel(client_id=pclid)
				playerlabel.value = f'pos: {pclpos} score: {score}'
				self.columns_list.append(playerlabel)
				self.columns = UIBoxLayout(align='left',vertical=True,children=self.columns_list,)
				self.anchor = self.manager.add(UIAnchorLayout())#, anchor_y='top'))
				self.anchor.add(child=self.columns, anchor_x='left', anchor_y='top')
	def update_poplist(self):
		for p in self.poplist:
			logger.info(f'plist={self.poplist} popping {p} gsp={self.game_state.players}')
			self.game_state.players.pop(p)
			logger.info(f'aftergsp={self.game_state.players}')
		self.poplist = []

	def on_update(self, dt):
		game_events = None
		try:
			game_events = self.game_state.event_queue.get_nowait()
			self.game_state.event_queue.task_done()
		except Empty:
			pass
		except Exception as e:
			logger.error(f'{e} {type(e)}')
		if game_events:
			self.handle_game_events([game_events,])

		self.timer.value += dt
		if len(self.game_state.players) > 0:
			self.update_netplayers()
			self.update_poplist()
		if self.debugmode or self.game_state.debugmode:
			self.status_label.value = f'id {self.playerone.client_id} score: {self.playerone.score} netplayers: {len(self.game_state.players)} dbg:{self.debugmode} gsdbg:{self.game_state.debugmode} '
		else:
			self.status_label.value = f'id {self.playerone.client_id} score: {self.playerone.score} netplayers: {len(self.game_state.players)} '
		self.pos_label.value = f'pos {self.playerone.position[0]:.2f} {self.playerone.position[1]:.2f}'
		self.health_label.value = f'health {self.playerone.health}'
		self.hitlist = self.physics_engine.update()

		for b in self.bomb_list:
			bombflames = b.update()
			if bombflames: # bomb returns flames when exploding
				self.particle_list.extend(bombflames.get("plist"))
				self.flame_list.extend(bombflames.get("flames"))
				if b.bomber == self.playerone.client_id:
					self.playerone.bombsleft += 1
					# logger.info(f'p: {len(bombflames.get("plist"))} pl: {len(self.particle_list)} p1: {self.playerone} b: {b}')
		for f in self.flame_list:
			if arcade.check_for_collision(f, self.playerone):
				# self.playerone.health -= 123
				event = {'event_time':0, 'event_type':'takedamage', 'damage': 101, 'killer':f.bomber, 'killed': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
				#self.game_state.game_events.append(event)
				self.eventq.put(event)
				# if self.playerone.health <= 0:
				# 	self.playerone.kill(killer=f)
				# 	self.game_state.players[self.playerone.client_id]['killed'] = True
				# 	event = {'event_time':0, 'event_type':'playerkilled', 'killer':f.bomber, 'killed': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
				# 	#self.game_state.game_events.append(event)
				# 	self.eventq.put(event)
				# 	if self.debugmode:
				# 		logger.info(f'playerkilled f={f} pone={self.playerone} gsp={self.game_state.players}')
					# [k.addscore(1) for k in self.netplayers if k.client_id == f.bomber]
					# killerid = [k for k in self.game_state.players if k == f.bomber][0]
					# logger.info(f'playerkilled f={f} killerid={killerid}  pone={self.playerone} gsp={self.game_state.players}')
					# killer = [self.game_state.players.get(k) for k in self.game_state.players if self.game_state.players.get(k).get('client_id')  == killerid][0]
					# killer['score'] += 1
					# logger.info(f'playerkilled f={f.bomber} killer:{killer} pone={self.playerone} self.playerone.ps={self.playerone.ps}')
					#if f.bomber == self.playerone.client_id:
					#	logger.info(f'playerselfkilled f={f.bomber} pone={self.playerone} self.playerone.ps={self.playerone.ps}')
				f.remove_from_sprite_lists()
			f_hitlist = arcade.check_for_collision_with_list(f, self.scenewalls)
			f_hitlist.extend(arcade.check_for_collision_with_list(f, self.sceneblocks))
			for hit in f_hitlist:
				hitblocktype = hit.properties.get('tile_id')
				match hitblocktype:
					case 10:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 5:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 3:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 2:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 11:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 12: # todo create updateblock
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
						hit.remove_from_sprite_lists()
						event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
						#self.game_state.game_events.append(event)
						self.eventq.put(event)
					case _:
						logger.info(f'f: {f} hit: {hit.properties.get("tile_id")} {hit}')

		for p in self.particle_list:
			p_hitlist = arcade.check_for_collision_with_list(p, self.scenewalls)
			p_hitlist.extend(arcade.check_for_collision_with_list(p, self.sceneblocks))
			if p_hitlist:
				for hit in p_hitlist:
					if p.change_x > 0:
						p.right = hit.left
					elif p.change_x < 0:
						p.left = hit.right
				if len(p_hitlist) > 0:
					p.change_x *= -1
		self.particle_list.update()
		self.flame_list.update()
		self.camera.center(self.playerone.position)

	def dropbomb(self, key):
		# logger.debug(f'p1: {self.playerone} drops bomb...')
		# logger.info(f'client: {self.client}')
		self.player_event.keys[key] = False
		if self.playerone.bombsleft <= 0:
			logger.warning(f'p1: {self.playerone} has no bombs left...')
		else:
			bomb = Bomb("data/bomb.png",scale=1, bomber=self.playerone.client_id, timer=1500)
			bomb.center_x = self.playerone.center_x
			bomb.center_y = self.playerone.center_y
			# self.bomb_list.append(bomb)
			self.playerone.bombsleft -= 1
			bombevent = {'event_time':0, 'event_type':'bombdrop', 'bomber': self.playerone.client_id, 'pos': bomb.position, 'timer': bomb.timer, 'handled': False, 'handledby': self.playerone.client_id, 'eventid': gen_randid()}
			# self.game_state.game_events.append(bombevent)
			self.eventq.put(bombevent)
			# logger.info(f'BE={bombevent} evq: {self.eventq.qsize()} bombdrop {bomb} by plid {self.playerone.client_id} bl: {len(self.bomb_list)} p1: {self.playerone}')
			# self.client.send_queue.put({'msgtype': 'bombdrop', 'bomber': self.client.client_id, 'pos': bomb.position, 'timer': bomb.timer})


async def thread_main(game, loop):
	async def pusher():
		# Push the player's INPUT state 60 times per second
		thrmain_cnt = 0
		# game_events = []
		while True:
			thrmain_cnt += 1
			try:
				game_events = game.eventq.get_nowait()
				game.eventq.task_done()
			except Empty:
				game_events = []
			msg = dict(
				thrmain_cnt=thrmain_cnt,
				# event=playereventdict,
				score=game.playerone.score,
				game_events=[game_events,], #game.game_state.game_events,
				client_id=game.playerone.client_id,
				position=game.playerone.position,
				health=game.playerone.health,
				timeout=game.playerone.timeout,
				killed=game.playerone.killed,
				msgsource='pushermsgdict',
				msg_dt=time.time())
			if game.connected():
				await game.push_sock.send_json(msg)
			await asyncio.sleep(1 / UPDATE_TICK)

	async def receive_game_state():
		gs = None
		while True:
			_gs = await game.sub_sock.recv_string()
			gs = json.loads(_gs)
			game.game_state.from_json(gs)
			await asyncio.sleep(1 / UPDATE_TICK)
			# try:
			# 	game.game_state.from_json(gs)
			# except TypeError as e:
			# 	logger.warning(f'{e} {type(e)} gs={_gs}')
			# except AttributeError as e:
			# 	logger.warning(f'{e} {type(e)} gs={_gs}')
			# except NameError as e:
			# 	logger.warning(f'{e} {type(e)} gs={_gs}')
			# except Exception as e:
			# 	logger.error(f'{e} {type(e)} gs={_gs}')
			# await asyncio.sleep(1 / UPDATE_TICK)
	await asyncio.gather(pusher(), receive_game_state())

def thread_worker(game):
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	looptask = loop.create_task(thread_main(game, loop))
	logger.info(f'threadworker loop: {loop} lt={looptask}')
	loop.run_forever()

def main():
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--server', action='store', dest='server', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()

	mainwindow = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, gc_mode='context_gc')
	game = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, args)
	mainmenu = MainMenu(game)
	thread = Thread(target=thread_worker, args=(game,), daemon=True)
	thread.start()
	mainwindow.show_view(mainmenu)
	arcade.run()

if __name__ == "__main__":
	arcade.enable_timings(1000)
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	main()
	# arcade.run()
