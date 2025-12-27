#!/usr/bin/python
import asyncio
import sys
import argparse
from argparse import ArgumentParser
from loguru import logger
from server.server import BombServer
from server.tui import ServerTUI

async def async_start_server(args: argparse.Namespace) -> None:
	server = BombServer(args)
	# apiserver = ApiServer("bombapi", server)
	tui = ServerTUI(server, args.debug)

	api_task = asyncio.create_task(server.apiserver.run(args.listen, args.api_port))
	tui_task = asyncio.create_task(tui.start())
	new_server_start_task = asyncio.create_task(server.new_start_server())

	logger.debug(f'{server=} {tui=} {server.apiserver=}')
	try:
		await asyncio.wait([api_task, tui_task, new_server_start_task], return_when=asyncio.FIRST_COMPLETED)
	except (asyncio.CancelledError, KeyboardInterrupt) as e:
		logger.info(f'{e} {type(e)}')
		api_task.cancel()
		tui_task.cancel()
		new_server_start_task.cancel()
		await asyncio.gather(api_task, tui_task, return_exceptions=True)

if __name__ == "__main__":
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	parser = ArgumentParser(description="server")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1")
	parser.add_argument("--server_port", action="store", dest="server_port", default=9696, type=int)
	parser.add_argument("--api_port", action="store", dest="api_port", default=9691, type=int)
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-g", "--debug_gamestate", action="store_true", dest="debug_gamestate", default=False)
	parser.add_argument("--map", action="store", dest="mapname", default="data/maptest5.tmx")
	parser.add_argument("--cprofile", action="store_true", dest="cprofile", default=False,)
	parser.add_argument("--cprofile_file", action="store", dest="cprofile_file", default='server.prof')
	args = parser.parse_args()

	if args.cprofile:
		import cProfile
		import pstats

		profiler = cProfile.Profile()
		profiler.enable()

		asyncio.run(async_start_server(args))

		profiler.disable()
		stats = pstats.Stats(profiler).sort_stats('cumtime')
		stats.print_stats(30)  # Print top 30 time-consuming functions

		# Optionally save results to a file
		stats.dump_stats(args.cprofile_file)
	else:
		asyncio.run(async_start_server(args))
