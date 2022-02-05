from pickle import dumps, loads
from struct import pack, unpack, error
from loguru import logger
from pickle import UnpicklingError
from globals import StoppableThread

data_identifiers = {'info': 0, 'data': 1, 'player': 2, 'netupdate': 3, 'request': 4, 'connect': 5, 'foobar6': 6, 'heartbeat': 7, 'send_pos': 8}


def send_data(conn, payload, data_id=0):
	"""
	@brief: send payload along with data size and data identifier to the connection
	@args[in]:
		conn: socket object for connection to which data is supposed to be sent
		payload: payload to be sent
		data_id: data identifier
	"""
	# serialize payload
	if conn.fileno() == -1:
		return
	serialized_payload = dumps(payload)
	# send data size, data identifier and payload
	try:
		conn.sendall(pack('>I', len(serialized_payload)))
		conn.sendall(pack('>I', data_id))
		conn.sendall(serialized_payload)
	except (BrokenPipeError, OSError) as e:
		logger.error(f'{e}')
		conn.close()


# logger.debug(f'send_data id:{type(payload)} size:{len(payload)}')

def receive_data(conn):
	"""
	@brief: receive data from the connection assuming that
		first 4 bytes represents data size,
		next 4 bytes represents data identifier and
		successive bytes of the size 'data size'is payload
	@args[in]:
		conn: socket object for conection from which data is supposed to be received
	"""
	# receive first 4 bytes of data as data size of payload
	if conn.fileno() == -1:
		return 0, 0
	try:
		data_size = unpack('>I', conn.recv(4))[0]
		# receive next 4 bytes of data as data identifier
		data_id = unpack('>I', conn.recv(4))[0]
		# receive payload till received payload size is equal to data_size received
		received_payload = b""
		reamining_payload_size = data_size
		while reamining_payload_size != 0:
			received_payload += conn.recv(reamining_payload_size)
			reamining_payload_size = data_size - len(received_payload)
	except (error, OSError) as e:
		logger.error(f'{e}')
		conn.close()
		return 0, 0
	payload = 0
	try:
		payload = loads(received_payload)
	except UnpicklingError as e:
		logger.error(f'ERR {e} size: {len(received_payload)} payload: {received_payload}')
	# logger.debug(f'receive_data id:{data_id} size:{len(payload)}')
	return data_id, payload


class DataSender(StoppableThread):
	def __init__(self, socket, queue):
		StoppableThread.__init__(self)
		self.socket = socket
		self.queue = queue

	def process_queue(self):
		if not self.queue.empty():
			data_id, payload = self.queue.get()
			# logger.debug(f'send qitem: id: {data_id} size:{len(payload)}')
			send_data(self.socket, payload, data_id)
		# try:
		# 	self.queue.task_done()
		# except ValueError as e:
		# 	logger.error(f'{e} dataid:{data_id} pl:{payload}')

	def run(self):
		while True:
			self.process_queue()


class DataReceiver(StoppableThread):
	def __init__(self, socket, queue):
		StoppableThread.__init__(self)
		self.socket = socket
		self.queue = queue

	def run(self):
		while True:
			data_id, payload = receive_data(self.socket)
			if self.socket.fileno() == -1:
				self.socket.close()
				break
			self.queue.put_nowait((data_id, payload))
