#!/usr/bin/python
import cProfile
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
from server.api import ApiServer
from aiohttp import web
from server.server import BombServer
from server.tui import ServerTUI

async def start_server(args) -> None:
	server = BombServer(args)
	apiserver = ApiServer("bombapi", server)
	tui = ServerTUI(server, args.debug)

	api_task = asyncio.create_task(apiserver.run(args.listen, 9699))
	tui_task = asyncio.create_task(tui.start())

	logger.debug(f'{server=} {tui=} {apiserver=}')
	try:
		await asyncio.wait([api_task, server.ticker_task, tui_task], return_when=asyncio.FIRST_COMPLETED)
	except (asyncio.CancelledError, KeyboardInterrupt) as e:
		logger.warning(f'{e} {type(e)}')
		api_task.cancel()
		tui_task.cancel()
		server.ticker_task.cancel()
		await asyncio.gather(api_task, tui_task, server.ticker_task, return_exceptions=True)

if __name__ == "__main__":
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	parser = ArgumentParser(description="server")
	parser.add_argument("--host", action="store", dest="host", default="127.0.0.1")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
	parser.add_argument("--port", action="store", dest="port", default=9696, type=int)
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-dp", "--debugpacket", action="store_true", dest="debugpacket", default=False,)
	parser.add_argument("--map", action="store", dest="mapname", default="data/map5.tmx")
	args = parser.parse_args()
	try:
		asyncio.run(start_server(args))
		# cProfile.run('asyncio.run(start_server(args))')
	except KeyboardInterrupt as e:
		logger.warning(f"Error starting server: {e} {type(e)}")
		sys.exit(0)
	except Exception as e:
		logger.error(f"Error starting server: {e} {type(e)}")
		sys.exit(1)
