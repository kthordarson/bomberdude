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
from network import Receiver

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

async def async_receiver(sub_sock, gsqueue, evqueue) -> int:
	# sub_sock=mainview.game.sub_sock, gsqueue=mainview.game.gsqueue, evqueue=mainview.game.evqueue
	pe_counter = 0
	# logger.info(f'{self} running')
	# try:
	# 	loop = asyncio.get_event_loop()
	# except RuntimeError as e:
	# 	if str(e).startswith('There is no current event loop in thread'):
	# 		loop = asyncio.new_event_loop()
	# 		asyncio.set_event_loop(loop)
	# 	else:
	# 		raise
	while True:
		try:
			_gs = await sub_sock.recv_json()
			print(f'{_gs=}')
			msgtype = _gs.get('msgtype', None)
			# gs = json.loads(_gs)
			if msgtype == 'gamestate':
				gsqueue.put(_gs.get('payload'))
			elif msgtype == 'pending_event':
				pe_counter += 1
				evqueue.put(_gs.get('payload'))
			else:
				logger.warning(f'{pe_counter} unknown msgtype: {msgtype} {_gs=}')
		except Exception as e:
			logger.error(f'{type(e)} {e=}')
		return pe_counter


async def main():
	parser = ArgumentParser(description='bdude')
	parser.add_argument('--testclient', default=False, action='store_true', dest='testclient')
	parser.add_argument('--name', action='store', dest='name', default='bdude')
	parser.add_argument('--listen', action='store', dest='listen', default='127.0.0.1')
	parser.add_argument('--server', action='store', dest='server', default='127.0.0.1')
	parser.add_argument('--port', action='store', dest='port', default=9696)
	parser.add_argument('-d', '--debug', action='store_true', dest='debugmode', default=False)
	parser.add_argument('-dt', '--debugtrace', action='store_true', dest='debugtrace', default=False)
	parser.add_argument('-dp', '--debugpacket', action='store_true', dest='packetdebugmode', default=False)
	args = parser.parse_args()

	app = arcade.Window(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE, resizable=True, gc_mode='context_gc')
	mainview = MainView(window=app, name='bomberdude', title='Bomberdude Main Menu', args=args)
	# receiver = Receiver(sub_sock=mainview.game.sub_sock, gsqueue=mainview.game.gsqueue, evqueue=mainview.game.evqueue)
	#thread = Thread(target=thread_worker, args=(mainview.game,), daemon=True)
	#thread.start()
	app.show_view(mainview)
	arcadethread = Thread(target=arcade.run(), daemon=True)
	print(f'{arcadethread=}')
	#arcadethread.start()
	loop = asyncio.get_event_loop()
	tasks = set()
	# task1 = await asyncio.to_thread(loop.create_task(arcade.run()))
	# task1 = asyncio.create_task(mainview.game.receiver.run())
	# print(f'{task1=}')
	task2 = asyncio.to_thread(arcadethread.start)
	print(f'{task2=}')
	#task2thread = asyncio.to_thread(task2)
	#print(f'{task2thread=}')
	# tasks.add(task1)
	tasks.add(task2)
	#r = Receiver(sub_sock=mainview.game.sub_sock, gsqueue=mainview.game.gsqueue, evqueue=mainview.game.evqueue)
	t = async_receiver(sub_sock=mainview.game.sub_sock, gsqueue=mainview.game.gsqueue, evqueue=mainview.game.evqueue)
	await asyncio.gather(t,task2)
	# async with asyncio.TaskGroup() as tg:
	# 	# app.show_view(mainview)
	# 	task1 = tg.create_task(asyncio.to_thread(arcade.run ))
	# 	task2 = tg.create_task(mainview.game.receiver.run())
	# print(f'{task1=} {task2=}')
		#
	#await asyncio.gather(mainview.game.receiver.run(), )
	#arcade.run()
	# await asyncio.gather(pusher(mainview.game), receive_game_state(mainview.game), )


if __name__ == "__main__":
	if sys.platform == 'win32':
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	asyncio.run(main())
# arcade.run()
