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

    def apply2(self, target):
        if isinstance(target, pygame.Rect):
            return target.move(self.camera.topleft)
        else:
            return target.rect.move(self.camera.topleft)

    def applyx(self, entity):
        # Move entity by camera offset
        return entity.rect.move(self.position.x, self.position.y)

class oldCamera:
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
        # Move camera to keep target centered
        x = -target.rect.centerx + int(self.width / 2)
        y = -target.rect.centery + int(self.height / 2)

        # Constrain camera to map bounds
        x = min(0, x)
        y = min(0, y)
        x = max(-(self.map_width - self.width), x)
        y = max(-(self.map_height - self.height), y)

        self.position = Vec2d(x, y)

    def update2(self, target):
        # Camera should move opposite to player movement
        x = int(self.width / 2) - target.rect.centerx
        y = int(self.height / 2) - target.rect.centery

        # Limit scrolling to map size
        x = min(0, x)
        y = min(0, y)
        x = max(-(self.map_width - self.width), x)
        y = max(-(self.map_height - self.height), y)
        self.position = Vec2d(x, y)

    def update1(self, target):
        x = -target.rect.centerx + int(self.width / 2)
        y = -target.rect.centery + int(self.height / 2)

        # Limit scrolling to map size
        x = min(0, x)  # Left
        y = min(0, y)  # Top
        x = max(-(self.map_width - self.width), x)  # Right
        y = max(-(self.map_height - self.height), y)  # Bottom
        self.camera = pygame.Rect(x, y, self.width, self.height)
        self.position = Vec2d(x, y)
