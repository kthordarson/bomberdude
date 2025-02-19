from pymunk import Vec2d
import time
import random
from queue import Queue, Empty
import arcade
from arcade.gui import (
    UIAnchorLayout,
    UIFlatButton,
    UIGridLayout,
    UIImage,
    UIOnChangeEvent,
    UITextureButton,
    UITextureToggle,
    UIView,
    UIManager,
)
from loguru import logger
from game import Bomberdude

class MainView(arcade.View):
    def __init__(self, window, args, **kwargs):  # , game, window, name, title):
        super().__init__()
        self.args = args
        self.debug = args.debug
        self.window = window
        self.game = Bomberdude(args)
        self.manager = UIManager()
        # self.grid = UIGridLayout(column_count=1, row_count=4)
        #  self.window.width / 2,   #  self.window.height / 2,
        self.grid = UIGridLayout(x=300,y=300,align_horizontal='center', align_vertical='center', column_count=8, row_count=8)  # x=30, y=300, column_count=1, row_count=3)  #, vertical_spacing=5, align_horizontal="center", align_vertical="top", )
        # self.sb = UIFlatButton(text="Start New Game", width=150)
        self.startbtn = self.grid.add(UIFlatButton(text="Start New Game", width=150), col_num=0,row=1)  # , col_num=0, row_num=10)
        # self.cb = UIFlatButton(text="Connect", width=250)
        self.connectb = self.grid.add(UIFlatButton(text="Connect", width=250), col_num=1,row=2)  # , col_num=2, row_num=1)
        # self.eb = UIFlatButton(text="Exit", width=150)
        self.exitbtn = self.grid.add(UIFlatButton(text="Exit", width=150), col_num=2,row=3)  # , col_num=0, row_num=2)
        # self.tb = UIFlatButton(text="test", width=150)
        self.testbtn = self.grid.add(UIFlatButton(text="test", width=150), col_num=3,row=4)  # , col_num=10, row_num=1)
        self.grid.do_layout()
        # self.grid.add(, col_num=0, row_num=0)
        # self.grid.add(self.connectb, col_num=0, row_num=1)
        # self.grid.add(self.exitbtn, col_num=0, row_num=2)
        self.anchor = self.manager.add(self.grid)
        # self.anchor = self.manager.add(UIAnchorLayout())  # anchor_x='left', anchor_y='top',
        # self.anchor.add(child=self.grid,)
        self.mouse_pos = Vec2d(x=0, y=0)

        @self.testbtn.event("on_click")
        def on_testbtn_click(event):
            logger.debug(f"{self} {event=}")

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
            self.connectb.text = f"{self.game.args.server}"
            self.connectb.disabled = True
            self.connectb.visible = False
            self.window.show_view(self.game)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.mouse_pos = Vec2d(x=x, y=y)

    def on_key_press(self, key, modifiers):
        if self.debug:
            pass  # logger.debug(f'{key=} {modifiers=} ap={self.anchor.position} gp={self.grid.position}')
        if key == arcade.key.F1:
            self.debug = not self.debug
            logger.debug(f"debug: {self.debug}")
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
            logger.warning("quit")
            arcade.close_window()
            return
        elif key == arcade.key.SPACE:
            pass
        elif key == arcade.key.UP or key == arcade.key.W:
            if modifiers == 16:
                pass  # self.anchor.move(0,1)
            if modifiers == 18:
                pass  # self.anchor.move(0,11)
        elif key == arcade.key.DOWN or key == arcade.key.S:
            if modifiers == 16:
                pass  # self.anchor.move(0,-1)
            if modifiers == 18:
                pass  # self.anchor.move(0, -11)
        elif key == arcade.key.LEFT or key == arcade.key.A:
            if modifiers == 16:
                pass  # self.anchor.move(-1,0)
            if modifiers == 18:
                pass  # self.anchor.move(-11,0)
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            if modifiers == 16:
                pass  # self.anchor.move(1,0)
            if modifiers == 18:
                pass  # self.anchor.move(11,0)

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        self.manager.enable()

    def on_draw(self):
        self.clear()
        self.manager.draw()

    def on_hide_view(self):
        self.manager.disable()  # pass
