#!/usr/bin/python
import sys
import asyncio
import json
from collections import deque
from threading import Thread
import time
from argparse import ArgumentParser
import random
from queue import Queue, Empty
import arcade
from arcade.gui import UIManager, UILabel, UIBoxLayout, UITextArea,UIFlatButton,UIGridLayout
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
		self.sb = UIFlatButton(text="Start New Game", width=150)
		self.eb = UIFlatButton(text="Exit", width=320)
		grid = UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		gridsb = grid.add(self.sb, col_num=1, row_num=0)
		grideb = grid.add(self.eb, col_num=0, row_num=2, col_span=2)
		anchor = self.manager.add(UIAnchorLayout())
		self.anchor = anchor.add(anchor_x="center_x", anchor_y="center_y", child=grid,)

		@self.sb.event("on_click")
		def on_click_start_new_game_button(event):
			self.game.setup()
			self.sb.visible = False
			self.eb.visible = False
			self.sb.disabled = True
			self.eb.disabled = True
			self.window.show_view(self.game)

		@self.eb.event("on_click")
		def on_click_exit_button(event):
			arcade.exit()

	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_ASPARAGUS
		self.manager.enable()

	def on_draw(self):
		self.clear()
		self.manager.draw()

	def on_hide_view(self):
		self.manager.disable() # pass

class Bomberdude(arcade.View):
	def __init__(self, width, height, title, args):
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
		self.game_state = GameState(player_states=[],game_seconds=0)
		self.game_state.players[self.playerone.client_id] = self.playerone.get_ps()

		self.ioctx = Context()
		self.sub_sock: Socket = self.ioctx.socket(zmq.SUB)
		self.push_sock: Socket = self.ioctx.socket(zmq.PUSH)
		self._connected = False
		self.physics_engine = None
		self.bomb_list = None
		self.particle_list = None
		self.flame_list = None
		self.netplayers = None
		self.title = title
		self.eventq = Queue()
		self.game_ready = False
		self.graw_graphs = False

		self.grid = UIGridLayout(column_count=2, row_count=3)#, horizontal_spacing=20, vertical_spacing=20)
		self.connectb = self.grid.add(UIFlatButton(text="Connect"), col_num=1, row_num=0)
		anchor = self.manager.add(UIAnchorLayout())
		self.anchor = anchor.add(anchor_x="right", anchor_y="top", child=self.grid,)
		self.connectb.visible = False
		self.connectb.disabled = True
		self.gsp = []

		@self.connectb.event("on_click")
		def on_connect_to_server(event):
			self.do_connect()

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.game_state.players)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

	def connected(self):
		return self._connected

	def do_connect(self):
		logger.info(f'{self} do_connect')
		self.sub_sock.connect(f'tcp://{self.args.server}:9696')
		self.sub_sock.subscribe('')
		self.push_sock.connect(f'tcp://{self.args.server}:9697')
		self._connected = True
		self.connectb.text = 'Connected'
		self.connectb.disabled = True

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

		self.bomb_list = arcade.SpriteList()
		self.particle_list = arcade.SpriteList()
		self.flame_list = arcade.SpriteList()
		self.netplayers = arcade.SpriteList()
		self.camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		self.background_color = arcade.color.AMAZON
		self.background_color = arcade.color.DARK_BLUE_GRAY
		self.scene.add_sprite_list_after("Player", "Walls")
		self.scenewalls = arcade.SpriteList()
		self.sceneblocks = arcade.SpriteList()
		_ = [self.sceneblocks.append(k) for k in self.scene['Blocks'].sprite_list]
		_ = [self.scenewalls.append(k) for k in self.scene['Walls'].sprite_list]
		self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.scenewalls,platforms=self.sceneblocks, gravity_constant=GRAVITY)
		self.connectb.visible = True
		self.connectb.disabled = False
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


		#anchor = self.manager.add(arcade.gui.UIBoxLayout())
		#self.anchor.add(child=panel_text)
		# self.manager.add(arcade.gui.UIAnchorLayout(anchor_x='center_x', anchor_y='center_y', child=v_box), index=None, layer=99)
		# columns = UIBoxLayout(align='left', vertical=False, children=[UIBoxLayout(align='left',vertical=True,children=[ ], ), ], )
		# anchor = self.manager.add(arcade.gui.UIAnchorLayout(x=4,align_x=1,anchor_x='left'))#, anchor_y='top'))
		# self.columns = anchor.add(child=columns,anchor_x='left', anchor_y='top',)

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
		print(f'=============================')
		print(f'scenewalls:{len(self.scenewalls)} sceneblocks:{len(self.sceneblocks)} bombs:{len(self.bomb_list)} particles:{len(self.particle_list)} flames:{len(self.flame_list)}')
		print(f'playerone: {self.playerone} pos={self.playerone.position} ') #  gspos={self.game_state.players[self.playerone.client_id]}')
		print(f'self.game_state.players = {len(self.gsp)}')
		print(f'=============================')
		for idx,p in enumerate(self.gsp):
			print(f"\tp {idx}/{len(self.gsp)} = {p.get('client_id')} {p.get('health')} {p.get('position')}")
		arcade.print_timings()


	def send_key_press(self, key, modifiers):
		pass

	def on_key_press(self, key, modifiers):
		# todo check collisions before sending keypress...
		sendmove = False
		# logger.debug(f'{key} {self} {self.client} {self.client.receiver}')
		if key == arcade.key.F1:
			self.debugmode = not self.debugmode
		if key == arcade.key.F2:
			self.dumpdebug()
		if key == arcade.key.F3:
			self.graw_graphs = not self.graw_graphs
		if key == arcade.key.F4:
			arcade.clear_timings()
		if key == arcade.key.ESCAPE or key == arcade.key.Q:
			logger.warning(f'quit')
			arcade.close_window()
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
		event_type = game_events.get('event')
		match event_type:
			case 'bombdrop':
				bomber = game_events.get('bomber')
				bombpos = game_events.get('pos')
				if bomber == self.playerone.client_id:
					logger.debug(f'ownbomb ... {event_type} from {bomber} pos {bombpos} ')
				else:
					bomb = Bomb("data/bomb.png",scale=1, bomber=bomber, timer=1500)
					bomb.center_x = bombpos[0]
					bomb.center_y = bombpos[1]
					self.bomb_list.append(bomb)
					logger.info(f'{event_type} from {bomber} pos {bombpos} ')
			case _:
				logger.warning(f'unknown game_events: {game_events} ')

	def update_netplayers(self):
		for p in self.gsp:
			pclid = p['client_id']
			pclpos = p['position']
			# if pclid == self.playerone.client_id:
			#	break
			if pclid in [k.client_id for k in self.netplayers]:
				if pclid != self.playerone.client_id:
					netplayer = [k for k in self.netplayers if k.client_id == pclid][0]
					npl = [k for k in self.columns.children if isinstance(k, UIPlayerLabel) and k.client_id == pclid][0]
					npl.value = f'pos: {pclpos}'
					netplayer.position = pclpos
			else:
				if pclid != self.playerone.client_id:
					newplayer = Bomberplayer(image="data/netplayer.png",scale=0.9, client_id=pclid, position=pclpos)
					self.netplayers.append(newplayer)
					logger.info(f'newplayer: {newplayer} pos: {pclpos} players: {len(self.netplayers)}')

					playerlabel = UIPlayerLabel(client_id=pclid)
					playerlabel.value = f'pos: {pclpos}'
					self.columns_list.append(playerlabel)
					self.columns = UIBoxLayout(align='left',vertical=True,children=self.columns_list,)
					self.anchor = self.manager.add(UIAnchorLayout())#, anchor_y='top'))
					self.anchor.add(child=self.columns, anchor_x='left', anchor_y='top')

			#gs_ghost = Rectangle(client_id=pclid, color = arcade.color.YELLOW, center_x=pclpos[0], center_y=pclpos[1])
			#gs_ghost.center_x = pclpos[0]
			#gs_ghost.center_y = pclpos[1] # self.game_state.players[pclid]['position']


	def on_update(self, dt):
		game_events = None
		try:
			game_events = self.game_state.event_queue.get_nowait()
		except Empty:
			pass
		except Exception as e:
			logger.error(f'{e} {type(e)}')
		if game_events:
			self.handle_game_events(game_events)
			self.game_state.event_queue.task_done()
		self.timer.value += dt
		self.game_state.players[self.playerone.client_id] = self.playerone.get_ps()
		self.gsp = self.game_state.players.get("players",[])
		if len(self.gsp) > 1:
			self.update_netplayers()
			#self.gs_ghost.visible = True
		self.status_label.value = f'id {self.playerone.client_id}  netplayers: {len(self.gsp)} '
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
				self.playerone.health -= 1
				self.playerone.ps.health -= 1
				if self.playerone.health <= 0 or self.playerone.ps.health <= 0:
					self.playerone.kill(killer=f)
					logger.info(f'playerkilled f={f} pone={self.playerone} self.playerone.ps={self.playerone.ps}')
				else:
					pass # logger.info(f'playerhit f={f} pone={self.playerone} self.playerone.ps={self.playerone.ps}')
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
					case _:
						logger.info(f'f: {f} hit: {hit.properties.get("tile_id")} {hit}')

		for p in self.particle_list:
			p_hitlist = arcade.check_for_collision_with_list(p, self.scenewalls)
			if p_hitlist:
				for hit in p_hitlist:
					if p.change_x > 0:
						p.right = hit.left
					elif p.change_x < 0:
						p.left = hit.right
				if len(p_hitlist) > 0:
					p.change_x *= -1
			p_hitlist = arcade.check_for_collision_with_list(p, self.scenewalls)
			if p_hitlist:
				for hit in p_hitlist:
					if p.change_y > 0:
						p.top = hit.bottom
					elif p.change_y < 0:
						p.bottom = hit.top
				if len(p_hitlist) > 0:
					p.change_y *= -1

		self.particle_list.update()
		self.flame_list.update()

		self.camera.center(self.playerone.position)

	def dropbomb(self, key):
		# logger.debug(f'p1: {self.playerone} drops bomb...')
		# logger.info(f'client: {self.client}')
		if self.playerone.bombsleft <= 0:
			logger.debug(f'p1: {self.playerone} has no bombs left...')
			return
		else:
			self.player_event.keys[key] = False
			bomb = Bomb("data/bomb.png",scale=1, bomber=self.playerone.client_id, timer=1500)
			bomb.center_x = self.playerone.center_x
			bomb.center_y = self.playerone.center_y
			self.bomb_list.append(bomb)
			self.playerone.bombsleft -= 1
			bombevent = {'event':'bombdrop', 'bomber': self.playerone.client_id, 'pos': bomb.position, 'timer': bomb.timer}
			self.eventq.put(bombevent)
			# logger.info(f'BE={bombevent} evq: {self.eventq.qsize()} bombdrop {bomb} by plid {self.playerone.client_id} bl: {len(self.bomb_list)} p1: {self.playerone}')
			# self.client.send_queue.put({'msgtype': 'bombdrop', 'bomber': self.client.client_id, 'pos': bomb.position, 'timer': bomb.timer})


async def thread_main(game, loop):
	async def pusher():
		# Push the player's INPUT state 60 times per second
		thrmain_cnt = 0
		game_events = None
		while True:
			thrmain_cnt += 1
			try:
				game_events = game.eventq.get_nowait()
				game.eventq.task_done()
			except Empty:
				game_events = None
			except Exception as e:
				logger.error(f'{e} {type(e)}')
				game_events = None
			if game_events:
				logger.info(f'{game.playerone.client_id} game_events:{game_events} ')
			playereventdict = game.player_event.asdict()
			try:
				playereventdict['client_id'] = {'client_id': game.playerone.client_id, 'position':game.playerone.position, 'health': game.playerone.health, 'msgsource':'pusher'}
			except KeyError as e:
				logger.error(f'{e} playereventdict={playereventdict} ')
			msg = dict(counter=thrmain_cnt, event=playereventdict, game_events=game_events, client_id=game.playerone.client_id, position=game.playerone.position, health=game.playerone.health, msg_dt=time.time())
			if game.connected():
				if game.debugmode:
					pass # logger.info(f'push msg: {msg} playereventdict={playereventdict}')
				await game.push_sock.send_json(msg)
			await asyncio.sleep(1 / UPDATE_TICK)

	async def receive_game_state():
		gs = None
		while True:
			_gs = await game.sub_sock.recv_string()
			gs = json.loads(_gs)
			game.game_state.from_json(gs, game.debugmode)
			await asyncio.sleep(1 / UPDATE_TICK)
			if game.debugmode:
				gsevents = gs.get('events')
				if len(gsevents) > 0:
					logger.info(f'gsevents: {gsevents} gs = {gs} ')
				# logger.info(f'p0: {pcount0} p1:{pcount1} players={game.game_state.players} gs={gs}' )
	try:
		await asyncio.gather(pusher(), receive_game_state())
	except Exception as e:
		logger.error(f'{e} {type(e)}')
	finally:
		logger.debug('closing sockets')
		game.sub_sock.close(1)
		game.push_sock.close(1)
		game.ctx.destroy(linger=1)

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
