#!/usr/bin/python
import traceback
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
	tasks = [asyncio.create_task(server.apiserver.run(args.listen, args.api_port)), asyncio.create_task(tui.start()), asyncio.create_task(server.new_start_server())]
	# api_task = asyncio.create_task(server.apiserver.run(args.listen, args.api_port))
	# tui_task = asyncio.create_task(tui.start())
	# new_server_start_task = asyncio.create_task(server.new_start_server())
	try:
		logger.debug(f'{server=} {tui=} {server.apiserver=}')
		try:
			# await asyncio.wait([api_task, tui_task, new_server_start_task], return_when=asyncio.FIRST_COMPLETED)
			await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
		except (asyncio.CancelledError, KeyboardInterrupt, OSError, Exception) as e:
			logger.info(f'{e} {type(e)}')
			# api_task.cancel()
			# tui_task.cancel()
			# new_server_start_task.cancel()
			# await asyncio.gather(api_task, tui_task, return_exceptions=True)
		finally:
			for task in tasks:
				task.cancel()
			await asyncio.gather(*tasks, return_exceptions=True)
	except Exception as e:
		logger.error(f"Error starting server: {e} {type(e)}")


if __name__ == "__main__":
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
		try:
			asyncio.run(async_start_server(args))
		except Exception as e:
			logger.error(f"Fatal server error: {e} {type(e)}")
			traceback.print_exc()
