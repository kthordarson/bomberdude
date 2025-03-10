import pygame
from pygame.math import Vector2 as Vec2d

class Camera:
    def __init__(self, width, height, map_width, map_height):
        self.width = width
        self.height = height
        self.map_width = map_width
        self.map_height = map_height
        self.position = Vec2d(0, 0)

    def oldupdate2(self, target):
        # Target should be centered on screen
        x = target.rect.centerx - (self.width // 2)
        y = target.rect.centery - (self.height // 2)

        # Clamp camera position to map bounds
        x = max(0, min(x, self.map_width - self.width))
        y = max(0, min(y, self.map_height - self.height))

        # Store negative position for correct rendering offset
        self.position = Vec2d(-x, -y)

    def update2(self, target):
        # Target should be centered on screen
        x = target.rect.centerx - (self.width // 2)
        y = target.rect.centery - (self.height // 2)

        # Clamp camera position to map bounds
        x = max(0, min(x, self.map_width - self.width))
        y = max(0, min(y, self.map_height - self.height))

        # Store the position without negating it
        self.position = Vec2d(x, y)

    def apply(self, rect):
        """Convert rect from world coordinates to screen coordinates"""
        # Create a new rect to avoid modifying the original
        # cam_rect = pygame.Rect(rect.x, rect.y, rect.width, rect.height)
        # cam_rect.x -= self.position.x
        # cam_rect.y -= self.position.y
        # return cam_rect
        return pygame.Rect(rect.x - self.position[0], rect.y - self.position[1], rect.width, rect.height)

    def reverse_apply(self, x, y):
        return (x + self.position[0], y + self.position[1]) # Return a tuple

    def old2apply(self, rect):
        """Convert rect from world coordinates to screen coordinates"""
        return pygame.Rect(rect.x - self.position.x, rect.y - self.position.y, rect.width, rect.height)
        # return rect.move(self.position.x, self.position.y)

    def oldapply(self, target):
        # Use position directly instead of camera.topleft
        if isinstance(target, pygame.Rect):
            return target.move(self.position.x, self.position.y)
        else:
            return target.rect.move(self.position.x, self.position.y)
