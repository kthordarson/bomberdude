from typing import List, Optional, Tuple, Union

from pyvex.utils import stable_hash
from pymunk import Vec2d
import copy
import arcade
from arcade.gui.style import UIStyleBase, UIStyledWidget
from arcade.tilemap import TileMap
from arcade.gui import UIManager, UIBoxLayout, UITextArea, UIFlatButton, UIGridLayout
from arcade.gui import UILabel, UIWidget, UIAnchorLayout
from arcade.math import (get_angle_radians, rotate_point, get_angle_degrees,)
from arcade.sprite_list import SpatialHash
from arcade.draw_commands import draw_line, draw_circle_filled, draw_circle_outline,draw_lrbt_rectangle_outline
import random
import math
from loguru import logger
from constants import *
import time
import hashlib
from queue import Queue, Empty
from typing import List, Dict
import json
from dataclasses import dataclass, asdict, field
from arcade.types import Point

from utils import gen_randid

class Panel(UIWidget):
	def __init__(self, x, y, width, height, window=None, panel_title='dummy'):
		super().__init__(x=x, y=y, width=width, height=height)
		self.title = panel_title
		self.bg_color = arcade.color.YELLOW
		# top left box
		self.tlb = arcade.SpriteSolidColor(width=self.width//2, height=self.height/2, center_x=self.position[0]+(self.width//4), center_y=self.position[1]+(self.height//4*3), color=arcade.color.BURNT_ORANGE)
		# bottom left box
		self.blb = arcade.SpriteSolidColor(width=self.width//2, height=self.height/2, center_x=self.position[0]+(self.width//4), center_y=self.position[1]+self.height//4, color=arcade.color.ORANGE)
		# top right box
		self.trb = arcade.SpriteSolidColor(width=self.width//2, height=self.height/2, center_x=self.position[0]+(self.width//4*3), center_y=self.position[1]+self.height//4, color=arcade.color.CADMIUM_ORANGE)
		# bottom right box
		self.brb = arcade.SpriteSolidColor(width=self.width//2, height=self.height/2, center_x=self.position[0]+(self.width//4*3), center_y=self.position[1]+(self.height//4*3), color=arcade.color.WHITE)
		self.boxes = arcade.SpriteList()
		self.boxes.append(self.tlb)
		self.boxes.append(self.blb)
		self.boxes.append(self.trb)
		self.boxes.append(self.brb)
		self.window = window

	def draw(self):
		self.do_render(self.window)
		self.boxes.draw()
		arcade.Text(f'{self.title} {self.x} {self.y}', self.x+2, self.y+self.height+2, arcade.color.WHITE, font_size=10).draw()
		arcade.Text(f'{self.title} {self.x} {self.y}', self.center_x, self.center_y, arcade.color.CG_BLUE, font_size=8).draw()
		for b in self.boxes:
			arcade.Text(f'{b.center_x} {b.center_y}', b.center_x, b.center_y, arcade.color.BLACK, font_size=10).draw()
		draw_lrbt_rectangle_outline(left=self.x, right=self.x+self.width, bottom=self.y, top=self.y+self.height, color=arcade.color.BLUE,border_width=1)
		draw_circle_filled(center_x=self.x, center_y=self.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=self.x+self.width, center_y=self.y, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=self.x+self.width, center_y=self.y+self.height, radius=2,  color=arcade.color.ORANGE) # .
		draw_circle_filled(center_x=self.x, center_y=self.y+self.height, radius=2,  color=arcade.color.ORANGE) # .

		draw_line(start_x=self.x, start_y=self.y, end_x=self.x+self.width//2, end_y=self.y+self.height//2, color=arcade.color.ORANGE, line_width=1)
		draw_line(start_x=self.x+self.width, start_y=self.y, end_x=self.x+self.width//2, end_y=self.y+self.height//2, color=arcade.color.ORANGE, line_width=1)
