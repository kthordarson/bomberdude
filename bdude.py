#!/usr/bin/python
import json
import sys
import asyncio
import time
from argparse import ArgumentParser
import pygame
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from panels import Mainmenu
from game import Bomberdude

async def pusher(game):
    logger.info(f'pushstarting event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')
    game_event = []
    while True:
        try:
            game_event = await game.client_game_state.event_queue.get()
        except asyncio.QueueEmpty:
            pass
        except Exception as e:
            logger.error(f"Error getting game_event: {e} {type(e)}")
            continue
        client_keys = json.loads(game.client_game_state.keyspressed.to_json())
        try:
            player_one = game.client_game_state.get_playerone()
        except AttributeError as e:
            logger.error(f'{e} {type(e)}')
            await asyncio.sleep(0.1)
            continue
        # playerlist = [player for player in game.client_game_state.playerlist.values()]
        playerlist = [player.to_dict() if hasattr(player, 'to_dict') else player for player in game.client_game_state.playerlist.values()]
        msg = {
            'game_event': game_event,
            'client_id': player_one.client_id,
            'position': (player_one.position[0], player_one.position[1]),
            'keyspressed': client_keys,
            'msgtype': "pushermsgdict",
            'handledby': "pusher",
            'msg_dt': time.time(),
            'playerlist': playerlist,
            # 'playerlist': [player for player in self.playerlist.values()]
        }
        try:
            data_out = json.dumps(msg).encode('utf-8') + b'\n'
            await asyncio.get_event_loop().sock_sendall(game.sock, data_out)
            game.client_game_state.event_queue.task_done()
            if game.args.debug:
                if msg.get('game_event').get('event_type') != 'player_update':
                    logger.debug(f"pusher sent: {msg.get('game_event').get('event_type')} from {msg.get('game_event').get('client_id')} event_queue: {game.client_game_state.event_queue.qsize()} client_queue:{game.client_game_state.client_queue.qsize()}")
        except Exception as e:
            logger.error(f'{e} {type(e)} msg: {msg}')
            game._connected = False
            break

async def receive_game_state(game):
    buffer = ""
    while True:
        try:
            data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
            if not data:
                if game.sock._closed or not game.connected():
                    game._connected = False
                    break
                else:
                    await asyncio.sleep(0.05)  # Reduced sleep time
                    continue

            buffer += data.decode('utf-8')

            # Process multiple messages at once if available
            while '\n' in buffer:
                message, buffer = buffer.split('\n', 1)
                if not message.strip():
                    continue

                game_state_json = json.loads(message)

                # Priority handling for critical events
                if game_state_json.get("msgtype") == "game_event":
                    event_type = game_state_json.get("event", {}).get("event_type")
                    if event_type in ("bulletfired", "drop_bomb", "player_update"):
                        # Process high priority events immediately
                        await game.client_game_state.update_game_event(game_state_json["event"])
                    else:
                        # Queue less critical events
                        asyncio.create_task(game.client_game_state.update_game_event(game_state_json["event"]))
                else:
                    # Process regular state updates
                    game.client_game_state.from_json(game_state_json)

        except (BlockingIOError, InterruptedError):
            await asyncio.sleep(0.001)  # Very short sleep to avoid CPU spinning
            continue
        except Exception as e:
            logger.warning(f"Error in receive_game_state: {e}")
            if isinstance(e, ConnectionResetError):
                game._connected = False
                break
            continue

def get_args():
    parser = ArgumentParser(description="bdude")
    parser.add_argument("--testclient", default=False, action="store_true", dest="testclient")
    parser.add_argument("--name", action="store", dest="name", default="bdude")
    parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
    parser.add_argument("--server", action="store", dest="server", default="127.0.0.1")
    parser.add_argument("--port", action="store", dest="port", default=9696)
    parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
    parser.add_argument("-dp", "--debugpacket", action="store_true", dest="debugpacket", default=False,)
    return parser.parse_args()

async def start_game(args):
    bomberdude_main = Bomberdude(args=args)

    # worker_task = asyncio.create_task(thread_worker(bomberdude_main))
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

    push_task = asyncio.create_task(pusher(bomberdude_main))
    receive_task = asyncio.create_task(receive_game_state(bomberdude_main))

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
                # logger.debug(f'keydown {event} event.key={event.key}')
                bomberdude_main.handle_on_key_press(event.key)
            elif event.type == pygame.KEYUP:
                # logger.info(f'keyup {event} event.key={event.key}')
                await bomberdude_main.handle_on_key_release(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                asyncio.create_task(bomberdude_main.handle_on_mouse_press(event.pos[0], event.pos[1], event.button))

        # Calculate sleep time to maintain constant frame rate
        elapsed = time.time() - frame_start
        sleep_time = max(0, frame_time - elapsed)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

    # Clean up tasks
    push_task.cancel()
    receive_task.cancel()
    await asyncio.gather(push_task, receive_task, return_exceptions=True)
    pygame.display.quit()
    pygame.quit()

async def main():
    pygame.init()
    args = get_args()
    # screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(SCREEN_TITLE)
    mainmenu = Mainmenu(screen=screen, args=args)
    action = mainmenu.run()
    if action == "start":
        await start_game(args)
    elif action == 'setup':
        logger.info("Setup not implemented")
    elif action == 'quit':
        logger.info("Quitting...")
    else:
        logger.warning(f"Unknown action: {action}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
    # cProfile.run('asyncio.run(main())')
