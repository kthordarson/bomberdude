import asyncio
from loguru import logger
from threading import Event
from typing import Any, cast

class ServerTUI():
	def __init__(self, server, debug=False, gq=None):
		# Thread.__init__(self, daemon=True, name="tui")
		self.gq = gq
		self.server = server
		self.debug = debug
		self._stop = Event()
		self.loop = asyncio.get_event_loop()

	def __repr__(self):
		return f"ServerTUI (s:{self.stopped()})"

	async def stop(self):
		self._stop.set()

		# Make sure we don't try to await None
		if hasattr(self, 'server') and self.server is not None:
			await self.server.stop()
		return True  # Return a value so it's awaitable

	def stopped(self):
		return self._stop.is_set()

	async def get_serverinfo(self):
		"""Get current server state information"""
		state: dict[str, Any] = {'playerlist': []}  # self.server.server_game_state.to_json()
		playerlist = cast(list[dict[str, Any]], state.get('playerlist') or [])
		logger.debug(
			f"players: {len(playerlist)} "
			f"event_queue: {self.server.server_game_state.event_queue.qsize()} "
			f"client_queue: {self.server.server_game_state.client_queue.qsize()}"
		)
		logger.debug(f"modified_tiles: {state.get('modified_tiles')}")

		for player in playerlist:
			# Fix nested quotes in the f-string
			logger.debug(f"player: {player.get('client_id')} {player.get('position')}")

		logger.info(f"status: {state}")

		# logger.debug(f"players: {len(state.get('playerlist'))} event_queue: {self.server.server_game_state.event_queue.qsize()} client_queue: {self.server.server_game_state.client_queue.qsize()}")
		# logger.debug(f'modified_tiles: {state.get("modified_tiles")}')
		# for player in state.get('playerlist'):
		# 	logger.debug(f'player: {player.get('client_id')} {player.get('position')}')
		# logger.info(f'status: {state}')

	def dumpgameevents(self):
		logger.debug(f"gamestate: {self.server.server_game_state} ")

	def printhelp(self):
		print("""
		cmds:
		s = show server info
		l = dump player list
		""")

	async def input_handler(self):
		"""Handle command input asynchronously"""
		while not self.stopped():
			try:
				cmd = await self.loop.run_in_executor(None, input, ":> ")
				await self.handle_command(cmd)
			except (EOFError, KeyboardInterrupt) as e:
				await self.stop()
				await self.server.stop()
				logger.error(f"{e} {type(e)} Stopping server and TUI")
				break

	async def handle_command(self, cmd):
		"""Handle individual commands"""
		if cmd[:1] == "?" or cmd[:1] == "h":
			self.printhelp()
		elif cmd[:1] == "s":
			await self.get_serverinfo()
		elif cmd[:1] == "r":
			...
		elif cmd[:1] == "l":
			pass  # self.dump_players()
		elif cmd[:1] == "e":
			self.dumpgameevents()
		elif cmd[:2] == "ec":
			pass  # self.cleargameevents()
		elif cmd[:1] == "q":
			await self.server.stop()
			await self.stop()

	async def start(self):
		"""Start the TUI"""
		try:
			await self.input_handler()
		except TypeError as e:
			# Handle the case where stop() is not awaitable
			logger.error(f"{e} Could not properly stop TUI")
			self._stop.set()
		except Exception as e:
			logger.error(f"TUI error: {e}")
			await self.stop()
			await asyncio.sleep(1)
			await self.server.stop()
