import pygame
from pygame.math import Vector2 as Vec2d

class Camera:
    def __init__(self, width, height, map_width, map_height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height
        self.map_width = map_width
        self.map_height = map_height
        self.position = Vec2d(0, 0)

    def screen_to_world(self, screen_pos):
        world_x = screen_pos.x - self.position.x
        world_y = screen_pos.y - self.position.y
        return Vec2d(world_x, world_y)

    def apply(self, target):
        if isinstance(target, pygame.Rect):
            return target.move(self.camera.topleft)
        else:
            return target.rect.move(self.camera.topleft)

    def update(self, target):
        x = -target.rect.centerx + int(self.width / 2)
        y = -target.rect.centery + int(self.height / 2)

        # Limit scrolling to map size
        x = min(0, x)  # Left
        y = min(0, y)  # Top
        x = max(-(self.map_width - self.width), x)  # Right
        y = max(-(self.map_height - self.height), y)  # Bottom
        self.camera = pygame.Rect(x, y, self.width, self.height)
        self.position = Vec2d(x, y)
