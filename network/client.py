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

DEBUG_INTERVAL = UPDATE_TICK * 2

async def send_game_state(game: Bomberdude) -> None:
	# Log less frequently to reduce overhead
	log_counter = 0
	send_counter = 0
	# Avoid writing to the socket before sock_connect completes.
	if game.socket_connected:
		await game.socket_connected.wait()
	while True:
		try:
			game_event = await game.game_state.event_queue.get()
		except asyncio.QueueEmpty:
			await asyncio.sleep(1 / UPDATE_TICK)
			continue
		except Exception as e:
			logger.error(f"Error getting event: {e} {type(e)}")
			continue

		if game.client_id == 'bdudenotset' or game.game_state.client_id == 'gamestatenotset' or game.game_state.client_id == 'missingclientid':
			logger.error(f'client_id not set game: {game}')
			await asyncio.sleep(1)
			continue
		else:
			player_one = game.game_state.get_playerone()

		# Cache keyspressed serialization
		client_keys = json.loads(game.game_state.keyspressed.to_json())

		# Convert PlayerState objects to dicts so dumps succeeds.
		playerlist = [p.to_dict() for p in game.game_state.playerlist.values()]
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
			game.game_state.event_queue.task_done()
			send_counter += 1
		except Exception as e:
			logger.error(f'Send error: {e} {type(e)}')
			break
		# Remove sleep to send as fast as possible, or adjust
		# await asyncio.sleep(1 / UPDATE_TICK)

		# Log periodically
		log_counter += 1
		# if log_counter % DEBUG_INTERVAL == 0 and game.args.debug_gamestate:  # Log every second at 60 FPS
		# 	logger.info(f'send_counter: {send_counter} event_queue: {game.game_state.event_queue.qsize()} client_queue: {game.game_state.client_queue.qsize()}')

async def receive_game_state(game: Bomberdude) -> None:
	# Log less frequently
	log_counter = 0
	# Avoid reading from the socket before sock_connect completes.
	if game.socket_connected:
		await game.socket_connected.wait()
	buffer = ""
	messages_processed = 0
	while True:
		try:
			data = await asyncio.get_event_loop().sock_recv(game.sock, 4096)
			if not data:
				# Connection closed
				break
			buffer += data.decode('utf-8')

			# Process multiple messages at once if available
			while '\n' in buffer:
				message, buffer = buffer.split('\n', 1)
				if not message.strip():
					continue
				game_state_json = json.loads(message)
				event = game_state_json.get("event")
				if event:
					# update_game_event is async now; schedule it without blocking receive loop
					asyncio.create_task(game.game_state.update_game_event(event))
					messages_processed += 1

			# Log periodically
			log_counter += 1
			# if log_counter % DEBUG_INTERVAL == 0 and game.args.debug_gamestate:  # Log every second at 60 FPS
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
