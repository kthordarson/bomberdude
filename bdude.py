#!/usr/bin/python
import sys
import asyncio
from threading import Thread
import time
from argparse import ArgumentParser
from queue import Empty
# import arcade
import pygame
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from menu import MainView
from game import Bomberdude
# todo get inital pos from server
# done draw netbombs
# done sync info bewteen Client and Bomberplayer
# done  update clients when new player connects
# task 1 send player input to server
# task 2 receive game state from server
# task 3 draw game

# task 1 accept connections
# taks 2 a. receive player input b. update game state
# task 3 send game state to clients


async def thread_main(game, loop):
    logger.info(f'{game} thread_main starting eventq: {game.eventq.qsize()}')

    async def pusher(game):
        logger.info(f'{game} pushstarting eventq: {game.eventq.qsize()}')
        thrmain_cnt = 0
        if game.debug:
            logger.info(f'{game} pusher starting eventq: {game.eventq.qsize()}')
        while True:
            thrmain_cnt += 1
            try:
                game_events = await game.eventq.get()
            except asyncio.QueueEmpty:
                game_events = []
            client_keys = game.client_game_state.keys_pressed.to_json()
            player_one = game.client_game_state.get_playerone()
            clidpush = player_one.client_id  # str([k for k in game.player_list][0].client_id)
            msg = dict(
                thrmain_cnt=thrmain_cnt,
                score=1,
                game_events=game_events,
                client_id=clidpush,
                name=f'xxxcasdfa-{clidpush}',
                position=(1,1),
                angle=1,
                health=4,
                timeout=False,
                killed=False,
                bombsleft=101,
                gotmap=True,
                keyspressed=client_keys,
                msgsource="pushermsgdict",
                msg_dt=time.time(),
            )
            if game.connected():
                await game.push_sock.send_json(msg)
            else:
                logger.warning(f'{game} not connected')
                await asyncio.sleep(1)
            # await asyncio.sleep(1 / UPDATE_TICK)

    async def receive_game_state(game):
        if game.debug:
            logger.info(f'{game} receive_game_state starting')
        while True:
            try:
                game_state_json = await game.sub_sock.recv_json()
                game.game_state.from_json(game_state_json)
                if game.args.debug:
                    logger.info(f"game_state_json: {game_state_json}")
            except Exception as e:
                logger.error(f"Error in receive_game_state: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on error
            # await asyncio.sleep(1 / UPDATE_TICK)


def thread_worker(game):
    logger.info(f"Starting thread_worker for {game}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    looptask = loop.create_task(thread_main(game, loop))
    logger.info(f"threadworker loop: {loop} lt={looptask} ")
    loop.run_forever()

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

async def new_main():
    pygame.init()
    args = get_args()
    eventq = asyncio.Queue()
    # screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(SCREEN_TITLE)
    # bomberdude_main = MainView(screen=screen, name="Bomberdude main", title="Bomberdude Main Menu", args=args, eventq=eventq)
    bomberdude_main = Bomberdude(args=args, eventq=eventq)
    logger.info(f"Starting thread_worker for {bomberdude_main}")
    thread = Thread(target=thread_worker, args=(bomberdude_main,), daemon=True)
    thread.start()
    logger.info(f"t={thread} mw={bomberdude_main}")

    # Main loop
    running = True
    while running:
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
                # bomberdude_main.handle_on_mouse_press(event.pos[0], event.pos[1], event.button)
                asyncio.create_task(bomberdude_main.handle_on_mouse_press(event.pos[0], event.pos[1], event.button))
        # await asyncio.sleep(1 / UPDATE_TICK)
    pygame.display.quit()
    pygame.quit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(new_main())
