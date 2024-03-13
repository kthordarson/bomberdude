import sys
import asyncio
from threading import Thread
import time
from argparse import ArgumentParser
from queue import Empty
from loguru import logger
from constants import *

class Receiver():
	def __init__(self,sub_sock, gsqueue,evqueue):
		self.sub_sock = sub_sock
		self.gsqueue = gsqueue
		self.evqueue = evqueue
		self.debugtrace = False
		self.pe_counter = 0
	def __repr__(self):
		return f'Receiver(pec:{self.pe_counter} {self.sub_sock=}, {self.gsqueue=}, {self.evqueue=})'

	async def check_sub_sock(self) -> int:
		self.pe_counter = 0
		# logger.info(f'{self} running')
		# try:
		# 	loop = asyncio.get_event_loop()
		# except RuntimeError as e:
		# 	if str(e).startswith('There is no current event loop in thread'):
		# 		loop = asyncio.new_event_loop()
		# 		asyncio.set_event_loop(loop)
		# 	else:
		# 		raise
		try:
			_gs = await self.sub_sock.recv_json()
			# print(f'{_gs=}')
			msgtype = _gs.get('msgtype', None)
			# gs = json.loads(_gs)
			if msgtype == 'gamestate':
				self.gsqueue.put(_gs.get('payload'))
			elif msgtype == 'pending_event':
				self.pe_counter += 1
				if self.debugtrace:
					logger.debug(f'{self.pe_counter} {_gs=}')
				# logger.debug(f'{_gs=}')
				self.evqueue.put(_gs.get('payload'))
			else:
				logger.warning(f'{self.pe_counter} unknown msgtype: {msgtype} {_gs=}')
		except Exception as e:
			logger.error(f'{type(e)} {e=}')
		return self.pe_counter

	async def asyncrun(self) -> int:
		self.pe_counter = 0
		# logger.info(f'{self} running')
		# try:
		# 	loop = asyncio.get_event_loop()
		# except RuntimeError as e:
		# 	if str(e).startswith('There is no current event loop in thread'):
		# 		loop = asyncio.new_event_loop()
		# 		asyncio.set_event_loop(loop)
		# 	else:
		# 		raise
		while True:
			try:
				_gs = await self.sub_sock.recv_json()
				# print(f'{_gs=}')
				msgtype = _gs.get('msgtype', None)
				# gs = json.loads(_gs)
				if msgtype == 'gamestate':
					self.gsqueue.put(_gs.get('payload'))
				elif msgtype == 'pending_event':
					self.pe_counter += 1
					if self.debugtrace:
						logger.debug(f'{self.pe_counter} {_gs=}')
					# logger.debug(f'{_gs=}')
					self.evqueue.put(_gs.get('payload'))
				else:
					logger.warning(f'{self.pe_counter} unknown msgtype: {msgtype} {_gs=}')
			except Exception as e:
				logger.error(f'{type(e)} {e=}')
		return self.pe_counter


def send_player_dict(game):
	msg = dict(
			thrmain_cnt=thrmain_cnt,
			score=game.playerone.score,
			client_id=game.playerone.client_id,
			name=game.playerone.name,
			position=game.playerone.position,
			angle=game.playerone.angle,
			health=game.playerone.health,
			timeout=game.playerone.timeout,
			killed=game.playerone.killed,
			bombsleft=game.playerone.bombsleft,
			got_map=game.got_map(),
			msgsource='send_player_dict',
			msg_dt=time.time())
	game.push_sock.send_json({'msgtype': 'msg', 'payload': msg})

def send_event_dict(game, game_event):
	game.push_sock.send_json({'msgtype': 'game_event', 'payload': game_event})
	if game.debugtrace:
		logger.info(f'push_sock.send_json from game.game_eventq ({game.game_eventq.qsize()}): msgtype: {game_event.get("event_type")} id={game_event.get("eventid")} ') # {game_event=}

async def pusher(game):
	# Push the player's INPUT state 60 times per second
	thrmain_cnt = 0
	while True:
		thrmain_cnt += 1
		msg = dict(
			thrmain_cnt=thrmain_cnt,
			score=game.playerone.score,
			client_id=game.playerone.client_id,
			name=game.playerone.name,
			position=game.playerone.position,
			angle=game.playerone.angle,
			health=game.playerone.health,
			timeout=game.playerone.timeout,
			killed=game.playerone.killed,
			bombsleft=game.playerone.bombsleft,
			got_map=game.got_map(),
			msgsource='pushermsgdict',
			msg_dt=time.time())
		try:
			game_event = game.game_eventq.get_nowait()
			if game_event:
				await game.push_sock.send_json({'msgtype': 'game_event', 'payload': game_event})
				game.game_eventq.task_done()
				if game.debugtrace:
					logger.info(f'push_sock.send_json from game.game_eventq ({game.game_eventq.qsize()}): msgtype: {game_event.get("event_type")} id={game_event.get("eventid")} ') # {game_event=}
		except Empty:
			pass  # game_events = None
		await game.push_sock.send_json({'msgtype': 'msg', 'payload': msg})
		await asyncio.sleep(1 / UPDATE_TICK)
			#if game.debugtrace:
			#	logger.debug(f'{msg=}')

	#            else:
	#                logger.warning(f'{game} is not connected.....')
	#                await asyncio.sleep(1)

async def receive_game_state(game):
	pe_counter = 0
	while True:
		_gs = await game.sub_sock.recv_json()
		msgtype = _gs.get('msgtype', None)
		# gs = json.loads(_gs)
		if msgtype == 'gamestate':
			game.game_state.from_json(_gs.get('payload'))
		elif msgtype == 'pending_event':
			pe_counter += 1
			if game.debugtrace:
				logger.debug(f'{pe_counter} {_gs=}')
			# logger.debug(f'{_gs=}')
			game.handle_game_events(_gs.get('payload'))
		else:
			logger.warning(f'{pe_counter} unknown msgtype: {msgtype} {_gs=}')




async def thread_worker(game):
	#loop = asyncio.new_event_loop()
	#asyncio.set_event_loop(loop)
	# looptask = loop.create_task(thread_main(game))
	# logger.info(f'threadworker loop: {loop} lt={looptask} ')
	#loop.run_forever()
	await asyncio.gather(pusher(game), receive_game_state(game), )
