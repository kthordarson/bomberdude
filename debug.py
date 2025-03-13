# debug.py
import pygame
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

    debug_text = font.render(f"Players: {len(game_state.playerlist)}/{len(game_state.players_sprites)} eq: {game_state.event_queue.qsize()} cq: {game_state.client_queue.qsize()}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 10))
    debug_text = font.render(f"bullets: {len(game_state.bullets)} bombs: {len(game_state.bombs)}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 30))
    debug_text = font.render(f"player_one: {game_state.get_playerone().client_id} {game_state.get_playerone().position} ", True, (55, 255, 55))
    screen.blit(debug_text, (10, 60))
    # y_pos = 80
    font = pygame.font.Font(None, 16)
    for player in game_state.playerlist.values():
        debug_text = font.render(f"netplayer: {player.client_id} {player.position}", True, (155, 125, 125))
        screen.blit(debug_text, player.position)
