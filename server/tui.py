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
		# self.loop = asyncio.new_event_loop()
		# self.loop = asyncio.get_running_loop()

	def __repr__(self):
		return f"ServerTUI (stopped:{self.stopped()})"

	async def stop(self):
		self._stop.set()

		# Make sure we don't try to await None
		if self.server:
			await self.server.stop()
		return True  # Return a value so it's awaitable

	def stopped(self):
		return self._stop.is_set()

	async def get_serverinfo(self):
		"""Get current server state information"""
		state_json = self.server.game_state.to_json()
		playerlist = cast(list[dict[str, Any]], state_json.get('playerlist') or [])
		print(f'server: {self.server}')
		print(f'self.server.game_state.client_id: {self.server.game_state.client_id}')
		print(f"playerlist: {len(playerlist)} players_sprites: {len(self.server.game_state.players_sprites)} upgrade_blocks: {len(self.server.game_state.upgrade_blocks)}")
		print(f'explosions: {len(self.server.game_state.processed_explosions)} hits: {len(self.server.game_state.processed_hits)} bullets: {len(self.server.game_state.processed_bullets)} upgrades: {len(self.server.game_state.processed_upgrades)}')
		print(f"event_queue: {self.server.game_state.event_queue.qsize()}  client_queue: {self.server.game_state.client_queue.qsize()} game_state connections: {len(self.server.game_state.connections)} ")
		print(f"state_json modified_tiles: {len(state_json.get('modified_tiles'))}")
		print(f"server gamestate: {self.server.game_state} ")
		print(f"statejsonkeys: {state_json.keys()} ")

		for player in self.server.game_state.playerlist.values():
			print(f"player ({type(player)}): {player.client_name}: {player.client_id} {player.position} {player.health} bombs_left: {player.bombs_left} bomb_power: {player.bomb_power} killed: {player.killed}")

	def printhelp(self):
		print("""
		cmds:
		s = show server info
		q = quit
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
			pass
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
