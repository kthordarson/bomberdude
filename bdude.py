#!/usr/bin/python
import json
import sys
import asyncio
from threading import Thread
import time
from argparse import ArgumentParser
from queue import Empty
import pygame
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from panels import Mainmenu
from game import Bomberdude

async def pusher(game):
    logger.info(f'{game} pushstarting eventq: {game.client_game_state.event_queue.qsize()}')
    try:
        while True:
            try:
                game_events = await game.client_game_state.event_queue.get()
            except asyncio.QueueEmpty:
                game_events = []  # [{'event_type': 'pushermsgdict'},]

            client_keys = json.loads(game.client_game_state.keyspressed.to_json())
            player_one = game.client_game_state.get_playerone()
            if not player_one:
                logger.error(f'No player one {game_events}')
                await asyncio.sleep(1)
                continue

            msg = {
                'game_events': game_events,
                'client_id': player_one.client_id,
                'name': f'{player_one.client_id}',
                'position': (player_one.position[0], player_one.position[1]),
                'keyspressed': client_keys,
                'msgtype': "pushermsgdict",
                'msg_dt': time.time(),
            }

            if game.connected():
                try:
                    data_out = json.dumps(msg).encode('utf-8') + b'\n'
                    await asyncio.get_event_loop().sock_sendall(game.sock, data_out)
                except Exception as e:
                    logger.error(f'{e} {type(e)}')
                    await asyncio.sleep(1)
            else:
                logger.warning(f'{game} not connected')
                await asyncio.sleep(1)

            # Clear game_events after sending
            # game.eventq.task_done()
            game.client_game_state.event_queue.task_done()
            await asyncio.sleep(1 / UPDATE_TICK)
    except Exception as e:
        logger.error(f'{e} {type(e)}')

async def receive_game_state(game):
    if game.debug:
        logger.info(f'{game} receive_game_state starting')
    buffer = ""
    while True:
        try:
            data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
            if not data:
                logger.warning(f"No data received, continuing...game.sock: {game.sock._closed}")
                if game.sock._closed:
                    game._connected = False
                    logger.warning(f'game.sock._closed {game.sock._closed}')
                    break
                await asyncio.sleep(1)  # Short sleep to prevent CPU spinning
                break

            buffer += data.decode('utf-8')
            while '\n' in buffer:
                message, buffer = buffer.split('\n', 1)
                if message.strip():  # Ignore empty messages
                    try:
                        game_state_json = json.loads(message)
                        game.client_game_state.from_json(game_state_json)
                        if game.args.debug:
                            pass  # logger.info(f"game_state_json: {game_state_json}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error decoding json: {e} message: {message}")
                        continue

        except (BlockingIOError, InterruptedError):
            await asyncio.sleep(0.101)
            continue
        except ConnectionResetError as e:
            logger.warning(f"Error in receive_game_state: {e} {type(e)}")
            game._connected = False
            break
        except TypeError as e:
            logger.error(f"Error in receive_game_state: {e} data: {data}")
            await asyncio.sleep(0.101)
            continue
        except Exception as e:
            logger.error(f"Error in receive_game_state: {e} {type(e)} data: {data}")
            game._connected = False
            await asyncio.sleep(1)  # Prevent tight loop on error
            break

async def oldreceive_game_state(game):
    if game.debug:
        logger.info(f'{game} receive_game_state starting')
    while True:
        try:
            data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
            if not data:
                logger.warning(f"No data received, continuing...game.sock: {game.sock._closed}")
                if game.sock._closed:
                    game._connected = False
                    logger.warning(f'game.sock._closed {game.sock._closed}')
                    break
                await asyncio.sleep(1)  # Short sleep to prevent CPU spinning
                break
            # Split the received data using the newline delimiter
            try:
                messages = data.decode('utf-8').split('\n')
                for message in messages:
                    if message.strip():  # Ignore empty messages
                        game_state_json = json.loads(message)
                        game.client_game_state.from_json(game_state_json)
                        if game.args.debug:
                            pass  # logger.info(f"game_state_json: {game_state_json}")
            except json.JSONDecodeError as e:
                logger.warning(f"Error decoding json: {e} data: {data}")
                await asyncio.sleep(0.5)  # Short sleep to prevent CPU spinning
                continue
        except (BlockingIOError, InterruptedError):
            await asyncio.sleep(0.101)
            continue
        except ConnectionResetError as e:
            logger.warning(f"Error in receive_game_state: {e} {type(e)}")
            game._connected = False
            break
        except TypeError as e:
            logger.error(f"Error in receive_game_state: {e} data: {data}")
            await asyncio.sleep(0.101)
            continue
        except Exception as e:
            logger.error(f"Error in receive_game_state: {e} {type(e)} data: {data}")
            game._connected = False
            await asyncio.sleep(1)  # Prevent tight loop on error
            break


async def olderreceive_game_state(game):
    if game.debug:
        logger.info(f'{game} receive_game_state starting')
    while True:
        try:
            data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
            if not data:
                logger.debug(f"No data received, continuing...game.sock: {game.sock._closed}")
                if game.sock._closed:
                    game._connected = False
                    logger.warning(f'game.sock._closed {game.sock._closed}')
                    break
                await asyncio.sleep(1 / UPDATE_TICK)  # Short sleep to prevent CPU spinning
                continue
            # Split the received data using the newline delimiter
            messages = data.decode('utf-8').split('\n')
            for message in messages:
                if message.strip():  # Ignore empty messages
                    try:
                        msg_json = json.loads(message)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error decoding json: {e} data: {data}")
                        await asyncio.sleep(0.5)  # Short sleep to prevent CPU spinning
                        continue
                    msgtype = msg_json.get('msgtype', 'msgtypeunknown')
                    if game.debug:
                        pass  # logger.debug(f"{message}")
                    match msgtype:
                        case 'playerlist':
                            if game.debug:
                                pass  # logger.debug(f"{message}")
                            game.client_game_state.from_json(msg_json)
                        case 'update_game_state':
                            if game.debug:
                                logger.debug(f"{message}")
                            game.client_game_state.from_json(msg_json)
                        case 'playerstate':
                            pass
                        case 'player_update':
                            if game.debug:
                                logger.debug(f"{message}")
                            game.client_game_state.from_json(msg_json)
                        case 'debug_dump':
                            pass
                        case 'msgtypeunknown':
                            logger.warning(f'unknown msgtype {msgtype=} {message=}')
                        case _:
                            logger.warning(f'unknown msgtype {msgtype=} {message=}')

                    # game_state_json = await game.sock.recv_json()
        except (BlockingIOError, InterruptedError):
            # Socket would block, just continue
            await asyncio.sleep(0.101)
            continue
        except ConnectionResetError as e:
            logger.warning(f"Error in receive_game_state: {e} {type(e)}")
            game._connected = False
            break
        except TypeError as e:
            logger.error(f"Error in receive_game_state: {e} data: {data}")
            await asyncio.sleep(0.101)
            continue
            # game._connected = False
            # break
        except Exception as e:
            logger.error(f"Error in receive_game_state: {e} {type(e)} data: {data}")
            game._connected = False
            await asyncio.sleep(1)  # Prevent tight loop on error
            break
        await asyncio.sleep(1 / UPDATE_TICK)

# def thread_worker(game):
#     logger.info(f"Starting thread_worker for {game}")
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     looptask = loop.create_task(thread_main(game, loop))
#     logger.info(f"threadworker loop: {loop} lt={looptask} ")
#     loop.run_forever()

def get_args():
    parser = ArgumentParser(description="bdude")
    parser.add_argument("--testclient", default=False, action="store_true", dest="testclient")
    parser.add_argument("--name", action="store", dest="name", default="bdude")
    parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
    parser.add_argument("--server", action="store", dest="server", default="127.0.0.1")
    parser.add_argument("--port", action="store", dest="port", default=9696)
    parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
    parser.add_argument("-dp", "--debugpacket", action="store_true", dest="packetdebugmode", default=False,)
    return parser.parse_args()

async def start_game(args, eventq):
    bomberdude_main = Bomberdude(args=args, eventq=eventq)
    connection_timeout = 5  # seconds
    try:
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
    # worker_task = asyncio.create_task(thread_worker(bomberdude_main))
    logger.info(f"Starting thread_worker for {bomberdude_main}")

    # Main loop
    running = True
    while running:
        start_time = time.time()

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
                bomberdude_main.handle_on_key_release(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                asyncio.create_task(bomberdude_main.handle_on_mouse_press(event.pos[0], event.pos[1], event.button))
        elapsed_time = time.time() - start_time
        await asyncio.sleep(max(0, 1 / UPDATE_TICK - elapsed_time))
        # await asyncio.sleep(1 / UPDATE_TICK)

    # Clean up tasks
    push_task.cancel()
    receive_task.cancel()
    await asyncio.gather(push_task, receive_task, return_exceptions=True)
    pygame.display.quit()
    pygame.quit()

async def main():
    pygame.init()
    args = get_args()
    eventq = asyncio.Queue()
    # screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(SCREEN_TITLE)
    # bomberdude_main = MainView(screen=screen, name="Bomberdude main", title="Bomberdude Main Menu", args=args, eventq=eventq)

    mainmenu = Mainmenu(screen=screen, args=args, eventq=eventq)
    action = mainmenu.run()
    if action == "start":
        await start_game(args, eventq)
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
