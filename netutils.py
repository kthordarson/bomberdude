from pickle import dumps, loads
from queue import Empty
from struct import pack, unpack, error
from loguru import logger
from pickle import UnpicklingError
from threading import Thread, Event
import socket
from queue import Queue
data_identifiers = {
	'info': 0,
	'data': 1,
	'player': 2,
	'netplayer': 3,
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

def get_ip_address():
	# returns the 'most real' ip address
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.connect(("8.8.8.8", 80))
	return s.getsockname()


def get_constants(prefix):
	return {getattr(socket, n): n for n in dir(socket) if n.startswith(prefix)}


families = get_constants('AF_')
types = get_constants('SOCK_')
protocols = get_constants('IPPROTO_')


def send_data(conn: socket, payload: str, data_id: int):
	if not payload or data_id == 0:
		logger.error(f'[send_data] invalid data conn: {type(conn)} {conn} id:{data_id} payload:{payload}')
		return
	if not isinstance(conn, socket.socket):
		logger.error(f'[send_data] err! conn: {type(conn)} {conn} payload {payload}')
		return
	try:
		serialized_payload = dumps(payload)
	except Exception as e:
		logger.error(f'[send_data] dump err: {e} data_id:{data_id} payload:{payload}')
		raise e
	# send data size, data identifier and payload
	try:
		conn.sendall(pack('>I', len(serialized_payload)))
		conn.sendall(pack('>I', data_id))
		conn.sendall(serialized_payload)
		logger.debug(f'[send_data] src:{conn.getsockname()} dst:{conn.getpeername()} id:{data_id} payload:{payload}') # {data_identifiers[data_id]} 
	except (BrokenPipeError, OSError) as e:
		logger.error(f'[send_data] err: {e} data_id:{data_id} payload:{payload}')
		conn.close()
		raise e

def receive_data(conn: socket):
	incoming = conn.recvfrom(1024)
	return incoming

def receive_dataold(conn: socket):
	if isinstance(conn, str):
		logger.error(f'recv error conntype:{type(conn)} conn:{conn}')
		return '-1', 'error'
	received_payload = b""
	data_size = None
	data_id = None
	try:
		data_size = unpack('>I', conn.recv(4))[0]
	except (error, OSError) as e:
		logger.error(f'recv err: {e} conn:{conn.fileno()} ')
		conn.close()
		return None
	# receive next 4 bytes of data as data identifier
	if data_size:
		try:
			data_id = unpack('>I', conn.recv(4))[0]
		except OSError as e:
			logger.error(f'recv err: {e} conn:{conn.fileno()} ')
			conn.close()
			return None			
		if data_id:
			# receive payload till received payload size is equal to data_size received		
			reamining_payload_size = data_size
			while reamining_payload_size != 0:
				try:
					received_payload += conn.recv(reamining_payload_size)
				except OSError as e:
					logger.error(f'recv err: {e} size:{data_size}/{reamining_payload_size} id:{data_id} p:{received_payload}')
					conn.close()
					return None
					# raise e
				reamining_payload_size = data_size - len(received_payload)
			payload = 0
			try:
				payload = loads(received_payload)
			except UnpicklingError as e:
				logger.error(f'recv err: {e}')
				return None
			return data_id, payload


class DataSender(Thread):
	def __init__(self, s_socket=None, queue=None, name=None, server=None, stop_event=None):
		_name = f'DS-{name}'
		Thread.__init__(self, name=_name, daemon=True, args=(stop_event,))
		self.name = _name
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.queue = Queue()
		self.kill = False
		self.server = server

	def run(self):
		# logger.debug(f'[datasender] {self.name} run socket:{self.socket} q:{self.queue.qsize()} server:{self.server}')
		while True:
			data_id = 1
			payload = None
			if self.kill:
				logger.debug(f'[datasender] {self.name} kill')
				break
				
			if not self.queue.empty():
				payload = self.queue.get(block=None)
				self.queue.task_done()
				if payload:
					# logger.debug(f'[DS] data_id:{data_id} payload:{payload} q:{self.queue.qsize()} server:{self.server}')
					try:
						self.socket.sendto(payload, self.server)
						# send_data(self.socket, payload=payload, data_id=data_id)
					except OSError as oserr:
						logger.error(f'[{self.name}] oserr:{oserr} {data_id} payload:{payload}')
						if oserr.errno == 9:
							self.socket.close()
							self.kill = True
						if oserr.errno == 32:
							self.kill = True
					except Exception as e:
						logger.error(f'[{self.name}] err:{e} {data_id} payload:{payload}')
						#raise e

class DataReceiver(Thread):
	def __init__(self, r_socket=socket, queue=None, name=None, server=None, localaddr=None, stop_event=None):
		_name = f'DR-{name}'
		Thread.__init__(self, name=_name, daemon=True, args=(stop_event,))
		self.name = _name
		self.localaddr = localaddr
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.queue = Queue()
		self.kill = False
		self.server = server

	def run(self):
		# logger.debug(f'[datareceiver] {self.name} run socket:{self.socket} q:{self.queue.qsize()} server:{self.server}')
		self.socket.bind(self.localaddr)
		while True:
			data_id = None
			payload = None
			if self.kill:
				logger.debug(f'[datareceiver] {self.name} kill')
				break
			try:
				payload = self.socket.recvfrom(1024)
			except ConnectionRefusedError as e:
				logger.error(f'[DR] err {e} sock:{self.socket} p:{payload} q:{self.queue.qsize()}')
			if payload:
				self.queue.put(payload)
				# logger.debug(f'[{self.name}] recv {data_id} p:{payload} src:{self.socket.getsockname()} dst:{self.socket.getpeername()} qs:{self.queue.qsize()}')
