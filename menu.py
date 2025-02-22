import pygame
from loguru import logger
from game import Bomberdude
class MainView:
    def __init__(self, screen, name, title, args, eventq):
        self.screen = screen
        self.name = name
        self.title = title
        self.args = args
        self.eventq = eventq
        self.debug = args.debug
        self.game = Bomberdude(args, eventq)

    def update(self):
        self.game.update()

    def draw(self):
        self.game.on_draw()

    def on_key_press(self, key, modifiers):
        self.game.on_key_press(key, modifiers)

    def on_key_release(self, key, modifiers):
        self.game.on_key_release(key, modifiers)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.game.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x, y, button, modifiers):
        self.game.on_mouse_press(x, y, button, modifiers)
