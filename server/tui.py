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

	def dump_players(self):
		for p in self.server.server_game_state.players:
			# print(f'p={p} pos = {self.server.server_game_state.players[p]["position"]} score: {self.server.server_game_state.players[p]["score"]} msgdt:{self.server.server_game_state.players[p]["msg_dt"]}')
			logger.debug(f"p={p} {self.server.server_game_state.players[p]}")

	async def get_serverinfo(self):
		"""Get current server state information"""
		try:
			state = {
				'players': len(self.server.server_game_state.players),
				'connections': len(self.server.server_game_state.connections)
			}
			dump = await self.server.server_game_state.debug_dump()
			logger.debug(f"Server info: {state}")
			logger.debug(f"debugdump: {dump}")
			return state
		except Exception as e:
			logger.error(f"Error getting server info: {e}")
			return {'error': str(e)}

	async def oldget_serverinfo(self):
		logger.debug(f"players={len(self.server.server_game_state.players)} threads:{active_count()} conns: {len(self.server.server_game_state.connections)}")
		logger.debug(f"{self.server.server_game_state}")
		dump = await self.server.server_game_state.debug_dump()
		logger.debug(f"debugdump: {dump}")
		# print(f'gamestate: {self.server.server_game_state}')
		# print(f'gamestateplayers: {self.server.server_game_state.players}')
		for p in self.server.server_game_state.players:
			logger.debug(f"p={p} pos = {self.server.server_game_state.players[p]['position']} score: {self.server.server_game_state.players[p]['score']} msgdt:{self.server.server_game_state.players[p]['msg_dt']:.2f} timeout:{self.server.server_game_state.players[p]['timeout']}")

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

	async def oldrun(self) -> None:
		while not self.stopped():
			try:
				cmd = input(":> ")
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
				elif cmd[:1] == "d":
					...
				elif cmd[:2] == "ds":
					...
				elif cmd[:3] == "dst":
					...
				elif cmd[:2] == "pd":
					...
				elif cmd[:1] == "q":
					logger.warning(f"{self} {self.server} tuiquit")
					# self.stop()
					asyncio.run_coroutine_threadsafe(self.server.stop(), self.server.loop)
					break
					# asyncio.run(self.server.stop())
					# asyncio.run_coroutine_threadsafe(self.server.stop(), self.server.loop)
					# self.server.sub_sock.close()
					# self.server.push_sock.close()
				else:
					pass  # logger.info(f'[tui] cmds: s=serverinfo, d=debug, p=playerlist, q=quit')
			except (EOFError, KeyboardInterrupt) as e:
				logger.warning(f"{type(e)} {e}")
				self.stop()
				asyncio.run_coroutine_threadsafe(self.server.stop(), self.server.loop)
				# self.server.stop()
				break
