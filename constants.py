from dataclasses import dataclass
from arcade.gui.style import UIStyleBase, UIStyledWidget
from arcade.text import FontNameOrNames
from arcade.types import Color, RGBA255, PointList
import arcade
import array
import math
from typing import Optional, Tuple
BLOCK = 32
BOMBTICKER = 10
BOMBTIMEOUT = 2000
BULLET_SPEED = 4
BULLET_TIMER = 2
CAMERA_SPEED = 0.1
FLAME_RATE = 33
FLAME_SPEED = 3
FLAME_TIME = 1000
FLAMEX = 12
FLAMEY = 12
FORMAT = 'utf8'
GRAPH_HEIGHT = 120
GRAPH_MARGIN = 5
GRAPH_WIDTH = 200
GRAVITY = 0
GRIDSIZE = 20
IMAGE_ROTATION = 90
MINIMAP_BACKGROUND_COLOR = arcade.color.ALMOND
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
PLAYER_DAMPING = 0.4
PLAYER_FRICTION = 0.6
PLAYER_MASS = 2.0
PLAYER_MOVEMENT_SPEED = 2
PLAYER_SCALING = 1
RECT_HEIGHT:int = BLOCK
RECT_WIDTH:int = BLOCK
SCREEN_HEIGHT = 600
SCREEN_TITLE = "bdude"
SCREEN_WIDTH = 800
SPRITE_SCALING = 1
TILE_SCALING = 1.0
UPDATE_TICK:int = 60
UPGRADETIMER = 20
VIEWPORT_MARGIN = 32
WALL_FRICTION = 0.6