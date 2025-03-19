#!/usr/bin/python
import orjson as json
import sys
import asyncio
import time
from argparse import ArgumentParser
import pygame
from loguru import logger
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, UPDATE_TICK
from panels import MainMenu, SetupMenu
from game.bomberdude import Bomberdude

async def send_game_state(game):
	logger.info(f'pushstarting event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')
	while True:
		try:
			game_event = await game.client_game_state.event_queue.get()
		except asyncio.QueueEmpty:
			await asyncio.sleep(1 / UPDATE_TICK)
			pass
		except Exception as e:
			logger.error(f"Error: {e} {type(e)}")
			continue
		client_keys = json.loads(game.client_game_state.keyspressed.to_json())
		try:
			player_one = game.client_game_state.get_playerone()
		except AttributeError as e:
			logger.error(f'{e} {type(e)}')
			await asyncio.sleep(1)
			continue
		# playerlist = [player.to_dict() if hasattr(player, 'to_dict') else player for player in game.client_game_state.playerlist.values()]
		playerlist = [player for player in game.client_game_state.playerlist.values()]
		msg = {
			'game_event': game_event,
			'client_id': player_one.client_id,
			'position': (player_one.position.x, player_one.position.y),
			'health': player_one.health,
			'score': player_one.score,
			'keyspressed': client_keys,
			'event_type': "send_game_state",
			'handledby': "send_game_state",
			'msg_dt': time.time(),
			'playerlist': playerlist,
		}
		try:
			data_out = json.dumps(msg) + b'\n'
			await asyncio.get_event_loop().sock_sendall(game.sock, data_out)  # Direct to socket
			game.client_game_state.event_queue.task_done()
		except Exception as e:
			logger.error(f'{e} {type(e)} msg: {msg}')
			break
		finally:
			await asyncio.sleep(1 / UPDATE_TICK)

async def receive_game_state(game):
	buffer = ""
	while True:
		try:
			data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
			if not data:
				if game.sock._closed:
					logger.warning(f'Connection closed {game.sock._closed}')
					break
				else:
					await asyncio.sleep(1 / UPDATE_TICK)
					continue
			buffer += data.decode('utf-8')

			# Process multiple messages at once if available
			while '\n' in buffer:
				message, buffer = buffer.split('\n', 1)
				if not message.strip():
					logger.warning(f'no message in buffer: {buffer}')
					continue
				game_state_json = json.loads(message)
				if game_state_json.get('event_type') == 'broadcast_event':
					asyncio.create_task(game.client_game_state.update_game_event(game_state_json["event"]))
				else:
					await game.client_game_state.from_json(game_state_json)
		except (BlockingIOError, InterruptedError) as e:
			await asyncio.sleep(1)
			logger.error(f'{e} {type(e)}')
			continue
		except Exception as e:
			logger.error(f"Error in receive_game_state: {e} {type(e)}")
			await asyncio.sleep(1)
			if isinstance(e, ConnectionResetError):
				game._connected = False
				break
			continue
