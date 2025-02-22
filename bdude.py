#!/usr/bin/python
import sys
import asyncio
from threading import Thread
import time
from argparse import ArgumentParser
from queue import Empty
import arcade
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from menu import MainView

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
                logger.debug(f'game_events={game_events}')
            except asyncio.QueueEmpty:
                game_events = []
            client_keys = game.client_game_state.keys_pressed.to_json()
            clidpush = str([k for k in game.player_list][0].client_id)
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
                logger.debug(f'{thrmain_cnt}')
                await asyncio.sleep(1 / UPDATE_TICK)
            else:
                logger.warning(f'{game} not connected')
                await asyncio.sleep(1)

    async def receive_game_state(game):
        if game.debug:
            logger.info(f'{game} receive_game_state starting')
        while True:
            game_state_json = await game.sub_sock.recv_json()
            game.game_state.from_json(game_state_json)
            if game.args.debug:
                logger.info(f"game_state_json: {game_state_json}")
    await asyncio.gather(pusher(game), receive_game_state(game))


def thread_worker(game):
    logger.info(f"Starting thread_worker for {game}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    looptask = loop.create_task(thread_main(game, loop))
    logger.info(f"threadworker loop: {loop} lt={looptask} ")
    loop.run_forever()


async def main():
    parser = ArgumentParser(description="bdude")
    parser.add_argument("--testclient", default=False, action="store_true", dest="testclient")
    parser.add_argument("--name", action="store", dest="name", default="bdude")
    parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
    parser.add_argument("--server", action="store", dest="server", default="127.0.0.1")
    parser.add_argument("--port", action="store", dest="port", default=9696)
    parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
    parser.add_argument("-dp", "--debugpacket", action="store_true", dest="packetdebugmode", default=False,)
    args = parser.parse_args()

    window = arcade.Window(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=True, gc_mode="context_gc",)
    eventq = asyncio.Queue()
    bomberdude_main = MainView(window=window, name="Bomberdude main", title="Bomberdude Main Menu", args=args, eventq=eventq)
    logger.info(f"Starting thread_worker for {bomberdude_main}")
    thread = Thread(target=thread_worker, args=(bomberdude_main.game,), daemon=True)
    thread.start()
    window.show_view(bomberdude_main)
    logger.info(f"app: {window} t={thread} mw={bomberdude_main}")
    arcade.run()
    # Run arcade in a separate thread
    # arcade_thread = Thread(target=arcade.run, daemon=True)
    # arcade_thread.start()

    # Keep the asyncio event loop running
    #while arcade_thread.is_alive():
#        await asyncio.sleep(0.1)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
