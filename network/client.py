#!/usr/bin/python
import orjson as json
import asyncio
import time
from loguru import logger
from constants import UPDATE_TICK
from game.bomberdude import Bomberdude

async def send_game_state(game: Bomberdude) -> None:
	logger.info(f'event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')
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
		if game.client_id == 'bdudenotset' or game.client_game_state.client_id == 'gamestatenotset' or game.client_game_state.client_id == 'missingclientid':
			logger.error(f'client_id not set game: {game}')
			await asyncio.sleep(1)
			continue
		else:
			try:
				player_one = game.client_game_state.get_playerone()
			except AttributeError as e:
				logger.error(f'{e} {type(e)}')
				await asyncio.sleep(1)
				continue
		playerlist = [player for player in game.client_game_state.playerlist.values()]
		msg = {
			'game_event': game_event,
			'client_id': player_one.client_id,
			'position': (player_one.position[0], player_one.position[1]),
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

async def receive_game_state(game: Bomberdude) -> None:
	logger.info(f'event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')
	buffer = ""
	while True:
		try:
			data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
			buffer += data.decode('utf-8')

			# Process multiple messages at once if available
			while '\n' in buffer:
				message, buffer = buffer.split('\n', 1)
				if not message.strip():
					logger.warning(f'no message in buffer: {buffer}')
					continue
				game_state_json = json.loads(message)
				event = game_state_json.get("event")
				if event:
					# update_game_event is async now; schedule it without blocking receive loop
					asyncio.create_task(game.client_game_state.update_game_event(event))

		except (BlockingIOError, InterruptedError) as e:
			await asyncio.sleep(1)
			logger.error(f'{e} {type(e)}')
			continue
		except ConnectionRefusedError as e:
			logger.error(f"Connection refused: {e} {type(e)}")
			await asyncio.sleep(1)
			break
		except Exception as e:
			logger.error(f"Error in receive_game_state: {e} {type(e)}")
			await asyncio.sleep(1)
			if isinstance(e, ConnectionResetError):
				game._connected = False
				break
			continue
