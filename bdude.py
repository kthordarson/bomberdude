#!/usr/bin/python
import orjson as json
import sys
import asyncio
import time
from argparse import ArgumentParser
import pygame
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from panels import MainMenu, SetupMenu
from game.bomberdude import Bomberdude
from network.client import send_game_state, receive_game_state

def get_args():
    parser = ArgumentParser(description="bdude")
    parser.add_argument("--testclient", default=False, action="store_true", dest="testclient")
    parser.add_argument("--name", action="store", dest="name", default="bdude")
    parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
    parser.add_argument("--server", action="store", dest="server", default="127.0.0.1")
    parser.add_argument("--port", action="store", dest="port", default=9696)
    parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
    parser.add_argument("-dp", "--debugpacket", action="store_true", dest="debugpacket", default=False,)
    parser.add_argument("--cprofile", action="store_true", dest="cprofile", default=False,)
    parser.add_argument("--cprofile_file", action="store", dest="cprofile_file", default='bdude_profile.prof')
    return parser.parse_args()

async def start_game(args):
    bomberdude_main = Bomberdude(args=args)

    sender_task = asyncio.create_task(send_game_state(bomberdude_main))
    receive_task = asyncio.create_task(receive_game_state(bomberdude_main))

    connection_timeout = 5  # seconds
    try:
        logger.info(f"Connecting.... {bomberdude_main}")
        connected = await asyncio.wait_for(bomberdude_main.connect(), timeout=connection_timeout)
        if not connected:
            logger.error("Failed to establish connection")
            return
    except asyncio.TimeoutError:
        logger.error("Connection attempt timed out")
        return
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return

    # Calculate frame time in seconds
    target_fps = UPDATE_TICK  # Using your constant from constants.py
    frame_time = 1.0 / target_fps

    # Main loop
    running = True
    while running:
        # start_time = time.time()
        frame_start = time.time()
        await bomberdude_main.update()
        bomberdude_main.on_draw()
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                bomberdude_main.running = False
                bomberdude_main._connected = False
                running = False
            elif event.type == pygame.KEYDOWN:
                await bomberdude_main.handle_on_key_press(event.key)
            elif event.type == pygame.KEYUP:
                await bomberdude_main.handle_on_key_release(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                asyncio.create_task(bomberdude_main.handle_on_mouse_press(event.pos[0], event.pos[1], event.button))

        # Calculate sleep time to maintain constant frame rate
        elapsed = time.time() - frame_start
        sleep_time = max(0, frame_time - elapsed)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        if sleep_time > 0.05:
            logger.warning(f"Sleep time: {sleep_time}")
            await asyncio.sleep(sleep_time)

    # Clean up tasks
    sender_task.cancel()
    receive_task.cancel()
    await asyncio.gather(sender_task, receive_task, return_exceptions=True)
    # pygame.display.quit()
    # pygame.quit()

async def main(args):
    pygame.init()
    # screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(SCREEN_TITLE)
    running = True
    try:
        mainmenu = MainMenu(screen=screen, args=args)
        while running:
            action = mainmenu.run()
            if action == "Start":
                await start_game(args)
            elif action == 'Back':
                pass
            elif action in ['option1', 'option2', 'option3']:
                logger.info(f"Setup {action} not implemented")
            elif action == 'Find server':
                logger.info("Find server ....")
                await asyncio.sleep(1)
            elif action == 'Quit':
                logger.info("Quitting...")
                running = False
            else:
                logger.warning(f"Unknown action: {action}")
                await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error in main: {e} {type(e)}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    args = get_args()
    if args.cprofile:
        import cProfile
        import pstats

        profiler = cProfile.Profile()
        profiler.enable()

        asyncio.run(main(args))

        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats('cumtime')
        stats.print_stats(30)  # Print top 30 time-consuming functions

        # Optionally save results to a file
        stats.dump_stats(args.cprofile_file)
    else:
        asyncio.run(main(args))
