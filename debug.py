# debug.py

import pygame

def draw_debug_info(screen, game_state):
    font = pygame.font.Font(None, 36)
    debug_text = font.render(f"Players: {len(game_state.playerlist)}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 10))
