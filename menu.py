import pygame
from loguru import logger
from game import Bomberdude
class MainView:
    def __init__(self, screen, name, title, args):
        self.screen = screen
        self.name = name
        self.title = title
        self.args = args
        self.game = Bomberdude(args)

    def update(self):
        self.game.update()

    def draw(self):
        self.game.on_draw()

    def on_key_press(self, key):
        # key = pygame.key.get_pressed()
        logger.info(f'key={key}')
        self.game.on_key_press(key)

    def on_key_release(self, key):
        logger.debug(f'key={key}')
        self.game.on_key_release(key)

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int):
        self.game.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x, y, button):
        self.game.on_mouse_press(x, y, button)
