#!/usr/bin/python
import os
import argparse
import asyncio
import hashlib
import json
import multiprocessing
import time
import traceback
from argparse import ArgumentParser

import pygame
import requests
from loguru import logger

import crypto_utils
from config import Config, load_config, save_config
from constants import UPDATE_TICK
from game.bomberdude import Bomberdude
from network.client import receive_game_state, send_game_state
from panels import AuthDialog, GamePreviewScreen, MainMenu
from server.api import ApiServer
from server.server import BombServer
from utils import async_load_image_cached, generate_password

# Global variable to track server process
server_process = None
MAPS_DIR = os.path.realpath("data")


async def _connect_with_timeout(bomberdude_main: Bomberdude, connection_timeout: float) -> bool:
	try:
		return (await asyncio.wait_for(bomberdude_main.connect(), timeout=connection_timeout))
	except json.decoder.JSONDecodeError as e:
		logger.error(f"JSON decode error during connection: {e} {type(e)}")
		return False
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


async def _run_game_loop(bomberdude_main: Bomberdude, frame_time: float, network_tasks: tuple[asyncio.Task, ...] = ()) -> None:
	while bomberdude_main.running:
		for task in network_tasks:
			if not task.done():
				continue
			exc = task.exception() if not task.cancelled() else None
			if exc is not None:
				logger.error(f"{task.get_name()} died: {exc} {type(exc)}; ending session")
			else:
				logger.warning(f"{task.get_name()} ended unexpectedly; ending session")
			bomberdude_main.running = False
		if not bomberdude_main.running:
			break

		frame_start = time.time()
		await _run_frame(bomberdude_main)

		elapsed = time.time() - frame_start
		sleep_time = max(0.0, frame_time - elapsed)
		if sleep_time > 0:
			if sleep_time > 0.05:
				logger.warning(f"Sleep time: {sleep_time}")
			await asyncio.sleep(sleep_time)


async def _handle_main_menu_action(bomberdude_main: Bomberdude, action: str, args: argparse.Namespace) -> bool:
	if action == "Start":
		if not await connect_and_preview(bomberdude_main, args):
			logger.info("Connection lobby quit before joining")
			return False
		started = await start_game(bomberdude_main, args)
		if not started:
			logger.warning("start_game exited without a successful session")
			return False
		return True

	elif action == "Start Server":
		success = await start_server_background(args)
		if success:
			bomberdude_main.mainmenu.server_running = True
			logger.info("Server started and ready. You can now connect.")
		# The game recreates the display surface; refresh the menu to use the new surface.
		# bomberdude_main.mainmenu.screen = pygame.display.get_surface()
		# bomberdude_main.mainmenu.setup_panel.screen = bomberdude_main.mainmenu.screen
		# bomberdude_main.mainmenu.discovery_panel.screen = bomberdude_main.mainmenu.screen
		return True

	elif action == "Stop Server":
		success = await stop_server_background()
		if success:
			bomberdude_main.mainmenu.server_running = False
		return True

	elif action == "Back":
		return True

	elif action in ["option1", "option2", "option3"]:
		logger.info(f"Setup {action} not implemented")
		return True

	elif action == "Find server":
		logger.info("Finding servers on LAN...")
		try:
			selected = await bomberdude_main.mainmenu.discovery_panel.run()
			if selected:
				# Discovery panel should set args.server, but keep this as a safe fallback.
				args = set_args(args, selected)
				if not await connect_and_preview(bomberdude_main, args):
					logger.info("Connection lobby quit before joining")
					return False
				await start_game(bomberdude_main, args)
		except Exception as e:
			logger.error(f"Error in discovery panel: {e} {type(e)}")
			return False
		logger.info("No servers on LAN...")
		return True

	elif action == "Quit":
		if bomberdude_main.mainmenu.server_running:
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

	# Create a headless version of the server startup
	async def run_headless_server():

		server = BombServer(args)
		server_task = asyncio.create_task(server.new_start_server(), name="server_task")
		apiserver = ApiServer(name="bombapi", server=server, game_state=server.game_state)
		api_task = asyncio.create_task(apiserver.run(args.listen, args.api_port), name="api_task")
		tasks = (server_task, api_task)

		try:
			await asyncio.gather(*tasks)
		except (asyncio.CancelledError, KeyboardInterrupt) as e:
			logger.info(f'{e} {type(e)}')
		finally:
			for task in tasks:
				if not task.done():
					task.cancel()
			await asyncio.gather(*tasks, return_exceptions=True)

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
		# args.server = "127.0.0.1"
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

async def _post_json(args: argparse.Namespace, path: str, payload: dict) -> dict:
	try:
		resptext = (await asyncio.to_thread(requests.post, f"http://{args.server}:{args.api_port}{path}", json=payload, timeout=10)).text
		return json.loads(resptext)
	except requests.exceptions.ConnectionError as e:
		logger.warning(f"Error: {e} {type(e)} path: {path}")
		return {"ok": False, "reason": "connection_error"}
	except Exception as e:
		logger.error(f"Error: {e} {type(e)} path: {path}")
		return {"ok": False, "reason": "connection_error"}


async def _fetch_lobby_info(args: argparse.Namespace) -> dict:
	try:
		resptext = (await asyncio.to_thread(requests.get, f"http://{args.server}:{args.api_port}/lobby_info", timeout=10)).text
		return json.loads(resptext)
	except Exception as e:
		logger.error(f"Error fetching lobby info: {e} {type(e)}")
		return {"players": [], "mapname": "", "map_width": 1, "map_height": 1}


async def _authenticate(args: argparse.Namespace, username: str, password: str) -> tuple[bool, str]:
	"""Log in; if the account doesn't exist yet, transparently register it."""
	resp = await _post_json(args, "/login", {"username": username, "password": password})
	if resp.get("ok"):
		return True, "ok"
	if resp.get("reason") == "not_found":
		resp = await _post_json(args, "/register", {"username": username, "password": password})
		return bool(resp.get("ok")), resp.get("reason", "register_failed")
	return False, resp.get("reason", "login_failed")


def resolve_credentials(config: Config, args: argparse.Namespace) -> tuple[str, str, bool]:
	"""Resolve login credentials: CLI args, then stored config, else a
	freshly generated default pair to show in the AuthDialog."""
	if args.username and args.password:
		return args.username, args.password, False
	if config.password_enc:
		try:
			key = crypto_utils.load_or_create_key(f"{args.config_path}.key")
			password = crypto_utils.decrypt_secret(config.password_enc, key)
			return config.player_name, password, False
		except (ValueError, KeyError) as e:
			logger.warning(f"Could not decrypt stored password: {e} {type(e)}; falling back to auth dialog")
	return config.player_name, generate_password(), True


async def _authenticate_loop(bomberdude_main: Bomberdude, args: argparse.Namespace) -> bool:
	"""Resolve/collect credentials and authenticate against the target
	server, retrying via the AuthDialog on failure. Returns False if the
	user quits instead of authenticating."""
	config = bomberdude_main.config
	username, password, need_dialog = resolve_credentials(config, args)
	error = ""
	while True:
		if need_dialog:
			dialog = AuthDialog(bomberdude_main.mainmenu.screen, username, password)
			dialog.set_error(error)
			action = dialog.run()
			if action == "Quit":
				return False
			username, password = dialog.username, dialog.password

		ok, reason = await _authenticate(args, username, password)
		if ok:
			config.player_name = username
			key = crypto_utils.load_or_create_key(f"{args.config_path}.key")
			config.password_enc = crypto_utils.encrypt_secret(password, key)
			save_config(config, args.config_path)
			return True

		logger.warning(f"Authentication failed for {username}: {reason}")
		error = f"Authentication failed: {reason}"
		need_dialog = True


async def connect_and_preview(bomberdude_main: Bomberdude, args: argparse.Namespace) -> bool:
	"""Authenticate against the target server, then show the pre-join lobby
	(player list + minimap, Join/Configure/Quit). Returns True if the user
	chose Join (caller should proceed to start_game), False if they quit."""
	if not await _authenticate_loop(bomberdude_main, args):
		return False

	lobby_info = await _fetch_lobby_info(args)
	while True:
		preview = GamePreviewScreen(bomberdude_main.mainmenu.screen, lobby_info, refresh_callback=lambda: _fetch_lobby_info(args))
		action = await preview.run()
		if action == "Join":
			return True
		elif action == "Configure":
			saved = bomberdude_main.mainmenu.configure_panel.run(bomberdude_main._apply_config_changes)
			if saved:
				bomberdude_main._apply_config_changes()
			lobby_info = await _fetch_lobby_info(args)
		else:
			return False


def _sanitize_mapname(mapname: str | None) -> str | None:
	"""Confine a server-reported map name to MAPS_DIR, rejecting anything
	with directory components (absolute paths, `..`, subdirectories).

	`mapname` comes from an untrusted server (over /get_map_name) and is
	used as a filesystem path for both reading and writing (see
	_ensure_local_map below) — without this, a malicious server could send
	e.g. "../../.ssh/authorized_keys" as the mapname and have the client
	overwrite arbitrary local files with attacker-controlled bytes.
	"""
	if not mapname:
		return None
	safe_name = os.path.basename(mapname)
	if not safe_name or safe_name in (".", ".."):
		return None
	target = os.path.realpath(os.path.join(MAPS_DIR, safe_name))
	if target != MAPS_DIR and not target.startswith(MAPS_DIR + os.sep):
		return None
	return target


async def _ensure_local_map(args: argparse.Namespace, mapname: str, server_hash: str | None) -> bool:
	"""Make sure `mapname` exists locally and matches the server's copy
	(per the map_hash from /get_map_name), downloading a fresh one via
	/get_map_file if it's missing or stale. Returns False only if no usable
	local file is available afterward."""
	local_hash = None
	if os.path.exists(mapname):
		try:
			with open(mapname, "rb") as f:
				local_hash = hashlib.sha256(f.read()).hexdigest()
		except OSError as e:
			logger.error(f"Error hashing local map '{mapname}': {e} {type(e)}")

	if local_hash is not None and server_hash and local_hash == server_hash:
		return True

	if local_hash is None:
		logger.warning(f"No local copy of map '{mapname}'; downloading from server.")
	else:
		logger.warning(f"Local map '{mapname}' does not match the server's copy (hash mismatch); downloading fresh copy.")

	try:
		resp = await asyncio.to_thread(requests.get, f"http://{args.server}:{args.api_port}/get_map_file", timeout=15)
		resp.raise_for_status()
		data = resp.content
	except Exception as e:
		logger.error(f"Error downloading map '{mapname}' from server: {e} {type(e)}")
		return local_hash is not None  # fall back to the stale local copy, if any

	try:
		parent = os.path.dirname(mapname)
		if parent:
			os.makedirs(parent, exist_ok=True)
		with open(mapname, "wb") as f:
			f.write(data)
		logger.info(f"Downloaded map '{mapname}' from server ({len(data)} bytes).")
		return True
	except OSError as e:
		logger.error(f"Error writing downloaded map '{mapname}': {e} {type(e)}")
		return local_hash is not None


async def start_game(bomberdude_main: Bomberdude, args: argparse.Namespace) -> bool:
	resptext = ''
	try:
		resptext = (await asyncio.to_thread(requests.get, f"http://{args.server}:{args.api_port}/get_client_id", timeout=10)).text
		resp = json.loads(resptext)
		client_id = resp.get("client_id")
	except requests.exceptions.ConnectionError as e:
		logger.warning(f"Error: {e} {type(e)} resptext: {resptext}")
		return False
	except Exception as e:
		logger.error(f"Error: {e} {type(e)} resptext: {resptext}")
		raise e
	try:
		resptext = (await asyncio.to_thread(requests.get, f"http://{args.server}:{args.api_port}/get_map_name", timeout=10)).text
		resp = json.loads(resptext)
		raw_mapname = resp.get("mapname")
		server_map_hash = resp.get("map_hash")
	except Exception as e:
		logger.error(f"Error: {e} {type(e)} resptext: {resptext}")
		raise e

	mapname = _sanitize_mapname(raw_mapname)
	if mapname is None:
		logger.error(f"Server returned an unusable map name '{raw_mapname}'; aborting connection.")
		return False

	if not await _ensure_local_map(args, mapname, server_map_hash):
		logger.error(f"No usable local copy of map '{mapname}' and download from server failed; aborting connection.")
		return False
	# try:
	# 	bomberdude_main = Bomberdude(args=args, client_id=client_id, mapname=mapname)
	# except Exception as e:
	# 	logger.error(f"Error creating Bomberdude instance: {e} {type(e)}")
	# 	raise e

	bomberdude_main.client_id = client_id
	bomberdude_main.client_id = client_id
	bomberdude_main.game_state.client_id = client_id
	bomberdude_main.mapname = mapname
	bomberdude_main.game_state._load_map(mapname)

	# Warm the flame image cache off the event loop thread now, so the first
	# bomb explosion doesn't stall the loop on synchronous pygame.image.load
	# (ExplosionManager.create_flames/Flame.flame_init are sync call sites and
	# can't await the async loader themselves).
	await async_load_image_cached('data/flameball.png')

	# Start networking tasks early so connect() can complete its readiness handshake.
	# The tasks will wait until the socket is connected before using it.
	sender_task = asyncio.create_task(send_game_state(bomberdude_main), name="sender_task")
	receive_task = asyncio.create_task(receive_game_state(bomberdude_main), name="receive_task")

	connection_timeout = 5  # seconds
	logger.info(f"Connecting {bomberdude_main}")
	try:
		connected = await _connect_with_timeout(bomberdude_main, connection_timeout)
		if not connected:
			logger.error("Failed to establish connection")
			return False

		# Calculate frame time in seconds
		frame_time = 1.0 / UPDATE_TICK
		await _run_game_loop(bomberdude_main, frame_time, network_tasks=(sender_task, receive_task))
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
	config_path = args.config
	config = load_config(config_path)
	args.config = config
	# Bomberdude.__init__ reads the loaded Config from args.config (above); keep
	# the original file path separately so credential resolution can derive
	# the client-side AES key path from it.
	args.config_path = config_path
	pygame.init()
	screen = pygame.display.set_mode((config.screen_width, config.screen_height), flags=pygame.RESIZABLE)
	pygame.display.set_caption('init')
	bomberdude_main = Bomberdude(args=args, mainmenu=MainMenu(screen=screen, args=args, config=config), client_id="noclientid", mapname="mapnotset", config=config)
	if args.autoconnect:
		running = await _handle_main_menu_action(bomberdude_main, "Start", args)
	else:
		try:
			running = True
			while running:
				action = bomberdude_main.mainmenu.run()
				if not action:
					logger.info("no action! Quitting...")
					break
				running = await _handle_main_menu_action(bomberdude_main, action, args)
				if not running:
					logger.info("Exiting main loop...")
					break
		except Exception as e:
			logger.error(f"Error in main: {e} {type(e)}")
			raise
		finally:
			# Ensure server is stopped on exit
			if bomberdude_main.mainmenu.server_running:
				await stop_server_background()
			pygame.quit()

def get_args():
	parser = ArgumentParser(description="bdude")
	parser.add_argument("--name", action="store", dest="name", default="bdude")
	parser.add_argument("--listen", action="store", dest="listen", default="127.0.0.1", help='ip address to listen (server mode)')
	parser.add_argument("--server", action="store", dest="server", default="127.0.0.1", help='ip address of the server (client mode)')
	parser.add_argument("--autoconnect", action="store_true", dest="autoconnect", default=False, help='autoconnect')
	parser.add_argument("--server_port", action="store", dest="server_port", default=9696, type=int, help='server_port port number')
	parser.add_argument("--api_port", action="store", dest="api_port", default=9691, type=int, help='API port number')
	parser.add_argument("--config", action="store", dest="config", default="bdude_config.json", help='Path to config file')
	parser.add_argument("--username", action="store", dest="username", default=None, help='Account username; skips the auth dialog if --password is also given')
	parser.add_argument("--password", action="store", dest="password", default=None, help='Account password in plain text; encrypted before any local storage')
	# server
	parser.add_argument("--host", action="store", dest="host", default="127.0.0.1")
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("-g", "--debug_gamestate", action="store_true", dest="debug_gamestate", default=False)
	parser.add_argument("--map", action="store", dest="mapname", default="data/maptest5.tmx")
	return parser.parse_args()

if __name__ == "__main__":
	args = get_args()
	asyncio.run(main(args))
