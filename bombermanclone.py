import pygame
import random
import time

# Initialize pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
tile_size = 40
grid_width = WIDTH // tile_size
grid_height = HEIGHT // tile_size

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (100, 100, 100)

# Load assets
player_img = pygame.Surface((tile_size, tile_size))
player_img.fill(BLUE)

bomb_img = pygame.Surface((tile_size, tile_size))
bomb_img.fill(RED)

wall_img = pygame.Surface((tile_size, tile_size))
wall_img.fill(GRAY)

# Game window
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Bomberman Clone")

# Clock
clock = pygame.time.Clock()

# Map generation
map_grid = [[1 if random.random() < 0.2 else 0 for _ in range(grid_width)] for _ in range(grid_height)]
map_grid[0][0] = 0  # Ensure starting position is free

# Classes
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = tile_size

    def move(self, dx, dy):
        new_x = self.x + dx * self.speed
        new_y = self.y + dy * self.speed
        grid_x, grid_y = new_x // tile_size, new_y // tile_size
        if 0 <= grid_x < grid_width and 0 <= grid_y < grid_height and map_grid[grid_y][grid_x] == 0:
            self.x = new_x
            self.y = new_y

    def draw(self, screen):
        screen.blit(player_img, (self.x, self.y))

class Bomb:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.start_time = time.time()
        self.exploded = False

    def draw(self, screen):
        screen.blit(bomb_img, (self.x, self.y))

    def check_explosion(self):
        if time.time() - self.start_time > 3:
            self.exploded = True

# Game loop
player = Player(0, 0)
bombs = []
running = True

while running:
    screen.fill(WHITE)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        player.move(-1, 0)
    if keys[pygame.K_RIGHT]:
        player.move(1, 0)
    if keys[pygame.K_UP]:
        player.move(0, -1)
    if keys[pygame.K_DOWN]:
        player.move(0, 1)
    if keys[pygame.K_SPACE]:
        bombs.append(Bomb(player.x, player.y))

    # Update bombs
    for bomb in bombs[:]:
        bomb.check_explosion()
        if bomb.exploded:
            bombs.remove(bomb)

    # Draw map
    for row in range(grid_height):
        for col in range(grid_width):
            if map_grid[row][col] == 1:
                screen.blit(wall_img, (col * tile_size, row * tile_size))

    # Draw everything
    player.draw(screen)
    for bomb in bombs:
        bomb.draw(screen)

    pygame.display.flip()
    clock.tick(10)

pygame.quit()
