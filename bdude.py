#!/usr/bin/python
from typing import List, Optional, Tuple, Union
from pyglet.math import Mat4, Vec2, Vec3
from pymunk import Vec2d
import math
import zlib
import pickle
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
from arcade import get_window
from arcade.draw_commands import draw_line, draw_circle_filled, draw_circle_outline
from arcade.gui.widgets import _ChildEntry
from arcade.gui import UIManager, UIBoxLayout, UITextArea, UIFlatButton, UIGridLayout
from arcade.gui import UILabel
from arcade.gui.widgets.layout import UIAnchorLayout
from arcade.types import Point
from arcade.math import (get_angle_radians, rotate_point, get_angle_degrees,)
from loguru import logger
from objects import Bomberplayer, Bomb, KeysPressed, PlayerEvent, PlayerState, GameState, gen_randid, UIPlayerLabel, Bullet
from objects import pack, unpack, send_zipped_pickle, recv_zipped_pickle
from debug import draw_debug_manager, draw_debug_game, draw_debug_view,debug_dump_game, draw_debug_widgets
from constants import *
import requests
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



class MainView(arcade.View):
	def __init__(self, window, args, **kwargs):#, game, window, name, title):
		super().__init__()
		self.debugmode = args.debugmode
		self.window = window
		#self.window.center_window()
		self.game = Bomberdude(args)
		self.manager = UIManager()
		self.grid = UIGridLayout(column_count=1, row_count=4, name='maingrid')
		#self.grid = UIGridLayout(x=self.window.width/2,y=self.window.height/2,column_count=1, row_count=3, vertical_spacing=5, align_horizontal='center', align_vertical='top')
		self.sb = UIFlatButton(name='sb', text="Start New Game", width=150)
		self.startbtn = self.grid.add(self.sb, col_num=0, row_num=0)
		self.cb = UIFlatButton(name='cb', text="Connect", width=150)
		self.connectb = self.grid.add(self.cb, col_num=0, row_num=1)
		self.eb = UIFlatButton(name='eb', text="Exit", width=150)
		self.exitbtn = self.grid.add(self.eb, col_num=0, row_num=2)
		self.tb = UIFlatButton(name='tb', text="test", width=150)
		self.testbtn = self.grid.add(self.tb, col_num=0, row_num=3)
		# self.grid.add(, col_num=0, row_num=0)
		# self.grid.add(self.connectb, col_num=0, row_num=1)
		# self.grid.add(self.exitbtn, col_num=0, row_num=2)
		# self.manager.add(self.grid)
		self.anchor = self.manager.add(UIAnchorLayout(name='anchormenu')) # anchor_x='left', anchor_y='top',
		self.anchor.add( child=self.grid,)
		self.mouse_pos = Vec2d(x=0,y=0)

		@self.testbtn.event('on_click')
		def on_testbtn_click(event):
			logger.debug(f'{self} {event=}')

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
			self.game.do_connect()
			self.startbtn.visible = False
			self.exitbtn.visible = False
			self.startbtn.disabled = True
			self.exitbtn.disabled = True
			# self.game._connected = True
			self.connectb.text = f'{self.game.args.server}'
			self.connectb.disabled = True
			self.connectb.visible = False
			self.window.show_view(self.game)

	def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
		self.mouse_pos = Vec2d(x=x,y=y)

	def on_key_press(self, key, modifiers):
		if self.debugmode:
			logger.debug(f'{key=} {modifiers=} ap={self.anchor.position} gp={self.grid.position}')
		if key == arcade.key.F1:
			self.debugmode = not self.debugmode
			logger.debug(f'debugmode: {self.debugmode}')
		elif key == arcade.key.F2:
			pass
		elif key == arcade.key.F3:
			pass
		elif key == arcade.key.F4:
			pass
		elif key == arcade.key.F5:
			pass
		elif key == arcade.key.F6:
			pass
		elif key == arcade.key.F7:
			pass
		elif key == arcade.key.ESCAPE or key == arcade.key.Q:
			logger.warning(f'quit')
			arcade.close_window()
			return
		elif key == arcade.key.SPACE:
			pass
		elif key == arcade.key.UP or key == arcade.key.W:
			if modifiers == 16:
				self.anchor.move(0,1)
			if modifiers == 18:
				self.anchor.move(0,11)
		elif key == arcade.key.DOWN or key == arcade.key.S:
			if modifiers == 16:
				self.anchor.move(0,-1)
			if modifiers == 18:
				self.anchor.move(0, -11)
		elif key == arcade.key.LEFT or key == arcade.key.A:
			if modifiers == 16:
				self.anchor.move(-1,0)
			if modifiers == 18:
				self.anchor.move(-11,0)
		elif key == arcade.key.RIGHT or key == arcade.key.D:
			if modifiers == 16:
				self.anchor.move(1,0)
			if modifiers == 18:
				self.anchor.move(11,0)

	def on_show_view(self):
		self.window.background_color = arcade.color.BLACK
		self.manager.enable()


	def on_draw(self):
		self.clear()
		self.manager.draw()
		if self.debugmode:
			# draw_debug_view(self)
			draw_debug_widgets([self.grid,])

	def on_hide_view(self):
		self.manager.disable() # pass

class Bomberdude(arcade.View):
	def __init__(self, args):
		super().__init__()
		self.title = "Bomberdude"
		self.args = args
		self.window = get_window()
		self.debugmode = self.args.debugmode
		self.manager = UIManager()
		# self.window.center_window() # set_location(0,0)
		self.width = self.window.width
		self.height = self.window.height
		self.t = 0
		self._gotmap = False
		self.playerone = Bomberplayer(image="data/playerone.png",scale=0.9, client_id=gen_randid())
		self.keys_pressed = KeysPressed(self.playerone.client_id)
		self.hitlist = []
		self.player_event = PlayerEvent()
		self.game_state = GameState(game_seconds=0)
		self.ioctx = Context.instance()
		self.sub_sock = self.ioctx.socket(zmq.SUB) # : Socket
		# self.data_sock: Socket = self.ioctx.socket(zmq.SUB)
		self.push_sock = self.ioctx.socket(zmq.PUSH) # : Socket
		self._connected = False
		self.physics_engine = None
		self.netplayers = []
		self.eventq = Queue()
		self.graw_graphs = False
		self.poplist = []

		self.bomb_list = arcade.SpriteList(use_spatial_hash=True)
		self.bullet_list = arcade.SpriteList(use_spatial_hash=True)
		self.particle_list = arcade.SpriteList(use_spatial_hash=True)
		self.flame_list = arcade.SpriteList(use_spatial_hash=True)
		self.sprite_items = [self.bomb_list, self.bullet_list, self.particle_list, self.flame_list,]
		self.netplayers = arcade.SpriteList(use_spatial_hash=True)
		self.scenewalls = arcade.SpriteList(use_spatial_hash=True)
		self.sceneblocks = arcade.SpriteList(use_spatial_hash=True)
		self.walls = arcade.SpriteList(use_spatial_hash=True)

		self._show_kill_screen = False
		self.show_kill_timer = 1
		self.show_kill_timer_start = 1
		self.timer = 0
		self.view_bottom = 0
		self.view_left = 0
		self.mouse_pos = Vec2d(x=0,y=0)

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.game_state.players)}  {len(self.bomb_list)} {len(self.particle_list)} {len(self.flame_list)})'

	def connected(self):
		return self._connected

	def show_kill_screen(self):
		self.show_kill_timer -= 1/UPDATE_TICK
		self.window.set_caption(f'{self.title} killed {self.show_kill_timer:.1f}')
		if self.show_kill_timer <= 0:
			self._show_kill_screen = False
			self.respawn_playerone()
			self.window.set_caption(f'{self.title} respawned')
		return self._show_kill_screen

	def respawn_playerone(self):
		repawnevent = {'event_time':0, 'event_type': 'respawn', 'client_id' : self.playerone.client_id, 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
		self.eventq.put(repawnevent)
		# self.playerone.respawn()

	def do_connect(self):
		self.sub_sock.connect(f'tcp://{self.args.server}:9696')
		self.sub_sock.subscribe('')
		#self.data_sock.connect(f'tcp://{self.args.server}:9699')
		#self.data_sock.subscribe('gamedata')
		#self.data_sock.setsockopt(zmq.SUBSCRIBE, b'gamedata')
		# logger.info(f'{self.data_sock=}')
		self.push_sock.connect(f'tcp://{self.args.server}:9697')
		connection_event = {
			'event_time':0,
			'event_type': 'newconn',
			'client_id' : self.playerone.client_id,
			'handled': False,
			'handledby': 'do_connect',
			'eventid': gen_randid()}
		self.eventq.put(connection_event)
		self._connected = True
		self.setup_network()
		self.window.set_caption(f'{self.title} connected to {self.args.server} playerid: {self.playerone.client_id}')

	# def on_resize(self, width, height):
	# 	self.width = width
	# 	self.height = height
	# 	self.camera.resize(width, height)

	def on_show_view(self):
		self.window.background_color = arcade.color.GRAY_BLUE
		self.manager.enable()


	def on_hide_view(self):
		self.manager.disable()

	def setup_network(self):
		# get tilemap and scene from server
		#request = {'event_time':0, 'event_type': 'getmap', 'client_id' : self.playerone.client_id, 'handled': False, 'handledby': 'setup_network', 'eventid': gen_randid()}
		#self.eventq.put(request)
		resp = json.loads(requests.get(f'http://{self.args.server}:9699/get_tile_map').text)
		logger.debug(f'{resp}')
		position = resp.get('position')
		self.game_state.load_tile_map(resp.get('mapname'))
		self._gotmap = True
		# resp = requests.get(f'http://{self.args.server}:9699/get_position')
		# pos = resp.text
		# logger.info(f'{self} {resp=} {self._gotmap=} {self.connected()=} {pos=}')
		self.setup(position)

	def setup(self,position=(99,99)):

		# self.tile_map = arcade.load_tilemap('data/map3.json', layer_options={"Blocks": {"use_spatial_hash": True},}, scaling=TILE_SCALING)
		# self.game_state.scene = arcade.Scene.from_tilemap(self.game_state.tile_map)
		#self.manager.adjust_mouse_coordinates = self.camera.mouse_coordinates_to_world

		self.background_color = arcade.color.AMAZON
		self.background_color = arcade.color.DARK_BLUE_GRAY
		#self.walls = []
		self.walls.extend(self.game_state.scene['Blocks'].sprite_list)
		self.walls.extend(self.game_state.scene['Walls'].sprite_list)
		logger.debug(f'wallsprites={len(self.walls.sprite_list)}')
		#_ = [self.sceneblocks.append(k) for k in self.game_state.scene['Blocks'].sprite_list]
		#_ = [self.scenewalls.append(k) for k in self.game_state.scene['Walls'].sprite_list]
		self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.walls, gravity_constant=GRAVITY)
		self.setup_panels()
		self.setup_perf()
		self.setup_labels()
		# self.manager.enable()
		self.manager.enable()
		self.playerone.position = position
		self.camera = arcade.Camera()
		self.guicamera = arcade.Camera()
		self.game_state.scene.add_sprite_list_after("Player", "Walls")

	def setup_labels(self):
		self.draw_labels = False
		self.showkilltext = arcade.Text(f"kill: {self.show_kill_timer:.1f}",100, 100, arcade.color.RED, 22)
		self.netplayer_labels = []
		self.netplayerboxes = []

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
		#self.grid = UIGridLayout(x=123,y=123,column_count=2, row_count=3, vertical_spacing=5)
		self.grid = self.manager.add(UIGridLayout(name='grid', column_count=2, row_count=2, vertical_spacing=5, align_horizontal='center', align_vertical='center', size_hint=(26,27)))
		# gridsb = self.grid.add(self.startbtn, col_num=0, row_num=0)
		font_size = 12
		pos=font_size*2
		sy=self.window.height-pos
		sx=self.window.width-100
		self.health_label = arcade.Text(text=f'h', start_x=sx, start_y=sy, color=arcade.color.RED, font_size=font_size)
		sy -= font_size + 3
		#sx += self.health_label.width + 5
		self.timer_label = arcade.Text(text=f't', start_x=sx, start_y=sy, color=arcade.color.RED, font_size=font_size)
		sy -= font_size + 3
		#sx += self.timer_label.width + 5
		self.score_label = arcade.Text(text=f's', start_x=sx, start_y=sy, color=arcade.color.RED, font_size=font_size)
		sy -= font_size + 3
		#sx += self.score_label.width + 5
		self.bombs_label = arcade.Text(text=f'b', start_x=sx, start_y=sy, color=arcade.color.RED, font_size=font_size)

		self.labels = [self.timer_label, self.health_label, self.score_label, self.bombs_label,]
		#self.netplayer_columns = UIBoxLayout(align='center',vertical=True,space_between=10)
		self.netplayer_grid = UIGridLayout(name='npgrid', x=23,y=23,size_hint=(144,178), column_count=4, row_count=4, vertical_spacing=15)

		xpos = self.window.width//2 # - len(self.netplayer_labels)*columns.width
		ypos = self.window.height//2 # - len(self.netplayer_labels)*20
		self.anchor = self.manager.add(UIAnchorLayout(name='npanchor', x=4, y=4, anchor_x='left', anchor_y='bottom' ))#, anchor_y='top'))
		self.anchor.add(child=self.netplayer_grid)

		#columns = UIBoxLayout(align='left',vertical=True,children=self.labels,)
		#anchor = self.manager.add(UIAnchorLayout())#, anchor_y='top'))
		#anchor.add(child=columns, anchor_x='left', anchor_y='top')
		#self.grid.add(anchor, col_num=0, row_num=0)

		# self.anchor.add(anchor_x="center_x", anchor_y="center_y", child=self.grid,)




	def center_camera_on_player(self, speed=0.2):
		screen_center_x = 1 * (self.playerone.center_x - (self.camera.viewport_width / 2))
		screen_center_y = 1 * (self.playerone.center_y - (self.camera.viewport_height / 2))
		if screen_center_x < 0:
			screen_center_x = 0
		if screen_center_y < 0:
			screen_center_y = 0
		player_centered = (screen_center_x, screen_center_y)
		self.camera.move_to(player_centered, speed)
		# self.guicamera.move_to(player_centered, speed)

	def xadjust_mouse_coordinates(self, x, y):
		"""
		This method is used, to translate mouse coordinates to coordinates
		respecting the viewport and projection of cameras.
		The implementation should work in most common cases.

		If you use scrolling in the :py:class:`arcade.experimental.camera.Camera2D` you have to reset scrolling
		or overwrite this method using the camera conversion: `ui_manager.adjust_mouse_coordinates = camera.mouse_coordinates_to_world`
		"""
		vx, vy, vw, vh = self.window.ctx.viewport
		pl, pr, pb, pt = self.window.ctx.projection_2d
		proj_width, proj_height = pr - pl, pt - pb
		dx, dy = proj_width / vw, proj_height / vh
		return (x - vx) * dx, (y - vy) * dy

	def adjust_mouse_coordinates(self, x, y):
		"""
		This method is used, to translate mouse coordinates to coordinates
		respecting the viewport and projection of cameras.
		The implementation should work in most common cases.

		If you use scrolling in the :py:class:`arcade.experimental.camera.Camera2D` you have to reset scrolling
		or overwrite this method using the camera conversion:   `ui_manager.adjust_mouse_coordinates = camera.mouse_coordinates_to_world`
		"""
		# vx, vy, vw, vh = self.window.ctx.viewport
		vx, vy, vw, vh = self.window.get_viewport()
		pl, pr, pb, pt = self.window.ctx.projection_2d
		proj_width, proj_height = pr - pl, pt - pb
		dx, dy = proj_width / (vw+1), proj_height / (vh+1)
		return (x + vx) * dx, (y + vy) * dy # only works if dx and dy = 1

	def on_draw(self):
		if not self._gotmap:
			return
		self.camera.use()
		arcade.start_render()
		# self.draw_player_panel()
		#self.camera.use()
		# self.guicamera.center(self.playerone.position)
		#self.clear()
		self.game_state.scene.draw()
		for sprite_list in self.sprite_items:
			sprite_list.draw()
		self.playerone.draw()
		self.manager.draw()
		#self.bullet_list.draw()
		if self.draw_labels:
			for label in self.labels:
				label.draw()
		# self.manager.draw()
		#self.bomb_list.draw()
		#self.particle_list.draw()
		#self.flame_list.draw()

		#self.netplayers.draw()
			# draw_line(start_x=self.mouse_pos.x, start_y=self.mouse_pos.y, end_x=self.playerone.center_x, end_y=self.playerone.center_y, color=arcade.color.RED, line_width=1)
			# draw_line(start_x=self.mouse_pos.x, start_y=self.playerone.center_y, end_x=self.playerone.center_x, end_y=self.mouse_pos.y, color=arcade.color.RED, line_width=1)

		if self.debugmode:
			arcade.Text(f'p1center: {self.playerone.center_x} {self.playerone.center_y} ', 23, 109, arcade.color.RED, font_size=12).draw()
			cgmpr = self.get_map_coordinates_rev(self.playerone.position)
			draw_line(start_x=cgmpr.x, start_y=cgmpr.y,end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, color=arcade.color.VIOLET_BLUE, line_width=1)

			# arcade.Text(f'GRID x={self.grid.x} y={self.grid.y} ', int(self.grid.x), int(self.grid.y), arcade.color.BLACK, font_size=10).draw()
			# draw_debug_view(self)
			draw_debug_widgets([self.grid,  self.netplayer_grid, self.anchor,])
			for bullet in self.bullet_list.sprite_list:
				draw_line(start_x=bullet.center_x, start_y=bullet.center_y, end_x=cgmpr.x, end_y=cgmpr.y, color=arcade.color.BLUE, line_width=1)
				#bullet.draw()
		if self._show_kill_screen:
			self.guicamera.use()
			self.show_kill_screen()
			#self.show_kill_timer = self.show_kill_timer_start-time.time()
			self.showkilltext.value = f"kill: {self.show_kill_timer:.1f}"
			self.showkilltext.draw()
		if self.graw_graphs:
			self.guicamera.use()
			self.perf_graph_list.draw()
			# Get & draw the FPS for the last 60 frames
			if arcade.timings_enabled():
				self.fps_text.value = f"FPS: {arcade.get_fps(60):5.1f}"
				self.fps_text.draw()
		self.camera.center(self.playerone.position)


	def send_key_press(self, key, modifiers):
		pass

	def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
		#self.mouse_pos = self.manager.adjust_mouse_coordinates(x,y)
		#x,y = self.mouse_pos = self.manager.adjust_mouse_coordinates(x,y)
		self.mouse_pos = Vec2d(x=x,y=y)
		#self.mouse_pos = (x+self.view_left,y+self.view_bottom)
		cgmpr = self.get_map_coordinates_rev(self.playerone.position)
		#x = x#+self.view_left
		#y = y#+self.view_bottom
		# mouse_angle = get_angle_degrees( self.playerone.center_x-self.view_left, self.playerone.center_y-self.view_bottom, x, y)
		mouse_angle = get_angle_degrees( cgmpr.x , cgmpr.y , x, y)
		# mouse_angle += 180
		angle_change = mouse_angle - self.playerone.angle
		self.playerone.rotate_around_point(self.playerone.position, angle_change)

		y_diff = self.mouse_pos.y-cgmpr.y
		x_diff = self.mouse_pos.x-cgmpr.x
		target_angle_radians = math.atan2(y_diff, x_diff)
		if target_angle_radians < 0:
			target_angle_radians += 2 * math.pi
		actual_angle_radians = math.radians(self.playerone.angle-90) #-90#  - IMAGE_ROTATION
		if actual_angle_radians > 2 * math.pi:
			actual_angle_radians -= 2 * math.pi
		elif actual_angle_radians < 0:
			actual_angle_radians += 2 * math.pi
		self.playerone.angle = math.degrees(actual_angle_radians) +90 # + IMAGE_ROTATION
		if self.playerone.angle > 360:
			self.playerone.angle = 0


	def flipyv(self, v):
		return Vec2d(x=int(v.x), y=int(-v.y + self.window.height))

	def get_map_coordinates_rev(self, camera_vector: Union[Vec2d, tuple]) -> Vec2d:
		"""
		* reversed Returns map coordinates in pixels from screen coordinates based on the camera position
		:param camera_vector: Vector captured from the camera viewport
		"""
		return Vec2d(*camera_vector) - Vec2d(*self.camera.position)

	def on_mouse_press(self, x, y, button, modifiers):
		self.mouse_pos = Vec2d(x=x,y=y)
		#self.mouse_pos = self.manager.adjust_mouse_coordinates(x,y)
		# x,y = self.manager.adjust_mouse_coordinates(x,y)
		# left, screen_width, bottom, screen_height = self.window.get_viewport()
		screen_center_x = self.camera.viewport_width // 2
		screen_center_y = self.camera.viewport_height // 2
		# print(f'{self.camera.viewport} {screen_center_x=} {screen_center_y=} {self.playerone.center_x=} {self.playerone.center_y=} {self.playerone.position=}')
		# print(f'{left=} {screen_width=} {bottom=} {screen_height=}')

		# if self.debugmode:
		# 	pxm,pym = self.adjust_mouse_coordinates(x=self.playerone.center_x, y=self.playerone.center_y)
		# 	mx,my = self.adjust_mouse_coordinates(x=self.mouse_pos[0], y=self.mouse_pos[1])
		# 	draw_circle_filled(x,y,1,arcade.color.YELLOW)
		# 	draw_circle_filled(pxm,pym,2,arcade.color.RED)
		# 	draw_circle_filled(mx,my,2,arcade.color.BLUE)
		# 	draw_circle_filled(self.mouse_pos[0],self.mouse_pos[1],2,arcade.color.GREEN)
		# 	logger.info(f'{x=} {y=} p1c=({self.playerone.center_x},{self.playerone.center_y}) -- {mx=} {pxm=} -  {my=}  {pym=}')
		# 	#draw_line(start_x=self.mouse_pos.x, start_y=self.mouse_pos.y, end_x=self.playerone.position[0], end_y=self.playerone.position[1], color=arcade.color.RED, line_width=1)
		# 	#draw_line(start_x=self.mouse_pos.x, start_y=self.mouse_pos.y, end_x=x, end_y=y, color=arcade.color.BLUE, line_width=1)
		# 	#draw_line(start_x=self.mouse_pos.x, start_y=self.mouse_pos.y, end_x=mx, end_y=my, color=arcade.color.GREEN, line_width=1)
		# 	cgmp = self.camera.get_map_coordinates(self.playerone.position)
		# 	cgmpr = self.get_map_coordinates_rev(self.playerone.position)
		# 	# draw_line(start_x=cgmp.x, start_y=cgmp.y,end_x=self.mouse_pos.x, end_y=self.mouse_pos.y, color=arcade.color.VIOLET_BLUE, line_width=1)
		# 	logger.debug(f'position {self.playerone.position} --- {cgmp=} --- {cgmpr=}')

		# 	cgmp = self.camera.get_map_coordinates(Vec2d(x=screen_center_x, y=screen_center_y))
		# 	cgmpr = self.get_map_coordinates_rev(Vec2d(x=screen_center_x, y=screen_center_y))
		# 	logger.debug(f'screen_center {screen_center_x} {screen_center_y} --- {cgmp=} --- {cgmpr=}')

		lzrsprt=arcade.load_texture("data/laserBlue01vv32.png")
		cgmpr = self.get_map_coordinates_rev(self.playerone.position)
		# start_x = cgmpr.x # self.playerone.center_x # screen_center_x
		# start_y = cgmpr.y # self.playerone.center_y # screen_center_y
		if button == 1:
			bullet = Bullet(lzrsprt, scale=1)
			bullet.center_x = cgmpr.x
			bullet.center_y = cgmpr.y
			# dest_x = x #+ self.view_left
			# dest_y = y #+ self.view_bottom
			x_diff = x - cgmpr.x
			y_diff = y - cgmpr.y
			# angle = math.atan2(y_diff, x_diff)  + 3.14 / 2
			angle = math.atan2(x_diff, y_diff)  + 3.14 / 2
			# angle = get_angle_radians(cgmpr.x, cgmpr.y, self.mouse_pos.x, self.mouse_pos.y)
		# print(f'{dest_x=} {x_diff=} {dest_y=} {y_diff=} {angle=} {self.playerone.angle=}')
			#size = max(self.playerone.width, self.playerone.height) / 4
			#bullet.center_x += size * math.cos(angle)
			#bullet.center_y += size * math.sin(angle)
			# angle = cgmpr.get_angle_between(self.mouse_pos)
			bullet.angle = math.degrees(angle) #- 180
			# xm,ym = self.manager.adjust_mouse_coordinates(x,y)#
			bullet.change_x = 1-math.cos(angle) * BULLET_SPEED
			bullet.change_y = math.sin(angle) * BULLET_SPEED
			# bullet.rotate_around_point(bullet.position, angle)
			bullet.center_x = self.playerone.center_x
			bullet.center_y = self.playerone.center_y
			self.bullet_list.extend([bullet,])
			logger.info(f"Bullet angle: {bullet.angle:.2f} p1a= {self.playerone.angle} a={angle} bcx={bullet.change_x} bcy={bullet.change_y}  x= {x} vl= {self.view_left} xl={x+self.view_left} y= {y} vb= {self.view_bottom} yb={y+self.view_bottom} {button=}")

		elif button == 4:
			bullet = Bullet(lzrsprt, scale=1)
			bp = Vec2d(x=cgmpr.x,y=cgmpr.y)
			bullet.center_x = bp.x
			bullet.center_y = bp.y
			p = self.flipyv(self.mouse_pos)# - bp
			bullet.change_x = p.x//100
			bullet.change_y = p.y//100
			self.bullet_list.extend([bullet,])
			#p = p.normalized()
			logger.info(f"Bullet angle: {bullet.angle:.2f} x= {x} vl= {self.view_left} xl={x+self.view_left} y= {y} vb= {self.view_bottom} yb={y+self.view_bottom} {button=}")
		else:
			logger.warning(f'{x=} {y=} {button=} {modifiers=}')
			return


	def on_key_press(self, key, modifiers):
		# todo check collisions before sending keypress...
		sendmove = False
		if self.playerone.killed:
			logger.warning(f'playerone killed')
			return
		# logger.debug(f'{key} {self} {self.client} {self.client.receiver}')
		elif key == arcade.key.F1:
			self.debugmode = not self.debugmode
			logger.debug(f'debugmode: {self.debugmode}')
		elif key == arcade.key.F2:
			self.game_state.debugmode = not self.game_state.debugmode
			logger.debug(f'gsdebugmode: {self.game_state.debugmode} debugmode: {self.debugmode}')
		elif key == arcade.key.F3:
			debug_dump_game(self)
		elif key == arcade.key.F4:
			self.graw_graphs = not self.graw_graphs
		elif key == arcade.key.F5:
			arcade.clear_timings()
		elif key == arcade.key.F6:
			self.draw_labels = not self.draw_labels
			# self.window.set_fullscreen(not self.window.fullscreen)
			# width, height = self.window.get_size()
			# self.window.set_viewport(0, width, 0, height)
			# self.camera = arcade.Camera(viewport=(0, 0, self.width, self.height))
		elif key == arcade.key.F7:
			self.window.set_fullscreen(not self.window.fullscreen)
			# width, height = self.window.get_size()
			self.window.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)
			self.camera = arcade.Camera(viewport=(0, 0, self.width, self.height))
		elif key == arcade.key.ESCAPE or key == arcade.key.Q:
			logger.warning(f'quit')
			arcade.close_window()
			return
		elif key == arcade.key.SPACE:
			self.dropbomb(key)

		#self.player_event.keys[key] = True
		#self.keys_pressed.keys[key] = True
		elif key == arcade.key.UP or key == arcade.key.W:
			if len(self.hitlist) == 0:
				self.playerone.change_y = PLAYER_MOVEMENT_SPEED
				sendmove = True
		elif key == arcade.key.DOWN or key == arcade.key.S:
			if len(self.hitlist) == 0:
				self.playerone.change_y = -PLAYER_MOVEMENT_SPEED
				sendmove = True
		elif key == arcade.key.LEFT or key == arcade.key.A:
			if len(self.hitlist) == 0:
				self.playerone.change_x = -PLAYER_MOVEMENT_SPEED
				sendmove = True
		elif key == arcade.key.RIGHT or key == arcade.key.D:
			if len(self.hitlist) == 0:
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
		if not self._gotmap:
			self.setup_network()
		for game_event in game_events:
			event_type = game_event.get('event_type')
			if self.debugmode:
				pass # logger.info(f'{event_type=} {game_event=} {game_events=}')
			match event_type:
				case 'ackrespawn':
					clid = game_event.get("client_id")
					[k.set_texture(arcade.load_texture('data/netplayer.png')) for k in self.netplayers if k.client_id == clid]#[0]
					logger.debug(f'{event_type} from {clid}')
					if clid == self.playerone.client_id:
						self.playerone.respawn()
				case 'upgradeblock':
					if self.debugmode:
						logger.info(f'{event_type} upgradetype {game_event.get("upgradetype")}')
				case 'acknewconn':
					if self.debugmode:
						logger.info(f'{event_type} {game_event}')
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
						self._show_kill_screen = True
						self.show_kill_timer = game_event.get('killtimer')
						self.show_kill_timer_start = game_event.get('killstart')
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
		gspcopy = copy.copy(self.game_state.players)
		for pclid in gspcopy:
			pclpos = self.game_state.players[pclid].get('position')
			# logger.info(f'pclid={pclid} gsp={self.game_state.players}')
			if pclid == self.playerone.client_id:
				continue
			if self.game_state.players[pclid].get('killed'): # add to pop list
				logger.info(f'killed pclid={pclid} gsp={self.game_state.players}')
			if pclid in [k.client_id for k in self.netplayers]:
				# logger.info(f'pclid={pclid} gsp={self.game_state.players}')
				if pclid != self.playerone.client_id:
					netplayer = [k for k in self.netplayers if k.client_id == pclid][0]
					player_label = [k for k in self.netplayer_labels if isinstance(k, UIPlayerLabel) and k.client_id == pclid][0]
					score = self.game_state.players[pclid].get('score')
					health = self.game_state.players[pclid].get('health')
					bombsleft = self.game_state.players[pclid].get('bombsleft')
					player_label.value = f'h:{health} s:{score} b:{bombsleft}'
					netplayer.position = pclpos
			else:
				# score = self.game_state.players[pclid].get('score')
				newplayer = Bomberplayer(image="data/netplayer.png",scale=0.9, client_id=pclid, position=pclpos)
				self.netplayers.append(newplayer)
				playerlabel = UIPlayerLabel(newplayer.client_id)
				# playerlabel.value = f'{pclid}' # pos: {pclpos} score: {score}'
				playerlabel.button.text = f'{pclid}'
				self.netplayer_labels.append(playerlabel)
				self.netplayer_grid.add(playerlabel.button, col_num=0, row_num=len(self.netplayer_labels))
				self.netplayer_grid.add(playerlabel, col_num=1, col_span=2,row_num=len(self.netplayer_labels)) # h
				# self.netplayerboxes.append(anchor)
				logger.info(f'newplayer: {newplayer} pos: {pclpos} players: {len(self.netplayers)} ')

	def update_poplist(self):
		for p in self.poplist:
			logger.info(f'plist={self.poplist} popping {p} gsp={self.game_state.players}')
			self.game_state.players.pop(p)
			logger.info(f'aftergsp={self.game_state.players}')
		self.poplist = []

	def update_viewport(self, dt):
		# --- Manage Scrolling ---
		# Track if we need to change the viewport
		changed = False
		# Scroll left
		left_bndry = self.view_left + VIEWPORT_MARGIN
		if self.playerone.left < left_bndry:
			self.view_left -= left_bndry - self.playerone.left
			changed = True

		# Scroll right
		right_bndry = self.view_left + SCREEN_WIDTH - VIEWPORT_MARGIN
		if self.playerone.right > right_bndry:
			self.view_left += self.playerone.right - right_bndry
			changed = True

		# Scroll up
		top_bndry = self.view_bottom + SCREEN_HEIGHT - VIEWPORT_MARGIN
		if self.playerone.top > top_bndry:
			self.view_bottom += self.playerone.top - top_bndry
			changed = True

		# Scroll down
		bottom_bndry = self.view_bottom + VIEWPORT_MARGIN
		if self.playerone.bottom < bottom_bndry:
			self.view_bottom -= bottom_bndry - self.playerone.bottom
			changed = True
#
		if changed:
			arcade.set_viewport(self.view_left, SCREEN_WIDTH + self.view_left, self.view_bottom, SCREEN_HEIGHT + self.view_bottom)

		# Save the time it took to do this.
		# self.processing_time = timeit.default_timer() - start_time

	def update_labels(self):
		self.timer_label.value = f'time {self.timer:.1f}'
		self.health_label.value = f'health {self.playerone.health}'
		self.score_label.value = f'score {self.playerone.score}'
		self.bombs_label.value = f'bombs {self.playerone.bombsleft}'

	def on_update(self, dt):
		if not self._gotmap:
			return
		# self.update_viewport(dt)
		self.update_labels()
		self.bullet_list.update()
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
		self.timer += dt
		if len(self.game_state.players) > 0:
			self.update_netplayers()
			self.update_poplist()

		self.hitlist = self.physics_engine.update()
		for b in self.bullet_list:
			b_hitlist = arcade.check_for_collision_with_list(b, self.walls)
			#b_hitlist.extend(arcade.check_for_collision_with_list(b, self.sceneblocks))
			for hit in b_hitlist:
				if self.debugmode:
					arcade.draw_rectangle_outline(center_x=hit.center_x, center_y=hit.center_y, width=hit.width-1, height=hit.height-1,color=arcade.color.RED)
					draw_circle_filled(center_x=hit.center_x, center_y=hit.center_y, radius=2, color=arcade.color.BLUE)
					draw_circle_filled(center_x=b.center_x, center_y=b.center_y, radius=2, color=arcade.color.ORANGE)
				hitblocktype = hit.properties.get('tile_id')
				#if hitblocktype == 12:
				logger.debug(f'{b} hit {hit} {hitblocktype=} hl={len(self.hitlist)}')
				b.remove_from_sprite_lists()

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
				event = {'event_time':0, 'event_type':'takedamage', 'damage': 10, 'killer':f.bomber, 'killed': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
				#self.game_state.game_events.append(event)
				self.eventq.put(event)
				f.remove_from_sprite_lists()
			f_hitlist = arcade.check_for_collision_with_list(f, self.walls)
			#f_hitlist.extend(arcade.check_for_collision_with_list(f, self.sceneblocks))
			for hit in f_hitlist:
				hitblocktype = hit.properties.get('tile_id')
				match hitblocktype:
					case 10:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 5:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						f.remove_from_sprite_lists()
					case 3 | 4:
						# logger.debug(f'hits: {len(f_hitlist)} flame {f} hit {hit} ')
						hit.remove_from_sprite_lists()
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
			p_hitlist = arcade.check_for_collision_with_list(p, self.walls)
			#p_hitlist.extend(arcade.check_for_collision_with_list(p, self.sceneblocks))
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
		# self.center_camera_on_player()


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
				bombsleft=game.playerone.bombsleft,
				gotmap=game._gotmap,
				msgsource='pushermsgdict',
				msg_dt=time.time())
			if game.connected():
				await game.push_sock.send_json(msg)
				await asyncio.sleep(1 / UPDATE_TICK)
			else:
				await asyncio.sleep(1)


	async def receive_game_state():
		gs = None
		while True:
			_gs = await game.sub_sock.recv_json()
			#gs = json.loads(_gs)
			game.game_state.from_json(_gs)
			#if game.debugmode:
			#	logger.info(f'_gs: {_gs.keys()=} {_gs=} ')
#			game.game_state.from_json(gs)
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
	await asyncio.gather(pusher(), receive_game_state(), )

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
	parser.add_argument('-d','--debug', action='store_true', dest='debugmode', default=False)
	parser.add_argument('-dp','--debugpacket', action='store_true', dest='packetdebugmode', default=False)
	args = parser.parse_args()

	app = arcade.Window(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=False, gc_mode='context_gc')
	# mainwindow = App(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=True)

	mainview = MainView(window=app, name='bomberdue', title='Bomberdude Main Menu', args=args)
	#mainwindow.add_page(MainPage, name='mainpage', title='Main Page')
	#mainwindow.add_page(MainMenu, name='mainmenu', title='Main Menu')
	#mainwindow.add_page(BomberdudePage, name='bdude', title='bdude')
	thread = Thread(target=thread_worker, args=(mainview.game,), daemon=True)
	thread.start()
	#mainwindow.show('mainpage')
	app.show_view(mainview)
	arcade.run()

if __name__ == "__main__":
	arcade.enable_timings(1000)
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	main()
	# arcade.run()
