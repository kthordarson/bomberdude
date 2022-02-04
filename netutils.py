from pickle import dumps, loads
from struct import pack, unpack, error
from loguru import logger
from queue import Queue
from threading import Thread

data_identifiers = {'info': 0, 'data': 1, 'player': 2, 'netupdate':3, 'foobar':4, 'foobar5':5, 'foobar6':6, 'heartbeat':7, 'sendpos': 8}

def send_data(conn, payload, data_id=0):
	'''
	@brief: send payload along with data size and data identifier to the connection
	@args[in]:
		conn: socket object for connection to which data is supposed to be sent
		payload: payload to be sent
		data_id: data identifier
	'''
	# serialize payload
	serialized_payload = dumps(payload)
	# send data size, data identifier and payload
	conn.sendall(pack('>I', len(serialized_payload)))
	conn.sendall(pack('>I', data_id))
	conn.sendall(serialized_payload)
	# logger.debug(f'send_data id:{type(payload)} size:{len(payload)}')

def receive_data(conn):
	'''
	@brief: receive data from the connection assuming that 
		first 4 bytes represents data size,  
		next 4 bytes represents data identifier and 
		successive bytes of the size 'data size'is payload
	@args[in]: 
		conn: socket object for conection from which data is supposed to be received
	'''
	# receive first 4 bytes of data as data size of payload
	try:
		data_size = unpack('>I', conn.recv(4))[0]
	except error as e:
		logger.error(f'{e}')
		conn.close()
		return (0,0)
	# receive next 4 bytes of data as data identifier
	data_id = unpack('>I', conn.recv(4))[0]
	# receive payload till received payload size is equal to data_size received
	received_payload = b""
	reamining_payload_size = data_size
	while reamining_payload_size != 0:
		received_payload += conn.recv(reamining_payload_size)
		reamining_payload_size = data_size - len(received_payload)
	payload = loads(received_payload)
	# logger.debug(f'receive_data id:{data_id} size:{len(payload)}')
	return (data_id, payload)


class DataSender(Thread):
	def __init__(self, socket, queue):
		Thread.__init__(self)
		self.socket = socket
		self.queue = queue

	def process_queue(self):
		if not self.queue.empty():
			data_id, payload = self.queue.get()
			# logger.debug(f'send qitem: id: {data_id} size:{len(payload)}')
			send_data(self.socket, payload, data_id)
			# self.queue.task_done()

	def run(self):
		while True:
			self.process_queue()

class DataReceiver(Thread):
	def __init__(self, socket, queue):
		Thread.__init__(self)
		self.socket = socket
		self.queue = queue

	def run(self):
		while True:
			data_id, payload = receive_data(self.socket)
			if self.socket.fileno() == -1:
				self.socket.close()
				break
			self.queue.put_nowait((data_id, payload))
				
			# if isinstance(_payload, int):
			# 	logger.debug(f'data_receiver id: {data_id} payload: {type(_payload)} {_payload} sock: {self.socket.fileno()}')
			# 	continue
			# if data_id == 1:
			# 	pass
			# 	# handle_gamedata(_payload)		
			# elif data_id == 2:				
			# 	pass
			# 	# set_netplayers(_payload)
			# elif data_id == 0 and len(_payload) <= 3:
			# 	try:
			# 		payload = _payload # .decode()
			# 		servermsg, serverdata, serverparams, *rest = payload.split(':')
			# 	except (AttributeError, UnicodeDecodeError) as e:
			# 		logger.error(f'{e} id:{data_id} payload: {len(_payload)} {type(_payload)} {_payload}')
			# 	except TypeError as e:
			# 		logger.error(f'{e} id:{data_id} ')
			# 	if servermsg and payload:
			# 		if servermsg == 'netupdate':
			# 			logger.debug(f'netupdate {payload}')
			# 		if servermsg == 'netplayers':
			# 			pass
			# 			# net_players = serverdata
			# 		if servermsg == 'connected':
			# 			response = f'confirm:0:0'
			# 			logger.debug(f'from server:{payload} sending:{response}')
			# 			send_data(self.socket, response)
			# 		if servermsg == 'confirmed':
			# 			response = f'conndone:0:0'
			# 			logger.debug(f'from server:{payload} sending:{response}')
			# 			send_data(self.socket, response)
