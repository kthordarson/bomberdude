#!/usr/bin/python
from typing import List, Optional, Tuple, Union

from pymunk import Vec2d
from arcade.draw_commands import draw_line, draw_circle_filled, draw_circle_outline
from arcade.gui import  UIGridLayout
from arcade.gui import UILabel
from arcade.gui.widgets.layout import UIAnchorLayout
from arcade.types import Point
from loguru import logger
from constants import *
from utils import get_map_coordinates_rev
def drawbox(sx,ex, sy, ey, color, lw):
	# sx = startx, ex = endx, sy = starty, ey = endy, color, lw=linew,
	textwidth = 444
	fontsize = 10
	draw_line(start_x=sx, start_y=sy, end_x=sx+textwidth, end_y=sy, color=color) # bottom line
	draw_line(start_x=sx, start_y=sy+fontsize, end_x=sx+textwidth, end_y=sy+fontsize, color=color) # top line
	draw_line(start_x=sx, start_y=sy, end_x=sx, end_y=sy+fontsize, color=color) # left line
	draw_line(start_x=sx+textwidth, start_y=sy, end_x=sx+textwidth, end_y=sy+fontsize, color=color) # right line

def draw_debug_players(players, labels, camera):
	poslist = {}
	for idx,p in enumerate(players):
		playerpos = Vec2d(x=players[p]['position'][0],y=players[p]['position'][1])
		client_id = players[p]['client_id']
		fp = get_map_coordinates_rev(playerpos, camera)
		draw_circle_filled(center_x=fp.x, center_y=fp.y, radius=7,  color=arcade.color.BLACK)
		poslist[client_id] = {'fp':fp, 'p':playerpos, 'client_id':client_id}
		# print(f'{poslist=}')
		for pl in poslist:
			# print(f'{pl=}')
			# print(f'{poslist=}')
			pass # draw_line(start_x=poslist[pl].get('fp').x, end_x=fp.x, start_y=poslist[pl].get('fp').y, end_y=fp.y,  color=arcade.color.GREEN, line_width=1)
	if len(poslist)>0:
		sx_id = [k for k in poslist][0]
		sx = poslist[sx_id].get('fp').x
		sy = poslist[sx_id].get('fp').y
		for pl in poslist:
			# plx = poslist[pl].get('p').x
			# ply = poslist[pl].get('p').y
			fpx = poslist[pl].get('fp').x
			fpy = poslist[pl].get('fp').y
			# draw_circle_filled(center_x=plx, center_y=ply, radius=3,  color=arcade.color.ORANGE)
			draw_circle_filled(center_x=fpx, center_y=fpy, radius=4,  color=arcade.color.GREEN)
			draw_line(start_x=fpx, start_y=fpy, end_x=camera.viewport_width//2, end_y=camera.viewport_height//2,  color=arcade.color.RED, line_width=1)
			draw_line(start_x=fpx, start_y=fpy, end_x=sx, end_y=sy,  color=arcade.color.BLUE, line_width=1)
		#draw_line(start_x=plx, start_y=plx, end_x=camera.viewport_width//2, end_y=camera.viewport_height//2,  color=arcade.color.YELLOW, line_width=1)
		# for l in labels:
		# 	if l == p:
		# 		lpos = get_map_coordinates_rev(labels[l].position, camera)
		# 		xlpos = Vec2d(x=labels[l].position[0], y=labels[l].position[1])
		# 		draw_line(start_x=lpos.x, end_x=fixed_pos.x, start_y=lpos.y, end_y=fixed_pos.y,  color=arcade.color.RED, line_width=1)
		# 		draw_line(start_x=xlpos.x, end_x=fixed_pos.x, start_y=xlpos.y, end_y=fixed_pos.y,  color=arcade.color.RED, line_width=1)

def draw_debug_widgets(widgets):
	tx = 433
	ty = 63
	ty_0 = ty
	panel_size = Vec2d(x=111,y=120)
	text_pos = Vec2d(x=tx, y=ty)
	text_pos0 = text_pos
	fontsize = 10
	textwidth = 450
	# arcade.draw_lrbt_rectangle_filled(left=tx, right=tx+textwidth, top=ty_0+20, bottom=text_pos.y-100, color=arcade.color.GRAY)
	for idx,w in enumerate(widgets):
		text_pos = render_widget_debug(idx,w,text_pos, fontsize)
		#draw_line(start_x=tx, end_x=tx, start_y=ty_0, end_y=ty, color=arcade.color.RED,line_width=1)
		#draw_line(start_x=tx, end_x=tx+300, start_y=ty_0, end_y=ty, color=arcade.color.GREEN,line_width=1) # under textline
		ty += idx+fontsize
	#arcade.draw_xywh_rectangle_outline(bottom_left_x=tx, bottom_left_y=ty_0, width=textwidth, height=ty, color=arcade.color.PURPLE, border_width=1)
	# arcade.draw_lrbt_rectangle_outline(left=tx, right=tx+textwidth, top=ty_0+20, bottom=text_pos.y, color=arcade.color.YELLOW, border_width=1)
		# arcade.draw_rectangle_outline( w.center_x, w.center_y, w.width, w.height, arcade.color.RED, border_width=1 )

def draw_debug_view(view):
	tx = 33
	ty = view.window.height-20
	for idx,item in enumerate(view.manager.walk_widgets()):
		# render_widget_debug(idx, item,tx,ty)
		ty -= idx+15

		# item_text = f'idx:{idx} {item.name} '
		# item_textpos = f' {item.x} {item.y} w: {item.width} h: {item.height} '

def render_widget_debug(idx, item, text_pos, fontsize):
		textspace = fontsize + 10
		ntp = text_pos
		color = arcade.color.Color(0, 0, idx*10, 255)# random.choice(PARTICLE_COLORS)
		#arcade.draw_rectangle_outline( item.center_x, item.center_y, item.width, item.height, color, border_width=1 )
		#arcade.Text(f'{idx} {item.name} - {item.x} {item.y} - {item.center_x} {item.center_y} - {item.width} {item.height}', ntp.x, ntp.y, arcade.color.BLUE, font_size=fontsize).draw()
		#draw_line(start_x=ntp.x, end_x=item.x, start_y=item.y, end_y=ntp.y, color=arcade.color.ORANGE, line_width=1)
		#ntp -= (0,textspace)
		# draw_line(start_x=ntp.x, end_x=ntp.x+100, start_y=ntp.y, end_y=ntp.y, color=arcade.color.RED, line_width=1)

		#arcade.Text(f'{idx} {item.name} {item.x} {item.y}', item.x+(idx*2), item.y+(idx*2), arcade.color.BROWN, font_size=10).draw()
		arcade.draw_lrbt_rectangle_outline(left=item.x, right=item.x+item.width, bottom=item.y-(idx*2), top=item.y+item.height-(idx*2), color=arcade.color.BLUE,border_width=1)
		#draw_line(start_x=item.x, start_y=item.y, end_x=item.x+item.width, end_y=item.y, color=arcade.color.LIGHT_MOSS_GREEN) # bottom line
		#draw_line(start_x=item.x, start_y=item.y+item.height, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.LIGHT_MOSS_GREEN) # top line
		#draw_line(start_x=item.x, start_y=item.y, end_x=item.x, end_y=item.y+item.height, color=arcade.color.LIGHT_MOSS_GREEN) # left line
		#draw_line(start_x=item.x+item.width, start_y=item.y, end_x=item.x+item.width, end_y=item.y+item.height, color=arcade.color.LIGHT_MOSS_GREEN) # right line

		draw_circle_filled(center_x=item.x, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x+item.width, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=item.x, center_y=item.y+item.height, radius=2,  color=arcade.color.ORANGE) # .
		return ntp

def debug_dump_game(game):
	bar = f'{"="*20}'
	shortbar = f'{"="*5}'
	print(f'{bar} {game.playerone.client_id} {bar}')
	print(f'bombs:{len(game.bomb_list)} particles:{len(game.particle_list)} flames:{len(game.flame_list)}')
	print(f'playerone: {game.playerone} pos={game.playerone.position} ') #  gspos={game.game_state.players[game.playerone.client_id]}')
	print(f'game.game_state.players = {len(game.game_state.players)} netplayers = {len(game.netplayers)}')
	print(f'{shortbar} {game.game_state} {shortbar}')
	print(f"gsp = {game.game_state.players}")
	print(f'{bar} netplayers {bar}')
	print(f"netplayers = {game.netplayers}")
	print(f'{bar} gamestateplayers {bar}')
	for idx,p in enumerate(game.game_state.players):
		gsp = game.game_state.players.get(p)
		print(f"\t{idx}/{len(game.game_state.players)} p={p} | {gsp['client_id']} {gsp['position']} a={gsp['angle']} h={gsp['health']} s={gsp['score']} to={gsp['timeout']} to={gsp['killed']}")
	print(f'{bar} netplayers {bar}')
	for idx,p in enumerate(game.netplayers):
		np = game.netplayers.get(p)
		print(f"\t{idx}/{len(game.game_state.players)} p={p} | {np.client_id} {np.position} a={np.angle} h={np.health} s={np.score} to={np.timeout} to={np.killed}")
	# print('='*80)
	# arcade.print_timings()
	# print('='*80)

def debug_dump_widgets(game):
	print('='*80)
	for k in game.manager.walk_widgets():
		print(f'widgetwalk {k=}')
		if isinstance(k, UIGridLayout):
			for sub in k.children:
				print(f'\tUIG  {sub=}')
		elif isinstance(k, UIAnchorLayout):
			for sub in k.children:
				print(f'\tUIA  {sub=}')
				for xsub in sub.children:
					print(f'\t   UIA   {xsub=}')
		else:
			print(f'\t {k=} {type(k)}')
	print('='*80)
	for item in game.manager.walk_widgets():
		print(f'{item=} {item.position} {item.x} {item.y}')
		for sub in item.children:
			print(f'\tsubitem  {sub} {sub.position} {sub.x} {sub.y}')
			for subsub in sub.children:
				print(f'\t - SUBsubitem   {subsub} {subsub.position} {subsub.x} {subsub.y}')
	print('='*80)
