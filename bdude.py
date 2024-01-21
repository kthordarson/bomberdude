#!/usr/bin/python
import sys
import asyncio
import json
from collections import deque
from threading import Thread
import time
import copy
from argparse import ArgumentParser
import random
from queue import Queue, Empty
import arcade
from arcade.gui import UIManager, UILabel, UIBoxLayout
from arcade.gui.widgets.layout import UIAnchorLayout

from loguru import logger
from objects import Bomberplayer, Bomb, KeysPressed, PlayerEvent, PlayerState, GameState, gen_randid, Rectangle
# from menus import MainMenu
from constants import *
from networking import Client
from exceptions import *

import zmq
from zmq.asyncio import Context, Socket
# todo get inital pos from server
# draw netbombs
# sync info bewteen Client and Bomberplayer
# update clients when new player connects
# task 1 send player input to server
# task 2 receive game state from server
# task 3 draw game

# task 1 accept connections
# taks 2 a. receive player input b. update game state
# task 3 send game state to clients

UPDATE_TICK = 60
RECT_WIDTH = 32
RECT_HEIGHT = 32

def get_random_color():
	acolors = dir(arcade.color)
	foundcolor = False
	while not foundcolor:
		res = eval(f'arcade.color.{random.choice(acolors)}')
		if isinstance(res, arcade.types.Color):
			foundcolor = True
			break
	#_acol_list = [f'arcade.color.{k}' for k in _acolors]
	return res


class UINumberLabel(UILabel):
    _value: float = 0

    def __init__(self, value=0, format="{value:.0f}", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.format = format
        self.value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self.text = self.format.format(value=value)
        self.fit_content()

class MainMenu(arcade.View):
	def __init__(self, game):
		super().__init__()
		# self.loop = asyncio.get_event_loop()
		#self.manager = UIManager()
		self.game = game
		self.manager = game.manager
		#self.game = game
		#self.manager = game.manager
		self.sb = arcade.gui.UIFlatButton(text="Start New Game", width=150)
		self.eb = arcade.gui.UIFlatButton(text="Exit", width=320)
		grid = arcade.gui.UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		gridsb = grid.add(self.sb, col_num=1, row_num=0)
		grideb = grid.add(self.eb, col_num=0, row_num=2, col_span=2)
		anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor = anchor.add(anchor_x="center_x", anchor_y="center_y", child=grid,)

		@self.sb.event("on_click")
		def on_click_start_new_game_button(event):
			self.game.setup()
			self.sb.visible = False
			self.eb.visible = False
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
		# Disable the UIManager when the view is hidden.
		self.manager.disable() # pass

class Bomberdude(arcade.View):
	def __init__(self, width, height, title):
		super().__init__()
		#super().__init__(width, height, title, resizable=True)
		self.debugmode = False
		self.manager = UIManager()
		self.window.center_window() # set_location(0,0)
		self.width = width
		self.height = height
		self.t = 0
		self.playerone = Bomberplayer(image="data/playerone.png",scale=0.9, client_id=gen_randid())
		self.ghost = Rectangle(client_id=self.playerone, color = arcade.color.ORANGE, center_x=self.playerone.center_x, center_y=self.playerone.center_y)
		self.gs_ghost = Rectangle(client_id=self.playerone, color = arcade.color.YELLOW, center_x=self.playerone.center_x, center_y=self.playerone.center_y)
		self.keys_pressed = KeysPressed(self.playerone.client_id)
		self.hitlist = []
		self.player_event = PlayerEvent()
		# ps = PlayerState(self.playerone.client_id)
		# ps.set_client_id(self.playerone.client_id)
		self.game_state = GameState(player_states=[],game_seconds=0)
		self.game_state.players[self.playerone.client_id] = self.playerone.get_ps()
		self.position_buffer = deque(maxlen=3)

		self.ctx = Context()
		self.sub_sock: Socket = self.ctx.socket(zmq.SUB)
		self.push_sock: Socket = self.ctx.socket(zmq.PUSH)
		self._connected = False
		# self.player_list = None
		self.physics_engine = None
		self.bomb_list = None
		self.particle_list = None
		self.flame_list = None
		self.ghost_list = None
		self.title = title
		self.eventq = Queue()
		# self.client = Client(serveraddress=('127.0.0.1', 9696), eventq=self.eventq)
		self.game_ready = False
		# self.timer = UILabel(text='.', align="right", size_hint_min=(30, 20))

		self.grid = arcade.gui.UIGridLayout(column_count=2, row_count=3)#, horizontal_spacing=20, vertical_spacing=20)
		connectb = arcade.gui.UIFlatButton(text="Connect", width=150)
		self.connectb = self.grid.add(connectb, col_num=1, row_num=0)
		anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor = anchor.add(anchor_x="right", anchor_y="top", child=self.grid,)
		self.timer = UINumberLabel(value=1)

		@self.connectb.event("on_click")
		def on_connect_to_server(event):
			self.do_connect()

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.game_state.players)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

	def connected(self):
		return self._connected

	def do_connect(self):
		logger.info(f'{self} do_connect')
		self.sub_sock.connect('tcp://127.0.0.1:9696')
		self.sub_sock.subscribe('')
		self.push_sock.connect('tcp://127.0.0.1:9697')
		self.ghost.center_x = self.playerone.center_x
		self.ghost.center_y = self.playerone.center_y
		self.gs_ghost.center_x = self.playerone.center_x
		self.gs_ghost.center_y = self.playerone.center_y
		self._connected = True
		self.connectb.text = 'Connected'
		self.connectb.disabled = True

	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_BLUE
		self.manager.enable()

	def on_hide_view(self):
		# Disable the UIManager when the view is hidden.
		self.manager.disable()

	def setup(self):
		#self.manager = UIManager()
		# self.health_label = UILabel(align="right", size_hint_min=(30, 20))
		# self.bombs_label = UILabel(align="right", size_hint_min=(30, 20))
		self.status_label = UILabel()#, size_hint_min=(30, 20))

		columns = UIBoxLayout(
			vertical=False,
			children=[
				UIBoxLayout(
					vertical=True,
					children=[
						UILabel(text="Time: "),
						# UILabel(text="health:", align="left", width=50),
						# UILabel(text="bombs:", align="left", width=50),
						UILabel(text="status: "),
					],
				),
				# Create one vertical UIBoxLayout per column and add the labels
				UIBoxLayout(vertical=True, children=[self.timer, self.status_label]), # self.health_label, self.bombs_label,
			],
		)

		anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.columns = anchor.add(child=columns,anchor_x="left", anchor_y="top", align_x=11, align_y=19)
		# self.anchor.
		layer_options = {"Blocks": {"use_spatial_hash": True},}
		self.tile_map = arcade.load_tilemap('data/map3.json', layer_options=layer_options, scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)

		self.bomb_list = arcade.SpriteList()
		self.particle_list = arcade.SpriteList()
		self.flame_list = arcade.SpriteList()
		self.ghost_list = arcade.SpriteList()
		self.ghost_list.append(self.ghost)
		self.ghost_list.append(self.gs_ghost)
		self.camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		# self.gui_camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		# self.end_of_map = (self.tile_map.width * self.tile_map.tile_width) * self.tile_map.scaling
		self.background_color = arcade.color.AMAZON
		self.manager.enable()
		self.background_color = arcade.color.DARK_BLUE_GRAY
		self.scene.add_sprite_list_after("Player", "Walls")
		self.scenewalls = arcade.SpriteList()
		self.sceneblocks = arcade.SpriteList()
		[self.sceneblocks.append(k) for k in self.scene['Blocks'].sprite_list]
		[self.scenewalls.append(k) for k in self.scene['Walls'].sprite_list]
		self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.scenewalls,platforms=self.sceneblocks, gravity_constant=GRAVITY)


	def on_draw(self):
		self.clear()
		self.camera.use()
		self.scene.draw()
		# self.scene.draw_hit_boxes(names=['Walls'])


		self.playerone.draw()
		self.ghost_list.draw()

		self.bomb_list.draw()
		self.particle_list.draw()
		self.flame_list.draw()
		self.manager.draw()

	def dumpdebug(self):
		print(f'scenewalls:{len(self.scenewalls)} sceneblocks:{len(self.sceneblocks)} bombs:{len(self.bomb_list)} particles:{len(self.particle_list)} flames:{len(self.flame_list)}')
		print(f'playerone: {self.playerone} pos={self.playerone.position} cx={self.playerone.center_x} cy={self.playerone.center_y} gspos={self.game_state.players[self.playerone.client_id]}')
		print(f'\tghost: {self.ghost} pos={self.ghost.position} cx={self.ghost.center_x} cy={self.ghost.center_y}')
		print(f'\tgs_ghost: {self.gs_ghost} pos={self.gs_ghost.position} cx={self.gs_ghost.center_x} cy={self.gs_ghost.center_y}')
		# logger.debug(f'player_event: {self.player_event}')
		# logger.debug(f'keys_pressed: {self.keys_pressed}')
		# logger.debug(f'game_state: {self.game_state}')
		print(f'gameplayers: {self.game_state.players}')
		for p in self.game_state.players:
			print(f'\tp={p} {self.game_state.players[p]}')

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
		if key == arcade.key.ESCAPE or key == arcade.key.Q:
			arcade.close_window()
			return
		if key == arcade.key.SPACE:
			self.dropbomb()
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


	def on_update(self, dt):
		self.timer.value += dt
		self.game_state.players[self.playerone.client_id] = self.playerone.get_ps()
		self.status_label.text = f'id {self.playerone.client_id} pos {self.playerone.position[0]:.2f} {self.playerone.position[1]:.2f} gsp {len(self.game_state.players)}'
		self.status_label.fit_content()
		self.ghost.center_x = self.playerone.center_x
		self.ghost.center_y = self.playerone.center_y
		gsp = self.game_state.players.get('players',[])
		for p in gsp:
			try:
				pclid = p['client_id']
				pclpos = p['position']
			except Exception as e:
				logger.error(f'{e} p={p} ')
				break
			if pclid != self.playerone.client_id:
				try:
					self.gs_ghost.center_x = pclpos[0]
					self.gs_ghost.center_y = pclpos[1] # self.game_state.players[pclid]['position']
				except KeyError as e:
					logger.error(f'{e} p={p}  gsp={self.game_state.players} p1={self.playerone.client_id} {self.playerone}')
				except AttributeError as e:
					logger.error(f'{e} p={p} gsp={self.game_state.players} p1={self.playerone.client_id} {self.playerone}')
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

	def dropbomb(self):
		# logger.debug(f'p1: {self.playerone} drops bomb...')
		# logger.info(f'client: {self.client}')
		if self.playerone.bombsleft <= 0:
			logger.debug(f'p1: {self.playerone} has no bombs left...')
			return
		else:
			bomb = Bomb("data/bomb.png",scale=1, bomber=self.playerone.client_id, timer=1500)
			bomb.center_x = self.playerone.center_x
			bomb.center_y = self.playerone.center_y
			self.bomb_list.append(bomb)
			self.playerone.bombsleft -= 1
			# logger.info(f'bombdrop {bomb} by plid {self.client.client_id} bl: {len(self.bomb_list)} p1: {self.playerone}')
			# self.client.send_queue.put({'msgtype': 'bombdrop', 'bomber': self.client.client_id, 'pos': bomb.position, 'timer': bomb.timer})


async def thread_main(game, loop):
	# todo do connection here
	async def pusher():
		"""Push the player's INPUT state 60 times per second"""
		thrmain_cnt = 0
		while True:
			thrmain_cnt += 1
			playereventdict = game.player_event.asdict()
			try:
				playereventdict['client_id'] = {'client_id': game.playerone.client_id, 'position':game.playerone.position, 'msgsource':'pusher'}
			except KeyError as e:
				logger.error(f'{e} playereventdict={playereventdict} ')
			msg = dict(counter=thrmain_cnt, event=playereventdict, client_id=game.playerone.client_id, position=game.playerone.position, msg_dt=time.time())
			# msg['players'][game.playerone.client_id] = {'position':game.playerone.position, 'gametimer': game.timer.value, 'msgsource': 'gamepusher'}
			# game.game_state.players[game.playerone.client_id] = {'position':game.playerone.position, 'gametimer': game.timer.value, 'msgsource': 'gamepushergamestate'}#  .get('position')
			# msg['msg_dt'] = time.time()
			if game.connected():
				if game.debugmode:
					pass # logger.info(f'push msg: {msg}')
				await game.push_sock.send_json(msg)
			await asyncio.sleep(1 / UPDATE_TICK)

	async def receive_game_state():
		while True:
			_gs = await game.sub_sock.recv_string()
			gs = json.loads(_gs)
			try:
				game.game_state.from_json(gs, game.debugmode)
			except KeyError as e:
				logger.error(f'{e} gs={gs} ')
				gs=None
			# game.game_state.players[game.playerone.client_id] = {'position':game.playerone.position, 'msgsource': 'recvgamestate'}#  .get('position')
			if game.debugmode:
				logger.info(f'gs = {gs} gsp = {game.game_state.players}')
			# logger.info(f'p0: {pcount0} p1:{pcount1} players={game.game_state.players} gs={gs}' )
	try:
		await asyncio.gather(pusher(), receive_game_state())
	except NameError as e:
		logger.warning(f'{e} {type(e)}')
	except TypeError as e:
		logger.warning(f'{e} {type(e)}')
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
	# window = MyGame(SCREEN_WIDTH, SCREEN_HEIGHT)
	# window.setup()

	# loop = asyncio.get_event_loop()

	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--server', action='store', dest='server', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()

	mainwindow = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	game = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	mainmenu = MainMenu(game)
	thread = Thread(target=thread_worker, args=(game,), daemon=True)
	thread.start()
	mainwindow.show_view(mainmenu)
	arcade.run()
	# gameview = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	#game = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	#window.setup()




if __name__ == "__main__":
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	main()
	# arcade.run()
