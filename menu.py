from arcade.gui import UIManager, UIFlatButton, UIGridLayout
from arcade.gui.widgets.layout import UIAnchorLayout
from loguru import logger
from pymunk import Vec2d

from constants import *
from debug import draw_debug_widgets
from game import Bomberdude


class MainView(arcade.View):
	def __init__(self, window, args, **kwargs):  # , game, window, name, title):
		super().__init__()
		self.debugmode = args.debugmode
		self.window = window
		# self.window.center_window()
		self.game = Bomberdude(args)
		self.manager = UIManager()
		self.grid = UIGridLayout(column_count=1, row_count=4)
		# self.grid = UIGridLayout(x=self.window.width/2,y=self.window.height/2,column_count=1, row_count=3, vertical_spacing=5, align_horizontal='center', align_vertical='top')
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
		self.anchor = self.manager.add(UIAnchorLayout())  # anchor_x='left', anchor_y='top',
		self.anchor.add(child=self.grid, )
		self.mouse_pos = Vec2d(x=0, y=0)

		@self.testbtn.event('on_click')
		def on_testbtn_click(event):
			logger.debug(f'{self} {event=}')

		@self.startbtn.event("on_click")
		def on_click_start_new_game_button(event):
			logger.debug(f'{event=}')
			self.startbtn.visible = False
			self.exitbtn.visible = False
			self.startbtn.disabled = True
			self.exitbtn.disabled = True
			self.connectb.disabled = True
			self.connectb.visible = False
			self.window.show_view(self.game)

		@self.exitbtn.event("on_click")
		def on_click_exit_button(event):
			logger.debug(f'{event=}')
			arcade.exit()

		@self.connectb.event("on_click")
		def on_connect_to_server(event):
			logger.debug(f'{event=}')
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
		self.mouse_pos = Vec2d(x=x, y=y)

	def on_key_press(self, key, modifiers):
		if self.debugmode:
			pass  # logger.debug(f'{key=} {modifiers=} ap={self.anchor.position} gp={self.grid.position}')
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
		if self.debugmode:
			draw_debug_widgets([self.grid, ])

	def on_hide_view(self):
		self.manager.disable()  # pass
