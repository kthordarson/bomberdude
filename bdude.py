#!/usr/bin/python
import sys
import asyncio
from threading import Thread
import time
from argparse import ArgumentParser
from queue import Empty
from loguru import logger
from constants import *
from menu import MainView


# todo get initial pos from server
# done draw netbombs
# done sync info between Client and Bomberplayer
# done  update clients when new player connects
# task 1 send player input to server
# task 2 receive game state from server
# task 3 draw game

# task 1 accept connections
# task 2 a. receive player input b. update game state
# task 3 send game state to clients

async def thread_main(game):
	async def pusher():
		# Push the player's INPUT state 60 times per second
		thrmain_cnt = 0
		while True:
			thrmain_cnt += 1
			msg = dict(
				thrmain_cnt=thrmain_cnt,
				score=game.playerone.score,
				client_id=game.playerone.client_id,
				name=game.playerone.name,
				position=game.playerone.position,
				angle=game.playerone.angle,
				health=game.playerone.health,
				timeout=game.playerone.timeout,
				killed=game.playerone.killed,
				bombsleft=game.playerone.bombsleft,
				got_map=game.got_map(),
				msgsource='pushermsgdict',
				msg_dt=time.time())
			try:
				game_event = game.game_eventq.get_nowait()
				game.game_eventq.task_done()
				await game.push_sock.send_json({'msgtype': 'game_event', 'payload': game_event})
			except Empty:
				pass  # game_events = None
			await game.push_sock.send_json({'msgtype': 'msg', 'payload': msg})
			await asyncio.sleep(1 / UPDATE_TICK)

	#            else:
	#                logger.warning(f'{game} is not connected.....')
	#                await asyncio.sleep(1)

	async def receive_game_state():
		pe = None
		while True:
			_gs = await game.sub_sock.recv_json()
			msgtype = _gs.get('msgtype')
			# gs = json.loads(_gs)
			if msgtype == 'gamestate':
				game.game_state.from_json(_gs.get('payload'))
			if msgtype == 'pending_event':
				if game.debugtrace:
					logger.debug(f'{_gs=}')				
				# logger.debug(f'{_gs=}')
				game.handle_game_events(_gs.get('payload'))

	await asyncio.gather(pusher(), receive_game_state(), )


def thread_worker(game):
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	looptask = loop.create_task(thread_main(game))
	logger.info(f'threadworker loop: {loop} lt={looptask} ')
	loop.run_forever()


def main():
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--name', action='store', dest='name', default='bdude')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--server', action='store', dest='server', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	parser.add_argument('-d', '--debug', action='store_true', dest='debugmode', default=False)
	parser.add_argument('-dp', '--debugpacket', action='store_true', dest='packetdebugmode', default=False)
	args = parser.parse_args()

	app = arcade.Window(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=True, gc_mode='context_gc')
	mainview = MainView(window=app, name='bomberdude', title='Bomberdude Main Menu', args=args)
	thread = Thread(target=thread_worker, args=(mainview.game,), daemon=True)
	thread.start()
	app.show_view(mainview)
	arcade.run()


if __name__ == "__main__":
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	main()
# arcade.run()
