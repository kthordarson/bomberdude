from dataclasses import dataclass
from arcade.gui.style import UIStyleBase, UIStyledWidget
from arcade.text import FontNameOrNames
from arcade.types import Color, RGBA255, PointList
import arcade
import array
import math
from typing import Optional, Tuple

# Physics
BLOCK = 32
BOMBTICKER = 10
BULLET_TIMER = 10
BOMBTIMEOUT = 2000
BULLET_SPEED = 11
CAMERA_SPEED = 0.1
FLAME_RATE = 33
FLAME_SPEED = 3
FLAME_TIME = 1000
FLAMEX = 16
FLAMEY = 16
FORMAT = 'utf8'
GRAPH_HEIGHT = 120
GRAPH_MARGIN = 5
GRAPH_WIDTH = 200
GRAVITY = 0
GRIDSIZE = 20
MINIMAP_BACKGROUND_COLOR = arcade.color.ALMOND
MOVEMENT_SPEED = 5
PARTICLE_COLORS = [arcade.color.ALIZARIN_CRIMSON, arcade.color.COQUELICOT, arcade.color.LAVA, arcade.color.KU_CRIMSON, arcade.color.DARK_TANGERINE]
PARTICLE_COUNT = 20
PARTICLE_FADE_RATE = 3
PARTICLE_GRAVITY = 0.05
PARTICLE_MIN_SPEED = 2.5
PARTICLE_RADIUS = 3
PARTICLE_SPARKLE_CHANCE = 0.02
PARTICLE_SPEED_RANGE = 2.5
PKTHEADER = 64
PKTLEN = 1024*2
PLAYER_MOVEMENT_SPEED = 4
PLAYER_SCALING = 1
RECT_HEIGHT:int = BLOCK
RECT_WIDTH:int = BLOCK
SCREEN_HEIGHT = 600
SCREEN_TITLE = "bdude"
SCREEN_WIDTH = 800
SPRITE_SCALING = 1
TILE_SCALING = 1
UPDATE_TICK:int = 60
VIEWPORT_MARGIN = 32
IMAGE_ROTATION = 90


@dataclass
class BombBUIStyle(UIStyleBase):
	"""
	Used to style the button. Below is its use case.

	.. code:: py

		button = UIFlatButton(style={"normal": UIFlatButton.UIStyle(...),})
	"""
	font_size: int = 10
	font_name: FontNameOrNames = ("calibri", "arial")
	font_color: RGBA255 = arcade.color.WHITE
	bg: RGBA255 = (51, 59, 51, 255)
	border: Optional[RGBA255] = None
	border_width: int = 0


NP_LABEL_STYLE = {
        "normal": BombBUIStyle(),
        "hover": BombBUIStyle(
            font_size=10,
            font_name=("calibri", "arial"),
            font_color=arcade.color.WHITE,
            bg=(51, 59, 51, 255),
            border=(77, 81, 87, 255),
            border_width=2,
        ),
        "press": BombBUIStyle(
            font_size=10,
            font_name=("calibri", "arial"),
            font_color=arcade.color.BLACK,
            bg=arcade.color.WHITE,
            border=arcade.color.WHITE,
            border_width=2,
        ),
        "disabled": BombBUIStyle(
            font_size=10,
            font_name=("calibri", "arial"),
            font_color=arcade.color.WHITE,
            bg=arcade.color.GRAY,
            border=None,
            border_width=2,
        )
    }
