import pygame
from pygame.math import Vector2 as Vec2d

class Camera:
    def __init__(self, width, height, map_width, map_height):
        self.width = width
        self.height = height
        self.map_width = map_width
        self.map_height = map_height
        self.position = Vec2d(0, 0)

    def update(self, target):
        # Calculate camera position to center on player
        target_x = target.position.x + target.rect.width / 2
        target_y = target.position.y + target.rect.height / 2

        # Position the camera so target is centered
        x = target_x - (self.width / 2)
        y = target_y - (self.height / 2)

        # Clamp to map boundaries
        x = max(0, min(x, self.map_width - self.width))
        y = max(0, min(y, self.map_height - self.height))

        # Store as integers for pixel-perfect rendering
        self.position = Vec2d(int(x), int(y))

    def apply(self, rect):
        """Convert rect from world coordinates to screen coordinates"""
        return pygame.Rect(int(rect.x - self.position.x), int(rect.y - self.position.y),rect.width, rect.height)

    def reverse_apply(self, x, y):
        """Convert screen coordinates to world coordinates"""
        return (x + self.position.x, y + self.position.y)
