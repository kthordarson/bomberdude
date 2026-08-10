#!/usr/bin/python
import argparse
import asyncio
import sys
from argparse import ArgumentParser

from loguru import logger

from server.api import ApiServer
from server.server import BombServer
from server.tui import ServerTUI


async def async_start_server(args: argparse.Namespace) -> None:
	server = BombServer(args)
	# apiserver = ApiServer("bombapi", server)
	tui = ServerTUI(server, args.debug)
	apiserver = ApiServer(name="bombapi", server=server, game_state=server.game_state)
	api_task = asyncio.create_task(apiserver.run(args.listen, args.api_port), name="api_task")
	tui_task = asyncio.create_task(tui.start(), name="tui_task")
	new_server_start_task = asyncio.create_task(server.new_start_server(), name="new_server_start_task")
	tasks = (api_task, tui_task, new_server_start_task)

	logger.debug(f'{server=} {tui=} {apiserver=}')
	try:
		done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
		for task in done:
			if task.cancelled():
				continue
			exc = task.exception()
			if exc is not None:
				logger.error(f"{task.get_name()} raised {exc} {type(exc)}; shutting down server")
			else:
				logger.warning(f"{task.get_name()} finished unexpectedly; shutting down server")
	except (asyncio.CancelledError, KeyboardInterrupt) as e:
		logger.info(f'{e} {type(e)}')
	finally:
		for task in tasks:
			if not task.done():
				task.cancel()
		await asyncio.gather(*tasks, return_exceptions=True)

def get_server_args() -> argparse.Namespace:
	parser = ArgumentParser(description="server")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
	parser.add_argument("--server_port", action="store", dest="server_port", default=9696, type=int)
	parser.add_argument("--api_port", action="store", dest="api_port", default=9691, type=int)
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-g", "--debug_gamestate", action="store_true", dest="debug_gamestate", default=False)
	parser.add_argument("--map", action="store", dest="mapname", default="data/maptest5.tmx")
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	args = get_server_args()
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

	asyncio.run(async_start_server(args))
