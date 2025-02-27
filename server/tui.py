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
		state = {'players_sprites': len(self.server.server_game_state.players_sprites),'connections': len(self.server.server_game_state.connections)}
		logger.debug(f"Server state: {state}")
		try:
			debug_dump = await self.server.server_game_state.debug_dump()
			logger.debug(f"debug_dump: {debug_dump}")
		except Exception as e:
			logger.error(f"Error getting server info: {e}")
		await asyncio.sleep(0.5)

	def dumpgameevents(self):
		logger.debug(f"gamestate: {self.server.server_game_state} events: {len(self.server.server_game_state.game_events)}")
		for e in self.server.server_game_state.game_events:
			logger.debug(f"event: {e}")

	def cleargameevents(self):
		logger.debug(f"clearevents gamestate: {self.server.server_game_state} events: {len(self.server.server_game_state.game_events)}")
		self.server.server_game_state.game_events = []

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
			self.server.remove_timedout_players()
		elif cmd[:1] == "l":
			self.dump_players()
		elif cmd[:1] == "e":
			self.dumpgameevents()
		elif cmd[:2] == "ec":
			self.cleargameevents()
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
