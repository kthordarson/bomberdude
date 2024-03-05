from arcade.draw_commands import draw_line, draw_circle_filled, draw_lrbt_rectangle_outline
from arcade.gui import UIWidget

from constants import *


class Panel(UIWidget):

	def __init__(self, x, y, width, height, owner, window=None, panel_title='dummy'):
		super().__init__(x=x, y=y, width=width, height=height)
		self.title = panel_title
		self.owner = owner
		self.client_id = owner
		self.name = owner
		self.bg_color = arcade.color.YELLOW
		# top left box
		self.tlb = arcade.SpriteSolidColor(width=self.width // 2, height=self.height / 2, center_x=self.position[0] + (self.width // 4), center_y=self.position[1] + (self.height // 4 * 3), color=arcade.color.BURNT_ORANGE)  # bottom left box
		self.blb = arcade.SpriteSolidColor(width=self.width // 2, height=self.height / 2, center_x=self.position[0] + (self.width // 4), center_y=self.position[1] + self.height // 4, color=arcade.color.ORANGE)  # top right box
		self.brb = arcade.SpriteSolidColor(width=self.width // 2, height=self.height / 2, center_x=self.position[0] + (self.width // 4 * 3), center_y=self.position[1] + self.height // 4, color=arcade.color.CADMIUM_ORANGE)  # bottom right box
		self.trb = arcade.SpriteSolidColor(width=self.width // 2, height=self.height / 2, center_x=self.position[0] + (self.width // 4 * 3), center_y=self.position[1] + (self.height // 4 * 3), color=arcade.color.GRAY)  # what box
		self.boxes = arcade.SpriteList()
		self.boxes.append(self.tlb)
		self.boxes.append(self.blb)
		self.boxes.append(self.trb)
		self.boxes.append(self.brb)
		self.window = window
		self.score = 0
		self.health = 0
		self.bombsleft = 0

	def drawpanel(self, panel):
		self.do_render(self.window)
		self.boxes.draw()
		arcade.Text(f'{panel.name} : {panel.owner}', self.x + 2, self.y + self.height + 2, arcade.color.WHITE, font_size=10).draw()  # todo set player name here
		arcade.Text(f'Score: {panel.score}', self.tlb.center_x - (self.width // 4) + 3, int(self.tlb.center_y), arcade.color.BLACK, font_size=10).draw()
		arcade.Text(f'Health: {panel.health}', self.blb.center_x - (self.width // 4) + 3, int(self.blb.center_y), arcade.color.BLACK, font_size=10).draw()
		arcade.Text(f'Bombs: {panel.bombsleft}', self.trb.center_x - (self.width // 4) + 3, int(self.trb.center_y), arcade.color.BLACK, font_size=10).draw()

	def update_data(self, player):
		self.name = player.name
		self.client_id = player.client_id
		self.score = player.score
		self.health = player.health
		self.bombsleft = player.bombsleft

	def draw(self):
		self.do_render(self.window)
		self.boxes.draw()
		player = self
		arcade.Text(f'{player.name} : {player.client_id}', self.x + 2, self.y + self.height + 2, arcade.color.WHITE,
		            font_size=10).draw()  # todo set player name here
		arcade.Text(f'Score: {player.score}', self.tlb.center_x - (self.width // 4) + 3, self.tlb.center_y,
		            arcade.color.BLACK, font_size=10).draw()
		arcade.Text(f'Health: {player.health}', self.blb.center_x - (self.width // 4) + 3, self.blb.center_y,
		            arcade.color.BLACK, font_size=10).draw()
		arcade.Text(f'Bombs: {player.bombsleft}', self.trb.center_x - (self.width // 4) + 3, self.trb.center_y,
		            arcade.color.BLACK, font_size=10).draw()

	def xdraw(self, player):
		self.do_render(self.window)
		self.boxes.draw()
		arcade.Text(f'{player.name} : {player.client_id}', self.x + 2, self.y + self.height + 2, arcade.color.WHITE, font_size=10).draw()  # todo set player name here
		arcade.Text(f'Score: {player.score}', self.tlb.center_x - (self.width // 4) + 3, self.tlb.center_y, arcade.color.BLACK, font_size=10).draw()
		arcade.Text(f'Health: {player.health}', self.blb.center_x - (self.width // 4) + 3, self.blb.center_y, arcade.color.BLACK, font_size=10).draw()
		arcade.Text(f'Bombs: {player.bombsleft}', self.trb.center_x - (self.width // 4) + 3, self.trb.center_y, arcade.color.BLACK, font_size=10).draw()

	# arcade.Text(f'{self.title} {self.x} {self.y}', self.center_x, self.center_y, arcade.color.CG_BLUE, font_size=8).draw()
	# for b in self.boxes:
	# arcade.Text(f'{b.center_x} {b.center_y}', b.center_x-(self.width//4)+3, b.center_y, arcade.color.BLACK, font_size=10).draw()
	def debugdraw(self):
		draw_lrbt_rectangle_outline(left=self.x, right=self.x + self.width, bottom=self.y, top=self.y + self.height, color=arcade.color.BLUE, border_width=1)
		draw_circle_filled(center_x=self.x, center_y=self.y, radius=2, color=arcade.color.ORANGE)  # .
		draw_circle_filled(center_x=self.x + self.width, center_y=self.y, radius=2, color=arcade.color.ORANGE)  # .
		draw_circle_filled(center_x=self.x + self.width, center_y=self.y + self.height, radius=2, color=arcade.color.ORANGE)  # .
		draw_circle_filled(center_x=self.x, center_y=self.y + self.height, radius=2, color=arcade.color.ORANGE)  # .

		draw_line(start_x=self.x, start_y=self.y, end_x=self.x + self.width // 2, end_y=self.y + self.height // 2, color=arcade.color.ORANGE, line_width=1)
		draw_line(start_x=self.x + self.width, start_y=self.y, end_x=self.x + self.width // 2, end_y=self.y + self.height // 2, color=arcade.color.ORANGE, line_width=1)
