import asyncio
from loguru import logger
from threading import Thread, Timer, active_count, Event

class ServerTUI():
	def __init__(self, server, debug=False, gq=None):
		Thread.__init__(self, daemon=True, name="tui")
		self.gq = gq
		self.server = server
		self.debug = debug
		self._stop = Event()
		self.loop = asyncio.get_event_loop()

	def __repr__(self):
		return f"ServerTUI (s:{self.stopped()})"

	def stop(self):
		self._stop.set()
		# self.server.stop()
		logger.warning(f"{self} stop {self.stopped()} server: {self.server.stopped()}")

	def stopped(self):
		return self._stop.is_set()

	async def get_serverinfo(self):
		"""Get current server state information"""
		state = self.server.server_game_state.to_json()
		logger.debug(f"players: {len(state.get('playerlist'))} event_queue: {self.server.server_game_state.event_queue.qsize()} client_queue: {self.server.server_game_state.client_queue.qsize()}")
		for player in state.get('playerlist'):
			logger.debug(f'player: {player.get('client_id')} {player.get('position')}')
		try:
			await self.server.server_game_state.debug_dump()
		except Exception as e:
			logger.error(f"Error getting server info: {e}")

	def dumpgameevents(self):
		logger.debug(f"gamestate: {self.server.server_game_state} ")

	def printhelp(self):
		help = """
		cmds:
		s = show server info
		l = dump player list
		"""
		print(help)

	async def input_handler(self):
		"""Handle command input asynchronously"""
		while not self.stopped():
			try:
				cmd = await self.loop.run_in_executor(None, input, ":> ")
				await self.handle_command(cmd)
			except (EOFError, KeyboardInterrupt) as e:
				logger.warning(f"{type(e)} {e}")
				self.stop()
				await self.server.stop()
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
			logger.warning(f"{self} {self.server} tuiquit")
			await self.server.stop()
			self.stop()

	async def start(self):
		"""Start the TUI"""
		try:
			await self.input_handler()
		except Exception as e:
			logger.error(f"TUI error: {e}")
			self.stop()
			await self.server.stop()
