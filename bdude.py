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
from objects import Bomberplayer, Bomb, KeysPressed, PlayerEvent, PlayerState, GameState, gen_randid
# from menus import MainMenu
from constants import *
from networking import Client
from exceptions import *
UPDATE_TICK = 60
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

class MainMenu(arcade.View):
	def __init__(self, game):
		super().__init__()
		# self.loop = asyncio.get_event_loop()
		self.manager = UIManager()
		self.game = game

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
		self.manager.disable()

class Bomberdude(arcade.View):
	def __init__(self, width, height, title):
		super().__init__()
		#super().__init__(width, height, title, resizable=True)
		self.t = 0
		self.playerone = Bomberplayer("data/playerone.png",scale=0.9, client_id=gen_randid(), center_x=128, center_y=128, visible=True)

		self.keys_pressed = KeysPressed(self.playerone.client_id)
		self.player_event = PlayerEvent()
		ps = PlayerState(self.playerone.client_id)
		ps.set_client_id(self.playerone.client_id)
		self.game_state = GameState(player_states=[ps],game_seconds=0)
		self.position_buffer = deque(maxlen=3)

		self.ctx = Context()
		self.sub_sock: Socket = self.ctx.socket(zmq.SUB)
		self.push_sock: Socket = self.ctx.socket(zmq.PUSH)
		self._connected = False
		self.manager = UIManager()
		self.window.center_window() # set_location(0,0)
		self.width = width
		self.height = height
		# self.player_list = None
		self.netplayers = []
		self.physics_engine = None
		self.bomb_list = None
		self.particle_list = None
		self.flame_list = None
		self.title = title
		self.eventq = Queue()
		self.client = Client(serveraddress=('127.0.0.1', 9696), eventq=self.eventq)
		self.game_ready = False
		self.timer = UILabel(text='.', align="right", size_hint_min=(30, 20))

		self.grid = arcade.gui.UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		self.connectb = arcade.gui.UIFlatButton(text="Connect", width=150)
		self.grid.add(self.connectb, col_num=1, row_num=0)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="right", anchor_y="top", child=self.grid,)

		health = UILabel(align="right", size_hint_min=(30, 20))
		bombs = UILabel(align="right", size_hint_min=(30, 20))
		status = UILabel(align="right", size_hint_min=(30, 20))

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
						UILabel(text="status:", align="left", width=50),
					],
				),
				# Create one vertical UIBoxLayout per column and add the labels
				UIBoxLayout(vertical=True, children=[self.timer, health, bombs, status]),
			],
		)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="left", anchor_y="top", child=self.columns,)

		@self.connectb.event("on_click")
		def on_connect_to_server(event):
			self.start_client()

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.netplayers)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

	def connected(self):
		return self._connected

	def start_client(self):
		logger.info(f'{self} start_client')
		self.sub_sock.connect('tcp://127.0.0.1:9696')
		self.sub_sock.subscribe('')
		self.push_sock.connect('tcp://127.0.0.1:9697')
		self._connected = True

	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_BLUE
		self.manager.enable()

	def on_draw(self):
		self.clear()
		self.manager.draw()

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
		# logger.debug(f'{key} pek:{self.player_event} skpk:{self.keys_pressed}')
		if key == arcade.key.ESCAPE or key == arcade.key.Q:
			arcade.close_window()

	def on_key_release(self, key, modifiers):
		self.player_event.keys[key] = False
		self.keys_pressed.keys[key] = False
	def oldon_key_release(self, key, modifiers):
		if key == arcade.key.UP or key == arcade.key.DOWN or key == arcade.key.W or key == arcade.key.S:
			self.playerone.change_y = 0
		elif key == arcade.key.LEFT or key == arcade.key.RIGHT or key == arcade.key.A or key == arcade.key.D:
			self.playerone.change_x = 0


	def posupdate(self, dt):
		self.t += dt
		# Now calculate the new position based on the server information
		if len(self.position_buffer) == 0:
			# logger.warning(f'position_buffer < 2 posb: {self.position_buffer} ppos: {self.playerone.position}')
			return

		if len(self.position_buffer) < 2:
			# p0, t0 = self.position_buffer.pop()
			#logger.warning(f'position_buffer < 2 posb: {self.position_buffer} {len(self.position_buffer)} ppos: {self.playerone.position} p0: {p0} t0: {t0}')
			#self.playerone.position = p0
			return

		# These are the last two positions. p1 is the latest, p0 is the
		# one immediately preceding it.
		p0, t0 = self.position_buffer.pop()
		p1, t1 = self.position_buffer.pop()

		dtt = t1 - t0
		if dtt == 0:
			return

		# Calculate a PREDICTED future position, based on these two.
		# velocity = (p1 - p0) / dtt
		velocity = PLAYER_MOVEMENT_SPEED/dtt
		self.playerone.position = p1
		# predicted position
		#predicted_position = velocity * dtt + p1
		# x = (self.t - 0) / dtt
		# x = min(x, 1)
		# try:
		# 	interp_position = arcade.math.lerp(self.player_position_snapshot, predicted_position, x)
		# except TypeError as e:
		# 	logger.warning(f'{e} {type(e)} possnap:{self.player_position_snapshot} predicted:{predicted_position}  x:{x} ')
		# 	interp_position = predicted_position
		# self.playerone.position = interp_position
		# self.player.position = p1
		# self.ghost.position = p1



	def on_update(self, dt):
		# self.posupdate(dt)
		# try:
		# 	if self.connected():
		# 		self.playerone.position = self.position_buffer.pop()
		# except Exception as e:
		# 	logger.error(f'{e} {type(e)} posb:  {self.position_buffer} ppos: {self.playerone.position}')
		try:
			self.physics_engine.update()
		except Exception as e:
			logger.error(f'{e} {type(e)} posb: {self.position_buffer} ppos: {self.playerone}')
		for b in self.bomb_list:
			bombflames = b.update()
			if bombflames: # bomb returns flames when exploding
				self.particle_list.extend(bombflames.get("plist"))
				self.flame_list.extend(bombflames.get("flames"))
				if b.bomber == self.client.client_id:
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
			bomb = Bomb("data/bomb.png",scale=1, bomber=self.client.client_id, timer=1500)
			bomb.center_x = self.playerone.center_x
			bomb.center_y = self.playerone.center_y
			self.bomb_list.append(bomb)
			self.playerone.bombsleft -= 1
			# logger.info(f'bombdrop {bomb} by plid {self.client.client_id} bl: {len(self.bomb_list)} p1: {self.playerone}')
			# self.client.send_queue.put({'msgtype': 'bombdrop', 'bomber': self.client.client_id, 'pos': bomb.position, 'timer': bomb.timer})


async def thread_main(window, mainmenu, game, loop):
	# todo do connection here
	async def pusher():
		"""Push the player's INPUT state 60 times per second"""
		while True:
			d = game.player_event.asdict()
			msg = dict(counter=1, event=d)
			msg['client_id'] = game.playerone.client_id
			if game.connected():
				# logger.info(f'push: {d} msg: {msg}')
				await game.push_sock.send_json(msg)
			await asyncio.sleep(1 / UPDATE_TICK)

	async def receive_game_state():
		while True:
			_gs = await game.sub_sock.recv_string()
			gs = json.loads(_gs)
			# game.game_state.from_json(gs)
			game.game_state.jsonupdate(gs)
			# print(f'_gs: {_gs}')
			# print(f'gs: {gs}')
			ps = game.game_state.player_states[0]
			# print(f'gamestate={game.game_state} ps={ps}')
			if len(game.game_state.player_states) >= 2:
				logger.info(f'game.game_state.player_states: {game.game_state.player_states}')
			t = time.time()
			try:
				# recvx = [k for k in gs.get('player_states') if k.get('client_id') == game.playerone.client_id][0]['x']
				# recvy = [k for k in gs.get('player_states') if k.get('client_id') == game.playerone.client_id][0]['y']
				# recvx = [k.get('x') for k in gs.get('player_states') if k.get('client_id') == game.playerone.client_id]
				# recvy = [k.get('y') for k in gs.get('player_states') if k.get('client_id') == game.playerone.client_id]
				# recv_pos = [(k.get('x'), k.get('y')) for k in gs.get('player_states') if k.get('client_id') == game.playerone.client_id][0]
				for p in gs.get('player_states'):
					# print(f'p: {p} ')
					if p.get('client_id') == game.playerone.client_id:
						recv_pos = (p.get('x'), p.get('y'))
						game.playerone.setpos(recv_pos)
						logger.debug(f'recvpos {recv_pos} p: {p}')
					else:
						logger.info(f'netplayer: {p}')
						# logger.debug(f'rx: {recvx} ry:{recvy} newpos: {recv_pos}')
			except (AttributeError,IndexError) as e:
				logger.error(f'{e} _gs: {_gs} gs: {gs}')
			#game.position_buffer.append(((ps.x, ps.y), t))
			game.t = 0
			game.player_position_snapshot = copy.copy(game.playerone.position)
			# if ps.client_id == game.playerone.client_id:
			# 	# oldpos = game.playerone.position
			# 	#game.playerone.position = (ps.x, ps.y)
			# 	# game.playerone.setpos((ps.x, ps.y))
			# 	if recv_pos:
			# 		game.playerone.setpos(recv_pos)
			# 	# logger.debug(f'rx: {recvx} ry:{recvy} ox:{ox} {oy} newpos: {game.playerone.position}\nrecv gs:{_gs}\nps:{ps}\ngamestate: {game.game_state}')

	try:
		await asyncio.gather(pusher(), receive_game_state())
	finally:
		logger.debug('closing sockets')
		game.sub_sock.close(1)
		game.push_sock.close(1)
		game.ctx.destroy(linger=1)


def thread_worker(window, mainmenu, game):
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	loop.create_task(thread_main(window, mainmenu, game, loop))
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
	thread = Thread(target=thread_worker, args=(mainwindow,mainmenu, game,), daemon=True)
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
