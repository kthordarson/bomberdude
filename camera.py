import pygame
from pygame.math import Vector2 as Vec2d

class Camera:
    def __init__(self, width, height, map_width, map_height):
        self.width = width
        self.height = height
        self.map_width = map_width
        self.map_height = map_height
        self.position = Vec2d(0, 0)

    def update2(self, target):
        # Target should be centered on screen
        x = target.rect.centerx - (self.width // 2)
        y = target.rect.centery - (self.height // 2)

        # Clamp camera position to map bounds
        x = max(0, min(x, self.map_width - self.width))
        y = max(0, min(y, self.map_height - self.height))

        # Store negative position for correct rendering offset
        self.position = Vec2d(-x, -y)

    def apply(self, target):
        # Use position directly instead of camera.topleft
        if isinstance(target, pygame.Rect):
            return target.move(self.position.x, self.position.y)
        else:
            return target.rect.move(self.position.x, self.position.y)
