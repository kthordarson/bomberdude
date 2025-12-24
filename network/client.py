#!/usr/bin/python
import json
import asyncio
import time
from loguru import logger
from constants import UPDATE_TICK
from game.bomberdude import Bomberdude

# Use orjson for faster serialization if available
# To optimize, install orjson and replace json.dumps with orjson.dumps, json.loads with orjson.loads
# orjson.dumps returns bytes, so adjust encoding accordingly
loads = json.loads

async def send_game_state(game: Bomberdude) -> None:
	# Log less frequently to reduce overhead
	log_counter = 0
	# Avoid writing to the socket before sock_connect completes.
	if game.socket_connected:
		await game.socket_connected.wait()
	while True:
		try:
			game_event = await game.client_game_state.event_queue.get()
		except asyncio.QueueEmpty:
			await asyncio.sleep(1 / UPDATE_TICK)
			continue
		except Exception as e:
			logger.error(f"Error getting event: {e} {type(e)}")
			continue

		# Ensure game_event is JSON-serializable (e.g. nested PlayerState objects).
		try:
			# if isinstance(game_event, dict):
			ge_playerlist = game_event.get("playerlist")
			# if isinstance(ge_playerlist, list):
			if ge_playerlist:
				game_event["playerlist"] = [(p.to_dict() if hasattr(p, "to_dict") else p) for p in ge_playerlist]
		except Exception as e:
			# Don't let cleanup break networking.
			logger.error(f"Error serializing game_event playerlist: {e} {type(e)} ge_playerlist: {ge_playerlist} game_event: {game_event}")

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

		# Cache keyspressed serialization
		client_keys = loads(game.client_game_state.keyspressed.to_json())

		# Convert PlayerState objects to dicts so dumps succeeds.
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
			data_out = (json.dumps(msg) + '\n').encode('utf-8')
			await asyncio.get_event_loop().sock_sendall(game.sock, data_out)  # Direct to socket
			game.client_game_state.event_queue.task_done()
		except Exception as e:
			logger.error(f'Send error: {e} {type(e)}')
			break
		# Remove sleep to send as fast as possible, or adjust
		# await asyncio.sleep(1 / UPDATE_TICK)

		# Log periodically
		log_counter += 1
		# if log_counter % 60 == 0:  # Log every second at 60 FPS
		# 	logger.info(f'event_queue: {game.client_game_state.event_queue.qsize()} client_queue: {game.client_game_state.client_queue.qsize()}')

async def receive_game_state(game: Bomberdude) -> None:
	# Log less frequently
	log_counter = 0
	# Avoid reading from the socket before sock_connect completes.
	if game.socket_connected:
		await game.socket_connected.wait()
	buffer = ""
	while True:
		try:
			data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
			if not data:
				# Connection closed
				break
			buffer += data.decode('utf-8')

			# Process multiple messages at once if available
			messages_processed = 0
			while '\n' in buffer:
				message, buffer = buffer.split('\n', 1)
				if not message.strip():
					continue
				game_state_json = json.loads(message)
				event = game_state_json.get("event")
				if event:
					# update_game_event is async now; schedule it without blocking receive loop
					asyncio.create_task(game.client_game_state.update_game_event(event))
					messages_processed += 1

			# Log periodically
			log_counter += 1
			# if log_counter % 60 == 0:
			# 	logger.info(f'receive: processed {messages_processed} messages, buffer size: {len(buffer)}')

		except (BlockingIOError, InterruptedError) as e:
			await asyncio.sleep(0.1)  # Shorter sleep
			continue
		except ConnectionRefusedError as e:
			logger.error(f"Connection refused: {e}")
			break
		except OSError as e:
			logger.error(f"OSError: {e}")
			break
		except Exception as e:
			logger.error(f"Error in receive_game_state: {e}")
			await asyncio.sleep(0.1)
			continue
