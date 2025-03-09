# debug.py

import pygame

def draw_debug_info(screen, game_state):
    font = pygame.font.Font(None, 26)
    debug_text = font.render(f"Players: {len(game_state.playerlist)} event_queue: {game_state.event_queue.qsize()} client_queue: {game_state.client_queue.qsize()}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 10))
    debug_text = font.render(f"bullets: {len(game_state.bullets)} bombs: {len(game_state.bombs)}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 30))
    debug_text = font.render(f"player_one: {game_state.get_playerone().client_id} {game_state.get_playerone().position}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 60))
