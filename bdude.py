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
    async def pusher():
        # Push the player's INPUT state 60 times per second
        thrmain_cnt = 0
        # game_events = []
        while True:
            thrmain_cnt += 1
            try:
                game_events = game.eventq.get_nowait()
                game.eventq.task_done()
            except Empty:
                game_events = []
            msg = dict(
                thrmain_cnt=thrmain_cnt,
                score=game.playerone.score,
                game_events=[
                    game_events,
                ],
                client_id=game.playerone.client_id,
                name=game.playerone.name,
                position=game.playerone.position,
                angle=game.playerone.angle,
                health=game.playerone.health,
                timeout=game.playerone.timeout,
                killed=game.playerone.killed,
                bombsleft=game.playerone.bombsleft,
                gotmap=game._gotmap,
                msgsource="pushermsgdict",
                msg_dt=time.time(),
            )
            if game.connected():
                await game.push_sock.send_json(msg)
                await asyncio.sleep(1 / UPDATE_TICK)
            else:
                await asyncio.sleep(1)

    async def receive_game_state():
        while True:
            _gs = await game.sub_sock.recv_json()
            # gs = json.loads(_gs)
            game.game_state.from_json(_gs)

    await asyncio.gather(
        pusher(),
        receive_game_state(),
    )


def thread_worker(game):
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

    app = arcade.Window(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=True, gc_mode="context_gc",)
    mainview = MainView(window=app, name="bomberdue", title="Bomberdude Main Menu", args=args)
    thread = Thread(target=thread_worker, args=(mainview.game,), daemon=True)
    thread.start()
    app.show_view(mainview)
    logger.info(f"arcaderun: {app} t={thread} mw={mainview}")
    arcade.run()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
    # asyncio.run(main())
    # arcade.run()
