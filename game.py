import requests
import copy
import zmq
from zmq.asyncio import Context, Socket
from pymunk import Vec2d
import math
import json
import time
import random
from queue import Queue, Empty
import arcade
from arcade import get_window
from arcade.draw_commands import draw_line, draw_circle_filled, draw_circle_outline
from arcade.gui import UIManager, UIBoxLayout, UITextArea, UIFlatButton, UIGridLayout, UILabel
from arcade.gui.widgets.layout import UIAnchorLayout
from arcade.types import Point
from arcade.math import (get_angle_radians, rotate_point, get_angle_degrees,)
from loguru import logger
from objects import Bomberplayer, Bomb, BiggerBomb, KeysPressed, PlayerEvent, PlayerState,  UIPlayerLabel, Bullet
from panels import Panel
from utils import get_map_coordinates_rev, gen_randid
from gamestate import GameState
from debug import debug_dump_game, draw_debug_widgets, draw_debug_players
from constants import *



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
		self.playerone = Bomberplayer(texture="data/playerone.png", name=args.name, client_id=gen_randid())
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
		self.netplayer_panels = {}


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
			'name': self.playerone.name,
			'handled': False,
			'handledby': 'do_connect',
			'eventid': gen_randid()}
		self.eventq.put(connection_event)
		self._connected = True
		self.setup_network()
		self.window.set_caption(f'{self.title} connected to {self.args.server} player {self.playerone.name} : {self.playerone.client_id}')

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
		try:
			resp = json.loads(requests.get(f'http://{self.args.server}:9699/get_tile_map').text)
			mapname = resp.get('mapname')
			pos = resp.get('position')
			position = Vec2d(x=pos[0], y=pos[1])
			logger.debug(f'map {mapname} {pos=} {resp=}')
		except Exception as e:
			logger.error(f'{type(e)} {e=}')
			mapname = 'data/maptest2.json'
			pos = (110,110)
			position = Vec2d(x=pos[0], y=pos[1])
		self.game_state.load_tile_map(mapname)
		self._gotmap = True
		# resp = requests.get(f'http://{self.args.server}:9699/get_position')
		# pos = resp.text
		# logger.info(f'{self} {resp=} {self._gotmap=} {self.connected()=} {pos=}')
		self.setup(position)

	def setup(self,position):
		self.background_color = arcade.color.BLACK
		self.bullet_sprite = arcade.load_texture("data/bullet0.png")

		self.setup_panels()
		self.setup_perf()
		self.setup_labels()
		# self.manager.enable()
		self.manager.enable()
		self.playerone.position = position
		self.camera = arcade.Camera()
		self.guicamera = arcade.Camera()
		self.game_state.scene.add_sprite_list('static')
		self.game_state.scene['static'].sprite_list.extend(self.game_state.tile_map.sprite_lists['Blocks'])
		self.game_state.scene['static'].sprite_list.extend(self.game_state.tile_map.sprite_lists['Walls'])

	def setup_labels(self):
		self.draw_labels = True
		self.showkilltext = arcade.Text(f"kill: {self.show_kill_timer:.1f}",100, 100, arcade.color.RED, 22)

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
		self.manager_visible = True
		#self.grid = UIGridLayout(x=123,y=123,column_count=2, row_count=3, vertical_spacing=5)
		self.grid = self.manager.add(UIGridLayout(column_count=4, row_count=4, vertical_spacing=5, align_horizontal='center', align_vertical='center', size_hint=(26,27)))
		# gridsb = self.grid.add(self.startbtn, col_num=0, row_num=0)
		font_size = 12
		pos=font_size*2
		sy=self.window.height-pos
		sx=self.window.width-100
		self.netplayer_grid = UIGridLayout(x=23,y=23,size_hint=(144,178), column_count=6, row_count=6, vertical_spacing=6, horizontal_spacing=6, align_horizontal='center', align_vertical='center')

		self.anchor = self.manager.add(UIAnchorLayout(x=4, y=4, anchor_x='left', anchor_y='bottom' ))#, anchor_y='top'))
		self.anchor.add(child=self.netplayer_grid)
		self.player_panel = Panel(10,10,250,50, owner=self.playerone.client_id, window=self.window)
		self.netplayer_panels[self.playerone.client_id] = self.player_panel

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
		if self.manager_visible:
			self.manager.draw()
		self.guicamera.use()

		for panel in self.netplayer_panels:
			self.netplayer_panels[panel].draw()

		# if self.draw_labels:
		# 	for label in self.labels:
		# 		label.draw()
		if self.debugmode and BULLETDEBUG:
			for b in self.game_state.scene['Bullets']:
				if b.can_kill:
					self.camera.use()
					draw_line(start_x=b.center_x, start_y=b.center_y, end_x=self.playerone.center_x, end_y=self.playerone.center_y, color=arcade.color.ORANGE, line_width=1)
					textpos = get_map_coordinates_rev(b.position, self.camera)
					self.guicamera.use()
					try:
						textpos += Vec2d(10,0)
						arcade.Text(text = f'bxc: {b.change_x:.2f} bcy: {b.change_y:.2f} ', start_x=int(textpos.x), start_y=int(textpos.y), color=arcade.color.BLACK, font_size=10).draw()
						textpos += Vec2d(0,11)
						arcade.Text(text = f'ba: {b.angle:.2f}', start_x=int(textpos.x), start_y=int(textpos.y), color=arcade.color.BLACK, font_size=10).draw()
					except AttributeError as e:
						logger.error(f'{e} textpos={textpos} {b=}')

		if self.draw_player_debug:
			try:
				self.guicamera.use()
				draw_debug_players(self.game_state.players,self.netplayer_panels, self.camera)
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
		cgmpr = get_map_coordinates_rev(self.playerone.position, self.camera)
		if button == 1:
			x_diff = x - cgmpr.x
			y_diff = y - cgmpr.y
			ba = math.atan2(x_diff, y_diff)  + 3.14 / 2

			change_x = 1-math.cos(ba) * BULLET_SPEED
			change_y = math.sin(ba) * BULLET_SPEED
			bullet_vel = Vec2d(x=change_x, y=change_y)
			bulletpos = Vec2d(x=self.playerone.center_x,y=self.playerone.center_y)
			event = {
				'event_time':0,
				'event_type':'bulletfired',
				'bullet_vel':bullet_vel,
				'shooter': self.playerone.client_id,
				'pos': bulletpos, #bullet.position,
				'ba': ba,
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
			pass #logger.info(f'{key=} {modifiers=} ')
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
		elif key == arcade.key.F7:
			self.window.set_fullscreen(not self.window.fullscreen)
			# width, height = self.window.get_size()
			self.window.set_viewport(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT)
			self.camera = arcade.Camera(viewport=(0, 0, self.width, self.height))
		elif key == arcade.key.TAB:
			self.manager_visible = not self.manager_visible
		elif key == arcade.key.ESCAPE or key == arcade.key.Q:
			self.playerone.killed = True
			self._connected = False
			quitevent = {'event_time':0, 'event_type':'playerquit', 'client_id': self.playerone.client_id, 'eventid': gen_randid()}
			self.eventq.put(quitevent)
			logger.warning(f'quit')
			arcade.close_window()
			return

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
		elif key == arcade.key.SPACE:
			self.playerone.dropbomb(self.selected_bomb, self.eventq)
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
			clid = game_event.get("client_id")
			match event_type:
				case 'extrabomb':
					logger.info(f'{event_type=} {game_event=}')
					if clid == self.playerone.client_id:
						self.playerone.bombsleft += 1
					else:
						self.netplayers[clid].bombsleft += 1
				case 'extrahealth':
					eh = game_event.get('amount')
					logger.info(f'{event_type=} {game_event=}')
					if clid == self.playerone.client_id:
						self.playerone.health += eh
					else:
						self.netplayers[clid].bombsleft += eh
				case 'playerquit':
					try:
						l0 = len(self.netplayers)
						self.netplayers[clid].remove_from_sprite_lists()
						self.netplayers.pop(clid)
						self.netplayer_panels.pop(clid)
						self.game_state.players.pop(clid)
						# self.netplayers.pop(self.netplayers[clid])
						logger.debug(f'{event_type} from {clid} {l0} -> {len(self.netplayers)}')
					except KeyError as e:
						logger.warning(f'{e} {clid=} {self.netplayers=}')
					except Exception as e:
						logger.error(f'{type(e)} {e} {clid=} {self.netplayers=}')
				case 'ackrespawn':
					[self.netplayers[k].set_texture(arcade.load_texture('data/netplayer.png')) for k in self.netplayers if k == clid]#[0]
					logger.debug(f'{event_type} from {clid}')
					if clid == self.playerone.client_id:
						self.playerone.respawn()
				case 'upgradeblock':
					upgradetype = game_event.get("upgradetype")
					blkpos = Vec2d(x=game_event.get("fpos")[0], y=game_event.get("fpos")[1])
					newblk = self.game_state.create_upgrade_block(upgradetype, blkpos)
					self.game_state.scene.add_sprite("Upgrades", newblk)
					if self.debugmode:
						logger.info(f'{event_type} upgradetype {game_event.get("upgradetype")} {newblk}')
				case 'acknewconn':
					name = game_event.get("name", 'missingfromacknewconn')
					if self.debugmode:
						if clid == self.playerone.client_id: # this is my connect ack
							logger.debug(f'{event_type} from {clid} {name}')
						else:
							logger.info(f'{event_type} from {clid} {name}') # new player connected
				case 'blkxplode':
					if self.debugmode:
						logger.info(f'{event_type} from {game_event.get("fbomber")}')
				case 'playerkilled' | 'dmgkill':
					#if self.debugmode:
					dmgfrom = game_event.get("dmgfrom")
					dmgto = game_event.get("dmgto")
					[self.netplayers[k].set_texture(arcade.load_texture('data/netplayerdead.png')) for k in self.netplayers if k == dmgto]#[0]
					logger.info(f'{event_type} from {dmgfrom=}  {dmgto=}')
					if dmgto == self.playerone.client_id:
						logger.debug(f'{event_type} from {dmgfrom=}  {dmgto=} {self.playerone=} ')
						self._show_kill_screen = True
						self.show_kill_timer = game_event.get('killtimer')
						self.show_kill_timer_start = game_event.get('killstart')
					if dmgfrom == self.playerone.client_id:
						logger.debug(f'{event_type} from {dmgfrom=}  {dmgto=} {self.playerone=} ')
					# self.game_state.players[dmgto]['score'] += kill_score

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
					# self.game_state.players[dmgfrom]['score'] += damage
					# self.game_state.players[dmgfrom]['health'] -= damage
					if dmgto == self.playerone.client_id:
						self.playerone.take_damage(damage, dmgfrom)
						# logger.debug(f'{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ')
					elif dmgfrom == self.playerone.client_id:
						# self.playerone.score += damage
						logger.info(f'{event_type} {damage} from {dmgfrom=}  {dmgto=} {self.playerone=} ')

				case 'ackbombxplode':
					bomber = game_event.get('bomber')
					eventid = game_event.get('eventid')
					# self.game_state.players[bomber]['bombsleft'] += 1
					if bomber == self.playerone.client_id:
						if eventid == self.playerone.lastdrop:
							self.playerone.candrop = True
							self.playerone.bombsleft += 1
							logger.info(f'{game_event.get("event_type")} ownbombxfrom {bomber} p1={self.playerone}')
					else:
						logger.info(f'{game_event.get("event_type")} otherbomb {bomber} p1={self.playerone}')
						pass # self.netplayers[bomber].bombsleft += 1
						# self.playerone.bombsleft += 1
						#self.game_state.players[bomber]['bombsleft'] += 1
						# self.netplayers[bomber].bombsleft += 1
						#pass #
				case 'ackbullet':
					shooter = game_event.get('shooter')
					bullet_vel = Vec2d(x=game_event.get('bullet_vel')[0], y=game_event.get('bullet_vel')[1])
					bulletpos = Vec2d(x=game_event.get('pos')[0], y=game_event.get('pos')[1])

					#position = Vec2d(x=self.center_x,y=self.center_y)-_bulletpos
					mnorm = bullet_vel.normalized()
					bulletpos += ( mnorm *22)

					bulletpos_fix = get_map_coordinates_rev(bulletpos, self.guicamera)
					bullet = Bullet(texture=self.bullet_sprite,scale=0.8, shooter=shooter)
					bullet.center_x = bulletpos.x
					bullet.center_y = bulletpos.y
					bullet.change_x = bullet_vel.x
					bullet.change_y = bullet_vel.y
					bullet.angle = game_event.get('ba')
					self.game_state.scene.add_sprite("Bullets", bullet)
				case 'ackbombdrop':
					bomber = game_event.get('bomber')
					eventid = game_event.get('eventid')
					bombpos = Vec2d(x=game_event.get('pos')[0], y=game_event.get('pos')[1])
					bombpos_fix = get_map_coordinates_rev(bombpos, self.camera)
					bombtype = game_event.get('bombtype')
					if bombtype == 1:
						bomb = Bomb("data/bomb.png",scale=0.5, bomber=bomber, timer=1500)
					else:
						bomb = BiggerBomb("data/bomb.png",scale=0.7, bomber=bomber, timer=1500)
					bomb.center_x = bombpos.x
					bomb.center_y = bombpos.y
					self.game_state.scene.add_sprite("Bombs", bomb)
					if bomber == self.playerone.client_id and eventid == self.playerone.lastdrop:
						self.playerone.candrop = True # player can drop again
						if self.debugmode:
							logger.info(f'{game_event.get("event_type")} ownbombfrom {bomber} pos {bombpos} {eventid=} ld={self.playerone.lastdrop} {self.playerone}')
					else:
						logger.debug(f'{game_event.get("event_type")} from {bomber} pos 	{bombpos} {bombpos_fix=}')
				case _:
					# game_events.remove(game_event)
					logger.warning(f'unknown type:{event_type} {game_events=} ')

	def update_netplayers(self):
		# gspcopy_ = copy.copy(self.game_state.players)
		# gspcopy = [{k: self.game_state.players[k]} for k in self.game_state.players if k != self.playerone.client_id]
		# _ = [self.netplayers[k].set_data(self.game_state.players[pclid]) for k in self.netplayers ] #  and k != self.playerone.client_id
		if self.playerone.client_id in self.game_state.players:
			try:
				playeronedata = self.game_state.players[self.playerone.client_id]
				self.playerone.update_netdata(playeronedata)
			except KeyError as e:
				logger.warning(f'keyerror {e} {self.game_state.players=} {self.playerone.client_id=}')
		gsplr_copy = [k for k in self.game_state.get_players(skip=self.playerone.client_id)]
		for gsplr in  gsplr_copy: #
			pclid = gsplr.get('client_id')
			playerdata = gsplr.get('playerdata')
			name = playerdata.get('name', 'gsmissing')
			score = playerdata.get('score',-3)
			angle = playerdata.get('angle')
			health = playerdata.get('health',-3)
			bombsleft = playerdata.get('bombsleft',-3)
			position = playerdata.get('position',(0,0))
			# position = Vec2d(x= ,y=self.game_state.players[pclid].get('position')[1])
			#netplayerpos = Vec2d(x=position.x,y=position.y)

			value = f'  h:{health} s:{score} b:{bombsleft} pos: {position=} '
			if pclid in [k for k in self.netplayers if k != self.playerone.client_id]: # update existing netplayer
				try:
					np = self.netplayers.get(pclid)
					panel = self.netplayer_panels.get(pclid)
					panel.update_data(np)
				except KeyError as e:
					logger.warning(f'KeyError {e} {pclid=} {self.netplayer_panels=} {value=}')
				for np in self.netplayers:
					self.netplayers[np].position = position
					self.netplayers[np].angle = angle
					self.netplayers[np].name = name
					self.netplayers[np].health = health
					self.netplayers[np].score = score
					self.netplayers[np].bombsleft = bombsleft
				#_ = [self.netplayers[k].set_data(self.game_state.players[pclid]) for k in self.netplayers if k == pclid] #  and k != self.playerone.client_id

			else: # create new netplayer
				position_fix = get_map_coordinates_rev(position, self.camera)
				if pclid == self.playerone.client_id:
					#logger.warning(f'{gsplr=} {pclid=} {self.playerone.client_id=}')
					newplayer = Bomberplayer(texture="data/playerone.png",client_id=pclid, name=name,position=position_fix)
					#playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id),name=name, text_color=arcade.color.BLUE)
					#playerlabel.button.text = f'Me {name}'
				else:
					newplayer = Bomberplayer(texture="data/netplayer.png", client_id=pclid,name=name, position=position_fix)
					#playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id), name=name, text_color=arcade.color.GREEN)
					#playerlabel.button.text = f'{name}'
					logger.info(f'newplayer: {name} id={newplayer.client_id} pos: {position} fix={position_fix} ')
				playerlabel = UIPlayerLabel(client_id=str(newplayer.client_id), name=name, text_color=arcade.color.GREEN)
				playerlabel.button.text = f'{name}'
				playerpanel = Panel(10,101-(len(self.netplayer_panels)*12),250,50, owner=pclid, window=self.window)
				if pclid != self.playerone.client_id:
					self.game_state.scene.add_sprite("Netplayers", newplayer)
					self.netplayers[pclid] = newplayer # {'client_id':pclid, 'position':position_fix}
					self.netplayer_panels[pclid] = playerpanel

					self.netplayer_grid.add(playerpanel, col_num=0, row_num=len(self.netplayer_panels))
					self.netplayer_grid.add(playerlabel.button, col_num=1, row_num=len(self.netplayer_panels))
					# self.netplayer_grid.add(playerlabel.textlabel, col_num=1, col_span=2,row_num=len(self.netplayer_panels)) # h
				#if pclid != self.playerone.client_id:

	def update_poplist(self):
		for p in self.poplist:
			logger.info(f'plist={self.poplist} popping {p} gsp={self.game_state.players}')
			self.game_state.players.pop(p)
			logger.info(f'aftergsp={self.game_state.players}')
		self.poplist = []

	def on_update(self, dt):
		self.timer += dt
		if not self._gotmap:
			return

		# self.update_labels()
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
		#if len(self.game_state.players) > 1:
		self.update_netplayers()
		self.update_poplist()
		self.player_panel.update_data(self.playerone)

		oldpos = self.playerone.position
		self.playerone.update()
		self.playerone.draw_hit_box(color=arcade.color.RED, line_thickness=4)
		checklist = arcade.SpriteList(use_spatial_hash=False)
		checklist.sprite_list.extend(self.game_state.scene['Walls'].sprite_list)
		checklist.sprite_list.extend(self.game_state.scene['Blocks'].sprite_list)
		colls = arcade.check_for_collision_with_list(self.playerone, checklist)
		if len(colls)>0:
			def checkx():
				if self.playerone.change_x < 0:
					#self.playerone.change_x = 0
					# self.playerone.left = colls[0].right
					self.playerone.position = oldpos
				if self.playerone.change_x > 0:
					#self.playerone.change_x = 0
					# self.playerone.right = colls[0].left
					self.playerone.position = oldpos
			def checky():
				if self.playerone.change_y > 0:
					#self.playerone.change_y = 0
					#self.playerone.top = colls[0].bottom
					self.playerone.position = oldpos
				if self.playerone.change_y < 0:
					#self.playerone.change_y = 0
					#self.playerone.bottom = colls[0].top
					self.playerone.position = oldpos
			checkx()
			checky()
		for b in self.game_state.scene['Bullets']:
			b_oldpos = b.position
			b.update()
			if arcade.check_for_collision(b, self.playerone):
				event = {'event_time':0, 'event_type':'takedamage', 'dmgto':self.playerone.client_id, 'dmgfrom':b.shooter, 'damage':b.damage, 'handled': False,  'eventid': gen_randid()}
				if self.debugmode:
					logger.debug(f'takedamage {self.playerone} from {b.shooter} {b.damage=}')
				#self.game_state.game_events.append(event)
				self.eventq.put(event)
				b.remove_from_sprite_lists()
			else:
				if arcade.check_for_collision_with_list(b, checklist):
					b.remove_from_sprite_lists()
				for hit in arcade.check_for_collision_with_list(b, self.game_state.scene['Netplayers']):
					logger.debug(f'netplayertakedamage {hit} from {b.shooter} {b.damage=}')
					b.remove_from_sprite_lists()
		for f in self.game_state.scene['Flames']:
			f.update()
			colls = arcade.check_for_collision_with_list(f, self.game_state.scene['Walls'])
			if len(colls) > 0:
				f.remove_from_sprite_lists()
			for hit in arcade.check_for_collision_with_list(f, self.game_state.scene['Blocks']):
				hitblocktype = hit.properties.get('tile_id')
				match hitblocktype:
					case 2:
						event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
						self.eventq.put(event)
						self.game_state.scene['Blocks'].remove(hit)
					case 3:
						hit.hit_count += 1
						logger.debug(f'hitcount: {hit.hit_count} {hit=}')
						if hit.hit_count > 3:
							event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
							self.eventq.put(event)
							self.game_state.scene['Blocks'].remove(hit)
					case 6:
						event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
						self.eventq.put(event)
						self.game_state.scene['Blocks'].remove(hit)
					case 9:
						event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
						self.eventq.put(event)
						self.game_state.scene['Blocks'].remove(hit)
					case 10:
						hit.hit_count += 1
						logger.debug(f'hitcount: {hit.hit_count} {hit=}')
						if hit.hit_count > 3:
							event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
							self.eventq.put(event)
							self.game_state.scene['Blocks'].remove(hit)
					case 11:
						event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
						self.eventq.put(event)
						self.game_state.scene['Blocks'].remove(hit)
					case 12:
						event = {'event_time':0, 'event_type':'blkxplode', 'hit':hitblocktype, 'flame':f.position, 'fbomber': f.bomber, 'client_id': self.playerone.client_id, 'handled': False, 'handledby': 'playerone', 'eventid': gen_randid()}
						self.eventq.put(event)
						self.game_state.scene['Blocks'].remove(hit)
				f.remove_from_sprite_lists()
		for b in self.game_state.scene["Bombs"]:
			b.update(self.game_state.scene, self.eventq)
		for upgr in self.game_state.scene['Upgrades']:
			upgr.update()
			upgradetype = upgr.upgradetype
			if arcade.check_for_collision(upgr, self.playerone):
				# self.playerone.health -= 123
				event = {'event_time':0, 'event_type':'takeupgrade', 'upgradetype':upgradetype, 'client_id': self.playerone.client_id, 'handled': False,  'eventid': gen_randid()}
				if self.debugmode:
					logger.debug(f'pickedup upgr: {upgr} {upgradetype=} {self.playerone} ')
				#self.game_state.game_events.append(event)
				self.eventq.put(event)
				upgr.remove_from_sprite_lists()
		for p in self.game_state.scene['Particles']:
			p.update()
			p_hitlist = arcade.check_for_collision_with_list(p, checklist)
			if p_hitlist:
				p.remove_from_sprite_lists()

