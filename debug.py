# debug.py
import traceback
import pygame
import time
from loguru import logger
import math
from collections import OrderedDict
from constants import BLOCK, PLAYER_SCALING

# Store the last few frame times for smoothing
frame_times = []
last_frame_time = time.time()

# Cache Font objects (creating fonts repeatedly is expensive)
_DEBUG_FONTS: dict[int, pygame.font.Font] = {}


def _get_font(size: int) -> pygame.font.Font:
    font = _DEBUG_FONTS.get(size)
    if font is None:
        font = pygame.font.Font(None, size)
        _DEBUG_FONTS[size] = font
    return font


# Small global text render cache.
_TEXT_CACHE_MAX = 512
_TEXT_CACHE: "OrderedDict[tuple[int, str, bool, tuple[int, int, int, int] | tuple[int, int, int], tuple[int, int, int, int] | tuple[int, int, int] | None], pygame.Surface]" = OrderedDict()


def _render_text_cached(font: pygame.font.Font, text: str, antialias: bool, color, background=None) -> pygame.Surface:
    surf = None
    key = (id(font), text, bool(antialias), tuple(color), tuple(background) if background is not None else None)
    if key:
        surf = _TEXT_CACHE.get(key)
    if surf:
        _TEXT_CACHE.move_to_end(key)
        return surf
    surf = font.render(text, antialias, color, background)
    _TEXT_CACHE[key] = surf
    _TEXT_CACHE.move_to_end(key)
    while len(_TEXT_CACHE) > _TEXT_CACHE_MAX:
        _TEXT_CACHE.popitem(last=False)
    return surf


# Per-line cache for dynamic debug strings (avoids render when text unchanged)
_LINE_CACHE: dict[str, tuple[str, pygame.Surface]] = {}


def _render_line(font: pygame.font.Font, cache_key: str, text: str, antialias: bool, color) -> pygame.Surface:
    cached = _LINE_CACHE.get(cache_key)
    if cached is not None and cached[0] == text:
        return cached[1]
    surf = _render_text_cached(font, text, antialias, color)
    _LINE_CACHE[cache_key] = (text, surf)
    return surf

def update_fps():
    """Calculate current FPS based on frame times"""
    global last_frame_time

    current_time = time.time()
    dt = current_time - last_frame_time
    last_frame_time = current_time

    # Store frame time, keep only last 30 frames
    frame_times.append(dt)
    if len(frame_times) > 30:
        frame_times.pop(0)

    # Calculate average FPS
    if frame_times:
        avg_frame_time = sum(frame_times) / len(frame_times)
        if avg_frame_time > 0:
            return int(1.0 / avg_frame_time)
    return 0

def draw_debug_info(screen, game_state, camera):
    font = _get_font(20)
    fps = update_fps()
    fps_text = _render_line(font, "fps", f"FPS: {fps}", True, (0, 255, 0))
    screen.blit(fps_text, (screen.get_width() - 100, 10))

    player_one = game_state.get_playerone()
    players_line = f"Players: {len(game_state.playerlist)}/{len(game_state.players_sprites)} eq: {game_state.event_queue.qsize()} "
    debug_text = _render_line(font, "players", players_line, True, (255, 255, 255))
    screen.blit(debug_text, (10, 10))

    bullets_line = f"bullets: {len(game_state.bullets)} bombs: {len(game_state.bombs)}"
    debug_text = _render_line(font, "projectiles", bullets_line, True, (255, 255, 255))
    screen.blit(debug_text, (10, 30))

    if player_one:
        p1_line = f"player_one: {player_one.client_id} {player_one.position} {player_one.health}"
        debug_text = _render_line(font, "player_one", p1_line, True, (55, 255, 55))
        screen.blit(debug_text, (10, 60))

    draw_bullet_debug(screen, game_state, camera)
    draw_other_player_id(screen, game_state, camera)
    try:
        draw_blocks_around_player(screen, game_state, camera)
    except AttributeError as e:
        logger.error(f"Error drawing blocks around player: {e} {type(e)}")
        traceback.print_exc()

def draw_other_player_id(screen, game_state, camera):
    # Draw player one's ID above their sprite
    font = _get_font(16)
    player_one = game_state.get_playerone()
    player_one_screen_pos = camera.apply(player_one.rect).topleft
    player_text = _render_text_cached(font, f"{player_one.health}", True, (50, 255, 50))
    screen.blit(player_text, (player_one_screen_pos[0], player_one_screen_pos[1] - 20))

    # Draw network players' IDs above their sprites
    for player in game_state.playerlist.values():
        if player.client_id != game_state.get_playerone().client_id:
            try:
                player_rect = pygame.Rect(player.position[0], player.position[1], BLOCK * PLAYER_SCALING, BLOCK * PLAYER_SCALING)
                # Convert world position to screen position
                screen_pos = camera.apply(player_rect).topleft
                # Generate and draw the player ID text above the sprite
                player_text = _render_text_cached(font, f"{player.health}", True, (255, 150, 150))
                text_x = screen_pos[0] + (player_rect.width // 2) - (player_text.get_width() // 2)
                text_y = screen_pos[1] - 20  # Position above the player sprite

                # Draw text with a small shadow for better visibility
                # shadow_text = font.render(f"{player.client_id}", True, (0, 0, 0))
                # screen.blit(shadow_text, (text_x + 1, text_y + 1))
                screen.blit(player_text, (text_x, text_y))
            except Exception as e:
                logger.error(f"Error drawing player ID: {e} {type(e)}")
                traceback.print_exc()

def draw_bullet_debug(screen, game_state, camera):
    # Draw debug lines for all bullets
    for bullet in game_state.bullets:
        bullet_screen = camera.apply(bullet.rect).center
        line_end = (bullet_screen[0] + bullet.direction.x * 25, bullet_screen[1] + bullet.direction.y * 25)
        pygame.draw.line(screen, (255, 0, 0), bullet_screen, line_end, 2)
        # Draw a line showing bullet direction
        start_pos = camera.apply(bullet.rect).center
        end_pos = (start_pos[0] + bullet.direction.x * 25, start_pos[1] + bullet.direction.y * 25)
        pygame.draw.line(screen, (255, 255, 0), start_pos, end_pos, 2)

def draw_blocks_around_player(screen, game_state, camera):
    """
    Highlights blocks near the player and shows their tile position/ID
    """
    # Get player position
    player_one = game_state.get_playerone()
    if not player_one:
        return

    # Convert player position to tile coordinates
    tile_width = game_state.tile_map.tilewidth
    tile_height = game_state.tile_map.tileheight
    player_tile_x = int(player_one.position.x // tile_width)
    player_tile_y = int(player_one.position.y // tile_height)

    # Create a font for block IDs
    font = _get_font(14)

    highlight_range = 2
    for tile in game_state.background_tiles:
        # Calculate tile coordinates
        tile_x = tile.rect.x // tile_width
        tile_y = tile.rect.y // tile_height
        width = 1
        # Check if within range of player
        if (abs(tile_x - player_tile_x) <= highlight_range and abs(tile_y - player_tile_y) <= highlight_range):
            # Convert to screen coordinates
            screen_rect = camera.apply(tile.rect)
            # Draw highlight
            highlight_color = (55, 55, 55, 128)
            # Draw outline around block
            pygame.draw.rect(surface=screen, color=highlight_color, rect=screen_rect, width=width)
            # Show block position/ID
            # pos_text = f"({tile_x},{tile_y})"
            pos_text = f"ID:{tile.id}"
            text_surf = _render_text_cached(font, pos_text, True, (255, 255, 255))
            screen.blit(text_surf, (screen_rect.centerx - text_surf.get_width()//2, screen_rect.centery - text_surf.get_height()//2))
            # Draw line from player to this block
            pygame.draw.line(screen, (200, 100, 255), camera.apply(player_one.rect).center, screen_rect.center, 1)

    # Define how many tiles around player to highlight
    highlight_range = 3
    # Highlight blocks around player
    for tile in game_state.collidable_tiles:
        # Calculate tile coordinates
        tile_x = tile.rect.x // tile_width
        tile_y = tile.rect.y // tile_height
        width = 2
        # Check if within range of player
        if (abs(tile_x - player_tile_x) <= highlight_range and abs(tile_y - player_tile_y) <= highlight_range):

            # Convert to screen coordinates
            screen_rect = camera.apply(tile.rect)

            # Draw highlight
            highlight_color = (255, 255, 0, 128)  # Yellow semi-transparent
            if tile.layer == 'Blocks':
                highlight_color = (0, 255, 255, 128)  # Cyan for destructible blocks
            if tile.layer == 'Walls':
                highlight_color = (255, 55, 110, 128)
                width = 1
            # Draw outline around block
            pygame.draw.rect(surface=screen, color=highlight_color, rect=screen_rect, width=width)
            # Show block position/ID
            # pos_text = f"({tile_x},{tile_y})"
            pos_text = f"ID:{tile.id}"
            text_surf = _render_text_cached(font, pos_text, True, (255, 255, 255))
            screen.blit(text_surf, (screen_rect.centerx - text_surf.get_width()//2, screen_rect.centery - text_surf.get_height()//2))
            # Draw line from player to this block
            pygame.draw.line(screen, (100, 100, 255), camera.apply(player_one.rect).center, screen_rect.center, 1)
    highlight_range = 5
    for tile in game_state.upgrade_blocks:
        # Calculate tile coordinates
        tile_x = tile.rect.x // tile_width
        tile_y = tile.rect.y // tile_height
        width = 2
        # Check if within range of player
        if (abs(tile_x - player_tile_x) <= highlight_range and abs(tile_y - player_tile_y) <= highlight_range):
            # Convert to screen coordinates
            screen_rect = camera.apply(tile.rect)
            # Draw highlight
            highlight_color = (255, 255, 255, 128)
            # Draw outline around block
            pygame.draw.rect(surface=screen, color=highlight_color, rect=screen_rect, width=width)
            # Show block position/ID
            # pos_text = f"({tile_x},{tile_y})"
            pos_text = f"ID:{tile.id}"
            text_surf = _render_text_cached(font, pos_text, True, (255, 255, 255))
            screen.blit(text_surf, (screen_rect.centerx - text_surf.get_width()//2, screen_rect.centery - text_surf.get_height()//2))
            # Draw line from player to this block
            pygame.draw.line(screen, (200, 100, 255), camera.apply(player_one.rect).center, screen_rect.center, 1)

