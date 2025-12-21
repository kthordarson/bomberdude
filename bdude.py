#!/usr/bin/python
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

def run_server_process(args_dict):
	"""Function to run server in a separate process"""
	import asyncio
	import sys
	from loguru import logger
	from bombserver import async_start_server

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
		api_task = asyncio.create_task(server.apiserver.run(args.listen, 9691))

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
	server_process = multiprocessing.Process(
		target=run_server_process,
		args=(args_dict,),
		daemon=True
	)
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
	parser.add_argument("--port", action="store", dest="port", default=9696, type=int, help='port number')
	# server
	parser.add_argument("--host", action="store", dest="host", default="127.0.0.1")
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-dp", "--debugpacket", action="store_true", dest="debugpacket", default=False,)
	parser.add_argument("--map", action="store", dest="mapname", default="data/maptest5.tmx")
	parser.add_argument("--cprofile", action="store_true", dest="cprofile", default=False,)
	parser.add_argument("--cprofile_file", action="store", dest="cprofile_file", default='server.prof')
	return parser.parse_args()

async def start_game(args: argparse.Namespace):
	try:
		bomberdude_main = Bomberdude(args=args)
	except Exception as e:
		logger.error(f'Error: {e} {type(e)}')
		raise e
	# sender_task = asyncio.create_task(asyncio.to_thread(send_game_state, bomberdude_main))
	# receive_task = asyncio.create_task(asyncio.to_thread(receive_game_state, bomberdude_main))

	sender_task = asyncio.create_task(send_game_state(bomberdude_main))
	receive_task = asyncio.create_task(receive_game_state(bomberdude_main))

	connection_timeout = 5  # seconds
	connection_attempts = 0
	try:
		logger.info(f"Connecting {connection_attempts} {bomberdude_main}")
		connection_attempts += 1
		connected = await asyncio.wait_for(bomberdude_main.connect(), timeout=connection_timeout)
		if not connected:
			logger.error("Failed to establish connection")
			return
	except TimeoutError as e:
		logger.error(f"Connection timed out after {connection_timeout} seconds: {e}")
		return
	except Exception as e:
		logger.error(f"Connection error: {e} {type(e)}")
		raise e

	# Calculate frame time in seconds
	target_fps = UPDATE_TICK  # Using your constant from constants.py
	frame_time = 1.0 / target_fps

	# Main loop
	while bomberdude_main.running:
		# start_time = time.time()
		frame_start = time.time()
		try:
			await bomberdude_main.update()
		except Exception as e:
			logger.error(f"Error in update: {e} {type(e)}")
			await asyncio.sleep(1)
			continue
		try:
			bomberdude_main.on_draw()
		except Exception as e:
			logger.error(f"Error in on_draw: {e} {type(e)}")
			await asyncio.sleep(1)
			continue
		pygame.display.flip()
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				bomberdude_main.running = False
				bomberdude_main._connected = False
			elif event.type == pygame.KEYDOWN:
				await bomberdude_main.handle_on_key_press(event.key)
			elif event.type == pygame.KEYUP:
				await bomberdude_main.handle_on_key_release(event.key)
			elif event.type == pygame.MOUSEBUTTONDOWN:
				asyncio.create_task(bomberdude_main.handle_on_mouse_press(event.pos[0], event.pos[1], event.button))

		# Calculate sleep time to maintain constant frame rate
		elapsed = time.time() - frame_start
		sleep_time = max(0, frame_time - elapsed)
		if sleep_time > 0:
			if sleep_time > 0.05:
				logger.warning(f"Sleep time: {sleep_time}")
			await asyncio.sleep(sleep_time)

	# Clean up tasks
	sender_task.cancel()
	receive_task.cancel()
	await asyncio.gather(sender_task, receive_task, return_exceptions=True)
	# pygame.display.quit()
	# pygame.quit()

async def main(args):
	pygame.init()
	screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
	pygame.display.set_caption(SCREEN_TITLE)
	running = True
	mainmenu = MainMenu(screen=screen, args=args)
	try:
		while running:
			action = mainmenu.run()
			if action == "Start":
				await start_game(args)
			elif action == "Start Server":
				success = await start_server_background(args)
				if success:
					mainmenu.server_running = True
					logger.info("Server started and ready. You can now connect.")
			elif action == "Stop Server":
				success = await stop_server_background()
				if success:
					mainmenu.server_running = False
			elif action == 'Back':
				pass
			elif action in ['option1', 'option2', 'option3']:
				logger.info(f"Setup {action} not implemented")
			elif action == 'Find server':
				logger.info("Find server ....")
				await asyncio.sleep(1)
			elif action == 'Quit':
				# Stop server if running before quitting
				if mainmenu.server_running:
					await stop_server_background()
				logger.info("Quitting...")
				running = False
			elif not action:
				logger.info("no action! Quitting...")
				running = False
			else:
				logger.warning(f"Unknown action: {action}")
				await asyncio.sleep(1)
	except Exception as e:
		logger.error(f"Error in main: {e} {type(e)}")
		raise e
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
