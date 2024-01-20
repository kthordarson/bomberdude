#!/usr/bin/python
from argparse import ArgumentParser

import asyncio
from typing import Dict, Tuple
from contextlib import suppress

import random
from queue import Queue, Empty
import arcade
from arcade.gui import UIManager, UILabel, UIBoxLayout
from arcade.gui.widgets.layout import UIAnchorLayout

from loguru import logger
from objects import Bomberplayer, Bomb, KeysPressed
# from menus import MainMenu
from constants import *
from networking import Client, BombClientProtocol, DatagramConnection
from exceptions import *

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
	def __init__(self):
		super().__init__()
		self.manager = UIManager()
		self.game = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
		start_new_game_button = arcade.gui.UIFlatButton(text="Start New Game", width=150)
		exit_button = arcade.gui.UIFlatButton(text="Exit", width=320)
		# Initialise a grid in which widgets can be arranged.
		self.grid = arcade.gui.UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		# Adding the buttons to the layout.
		self.grid.add(start_new_game_button, col_num=1, row_num=0)
		self.grid.add(exit_button, col_num=0, row_num=2, col_span=2)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="center_x", anchor_y="center_y", child=self.grid,)

		@start_new_game_button.event("on_click")
		def on_click_start_new_game_button(event):
			self.game.setup()
			self.window.show_view(self.game)

		@exit_button.event("on_click")
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
		self.manager = UIManager()
		self.window.set_location(0,0)
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
		self.playerone = None
		self.client = Client(serveraddress=('127.0.0.1', 9696), eventq=self.eventq)
		self.game_ready = False
		self.timer = UILabel(text='.', align="right", size_hint_min=(30, 20))
		# start_new_game_button = arcade.gui.UIFlatButton(text="Start New Game", width=150)
		# exit_button = arcade.gui.UIFlatButton(text="Exit", width=320)
		# Initialise a grid in which widgets can be arranged.
		# self.grid = arcade.gui.UIGridLayout(column_count=2, row_count=3, horizontal_spacing=20, vertical_spacing=20)
		# Adding the buttons to the layout.
		# self.grid.add(start_new_game_button, col_num=1, row_num=0)
		# self.grid.add(exit_button, col_num=0, row_num=2, col_span=2)

		wood = UILabel(align="right", size_hint_min=(30, 20))
		stone = UILabel(align="right", size_hint_min=(30, 20))
		food = UILabel(align="right", size_hint_min=(30, 20))

		self.columns = UIBoxLayout(
			vertical=False,
			children=[
				# Create one vertical UIBoxLayout per column and add the labels
				UIBoxLayout(
					vertical=True,
					children=[
						UILabel(text="Time:", align="left", width=50),
						UILabel(text="Wood:", align="left", width=50),
						UILabel(text="Stone:", align="left", width=50),
						UILabel(text="Food:", align="left", width=50),
					],
				),
				# Create one vertical UIBoxLayout per column and add the labels
				UIBoxLayout(vertical=True, children=[self.timer, wood, stone, food]),
			],
		)
		self.anchor = self.manager.add(arcade.gui.UIAnchorLayout())
		self.anchor.add(anchor_x="left", anchor_y="top", child=self.columns,)

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.netplayers)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

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

		# self.player_list = arcade.SpriteList()
		self.bomb_list = arcade.SpriteList()
		self.particle_list = arcade.SpriteList()
		self.flame_list = arcade.SpriteList()
		self.netplayers = arcade.SpriteList()
		# self.playerone = self.client.player # Bomberplayer("data/playerone.png",scale=0.9) # arcade.Sprite("data/playerone.png",scale=1)
		# self.playerone.center_x = 128
		# self.playerone.center_y = 128
		# self.player_list.append(self.playerone)
		# self.scene.add_sprite("Player", self.playerone)

		# self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.scene['Blocks'], gravity_constant=GRAVITY)
		self.camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		self.gui_camera = arcade.SimpleCamera(viewport=(0, 0, self.width, self.height))
		self.end_of_map = (self.tile_map.width * self.tile_map.tile_width) * self.tile_map.scaling
		self.background_color = arcade.color.AMAZON
		self.manager.enable()
		self.playerone = Bomberplayer("data/playerone.png",scale=0.9, client_id='101')
		doconn = self.client.do_connect()
		self.client.start()
		self.client.receiver.start()
		self.background_color = arcade.color.DARK_BLUE_GRAY

		# self.client.receiver.run()
		# logger.info(f'{self} self.client.receiver started {self.client} {self.client.receiver}')

	def on_draw(self):
		self.clear()
		self.camera.use()
		self.scene.draw()
		if self.game_ready and self.playerone:
			self.netplayers.draw()
			self.playerone.draw()
			self.bomb_list.draw()
			self.particle_list.draw()
			self.flame_list.draw()
			for np in self.netplayers:
				np.text.draw()
		self.manager.draw()

		# self.gui_camera.use()
		arcade.draw_rectangle_filled(self.width , 20, self.width, 40, arcade.color.ALMOND)

	def on_key_press(self, key, modifiers):
		if not self.game_ready:
			logger.warning(f'game not ready')
			#return
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
			self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})

	def on_key_release(self, key, modifiers):
		if not self.game_ready:
			return
		if key == arcade.key.UP or key == arcade.key.DOWN or key == arcade.key.W or key == arcade.key.S:
			self.playerone.change_y = 0
		elif key == arcade.key.LEFT or key == arcade.key.RIGHT or key == arcade.key.A or key == arcade.key.D:
			self.playerone.change_x = 0

	def handle_netevent(self, netevent):
		msgtype = netevent.get('msgtype', 'nonetype')
		match msgtype:
			case 'refresh_playerlist':
				playerlist = netevent.get('playerlist')
				for np in playerlist:
					npclid = playerlist[np].get('client_id')
					npos = playerlist[np].get('pos')
					# logger.info(f'np: {np} npos:{npos} {playerlist[np]}')
					text = arcade.Text(f'{npclid} {npos}', npos[0],npos[1], arcade.color.GREEN)
					[k.setpos(playerlist[np].get('pos')) for k in self.netplayers if k.client_id == np]
			case 'trigger_netplayers':
				playerlist = netevent.get('playerlist')
				newplayer = netevent.get('newplayer')
				newplayerpos = newplayer.get('pos')
				if newplayer:
					netplayer = Bomberplayer("data/netplayer.png",scale=0.9, client_id=newplayer.get('client_id'))
					netplayer.position = newplayerpos
					self.netplayers.append(netplayer)
					logger.debug(f'{msgtype} newplayer: {newplayer} netplayers:{len(self.netplayers)} ')
					netplayer.visible = True
			case 'trigger_newplayer':
				client_id = netevent.get('client_id')
				pos = netevent.get('setpos')
				self.playerone = Bomberplayer("data/playerone.png",scale=0.9, client_id=client_id)
				self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.scene['Blocks'], gravity_constant=GRAVITY)
				#self.playerone.client_id = client_id #  = Bomberplayer("data/playerone.png",scale=0.9, client_id=client_id)
				# self.playerone.change_x = 0
				# self.playerone.change_y = 0
				self.playerone.position = pos
				# self.playerone.center_x = pos[0]
				# self.playerone.center_y = pos[1]
				# self.player_list.append(self.playerone)
				self.game_ready = True
				logger.info(f'{msgtype} {self.playerone}')
				self.playerone.visible = True
			case 'bombdrop':
				if self.client.client_id != netevent.get('client_id'):
					logger.debug(f'{msgtype} {netevent}')
				# logger.debug(f'{msgtype} {netevent}')
			case 'playermove':
				clid = netevent.get('client_id')
				cx = netevent.get('pos')[0]
				cy = netevent.get('pos')[1]
				for player in self.netplayers:
					if clid == player.client_id:
						player.position = (cx,cy)
						player.text = arcade.Text(f'{clid} {player.position}', cx,cy, arcade.color.BLUE)
						# logger.debug(f'{msgtype} move {player} to {cx} {cy}')
					# else:
					# 	player.position = (cx,cy)
					# 	player.text = arcade.Text(f'{clid} {player.position}', cx,cy, arcade.color.RED)
					# 	logger.debug(f'{msgtype} move {player} to {cx} {cy}')

				#logger.debug(f'{msgtype} {netevent}')
			case _:
				logger.warning(f'{self} {netevent}')

	def on_update(self, delta_time):
		self.timer.value += delta_time
		if self.game_ready and self.playerone:
			try:
				self.physics_engine.update()
			except AttributeError as e:
				logger.error(f'{e} gameready:{self.game_ready} p1: {self.playerone}')
		self.client.update_run()
		self.client.update_run_recv()
		# self.client.send_queue.put({'msgtype': 'on_update', 'delta_time':delta_time, 'pos' : self.playerone.position, 'client_id': self.client.client_id})
		netevent = None
		try:
			netevent = self.client.eventq.get(block=False)
		except Empty:
			pass
		if netevent:
			self.handle_netevent(netevent)
		# self.bomb_list.update()
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
		if self.playerone and self.game_ready:
			self.camera.center(self.playerone.position)
		else:
			logger.warning(f'gameready: {self.game_ready} p1: {self.playerone}')

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
			self.client.send_queue.put({'msgtype': 'bombdrop', 'bomber': self.client.client_id, 'pos': bomb.position, 'timer': bomb.timer})

async def main(args, loop):
	""" Main function """
	loop = asyncio.get_event_loop()
	conn = await DatagramConnection.connect("127.0.0.1", 9696)
	logger.info(f'got conn: {conn}')
	for msg in conn.iter_messages():
		while msg:
			logger.info(f'got msg: {msg}')
			#msg = await conn.recv_message()
	await conn.wait_until_disconnected()

	# # connect = loop.create_datagram_endpoint(BombClientProtocol(loop), remote_addr=('127.0.0.1', 9696))
	# transport, protocol = await loop.create_datagram_endpoint(lambda: BombClientProtocol(loop),family=socket.AF_INET)
	# #transport, protocol = await connect
	# conn = cls(protocol)
	# try:
	# 	await asyncio.sleep(100000)
	# except asyncio.CancelledError:
	# 	transport.close()

	# mainwindow = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	# # gameview = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	# #game = Bomberdude(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
	# mainmenu = MainMenu()
	# mainwindow.show_view(mainmenu)
	# #window.setup()
	# arcade.run()


if __name__ == "__main__":
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--server', action='store', dest='server', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	parser.add_argument('-d','--debug', action='store_true', dest='debug', default=False)
	args = parser.parse_args()

	loop = asyncio.get_event_loop()
	loop.create_task(main(args, loop))
	loop.run_forever()
	loop.close()
