from multiprocessing.sharedctypes import Value
from pickle import dumps, loads
from struct import pack, unpack, error
from loguru import logger
from pickle import UnpicklingError
from threading import Thread
from globals import StoppableThread
import socket

data_identifiers = {
	'info': 0,
	'data': 1,
	'player': 2,
	'netupdate': 3,
	'request': 4,
	'connect': 5,
	'setclientid': 6,
	'heartbeat': 7,
	'send_pos': 8,
	'getclientid': 9,
	'mapdata': 10,
	'blockdata': 11,
	'get_net_players': 12,
	'newplayer': 13,
	'gamemapgrid': 14,
	'gameblocks': 15,
	'debugdump': 16,
	'nplpos': 17,
	'bcastmsg': 18,
	'sendyourpos': 19,
	'posupdate': 20
}

def get_constants(prefix):
    return {getattr(socket, n): n for n in dir(socket) if n.startswith(prefix)}


families = get_constants('AF_')
types = get_constants('SOCK_')
protocols = get_constants('IPPROTO_')


def send_data(conn=None, payload=None, data_id=0):
	if not isinstance(conn, socket.socket):
		logger.error(f'send err! conn: {type(conn)} {conn} payload {payload}')
		return
	try:
		serialized_payload = dumps(payload)
	except Exception as e:
		logger.error(f'send dump err: {e} data_id:{data_id} payload:{payload}')
		raise e
	# send data size, data identifier and payload
	try:
		conn.sendall(pack('>I', len(serialized_payload)))
		conn.sendall(pack('>I', data_id))
		conn.sendall(serialized_payload)
	except (BrokenPipeError, OSError) as e:
		logger.error(f'send err: {e} data_id:{data_id} payload:{payload}')
		conn.close()
		raise e

def receive_data(conn=None):
	if isinstance(conn, str):
		logger.error(f'recv error conntype:{type(conn)} conn:{conn}')
		return '-1', 'error'
	received_payload = b""
	try:
		data_size = unpack('>I', conn.recv(4))[0]
	except (error, OSError) as e:
		logger.error(f'recv err: {e} conn:{conn.fileno()} ')
		if e.errno == 104:
			conn.close()
		return None
	# receive next 4 bytes of data as data identifier
	data_id = unpack('>I', conn.recv(4))[0]
	# receive payload till received payload size is equal to data_size received		
	reamining_payload_size = data_size
	while reamining_payload_size != 0:
		received_payload += conn.recv(reamining_payload_size)
		reamining_payload_size = data_size - len(received_payload)
	payload = 0
	try:
		payload = loads(received_payload)
	except UnpicklingError as e:
		logger.error(f'recv err: {e}')
		return None
	return data_id, payload


class DataSender(Thread):
	def __init__(self, s_socket=None, queue=None, name=None):
		_name = f'DS-{name}'
		Thread.__init__(self, name=_name)
		self.name = _name
		self.socket = s_socket
		self.queue = queue
		self.kill = False

	def process_queue(self):
		if not self.queue.empty():
			data_id, payload = self.queue.get_nowait()
			if data_id not in data_identifiers.values():
				logger.error(f'unknown data_id id: {data_id} payload:{payload}')
			else:
				try:
					send_data(self.socket, payload=payload, data_id=data_id)
				except OSError as oserr:
					logger.error(f'[{self.name}] oserr:{oserr} {data_id} payload:{payload}')
					if oserr.errno == 9:
						self.socket.close()
						self.kill = True
					if oserr.errno == 32:
						self.kill = True
				except Exception as e:
					logger.error(f'[{self.name}] err:{e} {data_id} payload:{payload}')

	def run(self):
		while True:
			if self.kill:
				break
			self.process_queue()


class DataReceiver(Thread):
	def __init__(self, r_socket=None, queue=None, name=None):
		_name = f'DR-{name}'
		Thread.__init__(self, name=_name)
		self.name = _name
		self.socket = r_socket
		self.queue = queue
		self.kill = False

	def run(self):
		while True:
			data_id = None
			payload = None
			if self.kill:
				break
			try:
				data_id, payload = receive_data(self.socket)
			except (ConnectionResetError, TypeError) as e:
				logger.error(f'[{self.name}] err:{e} s:{self.socket.fileno()}')
				self.socket.close()
				self.kill = True
			if data_id:
				self.queue.put((data_id, payload))