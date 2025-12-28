#!/usr/bin/python
import traceback
import requests
import json
import sys
import asyncio
import time
import argparse
from argparse import ArgumentParser
import pygame
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from panels import MainMenu
from game.bomberdude import Bomberdude
from network.client import send_game_state, receive_game_state
import multiprocessing

# Global variable to track server process
server_process = None


async def _connect_with_timeout(bomberdude_main: Bomberdude, connection_timeout: float) -> bool:
	try:
		return bool(await asyncio.wait_for(bomberdude_main.connect(), timeout=connection_timeout))
	except TimeoutError as e:
		logger.error(f"Connection timed out after {connection_timeout} seconds: {e}")
		return False
	except Exception as e:
		logger.error(f"Connection error: {e} {type(e)}")
		raise


async def _process_pygame_events(bomberdude_main: Bomberdude) -> None:
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			bomberdude_main.running = False
			bomberdude_main._connected = False
		elif event.type == pygame.VIDEORESIZE:
			# While dragging the window edge, VIDEORESIZE can spam events; defer
			# the expensive set_mode() until the user releases the mouse.
			try:
				bomberdude_main.queue_resize(event.w, event.h)
			except Exception as e:
				logger.error(f"Error in queue_resize: {e} {type(e)}")
		elif event.type == pygame.KEYDOWN:
			await bomberdude_main.handle_on_key_press(event.key)
		elif event.type == pygame.KEYUP:
			await bomberdude_main.handle_on_key_release(event.key)
		elif event.type == pygame.MOUSEBUTTONDOWN:
			x, y = event.pos
			try:
				x, y = bomberdude_main.window_to_virtual(x, y)
			except Exception as e:
				logger.error(f"Error in window_to_virtual: {e} {type(e)}")
			asyncio.create_task(bomberdude_main.handle_on_mouse_press(x, y, event.button))
		elif event.type == pygame.MOUSEBUTTONUP:
			# Apply any pending resize after the user finishes dragging.
			try:
				bomberdude_main.apply_pending_resize()
			except Exception as e:
				logger.error(f"Error in apply_pending_resize: {e} {type(e)}")


async def _run_frame(bomberdude_main: Bomberdude) -> bool:
	try:
		await bomberdude_main.update()
	except Exception as e:
		logger.error(f"Error in update: {e} {type(e)}")
		traceback.print_exc()
		await asyncio.sleep(1)
		return False

	try:
		await bomberdude_main.on_draw()
	except Exception as e:
		logger.error(f"Error in on_draw: {e} {type(e)}")
		traceback.print_exc()
		await asyncio.sleep(1)
		return False

	# If the user finished resizing but we didn't see a mouse-up event, apply
	# the pending resize after a short debounce.
	try:
		bomberdude_main.maybe_apply_pending_resize()
	except Exception as e:
		logger.error(f"Error in maybe_apply_pending_resize: {e} {type(e)}")

	pygame.display.flip()
	await _process_pygame_events(bomberdude_main)
	return True


async def _run_game_loop(bomberdude_main: Bomberdude, frame_time: float) -> None:
	while bomberdude_main.running:
		frame_start = time.time()
		await _run_frame(bomberdude_main)

		elapsed = time.time() - frame_start
		sleep_time = max(0, frame_time - elapsed)
		if sleep_time > 0:
			if sleep_time > 0.05:
				logger.warning(f"Sleep time: {sleep_time}")
			await asyncio.sleep(sleep_time)


async def _handle_main_menu_action(action: str, mainmenu: MainMenu, args: argparse.Namespace) -> bool:
	if action == "Start":
		started = await start_game(args)
		return True

	elif action == "Start Server":
		success = await start_server_background(args)
		if success:
			mainmenu.server_running = True
			logger.info("Server started and ready. You can now connect.")
		# The game recreates the display surface; refresh the menu to use the new surface.
		mainmenu.screen = pygame.display.get_surface()
		mainmenu.setup_panel.screen = mainmenu.screen
		mainmenu.discovery_panel.screen = mainmenu.screen
		return True

	elif action == "Stop Server":
		success = await stop_server_background()
		if success:
			mainmenu.server_running = False
		return True

	elif action == "Back":
		return True

	elif action in ["option1", "option2", "option3"]:
		logger.info(f"Setup {action} not implemented")
		return True

	elif action == "Find server":
		logger.info("Finding servers on LAN...")
		try:
			selected = await mainmenu.discovery_panel.run()
			if selected:
				# Discovery panel should set args.server, but keep this as a safe fallback.
				args = set_args(args, selected)
				await start_game(args)
		except Exception as e:
			logger.error(f"Error in discovery panel: {e} {type(e)}")
			return False
		return True

	elif action == "Quit":
		if mainmenu.server_running:
			await stop_server_background()
		logger.info("Quitting...")
		return False
	elif action in ('noinput', 'nomouseaction'):
		return True
	else:
		logger.warning(f"Unknown action: {action}")
		await asyncio.sleep(1)
	return True

def set_args(args, selected):
	args.server = selected.get('host') or selected.get('listen') or args.server
	sp = selected.get('server_port')
	args.server_port = sp
	ap = selected.get('api_port')
	args.api_port = ap
	logger.info(f"Selected server: {selected}")
	return args

def run_server_process(args_dict):
	"""Function to run server in a separate process"""

	# Convert args_dict back to Namespace
	args = argparse.Namespace(**args_dict)

	# Set Windows event loop policy if needed
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

	# Create a headless version of the server startup
	async def run_headless_server():
		from server.server import BombServer

		server = BombServer(args)
		server_task = asyncio.create_task(server.new_start_server())
		api_task = asyncio.create_task(server.apiserver.run(args.listen, args.api_port))

		try:
			await asyncio.gather(server_task, api_task)
		except (asyncio.CancelledError, KeyboardInterrupt):
			server_task.cancel()
			api_task.cancel()
			await asyncio.gather(server_task, api_task, return_exceptions=True)

	# Run server without TUI
	try:
		asyncio.run(run_headless_server())
	except KeyboardInterrupt:
		logger.info("Server process terminated")
	except Exception as e:
		logger.error(f"Server process error: {e}")

async def start_server_background(args: argparse.Namespace):
	"""Start server in a separate process"""
	global server_process

	if server_process is not None and server_process.is_alive():
		logger.warning("Server is already running")
		return True

	# Convert Namespace to dict for pickling
	args_dict = vars(args)

	# Start server in a separate process
	server_process = multiprocessing.Process(target=run_server_process, args=(args_dict,), daemon=True)
	server_process.start()

	# Wait for server to initialize
	await asyncio.sleep(1.5)

	if server_process.is_alive():
		logger.info(f"Server started in background (PID: {server_process.pid})")
		# Set client to connect to localhost
		args.server = "127.0.0.1"
		return True
	else:
		logger.error("Failed to start server process")
		return False

async def stop_server_background():
	"""Stop the server running in background"""
	global server_process

	if server_process is None or not server_process.is_alive():
		logger.warning("No server is running")
		return True

	# Terminate the process
	server_process.terminate()
	server_process.join(timeout=2.0)

	if server_process.is_alive():
		logger.warning("Server did not terminate gracefully, forcing...")
		server_process.kill()
		server_process.join(timeout=1.0)

	server_process = None
	logger.info("Server stopped")
	return True

def get_args():
	parser = ArgumentParser(description="bdude")
	parser.add_argument("--name", action="store", dest="name", default="bdude")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1", help='ip address to listen (server mode)')
	parser.add_argument("--server", action="store", dest="server", default="127.0.0.1", help='ip address of the server (client mode)')
	parser.add_argument("--server_port", action="store", dest="server_port", default=9696, type=int, help='server_port port number')
	parser.add_argument("--api_port", action="store", dest="api_port", default=9691, type=int, help='API port number')
	# server
	parser.add_argument("--host", action="store", dest="host", default="127.0.0.1")
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-g", "--debug_gamestate", action="store_true", dest="debug_gamestate", default=False)
	parser.add_argument("--map", action="store", dest="mapname", default="data/maptest5.tmx")
	parser.add_argument("--cprofile", action="store_true", dest="cprofile", default=False,)
	parser.add_argument("--cprofile_file", action="store", dest="cprofile_file", default='bdude.prof')
	return parser.parse_args()

async def start_game(args: argparse.Namespace) -> bool:
	resptext = ''
	try:
		resptext = requests.get(f"http://{args.server}:{args.api_port}/get_client_id", timeout=10).text
		resp = json.loads(resptext)
		client_id = resp.get("client_id")
	except Exception as e:
		logger.error(f"Error: {e} {type(e)} resptext: {resptext}")
		raise e
	try:
		resptext = requests.get(f"http://{args.server}:{args.api_port}/get_map_name", timeout=10).text
		resp = json.loads(resptext)
		mapname = resp.get("mapname")
	except Exception as e:
		logger.error(f"Error: {e} {type(e)} resptext: {resptext}")
		raise e
	try:
		bomberdude_main = Bomberdude(args=args, client_id=client_id, mapname=mapname)
	except Exception as e:
		logger.error(f"Error creating Bomberdude instance: {e} {type(e)}")
		raise e

	# Start networking tasks early so connect() can complete its readiness handshake.
	# The tasks will wait until the socket is connected before using it.
	sender_task = asyncio.create_task(send_game_state(bomberdude_main))
	receive_task = asyncio.create_task(receive_game_state(bomberdude_main))

	connection_timeout = 5  # seconds
	logger.info(f"Connecting {bomberdude_main}")
	try:
		connected = await _connect_with_timeout(bomberdude_main, connection_timeout)
		if not connected:
			logger.error("Failed to establish connection")
			return False

		# Calculate frame time in seconds
		frame_time = 1.0 / UPDATE_TICK
		await _run_game_loop(bomberdude_main, frame_time)
	finally:
		# Clean up tasks even on early return/exception
		sender_task.cancel()
		receive_task.cancel()
		await asyncio.gather(sender_task, receive_task, return_exceptions=True)
		# Ensure socket is closed so server sees a clean disconnect
		try:
			await bomberdude_main.disconnect(return_to_menu=True)
		except Exception as e:
			logger.error(f"Error during disconnect: {e} {type(e)}")
	return True
	# pygame.display.quit()
	# pygame.quit()

async def main(args):
	pygame.init()
	screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags=pygame.RESIZABLE)
	pygame.display.set_caption(SCREEN_TITLE)
	mainmenu = MainMenu(screen=screen, args=args)
	try:
		running = True
		while running:
			action = mainmenu.run()
			if not action:
				logger.info("no action! Quitting...")
				break
			running = await _handle_main_menu_action(action, mainmenu, args)
	except Exception as e:
		logger.error(f"Error in main: {e} {type(e)}")
		raise
	finally:
		# Ensure server is stopped on exit
		if mainmenu.server_running:
			await stop_server_background()
		pygame.quit()

if __name__ == "__main__":
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	args = get_args()
	if args.cprofile:
		import cProfile
		import pstats

		profiler = cProfile.Profile()
		profiler.enable()

		asyncio.run(main(args))

		profiler.disable()
		stats = pstats.Stats(profiler).sort_stats('cumtime')
		stats.print_stats(30)  # Print top 30 time-consuming functions

		# Optionally save results to a file
		stats.dump_stats(args.cprofile_file)
	else:
		asyncio.run(main(args))
