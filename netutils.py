from pickle import dumps, loads
from struct import pack, unpack
import struct
from loguru import logger
from pickle import UnpicklingError
from threading import Thread, Event
import socket
from queue import Queue
dataidold = {
	'info': 0,
	'data': 1,
	'player': 2,
	'netplayer': 3,
	'request': 4,
	'connect': 5,
	'setclient_id': 6,
	'heartbeat': 7,
	'send_pos': 8,
	'getclient_id': 9,
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
	return ('127.0.0.1', 9999)

def get_ip_addressx():
	# returns the 'most real' ip address
	#s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	#s.connect(("8.8.8.8", 80))
	return ('192.168.1.122', 9191)#s.getsockname()


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
		logger.debug(f'[send_data] src:{conn.getsockname()} dst:{conn.getpeername()} id:{data_id} payload:{payload}') # {dataid[data_id]} 
	except (BrokenPipeError, OSError) as e:
		logger.error(f'[send_data] err: {e} data_id:{data_id} payload:{payload}')
		#conn.close()
		raise e

def receive_data(conn: socket):
	received_payload = b""
	data_size = None
	payload = None
	try:
		data_size = unpack('>I', conn.recv(1024)) #[0]
	except OSError as e:
		return None
	except struct.error as e:
		# logger.error(f'recv struct.error: {e} {e.with_traceback} connfileno:{conn.fileno()} conn:{conn} closed:{conn._closed}')
		return None
	if data_size:
		# receive payload till received payload size is equal to data_size received		
		reamining_payload_size = data_size
		# logger.debug(f'[receive_data] data_size:{data_size}')
		while reamining_payload_size != 0:
			try:
				received_payload += conn.recv(reamining_payload_size)
			except OSError as e:
				logger.error(f'recv OSError: {e} size:{data_size}/{reamining_payload_size} p:{received_payload}')
				#return None
			reamining_payload_size = data_size - len(received_payload)
		try:
			payload = loads(received_payload)
		except UnpicklingError as e:
			errmsg = f'recv UnpicklingError: {e} plen:{len(received_payload)} size:{data_size}  remain:{reamining_payload_size} p:{received_payload}'
			logger.error(errmsg)
			return f'200:error:{received_payload}'
	return payload


class DataSender(Thread):
	def __init__(self, s_socket=None, queue=None, name=None, server=None, stop_event=None):
		_name = f'DS-{name}'
		Thread.__init__(self, name=_name, daemon=True, args=(stop_event,))
		self.name = _name
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.queue = Queue()
		self.kill = False
		self.server = server
		self.sendpkts = 0
		self.qgetcnt = 0

	def __repr__(self):
		return f'DataSender({self.name}) self.sendpkts:{self.sendpkts} self.qgetcnt:{self.qgetcnt}'

	def update_server(self, server_addr, server_port):
		logger.debug(f'[ds] updating server from {self.server} to addr:{server_addr} port:{server_port}')
		self.server = (server_addr, server_port)
		
	def run(self):
		# logger.debug(f'[datasender] {self.name} run socket:{self.socket} q:{self.queue.qsize()} server:{self.server}')
		while True:
			data_id = None
			payload = None
			if self.kill:
				logger.debug(f'[datasender] {self} kill ')
				break
				
			if not self.queue.empty():
				payload = self.queue.get(block=None)
				self.qgetcnt += 1
				# self.queue.task_done()
				if payload:
					# logger.debug(f'[DS] data_id:{data_id} payload:{payload} q:{self.queue.qsize()} server:{self.server}')
					try:
						self.socket.sendto(payload, self.server)
						self.sendpkts += 1
						# send_data(self.socket, payload=payload, data_id=data_id)
					except OSError as oserr:
						logger.error(f'[{self.name}] oserr:{oserr} {data_id} payload:{payload} self.sendpkts:{self.sendpkts} self.qgetcnt:{self.qgetcnt}')
						if oserr.errno == 9:
							self.socket.close()
							self.kill = True
						if oserr.errno == 32:
							self.kill = True
					except Exception as e:
						logger.error(f'[{self.name}] err:{e} {data_id} payload:{payload} self.sendpkts:{self.sendpkts} self.qgetcnt:{self.qgetcnt}')
						#raise e

class DataReceiver(Thread):
	def __init__(self, r_socket=socket, queue=None, name=None, server=None, localaddr=None, stop_event=None):
		_name = f'DR-{name}'
		Thread.__init__(self, name=_name, daemon=True, args=(stop_event,))
		self.name = _name
		self.r_socket = r_socket
		self.localaddr = localaddr
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.queue = Queue()
		self.kill = False
		self.server = server
		self.rcvpkts = 0
		self.qputcnt = 0

	def __repr__(self):
		return f'DataReceiver({self.name}) self.rcvpkts:{self.rcvpkts} self.qputcnt:{self.qputcnt}'

	def run(self):
		# logger.debug(f'[datareceiver] {self.name} run socket:{self.socket} q:{self.queue.qsize()} server:{self.server}')
		self.socket.bind(self.localaddr)
		self.socket.settimeout(1)
		while True:
			data_id = None
			payload = None
			if self.kill:
				logger.debug(f'[datareceiver] {self} kill')
				break
			try:
				payload = self.socket.recvfrom(1024)
				self.rcvpkts += 1
			except TimeoutError as e:
				continue
			except ConnectionRefusedError as e:
				logger.error(f'[DR] err {e} sock:{self.socket} p:{payload} q:{self.queue.qsize()} self.rcvpkts:{self.rcvpkts} self.qputcnt:{self.qputcnt}')
			if payload:
				self.queue.put(payload)
				self.qputcnt += 1
				#logger.debug(f'[{self.name}] recv {data_id} p:{payload} qs:{self.queue.qsize()}')


def sendmsg_client(msgid=None, client_id=None, msgdata=None, socket=None):
	data = f'{msgid}:{client_id}:{msgdata}'.encode('utf-8')
	#data = f'{self.client_id}:{msgdata}'.encode('utf-8')
	serialized_payload = None
	try:
		serialized_payload = dumps(data)
	except Exception as e:
		logger.error(f'[testclient] sendmsg err {e}')
		return False
	try:
		socket.sendall(pack('>I', len(serialized_payload)))
		socket.sendall(serialized_payload)
		return True
	except BrokenPipeError as e:
		logger.warning(f'[testclient] BrokenPipeError2 {e} sendmsg fail socket:{socket} msgid:{msgid} msgdata:{msgdata} splen:{len(serialized_payload)} {serialized_payload} ')
		return False
	except OSError as e:
		logger.warning(f'[testclient] oserror {e} {msgid} {msgdata} splen:{len(serialized_payload)} {serialized_payload}')
		return False


def sendmsg_server(msgid=None, client_id=None, msgdata=None, csocket=None):
	if csocket._closed:
		logger.warning(f'[ch] socket closed sclosed:{csocket._closed}')
	data = f'{msgid}:{client_id}:{msgdata}'.encode('utf-8')
	serialized_payload = dumps(data)
	try:			
		csocket.sendall(pack('>I', len(serialized_payload)))
		csocket.sendall(serialized_payload)
	except OSError as e:
		logger.error(f'[ch] send err {e} msgid:{msgid} msgdata:{msgdata} socket:{csocket} sclosed:{csocket._closed}')
		return False
