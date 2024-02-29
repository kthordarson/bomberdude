#!/usr/bin/python
from typing import List, Optional, Tuple, Union
from pyglet.math import Mat4, Vec2, Vec3
from pymunk import Vec2d
import math
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
from arcade.gui import UIManager, UIBoxLayout, UITextArea, UIFlatButton, UIGridLayout, UILabel
from arcade.gui.widgets.layout import UIAnchorLayout
from arcade.types import Point
from arcade.math import (get_angle_radians, rotate_point, get_angle_degrees,)
from loguru import logger
from objects import Bomberplayer, Bomb, BiggerBomb, KeysPressed, PlayerEvent, PlayerState, gen_randid, UIPlayerLabel, Bullet
from objects import get_map_coordinates_rev
from objects import create_upgrade_block
from gamestate import GameState
from debug import debug_dump_game, draw_debug_widgets, draw_debug_players
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
		self.grid = UIGridLayout(column_count=1, row_count=4)
		#self.grid = UIGridLayout(x=self.window.width/2,y=self.window.height/2,column_count=1, row_count=3, vertical_spacing=5, align_horizontal='center', align_vertical='top')
		self.sb = UIFlatButton(text="Start New Game", width=150)
		self.startbtn = self.grid.add(self.sb, col_num=0, row_num=0)
		self.cb = UIFlatButton(text="Connect", width=150)
		self.connectb = self.grid.add(self.cb, col_num=0, row_num=1)
		self.eb = UIFlatButton(text="Exit", width=150)
		self.exitbtn = self.grid.add(self.eb, col_num=0, row_num=2)
		self.tb = UIFlatButton(text="test", width=150)
		self.testbtn = self.grid.add(self.tb, col_num=0, row_num=3)
		# self.grid.add(, col_num=0, row_num=0)
		# self.grid.add(self.connectb, col_num=0, row_num=1)
		# self.grid.add(self.exitbtn, col_num=0, row_num=2)
		# self.manager.add(self.grid)
		self.anchor = self.manager.add(UIAnchorLayout()) # anchor_x='left', anchor_y='top',
		self.anchor.add( child=self.grid,)
		self.mouse_pos = Vec2d(x=0,y=0)

		@self.testbtn.event('on_click')
		def on_testbtn_click(event):
			logger.debug(f'{self} {event=}')

		@self.startbtn.event("on_click")
		def on_click_start_new_game_button(event):
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
			pass # logger.debug(f'{key=} {modifiers=} ap={self.anchor.position} gp={self.grid.position}')
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
				pass #self.anchor.move(0,1)
			if modifiers == 18:
				pass #self.anchor.move(0,11)
		elif key == arcade.key.DOWN or key == arcade.key.S:
			if modifiers == 16:
				pass #self.anchor.move(0,-1)
			if modifiers == 18:
				pass #self.anchor.move(0, -11)
		elif key == arcade.key.LEFT or key == arcade.key.A:
			if modifiers == 16:
				pass #self.anchor.move(-1,0)
			if modifiers == 18:
				pass #self.anchor.move(-11,0)
		elif key == arcade.key.RIGHT or key == arcade.key.D:
			if modifiers == 16:
				pass #self.anchor.move(1,0)
			if modifiers == 18:
				pass #self.anchor.move(11,0)

	def on_show_view(self):
		self.window.background_color = arcade.color.BLACK
		self.manager.enable()


	def on_draw(self):
		self.clear()
		self.manager.draw()
		if self.debugmode:
			draw_debug_widgets([self.grid,])

	def on_hide_view(self):
		self.manager.disable() # pass

class Bomberdude(arcade.View):
	def __init__(self, args):
		super().__init__()
		self.title = "Bomberdude"
		self.args = args
		self.left_pressed = False
		self.right_pressed = False
		self.up_pressed = False
		self.down_pressed = False
		self.window = get_window()
		self.debugmode = self.args.debugmode
		self.manager = UIManager()
		# self.window.center_window() # set_location(0,0)
		self.width = self.window.width
		self.height = self.window.height
		self.t = 0
		self._gotmap = False
		self.playerone = Bomberplayer(texture="data/playerone.png", client_id=gen_randid())
		self.selected_bomb = 1
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
		self.eventq = Queue()
		self.draw_graphs = False
		self.draw_player_debug = False
		self.poplist = []
		self.netplayers = {}

		self.bomb_list = arcade.SpriteList(use_spatial_hash=True)
		# self.bullet_list = arcade.SpriteList(use_spatial_hash=True)
		self.particle_list = arcade.SpriteList(use_spatial_hash=True)
		self.flame_list = arcade.SpriteList(use_spatial_hash=True)
		self._show_kill_screen = False
		self.show_kill_timer = 1
		self.show_kill_timer_start = 1
		self.timer = 0
		self.view_bottom = 0
		self.view_left = 0
		self.mouse_pos = Vec2d(x=0,y=0)

	def __repr__(self):
		return f'Bomberdude( {self.title} np: {len(self.game_state.players)}  )'

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
		self.push_sock.connect(f'tcp://{self.args.server}:9697')
		connection_event = {
			'event_time':0,
			'event_type': 'newconnection',
			'client_id' : self.playerone.client_id,
			'handled': False,
			'handledby': 'do_connect',
			'eventid': gen_randid()}
		self.eventq.put(connection_event)
		self._connected = True
		self.setup_network()
		self.window.set_caption(f'{self.title} connected to {self.args.server} playerid: {self.playerone.client_id}')

	def on_resize(self, width, height):
		self.width = width
		self.height = height
		self.camera.resize(width, height)

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
		logger.debug(f'map {resp=}')
		position = Vec2d(x=resp.get('position')[0], y=resp.get('position')[1])
		self.game_state.load_tile_map(resp.get('mapname'))
		self._gotmap = True
		# resp = requests.get(f'http://{self.args.server}:9699/get_position')
		# pos = resp.text
		# logger.info(f'{self} {resp=} {self._gotmap=} {self.connected()=} {pos=}')
		self.setup(position)

	def setup(self,position):
		def bullet_hit_wall(bullet, wall, arbiter, space, data):
			bullet_shape = arbiter.shapes[0]	
			bullet_sprite = self.bullet_engine.get_sprite_for_shape(bullet_shape)
			bullet_sprite.remove_from_sprite_lists()
			# bullet.kill()
		# self.background_color = arcade.color.AMAZON
		self.background_color = arcade.color.BLACK
		#self.walls = []
		# self.walls.extend(self.game_state.scene['Blocks'].sprite_list)
		# self.walls.extend(self.game_state.scene['Walls'].sprite_list)
		# logger.debug(f'wallsprites={len(self.walls.sprite_list)}')
		#_ = [self.sceneblocks.append(k) for k in self.game_state.scene['Blocks'].sprite_list]
		#_ = [self.scenewalls.append(k) for k in self.game_state.scene['Walls'].sprite_list]
		# self.physics_engine = arcade.PhysicsEnginePlatformer(self.playerone, walls=self.game_state.scene["Walls"], platforms=self.game_state.scene["Blocks"], gravity_constant=GRAVITY)
		self.physics_engine = arcade.PhysicsEngineSimple(self.playerone, walls=[self.game_state.scene["Blocks"], self.game_state.scene["Walls"],])
		self.bullet_engine = arcade.PymunkPhysicsEngine(gravity=(0, -0), damping=1.0)
		self.bullet_engine.add_sprite_list(self.game_state.scene["Walls"], friction=WALL_FRICTION, collision_type="Walls", body_type=arcade.PymunkPhysicsEngine.STATIC)
		self.bullet_engine.add_sprite_list(self.game_state.scene["Blocks"], friction=WALL_FRICTION, collision_type="Walls", body_type=arcade.PymunkPhysicsEngine.STATIC)
		self.bullet_engine.add_collision_handler("Bullets", "Walls", post_handler=bullet_hit_wall)
		self.bullet_sprite = arcade.load_texture("data/bullet0.png")
		# self.physics_engine.walls.extend()

		#self.physics_engine = arcade.PymunkPhysicsEngine(gravity=(0, -0), damping=0.5)
		#self.physics_engine.add_sprite(self.playerone, friction=PLAYER_FRICTION, mass=PLAYER_MASS, collision_type="Players", max_horizontal_velocity=PLAYER_MAX_HORIZONTAL_SPEED, max_vertical_velocity=PLAYER_MAX_VERTICAL_SPEED)
		#self.physics_engine.add_sprite_list(self.game_state.scene['Background'], friction=WALL_FRICTION, collision_type="Background", body_type=arcade.PymunkPhysicsEngine.STATIC)
		#self.physics_engine.add_sprite_list(self.game_state.scene['Walls'], friction=WALL_FRICTION, collision_type="WALLS", body_type=arcade.PymunkPhysicsEngine.STATIC)

		self.setup_panels()
		self.setup_perf()
		self.setup_labels()
		# self.manager.enable()
		self.manager.enable()
		self.playerone.position = position
		self.camera = arcade.Camera()
		self.guicamera = arcade.Camera()

	def setup_labels(self):
		self.draw_labels = True
		self.showkilltext = arcade.Text(f"kill: {self.show_kill_timer:.1f}",100, 100, arcade.color.RED, 22)
		self.netplayer_labels = {}
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
		self.grid = self.manager.add(UIGridLayout(column_count=4, row_count=4, vertical_spacing=5, align_horizontal='center', align_vertical='center', size_hint=(26,27)))
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
		sy -= font_size + 3
		#sx += self.score_label.width + 5
		self.info_label = arcade.Text(text=f'i', start_x=sx, start_y=sy, color=arcade.color.RED, font_size=font_size)

		self.labels = [self.timer_label, self.health_label, self.score_label, self.bombs_label, self.info_label,]
		#self.netplayer_columns = UIBoxLayout(align='center',vertical=True,space_between=10)
		self.netplayer_grid = UIGridLayout(x=23,y=23,size_hint=(144,178), column_count=6, row_count=6, vertical_spacing=6, horizontal_spacing=6, align_horizontal='center', align_vertical='center')

		xpos = self.window.width//2 # - len(self.netplayer_labels)*columns.width
		ypos = self.window.height//2 # - len(self.netplayer_labels)*20
		self.anchor = self.manager.add(UIAnchorLayout(x=4, y=4, anchor_x='left', anchor_y='bottom' ))#, anchor_y='top'))
		self.anchor.add(child=self.netplayer_grid)

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

	def on_draw(self):
		if not self._gotmap:
			return
		self.camera.use()
		arcade.start_render()
		# self.draw_player_panel()
		#self.camera.use()
		# self.guicamera.center(self.playerone.position)
		#self.clear()
		self.game_state.scene['Background'].draw()
		self.game_state.scene['Walls'].draw()
		self.game_state.scene['Blocks'].draw()
		self.game_state.scene['Bullets'].draw()
		self.game_state.scene['Bombs'].draw()
		self.game_state.scene['Flames'].draw()
		self.game_state.scene['Particles'].draw()
		self.game_state.scene["Upgrades"].draw()
		self.game_state.scene["Netplayers"].draw()
		#for sprite_list in self.sprite_items:
		#	sprite_list.draw()
		self.playerone.draw()
		self.manager.draw()

		#self.bomb_list.draw()
		# self.flame_list.draw()
		# self.particle_list.draw()

		# self.netplayers.draw()
		# self.flame_list.draw()
		# self.particle_list.draw()
		# self.bomb_list.draw()
		#self.bullet_list.draw()
		# _ = [k.draw() for k in self.netplayers]
		#self.bullet_list.draw()
		if self.draw_labels:
			for label in self.labels:
				label.draw()
		if self.debugmode:
			self.camera.use()
			self.game_state.scene['Bullets'].draw_hit_boxes()
			self.game_state.scene['Blocks'].draw_hit_boxes()
		if self.debugmode:
			self.guicamera.use()
			arcade.Text(f'p1center: {self.playerone.center_x} {self.playerone.center_y} ', 23, 109, arcade.color.RED, font_size=12).draw()
			# draw_debug_widgets([self.grid,  self.netplayer_grid, self.anchor,])
		if self.draw_player_debug:
			try:
				draw_debug_players(self.game_state.players,self.netplayer_labels, self.camera)
			except Exception as e:
				logger.error(f'{e=} {type(e)}')
		if self._show_kill_screen:
			self.guicamera.use()
			self.show_kill_screen()
			#self.show_kill_timer = self.show_kill_timer_start-time.time()
			self.showkilltext.value = f"kill: {self.show_kill_timer:.1f}"
			self.showkilltext.draw()
		if self.draw_graphs:
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
		self.mouse_pos = Vec2d(x=x,y=y)
		cgmpr = get_map_coordinates_rev(self.playerone.position, self.camera) # get playerpos
		mouse_angle = get_angle_degrees( cgmpr.x , cgmpr.y , x, y)
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
		#if self.playerone.angle > 360:
		#	self.playerone.angle = 0

	def flipyv(self, v):
		return Vec2d(x=int(v.x), y=int(-v.y + self.window.height))


	def on_mouse_press(self, x, y, button, modifiers):
		self.mouse_pos = Vec2d(x=x,y=y)
		screen_center_x = self.camera.viewport_width // 2
		screen_center_y = self.camera.viewport_height // 2

		#cgmpr = Vec2d(x=x,y=y)
		cgmpr = get_map_coordinates_rev(self.playerone.position, self.camera)
		if button == 1:
			bullet = Bullet(texture=self.bullet_sprite, scale=1, shooter=self.playerone.client_id)
			#bullet.center_x = cgmpr.x
			#bullet.center_y = cgmpr.y
			bullet.center_x = self.playerone.center_x# + (bullet.change_x * 2)
			bullet.center_y = self.playerone.center_y# + (bullet.change_y * 2)
			x_diff = x - cgmpr.x
			y_diff = y - cgmpr.y
			angle = math.atan2(x_diff, y_diff)  + 3.14 / 2
			bullet.angle = math.degrees(angle) #- 180
			bullet.change_x = 1-math.cos(angle) * BULLET_SPEED
			bullet.change_y = math.sin(angle) * BULLET_SPEED
			if bullet.change_y == 0:
				logger.warning(f'{bullet.change_y=} {angle=} {x_diff=} {y_diff=}')
			bullet_vel = Vec2d(x=bullet.change_x, y=bullet.change_y)
			bullet.center_x += bullet_vel.x*5
			bullet.center_y += bullet_vel.y*5
			#self.game_state.scene.add_sprite("Bullets",bullet)
			# logger.info(f"Bullet angle: {bullet.angle:.2f} p1a= {self.playerone.angle:.2f} a={angle:.2f} bcx={bullet.change_x:.2f} bcy={bullet.change_y:.2f}  x= {x} vl= {self.view_left} xl={x+self.view_left} y= {y} vb= {self.view_bottom} yb={y+self.view_bottom} {button=}")
			bulletpos = Vec2d(x=bullet.center_x,y=bullet.center_y)
			rads = math.radians(angle)
			distance = 16
			fix_x = bulletpos.x +  math.cos(rads) * distance
			fix_y = bulletpos.y + math.sin(rads) * distance
			bulletpos_fix = Vec2d(x=fix_x, y=fix_y)
			# bulletpos_fix = get_map_coordinates_rev(bulletpos, self.camera)
			event = {
				'event_time':0,
				'event_type':'bulletfired',
				'bullet_vel':bullet_vel,
				'shooter': self.playerone.client_id,
				'posfix': bulletpos_fix,
				'pos': bulletpos, #bullet.position,
				'bcx':bullet.change_x,
				'bcy':bullet.change_y,
				'ba': bullet.angle,
				'timer': 3515,
				'handled': False,
				'handledby': self.playerone.client_id,
				'eventid': gen_randid()}
			self.eventq.put(event)
		else:
			logger.warning(f'{x=} {y=} {button=} {modifiers=}')
			return


	def on_key_press(self, key, modifiers):
		# todo check collisions before sending keypress...
		sendmove = False
		if self.debugmode:
			logger.info(f'{key=} {modifiers=} ')
		if self.playerone.killed:
			logger.warning(f'playerone killed')
			#return
		# logger.debug(f'{key} {self} {self.client} {self.client.receiver}')
		if key == arcade.key.KEY_1:
			self.selected_bomb = 1
		elif key == arcade.key.KEY_2:
			self.selected_bomb = 2
		elif key == arcade.key.F1:
			self.debugmode = not self.debugmode
			logger.debug(f'debugmode: {self.debugmode}')
		elif key == arcade.key.F2:
			self.game_state.debugmode = not self.game_state.debugmode
			logger.debug(f'gsdebugmode: {self.game_state.debugmode} debugmode: {self.debugmode}')
		elif key == arcade.key.F3:
			debug_dump_game(self)
			self.draw_player_debug = not self.draw_player_debug
		elif key == arcade.key.F4:
			self.draw_graphs = not self.draw_graphs
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
			self.playerone.change_y = PLAYER_MOVEMENT_SPEED
			self.up_pressed = True
		elif key == arcade.key.DOWN or key == arcade.key.S:
			self.playerone.change_y = -PLAYER_MOVEMENT_SPEED
			self.down_pressed = True
		elif key == arcade.key.LEFT or key == arcade.key.A:
			self.playerone.change_x = -PLAYER_MOVEMENT_SPEED
			self.left_pressed = True
		elif key == arcade.key.RIGHT or key == arcade.key.D:
			self.playerone.change_x = PLAYER_MOVEMENT_SPEED
			self.right_pressed = True
			# self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})

	def on_key_release(self, key, modifiers):
		if key == arcade.key.UP or key == arcade.key.W:
			# self.playerone.change_y = PLAYER_MOVEMENT_SPEED
			self.up_pressed = False
		elif key == arcade.key.DOWN or key == arcade.key.S:
			# self.playerone.change_y = -PLAYER_MOVEMENT_SPEED
			self.down_pressed = False
		elif key == arcade.key.LEFT or key == arcade.key.A:
			# self.playerone.change_x = -PLAYER_MOVEMENT_SPEED
			self.left_pressed = False
		elif key == arcade.key.RIGHT or key == arcade.key.D:
			# self.playerone.change_x = PLAYER_MOVEMENT_SPEED
			self.right_pressed = False
			# self.client.send_queue.put({'msgtype': 'playermove', 'key': key, 'pos' : self.playerone.position, 'client_id': self.client.client_id})
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
					upgradetype = game_event.get("upgradetype")
					blkpos = Vec2d(x=game_event.get("fpos")[0], y=game_event.get("fpos")[1])
					newblk = create_upgrade_block(upgradetype, blkpos)
					self.game_state.scene.add_sprite("Upgrades", newblk)
					if self.debugmode:
						logger.info(f'{event_type} upgradetype {game_event.get("upgradetype")} {newblk}')
				case 'acknewconn':
					clid = game_event.get("client_id")
					if self.debugmode:
						if clid == self.playerone.client_id: # this is my connect ack
							logger.debug(f'{event_type} from {clid}')
						else:
							logger.info(f'{event_type} from {clid}') # new player connected
				case 'blkxplode':
					if self.debugmode:
						logger.info(f'{event_type} from {game_event.get("fbomber")}')
				case 'playerkilled' | 'dmgkill':
					#if self.debugmode:
					dmgfrom = game_event.get("dmgfrom")
					dmgto = game_event.get("dmgto")
					self.game_state.players[dmgto]['score'] += 10
					kill_score = 1
					[self.netplayers[k].set_texture(arcade.load_texture('data/netplayerdead.png')) for k in self.netplayers if k == dmgto]#[0]
					[self.netplayers[k].addscore(kill_score) for k in self.netplayers if k == dmgfrom]
					logger.info(f'{event_type} from {dmgfrom=}  {dmgto=}')
					if dmgto == self.playerone.client_id:
						kill_score += self.playerone.kill(dmgfrom)
						logger.debug(f'{event_type} from {dmgfrom=}  {dmgto=} {self.playerone=} {kill_score=}')
						self._show_kill_screen = True
						self.show_kill_timer = game_event.get('killtimer')
						self.show_kill_timer_start = game_event.get('killstart')
					if dmgfrom == self.playerone.client_id:
						self.playerone.score += kill_score
						logger.debug(f'{event_type} from {dmgfrom=}  {dmgto=} {self.playerone=} {kill_score=}')
					self.game_state.players[dmgto]['score'] += kill_score

				case 'takedamage':
					#if self.debugmode:
					dmgfrom = game_event.get("dmgfrom")
					dmgto = game_event.get("dmgto")
					damage = game_event.get("damage")
					# self.game_state.players[killed]['score'] += damage
					# [k.take_damage(damage, dmgfrom) for k in self.netplayers if k.client_id == killed]
					# logger.info(f'{event_type} from {dmgfrom=}  {killed=} {score=}')
					if dmgto == self.playerone.client_id:
						#self.playerone.score += damage
						#self.playerone.take_damage(damage, dmgfrom)
						logger.debug(f'{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ')
					# self.game_state.players[killed]['score'] += score
				case 'acktakedamage':
					#if self.debugmode:
					dmgfrom = game_event.get("dmgfrom")
					dmgto = game_event.get("dmgto")
					damage = game_event.get("damage")
					self.game_state.players[dmgfrom]['score'] += damage
					self.game_state.players[dmgfrom]['health'] -= damage
					if dmgto == self.playerone.client_id:
						self.playerone.take_damage(damage, dmgfrom)
						logger.debug(f'{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ')
					elif dmgfrom == self.playerone.client_id:
						self.playerone.score += damage
						logger.info(f'{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ')

				case 'ackbombxplode':
					bomber = game_event.get('bomber')
					# self.netplayers[bomber].bombsleft += 1
					# self.game_state.players[bomber]['bombsleft'] += 1
					if bomber == self.playerone.client_id:
						self.playerone.bombsleft += 1
						logger.info(f'{game_event.get("event_type")} ownbombxfrom {bomber} p1={self.playerone}')
						# self.playerone.bombsleft += 1
						#self.game_state.players[bomber]['bombsleft'] += 1
						# self.netplayers[bomber].bombsleft += 1
						#pass #
				case 'ackbullet':
					shooter = game_event.get('shooter')
					bullet_vel = Vec2d(x=game_event.get('bullet_vel')[0], y=game_event.get('bullet_vel')[1])
					bulletpos = Vec2d(x=game_event.get('pos')[0], y=game_event.get('pos')[1])
					# bulletpos_fix = get_map_coordinates_rev(bulletpos, self.camera)
					bullet = Bullet(texture=self.bullet_sprite,scale=1, shooter=shooter)
					bullet.center_x = bulletpos.x
					bullet.center_y = bulletpos.y
					bullet.change_x = bullet_vel.x
					bullet.change_y = bullet_vel.y
					bullet.angle = game_event.get('ba')
					#if shooter != self.playerone.client_id:
					self.game_state.scene.add_sprite("Bullets", bullet)
					self.bullet_engine.add_sprite(bullet, friction=0.01, mass=0.01, collision_type="Bullets", elasticity=0.5, moment_of_inertia=0.01)
					self.bullet_engine.set_velocity(bullet, (bullet_vel.x*10, bullet_vel.y*10))
				case 'ackbombdrop':
					bomber = game_event.get('bomber')
					bombpos = Vec2d(x=game_event.get('pos')[0], y=game_event.get('pos')[1])
					bombpos_fix = get_map_coordinates_rev(bombpos, self.camera)
					bombtype = game_event.get('bombtype')
					if bombtype == 1:
						bomb = Bomb("data/bomb.png",scale=1, bomber=bomber, timer=1500)
					else:
						bomb = BiggerBomb("data/bomb.png",scale=1, bomber=bomber, timer=1500)
					bomb.center_x = bombpos.x
					bomb.center_y = bombpos.y

					# bomb2 = Bomb("data/bomb2.png",scale=1, bomber=bomber, timer=1500)
					# bomb2.center_x = bombpos_fix.x
					# bomb2.center_y = bombpos_fix.y
					self.game_state.scene.add_sprite("Bombs", bomb)
					# self.game_state.scene.add_sprite("Bombs", bomb2)
					# self.bomb_list.append(bomb2)
					# self.bomb_list.append(bomb)
					# self.bomb_list.append(bomb2)
					if self.debugmode:
						if bomber == self.playerone.client_id:
							logger.info(f'{game_event.get("event_type")} ownbombfrom {bomber} pos 	{bombpos} {bombpos_fix=}')
							self.playerone.bombsleft -= 1
						else:
							logger.debug(f'{game_event.get("event_type")} from {bomber} pos 	{bombpos} {bombpos_fix=}')
				case _:
					# game_events.remove(game_event)
					logger.warning(f'unknown type:{event_type} {game_events=} ')

	def update_gamestate_players(self):
		for pclid in self.game_state.players:
			if self.game_state.players[pclid].get('timeout'):
				logger.info(f'timeout ppclid={pclid} gsp={self.game_state.players}')
				self.poplist.append(pclid)

	def update_netplayers(self):
		# gspcopy_ = copy.copy(self.game_state.players)
		# gspcopy = [{k: self.game_state.players[k]} for k in self.game_state.players if k != self.playerone.client_id]
		# _ = [self.netplayers[k].set_data(self.game_state.players[pclid]) for k in self.netplayers ] #  and k != self.playerone.client_id
		for gsplr in self.game_state.get_players(skip=self.playerone.client_id):
			pclid = gsplr.get('client_id')
			playerdata = gsplr.get('playerdata')
			score = playerdata.get('score')
			angle = playerdata.get('angle')
			health = playerdata.get('health')
			bombsleft = playerdata.get('bombsleft')
			position = Vec2d(x=playerdata.get('position')[0], y=playerdata.get('position')[1])
			# position = Vec2d(x= ,y=self.game_state.players[pclid].get('position')[1])
			#netplayerpos = Vec2d(x=position.x,y=position.y)
			position_fix = get_map_coordinates_rev(position, self.camera)
			value = f'  h:{health} s:{score} b:{bombsleft} pos: {position.x},{position.y} '
			if pclid in [k for k in self.netplayers]:
				self.netplayer_labels[pclid].value = value
				for np in self.netplayers:
					self.netplayers[np].position = position
					self.netplayers[np].angle = angle
					self.netplayers[np].health = health
					self.netplayers[np].score = score
					self.netplayers[np].bombsleft = bombsleft
				#_ = [self.netplayers[k].set_data(self.game_state.players[pclid]) for k in self.netplayers if k == pclid] #  and k != self.playerone.client_id

			else:
				if pclid == self.playerone.client_id:
					logger.warning(f'{gsplr=} {pclid=} {self.playerone.client_id=}')
					newplayer = Bomberplayer(texture="data/playerone.png",client_id=pclid, position=position_fix)
					playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id), text_color=arcade.color.BLUE)
					playerlabel.button.text = f'Me {pclid}'
				else:
					newplayer = Bomberplayer(texture="data/netplayer.png", client_id=pclid, position=position_fix)
					playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id), text_color=arcade.color.GREEN)
					playerlabel.button.text = f'{pclid}'
					self.netplayers[pclid] = newplayer # {'client_id':pclid, 'position':position_fix}
					self.game_state.scene.add_sprite("Netplayers", newplayer)
					logger.info(f'newplayer: id={newplayer.client_id} pos: {position} fix={position_fix} ')
				self.netplayer_labels[pclid] = playerlabel

				self.netplayer_grid.add(playerlabel.button, col_num=0, row_num=len(self.netplayer_labels))
				self.netplayer_grid.add(playerlabel.textlabel, col_num=1, col_span=2,row_num=len(self.netplayer_labels)) # h
				#if pclid != self.playerone.client_id:

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
		if changed:
			arcade.set_viewport(self.view_left, SCREEN_WIDTH + self.view_left, self.view_bottom, SCREEN_HEIGHT + self.view_bottom)

	def update_labels(self):
		self.timer_label.value = f'time {self.timer:.1f}'
		self.health_label.value = f'health {self.playerone.health}'
		self.score_label.value = f'score {self.playerone.score}'
		self.bombs_label.value = f'bombs {self.playerone.bombsleft}'
		self.info_label.value = f' B {self.selected_bomb}'

	def on_update(self, dt):
		self.timer += dt
		if not self._gotmap:
			return
		# self.update_viewport(dt)

		self.update_labels()
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
		# self.game_state.scene.update()
		if len(self.game_state.players) > 1:
			try:
				self.update_netplayers()
				try:
					self.playerone.network_sync(self.game_state.players[self.playerone.client_id])
				except KeyError as ex:
					logger.error(f'{ex=} {self.game_state.players}')
			except RuntimeError as e:
				logger.error(f'{e}')
			self.update_poplist()
		hitlist = self.physics_engine.update()
		self.bullet_engine.step()
		self.playerone.update()
		flames = []
		particles = []
		# self.bomb_list.update()
		for f in self.game_state.scene['Flames']:
			f.update()
		for b in self.game_state.scene['Blocks']:
			b.update()
		for p in self.game_state.scene['Particles']:
			p.update()
		#self.game_state.scene.update(names=['Bombs'])
		for b in self.game_state.scene["Bombs"]:
			b.update(self.game_state.scene, self.eventq)
#			flames.extend(bu.get('flames'))
#			particles.extend(bu.get('plist'))
#		self.flame_list.extend(flames)
#		self.particle_list.extend(particles)
		# self.game_state.scene['Blocks']
		# self.bullet = Bullet(texture=self.bullet_sprite, scale=1, shooter=self.playerone.client_id)

		for bullet in self.game_state.scene['Bullets']:
			# bullet.update()
			self.bullet_engine.apply_force(bullet, (bullet.change_x, bullet.change_y))
			bullet_wall_hits = [] # arcade.PhysicsEngineSimple(bullet, walls=[self.game_state.scene["Blocks"], self.game_state.scene["Walls"],]).update()
			# arcade.PymunkPhysicsEngine(gravity=(0, -0), damping=0.5)
			# self.bullet.position = bullet.position
			for bwh in bullet_wall_hits:
				logger.info(f'bwh hit: {bwh=} {bullet=}')
				#bullet.remove_from_sprite_lists()
			bullet_np_hits = arcade.check_for_collision_with_list(bullet, self.game_state.scene["Netplayers"])
			for nphit in bullet_np_hits:
				logger.info(f'nphit: {nphit=} {bullet=}')
				#bullet.remove_from_sprite_lists()
			if bullet.can_kill:
				if arcade.check_for_collision(bullet, self.playerone):
					event = {'event_time':0, 'event_type':'takedamage', 'damage': 1, 'dmgfrom':bullet.shooter, 'dmgto': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
					#self.game_state.game_events.append(event)
					if bullet.shooter != self.playerone.client_id: # skip own bullets
						self.eventq.put(event)
						#bullet.remove_from_sprite_lists()
						# bullet.hit(self.playerone)
				# bullet.hit(bwh)
				# bwh.remove_from_sprite_lists()
		# bullet_hits_p1 = arcade.check_for_collision_with_list(self.playerone, self.game_state.scene['Bullets'])
		# for bullet in bullet_hits_p1:
		# 	if bullet.shooter == self.playerone.client_id:
		# 		logger.warning(f'bullet hit playerone: {bullet=} {self.playerone=}')
		# 	else:
		# 		event = {'event_time':0, 'event_type':'takedamage', 'damage': 1, 'dmgfrom':bullet.shooter, 'dmgto': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}

			# self.bullet_engine.player_sprite = bullet
			# event = {'event_time':0, 'event_type':'takedamage', 'damage': 1, 'dmgfrom':bullet.shooter, 'dmgto': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
			#self.game_state.game_events.append(event)
			#if bullet.shooter != self.playerone.client_id: # skip own bullets
			#	self.eventq.put(event)
			#	bullet.remove_from_sprite_lists()
		#		bullet.hit()

		# for bullet in self.game_state.scene['Bullets']:
		# 	self.bullet_engine.player_sprite = bullet
		# 	if bullet.can_kill:
		# 		if arcade.check_for_collision(bullet, self.playerone):
		# 			event = {'event_time':0, 'event_type':'takedamage', 'damage': 1, 'dmgfrom':bullet.shooter, 'dmgto': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
		# 			#self.game_state.game_events.append(event)
		# 			if bullet.shooter != self.playerone.client_id: # skip own bullets
		# 				self.eventq.put(event)
		# 				bullet.remove_from_sprite_lists()
		# 				bullet.hit()
		# for bullet in self.game_state.scene['Bullets']:
		# 	hits = arcade.check_for_collision_with_list(bullet, self.game_state.scene['Blocks'])
		# 	for hit in hits:
		# 		if self.debugmode:
		# 			logger.debug(f'b={bullet} {hits=}')
		# 		bullet.remove_from_sprite_lists()
		# 		# bullet.hit(hit)
		# for bullet in self.game_state.scene['Bullets']:
		# 	bullet.draw_hit_box(color=arcade.color.GREEN, line_thickness=5)
		# 	hits = arcade.check_for_collision_with_list(bullet, self.game_state.scene['Walls'])
		# 	#hits.extend(arcade.check_for_collision_with_list(bullet, self.game_state.scene['Blocks']))
		# 	for hit in hits:
		# 		if self.debugmode:
		# 			logger.debug(f'b={bullet} {hits=}')
		# 		# bullet.remove_from_sprite_lists()
		# 		bullet.hit(hit)

				#break
		for upgr in self.game_state.scene['Upgrades']:
			upgr.update()
			if arcade.check_for_collision(upgr, self.playerone):
				# self.playerone.health -= 123
				event = {'event_time':0, 'event_type':'takeupgrade', 'client_id': self.playerone.client_id, 'handled': False,  'eventid': gen_randid()}
				if self.debugmode:
					logger.debug(f'upgr: {upgr} hit: {self.playerone} {event=}')
				#self.game_state.game_events.append(event)
				self.eventq.put(event)
				upgr.remove_from_sprite_lists()
		for f in self.game_state.scene['Flames']:
			if arcade.check_for_collision(f, self.playerone):
				# self.playerone.health -= 123
				event = {'event_time':0, 'event_type':'takedamage', 'damage': 10, 'dmgfrom':f.bomber, 'dmgto': self.playerone.client_id, 'handled': False, 'handledby': f'playerone-{self.playerone.client_id}', 'eventid': gen_randid()}
				#self.game_state.game_events.append(event)
				self.eventq.put(event)
				f.remove_from_sprite_lists()
			f_hitlist = arcade.check_for_collision_with_list(f, self.game_state.scene['Walls'])
			f_hitlist.extend(arcade.check_for_collision_with_list(f, self.game_state.scene['Blocks'])) # toodo split and move to gamestate
			#f_hitlist.extend(arcade.check_for_collision_with_list(f, self.sceneblocks))
			for hit in f_hitlist:
				hitblocktype = hit.properties.get('tile_id') # todo move this logic to gamestate
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
						self.eventq.put(event)
					case _:
						logger.info(f'f: {f} hit: {hit.properties.get("tile_id")} {hit}')

		for p in self.game_state.scene['Particles']:
			p_hitlist = arcade.check_for_collision_with_list(p, self.game_state.scene['Walls'])
			p_hitlist.extend(arcade.check_for_collision_with_list(p, self.game_state.scene['Blocks']))
			#p_hitlist.extend(arcade.check_for_collision_with_list(p, self.sceneblocks))
			if p_hitlist:
				for hit in p_hitlist:
					if p.change_x > 0:
						p.right = hit.left
					elif p.change_x < 0:
						p.left = hit.right
				if len(p_hitlist) > 0:
					p.change_x *= -1

	def dropbomb(self, key):
		self.player_event.keys[key] = False
		if self.playerone.bombsleft <= 0:
			logger.warning(f'p1: {self.playerone} has no bombs left...')
		else:
			bombpos = Vec2d(x=self.playerone.center_x,y=self.playerone.center_y)
			bombevent = {'event_time':0, 'event_type':'bombdrop', 'bombtype':self.selected_bomb, 'bomber': self.playerone.client_id, 'pos': bombpos, 'timer': 1515, 'handled': False, 'handledby': self.playerone.client_id, 'eventid': gen_randid()}
			self.eventq.put(bombevent)

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
				thrmain_cnt = thrmain_cnt,
				score = game.playerone.score,
				game_events = [game_events,],
				client_id = game.playerone.client_id,
				position = game.playerone.position,
				angle = game.playerone.angle,
				health = game.playerone.health,
				timeout = game.playerone.timeout,
				killed = game.playerone.killed,
				bombsleft = game.playerone.bombsleft,
				gotmap = game._gotmap,
				msgsource = 'pushermsgdict',
				msg_dt = time.time())
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
			await asyncio.sleep(1 / UPDATE_TICK)
	await asyncio.gather(pusher(), receive_game_state(), )

async def testworker():
	logger.info('testworker')
	async def test_ticker():
		ticks = 0
		while True:
			ticks += 1
			logger.info(f'test_ticker {ticks}')
			await asyncio.sleep(1)
	await asyncio.sleep(1)
	await asyncio.gather(test_ticker(), )
	logger.info('testworker done')


def thread_worker(game):
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	looptask = loop.create_task(thread_main(game, loop))
	logger.info(f'threadworker loop: {loop} lt={looptask} ')
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

	app = arcade.Window(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=True, gc_mode='context_gc')
	mainview = MainView(window=app, name='bomberdue', title='Bomberdude Main Menu', args=args)
	thread = Thread(target=thread_worker, args=(mainview.game,), daemon=True)
	thread.start()
	app.show_view(mainview)
	arcade.run()

if __name__ == "__main__":
	arcade.enable_timings(1000)
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	main()
	# arcade.run()
