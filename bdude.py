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
# draw netplayers
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
RECT_WIDTH = 50
RECT_HEIGHT = 50


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
		self.game = game
		self.manager = UIManager()
		#self.game = game
		#self.manager = game.manager
		self.sb = arcade.gui.UIFlatButton(text="Start New Game", width=150)
		self.eb = arcade.gui.UIFlatButton(text="Exit", width=320)
		self.grid = arcade.gui.UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		self.grid.add(self.sb, col_num=1, row_num=0)
		self.grid.add(self.eb, col_num=0, row_num=2, col_span=2)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="center_x", anchor_y="center_y", child=self.grid,)

		@self.sb.event("on_click")
		def on_click_start_new_game_button(event):
			self.game.setup()
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
		self.manager = UIManager()
		self.window.center_window() # set_location(0,0)
		self.width = width
		self.height = height
		self.t = 0
		self.playerone = Bomberplayer(image="data/playerone.png",scale=0.9, client_id=gen_randid())
		self.ghost = Rectangle()
		self.keys_pressed = KeysPressed(self.playerone.client_id)
		self.player_event = PlayerEvent()
		# ps = PlayerState(self.playerone.client_id)
		# ps.set_client_id(self.playerone.client_id)
		self.game_state = GameState(player_states=[self.playerone.get_ps()],game_seconds=0)
		self.position_buffer = deque(maxlen=3)

		self.ctx = Context()
		self.sub_sock: Socket = self.ctx.socket(zmq.SUB)
		self.push_sock: Socket = self.ctx.socket(zmq.PUSH)
		self._connected = False
		# self.player_list = None
		self.netplayers = []
		self.physics_engine = None
		self.bomb_list = None
		self.particle_list = None
		self.flame_list = None
		self.title = title
		self.eventq = Queue()
		# self.client = Client(serveraddress=('127.0.0.1', 9696), eventq=self.eventq)
		self.game_ready = False
		# self.timer = UILabel(text='.', align="right", size_hint_min=(30, 20))
		self.timer = UINumberLabel(value=20, align="right", size_hint_min=(30, 10))

		self.grid = arcade.gui.UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		self.connectb = arcade.gui.UIFlatButton(text="Connect", width=150)
		self.grid.add(self.connectb, col_num=1, row_num=0)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="right", anchor_y="top", child=self.grid,)

		self.health_label = UILabel(align="right", size_hint_min=(30, 20))
		self.bombs_label = UILabel(align="right", size_hint_min=(30, 20))
		self.status_label = UILabel(align="right", size_hint_min=(30, 20))

		self.columns = UIBoxLayout(
			vertical=False,
			children=[
				# Create one vertical UIBoxLayout per column and add the labels
				UIBoxLayout(
					vertical=True,
					children=[
						UILabel(text="Time:", align="left", width=50),
						UILabel(text="health:", align="left", width=50),
						UILabel(text="bombs:", align="left", width=50),
						UILabel(text="status:", align="left", width=150),
					],
				),
				# Create one vertical UIBoxLayout per column and add the labels
				UIBoxLayout(vertical=True, children=[self.timer, self.health_label, self.bombs_label, self.status_label]),
			],
		)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="left", anchor_y="top", child=self.columns,)

		@self.connectb.event("on_click")
		def on_connect_to_server(event):
			self.do_connect()

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.netplayers)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

	def connected(self):
		return self._connected

	def do_connect(self):
		logger.info(f'{self} do_connect')
		self.sub_sock.connect('tcp://127.0.0.1:9696')
		self.sub_sock.subscribe('')
		self.push_sock.connect('tcp://127.0.0.1:9697')
		self._connected = True

	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_BLUE
		self.manager.enable()

	def on_hide_view(self):
		# Disable the UIManager when the view is hidden.
		self.manager.disable()

	def setup(self):

		layer_options = {"Blocks": {"use_spatial_hash": True},}
		self.tile_map = arcade.load_tilemap('data/map.json', layer_options=layer_options, scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)
		self.scene.add_sprite_list_after("Player", "Foreground")

		self.bomb_list = arcade.SpriteList()
		self.particle_list = arcade.SpriteList()
		self.flame_list = arcade.SpriteList()
		self.netplayers = arcade.SpriteList()

		self.camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		self.gui_camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		self.end_of_map = (self.tile_map.width * self.tile_map.tile_width) * self.tile_map.scaling
		self.background_color = arcade.color.AMAZON
		self.manager.enable()
		self.background_color = arcade.color.DARK_BLUE_GRAY
		self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.scene['Blocks'], gravity_constant=GRAVITY)


	def on_draw(self):
		self.clear()
		self.camera.use()
		self.scene.draw()

		self.netplayers.draw()
		self.playerone.draw()
		self.ghost.draw()

		self.bomb_list.draw()
		self.particle_list.draw()
		self.flame_list.draw()
		self.manager.draw()

		# self.gui_camera.use()

	def send_key_press(self, key, modifiers):
		pass

	def on_key_press(self, key, modifiers):
		self.player_event.keys[key] = True
		self.keys_pressed.keys[key] = True
		sendmove = False
		# logger.debug(f'{key} {self} {self.client} {self.client.receiver}')
		if key == arcade.key.ESCAPE or key == arcade.key.Q:
			arcade.close_window()
		elif key == arcade.key.UP or key == arcade.key.W:
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
		elif key == arcade.key.SPACE:
			self.dropbomb()
		if sendmove:
			pass
			# self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})


	def on_key_press_net(self, key, modifiers):
		self.player_event.keys[key] = True
		self.keys_pressed.keys[key] = True
		# logger.debug(f'{key} pek:{self.player_event} skpk:{self.keys_pressed}')
		if key == arcade.key.ESCAPE or key == arcade.key.Q:
			arcade.close_window()

	def on_key_release(self, key, modifiers):
		if key == arcade.key.UP or key == arcade.key.DOWN or key == arcade.key.W or key == arcade.key.S:
			self.playerone.change_y = 0
		elif key == arcade.key.LEFT or key == arcade.key.RIGHT or key == arcade.key.A or key == arcade.key.D:
			self.playerone.change_x = 0
		self.player_event.keys[key] = False
		self.keys_pressed.keys[key] = False

	def oldon_key_release(self, key, modifiers):
		if key == arcade.key.UP or key == arcade.key.DOWN or key == arcade.key.W or key == arcade.key.S:
			self.playerone.change_y = 0
		elif key == arcade.key.LEFT or key == arcade.key.RIGHT or key == arcade.key.A or key == arcade.key.D:
			self.playerone.change_x = 0

	def on_update(self, dt):
		self.timer.value += dt
		self.status_label.text = f'{self.playerone.client_id} {self.playerone.position}'
		self.status_label.fit_content()
		if len(self.game_state.players) >= 2:
			for p in self.game_state.players:
				try:
					self.ghost.position = self.game_state.players[p].get('position')
					logger.debug(f'updateghost p={p} self.game_state.players={self.game_state.players}')
				except AttributeError as e:
					logger.error(f'{e} p={p} self.game_state.players={self.game_state.players}')
		# self.game_state = GameState(player_states=[self.playerone.setpos(self.playerone.position)],game_seconds=self.timer.value)
		try:
			self.physics_engine.update()
		except Exception as e:
			logger.error(f'{e} {type(e)} posb: {self.position_buffer} ppos: {self.playerone}')
		for b in self.bomb_list:
			bombflames = b.update()
			if bombflames: # bomb returns flames when exploding
				self.particle_list.extend(bombflames.get("plist"))
				self.flame_list.extend(bombflames.get("flames"))
				if b.bomber == self.playerone.client_id:
					self.playerone.bombsleft += 1
					# logger.info(f'p: {len(bombflames.get("plist"))} pl: {len(self.particle_list)} p1: {self.playerone} b: {b}')
		for f in self.flame_list:
			f_hitlist = arcade.check_for_collision_with_list(f, self.scene['Blocks'])
			if f_hitlist:
				for hit in f_hitlist:
					if hit.properties.get('tile_id') == 10:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()

					if hit.properties.get('tile_id') == 5:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()

					if hit.properties.get('tile_id') == 11:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()

					if hit.properties.get('tile_id') == 12: # todo create updateblock
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
						hit.remove_from_sprite_lists()

		for p in self.particle_list:
			p_hitlist = arcade.check_for_collision_with_list(p, self.scene['Blocks'])
			if p_hitlist:
				for hit in p_hitlist:
					if p.change_x > 0:
						p.right = hit.left
					elif p.change_x < 0:
						p.left = hit.right
				if len(p_hitlist) > 0:
					p.change_x *= -1
			p_hitlist = arcade.check_for_collision_with_list(p, self.scene['Blocks'])
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
		if self.playerone:
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
			d = game.player_event.asdict()
			msg = dict(counter=thrmain_cnt, event=d)
			msg['client_id'] = game.playerone.client_id
			msg['position'] = game.playerone.position
			if game.connected():
				# logger.info(f'push: {d} msg: {msg}')
				await game.push_sock.send_json(msg)
			await asyncio.sleep(1 / UPDATE_TICK)

	async def receive_game_state():
		while True:
			_gs = await game.sub_sock.recv_string()
			gs = json.loads(_gs)
			pcount0 = len(game.game_state.players)
			game.game_state.from_json(gs, game.game_state.players)
			pcount1 = len(game.game_state.players)
			logger.info(f'p0: {pcount0} p1:{pcount1} players={game.game_state.players} gs={gs}' )
	try:
		await asyncio.gather(pusher(), receive_game_state())
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
