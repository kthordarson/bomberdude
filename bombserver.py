#!/usr/bin/python
import copy
import asyncio
import sys
import json
from argparse import ArgumentParser
from threading import Thread, Timer, active_count, Event
from loguru import logger
import random
from constants import BLOCK, GRIDSIZE, UPDATE_TICK
from gamestate import GameState
from asyncio import create_task, CancelledError
from api import ApiServer
# import zmq
# from zmq.asyncio import Context
from aiohttp import web
from server.server import BombServer


async def start_server(args) -> None:
	fut = asyncio.Future()
	# app = App(signal=fut)
	# ctx = Context()
	server = BombServer(args)
	# tui = ServerTUI(server, debug=args.debug)
	server.tui.start()
	apiserver = ApiServer("bombapi")
	apiserver.add_url_rule("/get_game_state", view_func=server.get_game_state, methods=["GET"])
	apiserver.add_url_rule("/get_tile_map", view_func=server.get_tile_map, methods=["GET"])
	apiserver.add_url_rule("/get_position", view_func=server.get_position, methods=["GET"])
	# apithread = Thread(target=apiserver.run, name=apiserver._import_name, args=(args.listen, 9699), daemon=True)
	api_task = asyncio.create_task(apiserver.run(args.listen, 9699))
	try:
		await asyncio.wait_for(apiserver.wait_until_ready(), timeout=5.0)
		# apithread.start()
		logger.debug(f'{server=} {server.tui=} {apiserver=}')
		# await asyncio.wait([server.ticker_task, fut], return_when=asyncio.FIRST_COMPLETED)
		await asyncio.wait([api_task, server.ticker_task, fut], return_when=asyncio.FIRST_COMPLETED)
	except CancelledError as e:
		logger.warning(f"main Cancelled {e}")
	finally:
		logger.info(f"main exit {server}")
		# server.tui.stop()
		# server.stop()
		# await server.ticker_task
		# server.loop.stop()
		# server.push_sock.close(1)
		# server.sub_sock.close(1)
		# ctx.destroy(linger=1000)


if __name__ == "__main__":
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	parser = ArgumentParser(description="server")
	parser.add_argument("--host", action="store", dest="host", default="127.0.0.1")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
	parser.add_argument("--port", action="store", dest="port", default=9696, type=int)
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-dp", "--debugpacket", action="store_true", dest="packetdebugmode", default=False,)
	parser.add_argument("--map", action="store", dest="mapname", default="data/map3.tmx")
	args = parser.parse_args()
	asyncio.run(start_server(args))
