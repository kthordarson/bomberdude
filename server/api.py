from aiohttp import web
from loguru import logger
import asyncio

class ApiServer:
	def __init__(self, name, server, game_state):
		self.app = web.Application()
		self._name = name
		self.runner = None
		self.site = None
		self._ready = asyncio.Event()
		self.add_url_rule("/get_tile_map", view_func=server.get_tile_map, methods=["GET"])
		self.add_url_rule("/get_position", view_func=server.get_position, methods=["GET"])
		self.game_state = game_state

	def __repr__(self):
		return f'ApiServer({self._name})'

	def add_url_rule(self, path, view_func, methods=None):
		if methods is None:
			methods = ["GET"]
		for method in methods:
			self.app.router.add_route(method, path, view_func)

	async def wait_until_ready(self):
		"""Wait until the server is ready to handle requests"""
		await self._ready.wait()

	async def run(self, host, port):
		try:
			self.runner = web.AppRunner(self.app)
			await self.runner.setup()
			logger.debug(f'{self} runner host {host} port {port}')
			self.site = web.TCPSite(self.runner, host, port)
			await self.site.start()
			self._ready.set()
			logger.info(f"API server running at http://{host}:{port}")
			# Keep the server running
			while True:
				await asyncio.sleep(3600)  # Sleep for an hour
		except Exception as e:
			logger.error(f"API server error: {e}")
		finally:
			if self.runner:
				await self.runner.cleanup()

if __name__ == '__main__':
	pass
