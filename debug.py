# debug.py

import pygame
from loguru import logger
import time

# Store the last few frame times for smoothing
frame_times = []
last_frame_time = time.time()

def update_fps():
    """Calculate current FPS based on frame times"""
    global frame_times, last_frame_time

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

def draw_debug_info(screen, game_state):
    font = pygame.font.Font(None, 26)
    fps = update_fps()
    fps_text = font.render(f"FPS: {fps}", True, (0, 255, 0))
    screen.blit(fps_text, (screen.get_width() - 100, 10))

    debug_text = font.render(f"Players: {len(game_state.playerlist)} players_sprites: {len(game_state.players_sprites)} event_queue: {game_state.event_queue.qsize()} client_queue: {game_state.client_queue.qsize()}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 10))
    debug_text = font.render(f"bullets: {len(game_state.bullets)} bombs: {len(game_state.bombs)}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 30))
    debug_text = font.render(f"player_one: {game_state.get_playerone().client_id} {game_state.get_playerone().position} ", True, (55, 255, 55))
    screen.blit(debug_text, (10, 60))
    y_pos = 80
    for player in game_state.playerlist.values():
        if isinstance(player, dict):
            debug_text = font.render(f"player(dict): {player.get('client_id')} {player.get('position')}", True, (255, 255, 155))
            screen.blit(debug_text, (10, y_pos))
            y_pos += 20
        else:
            # Skip rendering player_one again since we already did it above
            if player.client_id != game_state.get_playerone().client_id:
                debug_text = font.render(f"netplayer: {player.client_id} {player.position}", True, (55, 25, 25))
                screen.blit(debug_text, (10, y_pos))
                y_pos += 20

    # for player in game_state.playerlist.values():
    #     if isinstance(player, dict):
    #         pass  # debug_text = font.render(f"player: {player.get('client_id')} {player.get('position')}", True, (255, 255, 155))
    #     else:
    #         if player.client_id == game_state.get_playerone().client_id:
    #             debug_text = font.render(f"p1: {player.client_id} {player.position} ", True, (55, 255, 55))
    #         else:
    #             debug_text = font.render(f"netplayer: {player.client_id} {player.position}", True, (55, 25, 25))
    #     screen.blit(debug_text, (10, y_pos))
    #     y_pos += 20
