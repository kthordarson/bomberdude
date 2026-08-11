# debug.py
import time
import traceback
from collections import OrderedDict

import pygame
from loguru import logger

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


def _render_debug_text(font: pygame.font.Font, text: str, antialias: bool, color, background=None) -> pygame.Surface:
    surf = None
    key = (id(font), text, antialias, tuple(color), tuple(background) if background is not None else None)
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
    surf = _render_debug_text(font, text, antialias, color)
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

def draw_other_player_id(screen, game_state, camera):
    # Draw player one's ID above their sprite
    font = _get_font(16)
    player_one = game_state.get_playerone()
    player_one_screen_pos = camera.apply(player_one.rect).topleft
    player_text = _render_debug_text(font, f"{player_one.health}", True, (50, 255, 50))
    screen.blit(player_text, (player_one_screen_pos[0], player_one_screen_pos[1] - 20))

    # Draw network players' IDs above their sprites
    for player in game_state.playerlist.values():
        if player.client_id != game_state.get_playerone().client_id:
            try:
                player_rect = pygame.Rect(player.position[0], player.position[1], BLOCK * PLAYER_SCALING, BLOCK * PLAYER_SCALING)
                # Convert world position to screen position
                screen_pos = camera.apply(player_rect).topleft
                # Generate and draw the player ID text above the sprite
                player_text = _render_debug_text(font, f"{player.health}", True, (255, 150, 150))
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
    """Draw a direction indicator for each bullet."""
    for bullet in game_state.bullets:
        center = camera.apply(bullet.rect).center
        tip = (center[0] + bullet.direction.x * 25, center[1] + bullet.direction.y * 25)
        pygame.draw.line(screen, (255, 255, 0), center, tip, 2)
