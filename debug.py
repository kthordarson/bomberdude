# debug.py
import pygame
import time
from loguru import logger
import math

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

def draw_debug_info(screen, game_state, camera):
    font = pygame.font.Font(None, 20)
    fps = update_fps()
    fps_text = font.render(f"FPS: {fps}", True, (0, 255, 0))
    screen.blit(fps_text, (screen.get_width() - 100, 10))

    debug_text = font.render(f"Players: {len(game_state.playerlist)}/{len(game_state.players_sprites)} eq: {game_state.event_queue.qsize()} cq: {game_state.client_queue.qsize()}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 10))
    debug_text = font.render(f"bullets: {len(game_state.bullets)} bombs: {len(game_state.bombs)}", True, (255, 255, 255))
    screen.blit(debug_text, (10, 30))
    debug_text = font.render(f"player_one: {game_state.get_playerone().client_id} {game_state.get_playerone().position} {game_state.get_playerone().health} ", True, (55, 255, 55))
    screen.blit(debug_text, (10, 60))
    # y_pos = 80
    # font = pygame.font.Font(None, 16)
    # for player in game_state.playerlist.values():
    #     debug_text = font.render(f"netplayer: {player.client_id} {player.position}", True, (155, 125, 125))
    #     screen.blit(debug_text, player.position)

    draw_bullet_debug(screen, game_state, camera)
    draw_other_player_id(screen, game_state, camera)
    draw_blocks_around_player(screen, game_state, camera)

def draw_other_player_id(screen, game_state, camera):
    # Draw player one's ID above their sprite
    font = pygame.font.Font(None, 16)
    player_one = game_state.get_playerone()
    player_one_screen_pos = camera.apply(player_one.rect).topleft
    player_text = font.render(f"{player_one.health}", True, (50, 255, 50))
    screen.blit(player_text, (player_one_screen_pos[0], player_one_screen_pos[1] - 20))

    # Draw network players' IDs above their sprites
    for player in game_state.playerlist.values():
        if player.client_id != game_state.get_playerone().client_id:
            try:
                player_rect = pygame.Rect(player.position[0], player.position[1], 32, 32)
                # Convert world position to screen position
                screen_pos = camera.apply(player_rect).topleft
                # Generate and draw the player ID text above the sprite
                player_text = font.render(f"{player.health}", True, (255, 150, 150))
                text_x = screen_pos[0] + (player_rect.width // 2) - (player_text.get_width() // 2)
                text_y = screen_pos[1] - 20  # Position above the player sprite

                # Draw text with a small shadow for better visibility
                # shadow_text = font.render(f"{player.client_id}", True, (0, 0, 0))
                # screen.blit(shadow_text, (text_x + 1, text_y + 1))
                screen.blit(player_text, (text_x, text_y))
            except Exception as e:
                logger.error(f"Error drawing player ID: {e} {type(e)}")

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

    # Define how many tiles around player to highlight
    highlight_range = 3

    # Create a font for block IDs
    font = pygame.font.Font(None, 14)

    # Highlight blocks around player
    for tile in game_state.collidable_tiles:
        # Calculate tile coordinates
        tile_x = tile.rect.x // tile_width
        tile_y = tile.rect.y // tile_height

        # Check if within range of player
        if (abs(tile_x - player_tile_x) <= highlight_range and abs(tile_y - player_tile_y) <= highlight_range):

            # Convert to screen coordinates
            screen_rect = camera.apply(tile.rect)

            # Draw highlight
            highlight_color = (255, 255, 0, 128)  # Yellow semi-transparent
            if hasattr(tile, 'layer') and tile.layer == 'Blocks':
                highlight_color = (0, 255, 255, 128)  # Cyan for destructible blocks

            # Draw outline around block
            pygame.draw.rect(screen, highlight_color, screen_rect, 2)

            # Show block position/ID
            pos_text = f"({tile_x},{tile_y})"
            if hasattr(tile, 'id'):
                pos_text = f"ID:{tile.id}"

            text_surf = font.render(pos_text, True, (255, 255, 255))
            screen.blit(text_surf, (screen_rect.centerx - text_surf.get_width()//2,
                                   screen_rect.centery - text_surf.get_height()//2))

            # Draw line from player to this block
            pygame.draw.line(
                screen,
                (100, 100, 255),  # Light blue
                camera.apply(player_one.rect).center,
                screen_rect.center,
                1  # Line width
            )
