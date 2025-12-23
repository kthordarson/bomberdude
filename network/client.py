#!/usr/bin/python
import json
import asyncio
import time
from loguru import logger
from constants import UPDATE_TICK
from game.bomberdude import Bomberdude

async def send_game_state(game: Bomberdude) -> None:
	logger.info(f'event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')
	# Avoid writing to the socket before sock_connect completes.
	try:
		if hasattr(game, 'socket_connected'):
			await game.socket_connected.wait()  # type: ignore[attr-defined]
	except asyncio.CancelledError:
		return
	while True:
		try:
			game_event = await game.client_game_state.event_queue.get()
		except asyncio.QueueEmpty:
			await asyncio.sleep(1 / UPDATE_TICK)
			pass
		except Exception as e:
			logger.error(f"Error: {e} {type(e)}")
			continue

		# Ensure game_event is JSON-serializable (e.g. nested PlayerState objects).
		try:
			if isinstance(game_event, dict):
				ge_playerlist = game_event.get("playerlist")
				if isinstance(ge_playerlist, list):
					game_event["playerlist"] = [
						(p.to_dict() if hasattr(p, "to_dict") else p) for p in ge_playerlist
					]
		except Exception:
			# Don't let cleanup break networking.
			pass

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
		# Convert PlayerState objects to dicts so json.dumps succeeds.
		playerlist = [
			(p.to_dict() if hasattr(p, "to_dict") else p)
			for p in game.client_game_state.playerlist.values()
		]
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
			data_out = json.dumps(msg) + '\n'
			await asyncio.get_event_loop().sock_sendall(game.sock, data_out.encode('utf-8'))  # Direct to socket
			game.client_game_state.event_queue.task_done()
		except Exception as e:
			logger.error(f'{e} {type(e)} msg: {msg}')
			break
		finally:
			await asyncio.sleep(1 / UPDATE_TICK)

async def receive_game_state(game: Bomberdude) -> None:
	logger.info(f'event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')
	# Avoid reading from the socket before sock_connect completes.
	try:
		if hasattr(game, 'socket_connected'):
			await game.socket_connected.wait()  # type: ignore[attr-defined]
	except asyncio.CancelledError:
		return
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
		except OSError as e:
			logger.error(f"OSError: {e} {type(e)} game.sock: {game.sock}")
			await asyncio.sleep(1)
		except Exception as e:
			logger.error(f"Error in receive_game_state: {e} {type(e)} game.sock: {game.sock}")
			await asyncio.sleep(1)
			continue
