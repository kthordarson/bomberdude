#!/usr/bin/python
import asyncio
import json

from loguru import logger

from constants import UPDATE_TICK
from game.bomberdude import Bomberdude

# Use orjson for faster serialization if available
# To optimize, install orjson and replace json.dumps with orjson.dumps, json.loads with orjson.loads
# orjson.dumps returns bytes, so adjust encoding accordingly

# Guard against a dead/unresponsive peer hanging these loops forever.
SEND_TIMEOUT = 10
RECV_TIMEOUT = 30

async def send_game_state(game: Bomberdude) -> None:
	# Log less frequently to reduce overhead
	send_counter = 0
	# Avoid writing to the socket before sock_connect completes.
	if game.socket_connected:
		await game.socket_connected.wait()
	# A discrete (non-player_update) event pulled while coalescing a burst of
	# player_update snapshots below; sent on the next iteration so its
	# relative order versus other discrete events is preserved.
	pending_event = None
	while True:
		if pending_event is not None:
			game_event = pending_event
			pending_event = None
		else:
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

		# Coalesce a burst of back-to-back player_update events: each one is
		# a full state snapshot (not a delta), so under load only the latest
		# is worth sending. Any other event type found while draining is
		# stashed in `pending_event` rather than dropped.
		while game_event.get('event_type') == 'player_update':
			try:
				next_event = game.game_state.event_queue.get_nowait()
			except asyncio.QueueEmpty:
				break
			if next_event.get('event_type') == 'player_update':
				game.game_state.event_queue.task_done()
				game_event = next_event
			else:
				pending_event = next_event
				break

		# The server only ever reads `game_event` and `client_id` from this
		# message (see server/server.py:process_messages) — everything else
		# once sent here (position/health/playerlist/keyspressed/...) was
		# dead weight resent on every single message.
		msg = {
			'game_event': game_event,
			'client_id': player_one.client_id,
		}
		try:
			data_out = (json.dumps(msg) + '\n').encode('utf-8')
			await asyncio.wait_for(asyncio.get_running_loop().sock_sendall(game.sock, data_out), timeout=SEND_TIMEOUT)  # Direct to socket
			game.game_state.event_queue.task_done()
			send_counter += 1
		except asyncio.TimeoutError:
			logger.error(f'Send timed out after {SEND_TIMEOUT}s; treating connection as dead')
			break
		except Exception as e:
			logger.error(f'Send error: {e} {type(e)} msg: {msg}')
			break
		# Remove sleep to send as fast as possible, or adjust
		# await asyncio.sleep(1 / UPDATE_TICK)

def _log_event_task_exception(task: asyncio.Task) -> None:
	if task.cancelled():
		return
	exc = task.exception()
	if exc is not None:
		logger.error(f"Error handling game event: {exc} {type(exc)}")

async def receive_game_state(game: Bomberdude) -> None:
	# Log less frequently
	# Avoid reading from the socket before sock_connect completes.
	if game.socket_connected:
		await game.socket_connected.wait()
	buffer = ""
	messages_processed = 0
	# Keep a strong reference to in-flight event tasks so they aren't GC'd mid-run,
	# and so exceptions raised inside them are logged instead of vanishing silently.
	event_tasks: set[asyncio.Task] = set()
	while True:
		try:
			data = await asyncio.wait_for(asyncio.get_running_loop().sock_recv(game.sock, 4096), timeout=RECV_TIMEOUT)
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
					event_task = asyncio.create_task(game.game_state.update_game_event(event))
					event_tasks.add(event_task)
					event_task.add_done_callback(event_tasks.discard)
					event_task.add_done_callback(_log_event_task_exception)
					messages_processed += 1

		except asyncio.TimeoutError:
			logger.error(f'No data received for {RECV_TIMEOUT}s; treating connection as dead')
			break
		except (BlockingIOError, InterruptedError):
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
