#!/usr/bin/python
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
from objects import Bomberplayer, Bomb, KeysPressed, PlayerEvent, PlayerState, GameState, gen_randid, UIPlayerLabel
from objects import pack, unpack, send_zipped_pickle, recv_zipped_pickle
from constants import *
import requests
import zmq
from zmq.asyncio import Context, Socket

def draw_debug_game(game):
	tx = 33
	ty = game.window.height-20
	for idx,item in enumerate(game.manager.walk_widgets()):
		item_text = f'idx:{idx} {item.name} '
		item_textpos = f' {item.x} {item.y} w: {item.width} h: {item.height} '
		color = arcade.color.Color(0, 0, idx*30, 255)# random.choice(PARTICLE_COLORS)
		arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width, item.height, color, border_width=3 )
		# arcade.draw_rectangle_outline( item.center_x, item.center_y ,item.width-10, item.height-10, random.choice(PARTICLE_COLORS), border_width=1 )
		# text_items.append(item_text)
		# item_text.draw()
		arcade.Text(f'{item_text}', tx, ty, arcade.color.BLUE, font_size=10).draw()
		ty -= idx+19
		arcade.Text(f'{item_textpos}', tx+10, ty, arcade.color.CYAN, font_size=10).draw()
		arcade.Text(f'XY {item.name} {item_textpos}', item.x+5, item.y+5, arcade.color.BROWN, font_size=10).draw()
		arcade.Text(f'CENTER {item.name} ', item.center_x, item.center_y, arcade.color.PINK, font_size=10).draw()
		arcade.Text(f' {item_textpos}', item.center_x, item.center_y+13, arcade.color.PINK, font_size=10).draw()
		#draw_line(start_x=tx, start_y=ty, end_x=game.mouse_pos[0], end_y=game.mouse_pos[1], color=color)
		draw_line(start_x=item.x, start_y=item.y, end_x=game.mouse_pos[0], end_y=game.mouse_pos[1], color=arcade.color.GREEN)

		draw_line(start_x=item.center_x, start_y=item.center_y, end_x=game.mouse_pos[0], end_y=game.mouse_pos[1], color=arcade.color.GREEN)
		draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y, color=arcade.color.ORANGE) # bottom line
		draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # top line
		draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.ORANGE) # left line
		draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # right line

		draw_circle_filled(center_x=item.x, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		ty -= idx+15



def draw_debug_manager(manager):
	tx = 33
	ty = manager.window.height//2
	for idx,item in enumerate(manager.walk_widgets()):
		item_text = f'idx:{idx} {item} {item.name} '
		item_textpos = f' {item.x} {item.y} w: {item.width} h: {item.height} '
		color = arcade.color.Color(0, 0, idx*10, 255)# random.choice(PARTICLE_COLORS)
		arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width, item.height, color, border_width=2 )
		arcade.draw_rectangle_outline( item.center_x, item.center_y ,item.width-10, item.height-10, random.choice(PARTICLE_COLORS), border_width=1 )
		if isinstance(item, UILabel) or isinstance(item, UIFlatButton):
			item_text += f' {item.text} '
		# text_items.append(item_text)
		# item_text.draw()
		arcade.Text(f'{item_text}', tx, ty, arcade.color.BLUE, font_size=10).draw()
		ty -= idx+19
		arcade.Text(f'{item_textpos}', tx+10, ty, arcade.color.CYAN, font_size=10).draw()
		arcade.Text(f'XY {item.name} {item_textpos}', item.x+5, item.y+5, arcade.color.BROWN, font_size=10).draw()
		arcade.Text(f'CENTER {item.name} {item_textpos}', item.center_x, item.center_y, arcade.color.PINK, font_size=10).draw()
		#draw_line(start_x=tx, start_y=ty, end_x=game.mouse_pos[0], end_y=game.mouse_pos[1], color=color)
		# draw_line(start_x=item.x, start_y=item.y, end_x=game.mouse_pos[0], end_y=game.mouse_pos[1], color=arcade.color.GREEN)

		draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y, color=arcade.color.ORANGE) # bottom line
		draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # top line
		draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.ORANGE) # left line
		draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # right line

		draw_circle_filled(center_x=item.x, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		ty -= idx+15







	# def draw_debug(self):
	# 	tx = 63
	# 	ty = self.window.height-22
	# 	for idx,item in enumerate(self.manager.walk_widgets()):
	# 		item_text = f'idx:{idx} {item.name} '
	# 		item_textpos = f' {item.x} {item.y} w: {item.width} h: {item.height} '
	# 		color = arcade.color.Color(0, 0, idx*20, 255)# random.choice(PARTICLE_COLORS)
	# 		arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width, item.height, color, border_width=2 )
	# 		arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width-10, item.height-10, random.choice(PARTICLE_COLORS), border_width=1 )
	# 		#if isinstance(item, UILabel) or isinstance(item, UIFlatButton):
	# 		#	item_text += f' {item.text} '
	# 		# text_items.append(item_text)
	# 		# item_text.draw()
	# 		arcade.Text(f'{item_text}', tx, ty, arcade.color.BLUE, font_size=10).draw()
	# 		ty -= idx+18
	# 		arcade.Text(f'{item_textpos}', tx+10, ty, arcade.color.CYAN, font_size=10).draw()
	# 		# arcade.Text(f'XY {item.name} {item_textpos}', item.x, item.y, arcade.color.BROWN, font_size=10).draw()
	# 		arcade.Text(f'CENTER {item.name} {item_textpos}', item.center_x, item.center_y, arcade.color.PINK, font_size=10).draw()
	# 		#draw_line(start_x=tx, start_y=ty, end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], color=color)
	# 		#draw_line(start_x=item.x, start_y=item.y, end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], color=arcade.color.BLUE)
	# 		draw_line(start_x=item.center_x, start_y=item.center_y, end_x=self.mouse_pos[0], end_y=self.mouse_pos[1], color=arcade.color.LIGHT_BLUE)
	# 		#draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.GREEN)
	# 		#draw_line(start_x=item.x, start_y=item.y, end_x=item.x-item.width, end_y=item.y, color=arcade.color.GREEN)
	# 		#draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y-item.height, color=arcade.color.ORANGE)
	# 		#draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y-item.height, color=arcade.color.ORANGE)

	# 		#draw_line(start_x=item.x, start_y=item.y-item.height, end_x=item.x+item.width, end_y=item.y-item.height, color=arcade.color.ORANGE)
	# 		draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y, color=arcade.color.ORANGE) # bottom line
	# 		draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # top line
	# 		draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.ORANGE) # left line
	# 		draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # left line
	# 		ty -= idx+15



def draw_debug_view(view):
	tx = 33
	ty = view.window.height-20
	for idx,item in enumerate(view.manager.walk_widgets()):
		# item_text = f'idx:{idx} {item.name} '
		# item_textpos = f' {item.x} {item.y} w: {item.width} h: {item.height} '
		color = arcade.color.Color(0, 0, idx*10, 255)# random.choice(PARTICLE_COLORS)
		arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width, item.height, color, border_width=3 )
		# arcade.draw_rectangle_outline( item.center_x, item.center_y ,item.width-10, item.height-10, random.choice(PARTICLE_COLORS), border_width=1 )
		# text_items.append(item_text)
		# item_text.draw()
		arcade.Text(f'{idx} {item.name} - {item.x} {item.y} - {item.center_x} {item.center_y} - {item.width} {item.height}', tx, ty, arcade.color.BLUE, font_size=10).draw()
		# arcade.Text(f'{item.x} {item.y}', tx+10, ty, arcade.color.CYAN, font_size=10).draw()
		arcade.Text(f'{idx} {item.name} {item.x} {item.y}', item.x+13, item.y+11, arcade.color.BROWN, font_size=10).draw()
		#arcade.Text(f'CENTER {item.name} ', item.center_x, item.center_y, arcade.color.PINK, font_size=10).draw()
		arcade.Text(f' {item.center_x} {item.center_y}', item.center_x, item.center_y, arcade.color.PINK, font_size=10).draw()
		#draw_line(start_x=tx, start_y=ty, end_x=view.mouse_pos[0], end_y=view.mouse_pos[1], color=color)
		draw_line(start_x=item.x, start_y=item.y, end_x=view.mouse_pos[0], end_y=view.mouse_pos[1], color=arcade.color.DARK_GREEN)

		draw_line(start_x=item.center_x, start_y=item.center_y, end_x=view.mouse_pos[0], end_y=view.mouse_pos[1], color=arcade.color.GREEN) # mouse

		draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y, color=arcade.color.ORANGE) # bottom line
		draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # top line
		draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.ORANGE) # left line
		draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # right line

		draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.ORANGE) # xline
		draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y, color=arcade.color.ORANGE) # xline


		draw_circle_filled(center_x=item.x, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		ty -= idx+15



def debug_dump_game(game):
	print('='*80)
	print(f'scenewalls:{len(game.scenewalls)} sceneblocks:{len(game.sceneblocks)} bombs:{len(game.bomb_list)} particles:{len(game.particle_list)} flames:{len(game.flame_list)}')
	print(f'playerone: {game.playerone} pos={game.playerone.position} ') #  gspos={game.game_state.players[game.playerone.client_id]}')
	print(f'game.game_state.players = {len(game.game_state.players)} gsge={len(game.game_state.game_events)}')
	print('='*80)
	for idx,p in enumerate(game.game_state.players):
		print(f"\t{idx}/{len(game.game_state.players)} p={p} | {game.game_state.players.get(p)} | {game.game_state.players}")
	print('='*80)
	for idx,e in enumerate(game.game_state.game_events):
		print(f"\t{idx}/{len(game.game_state.game_events)} event={e} ")
	# print('='*80)
	# arcade.print_timings()
	# print('='*80)
	griditems = []
	for k,data in game.grid._children:
		print(f'_sgc {k=} {data=}')
		if isinstance(k, _ChildEntry):
			for sub in k.children:
				print(f'\tsgc {k=} {sub=}')
	for k,data in game.netplayer_anchor._children:
		print(f'NPA {k=} {data=}')
		if isinstance(k, _ChildEntry):
			for sub in k.children:
				print(f'\tnpasgc {k=} {sub=}')
		if isinstance(k, UIGridLayout):
			for sub in k.children:
				print(f'\tnpasgcg {k=} {sub=}')
	for k,data in game.netplayer_grid._children:
		print(f'NPG {k=} {data=}')
		if isinstance(k, _ChildEntry):
			for sub in k.children:
				print(f'\tsgc {k=} {sub=}')
	#items.extend([k for k in game.grid._children])
	#items.extend([k for k in game.manager.walk_widgets()])
	#items.extend(grid_items)
	# griditems = [k for k in game.grid._children]
	# _ = [print(f'walk {k}') for k in game.manager.walk_widgets()]
	for k in game.manager.walk_widgets():
		print(f'widgetwalk {k.name} {k=}')
		if isinstance(k, UIGridLayout):
			for sub in k.children:
				print(f'\tUIG {sub.name} {sub=}')
		elif isinstance(k, UIAnchorLayout):
			for sub in k.children:
				print(f'\tUIA  {sub.name} {sub=}')
				for xsub in sub.children:
					print(f'\t   UIA {xsub.name} {xsub=}')
		else:
			print(f'\t {k=} {type(k)}')
	#items = []
	#items.extend([k for k in game.manager.walk_widgets()])
	#items.extend([k.children for k in items])
	for item in game.manager.walk_widgets():
		print(f'{item.name} {item=} {item.position} {item.x} {item.y}')
		for sub in item.children:
			print(f'\tsubitem {sub.name} {sub} {sub.position} {sub.x} {sub.y}')
			for subsub in sub.children:
				print(f'\t - SUBsubitem {subsub.name} {subsub} {subsub.position} {subsub.x} {subsub.y}')

	# text_items = []
