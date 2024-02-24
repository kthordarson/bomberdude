#!/usr/bin/python
from arcade.draw_commands import draw_line, draw_circle_filled, draw_circle_outline
from arcade.gui import  UIGridLayout
from arcade.gui import UILabel
from arcade.gui.widgets.layout import UIAnchorLayout
from arcade.types import Point
from loguru import logger
from constants import *

def draw_debug_widgets(widgets):
	tx = 33
	ty = 333
	for idx,w in enumerate(widgets):
		render_widget_debug(idx,w,tx,ty)
		ty -= idx+15
		# arcade.draw_rectangle_outline( w.center_x, w.center_y, w.width, w.height, arcade.color.RED, border_width=1 )

def draw_debug_view(view):
	tx = 33
	ty = view.window.height-20
	for idx,item in enumerate(view.manager.walk_widgets()):
		render_widget_debug(idx, item,tx,ty)
		ty -= idx+15
		# item_text = f'idx:{idx} {item.name} '
		# item_textpos = f' {item.x} {item.y} w: {item.width} h: {item.height} '

def render_widget_debug(idx, item,tx,ty):
		color = arcade.color.Color(0, 0, idx*10, 255)# random.choice(PARTICLE_COLORS)
		arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width, item.height, color, border_width=1 )
		arcade.Text(f'{idx} {item.name} - {item.x} {item.y} - {item.center_x} {item.center_y} - {item.width} {item.height}', tx, ty, arcade.color.BLUE, font_size=10).draw()
		arcade.Text(f'{idx} {item.name} {item.x} {item.y}', item.x+13, item.y+11, arcade.color.BROWN, font_size=10).draw()

		draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y, color=arcade.color.LIGHT_MOSS_GREEN) # bottom line
		draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.LIGHT_MOSS_GREEN) # top line
		draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.LIGHT_MOSS_GREEN) # left line
		draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.LIGHT_MOSS_GREEN) # right line

		draw_circle_filled(center_x=item.x, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .

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
	print('='*80)
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
	print('='*80)
	for item in game.manager.walk_widgets():
		print(f'{item.name} {item=} {item.position} {item.x} {item.y}')
		for sub in item.children:
			print(f'\tsubitem {sub.name} {sub} {sub.position} {sub.x} {sub.y}')
			for subsub in sub.children:
				print(f'\t - SUBsubitem {subsub.name} {subsub} {subsub.position} {subsub.x} {subsub.y}')
	print('='*80)
