from threading import Thread
import time
import struct
import pickle
from pickle import UnpicklingError
from loguru import logger
dataid = {
	'info': 0,
	'data': 1,
	'dummy': 2,
	'playerpos': 3,
	'update': 4,
	'updatefromserver':5,
	'gamegrid': 6,
	'reqmap': 7,
	'requpdate':8,
	'gameevent':9,
	'eventfromserver':10,
	'bombdrop': 11,
	'auth':101,
	'error':1000,
	'errorfromserver':1001,
	'UnpicklingError':1002
	}
def send_data(conn=None, data_id=None, payload=None):
	if conn is None or conn._closed:
		logger.error(f'No connection conn:{conn} data_id:{data_id} payload:{payload}')
		return
	if payload is None:
		logger.error('No payload')
		return
	if data_id is None:
		logger.error('No data_id')
		return
	#data_id = data_id.encode('utf-8')
	#payload = payload.encode('utf-8')
	payload2 = {'data_id': data_id, 'payload': payload}
	serialized_payload = pickle.dumps(payload2, protocol=pickle.HIGHEST_PROTOCOL)
	splen = len(serialized_payload)
	pktlen = struct.pack('>I', splen)
	#dpkt = struct.pack('>I', data_id)
	#conn.sendall(pktlen)
	#conn.sendall(dpkt)
	if splen > 1024:
		logger.warning(f'[send] payload size {splen} {pktlen}')
	conn.sendall(pktlen)
	conn.sendall(serialized_payload)

def receive_data(conn):
	#datasize = conn.recv(4)
	datasize = struct.unpack('>I', conn.recv(4))[0]
	rcvdpayload = b''
	rcvdsize = 0
	remain = datasize
	while remain > 0:
		rcvdpayload += conn.recv(remain)
		remain = datasize - len(rcvdpayload)
	payloadid = None
	payload = None
	rawpayload = None
	try:
		rawpayload = pickle.loads(rcvdpayload)
	except UnpicklingError as e:
		# logger.error(f'[recv] UnpicklingError:{e} data:{data} c:{conn}')
		return (dataid['UnpicklingError'], None)
	except UnicodeDecodeError as e:
		logger.error(f'[recv] UnicodeDecodeError:{e} data:{rcvdpayload} c:{conn}')
		return (None, None)
	payloadid = rawpayload.get('data_id')
	payload = rawpayload.get('payload')
	return (payloadid, payload)

def receive_data_old(conn):
	if not conn:
		return None, None
	try:
		#data_size = struct.unpack('>I', firstbytes)
		data_size = struct.unpack('>I', conn.recv(4))[0]
	except TypeError as e:
		logger.error(f'[receive_data] TypeError {e} ')
		data_size = 0
	except struct.error as e:
		logger.warning(f'[structerr] {e}')
		#conn.close()
		return None, None
	data_id = struct.unpack('>I', conn.recv(4))[0]
	received_payload = b""
	reamining_payload_size = data_size
	while reamining_payload_size != 0:
		received_payload += conn.recv(reamining_payload_size)
		reamining_payload_size = data_size - len(received_payload)
	try:
		payload = pickle.loads(received_payload)
	except EOFError as e:
		logger.error(f'[recv] EOFError:{e} id:{data_id} payload:{received_payload}')
		return (dataid['error'], 'eoferror')
	except UnpicklingError as e:
		logger.error(f'[recv] UnpicklingError:{e} id:{data_id} payload:{received_payload}')
		conn.close()
		return (dataid['error'], 'UnpicklingError')
	return (data_id, payload)


class ConnectionHandler(Thread):
	def __init__(self, conn=None, conn_name=None, client_id=None):
		Thread.__init__(self)
		self.conn = conn
		self.conn_name = conn_name
		self.client_id = client_id
		self.kill = False

	def __str__(self):
		return f'{self.client_id}'

	def run(self):
		logger.debug(f'[ch] {self.client_id} run! ')
		while True:
			if self.kill:
				logger.debug(F'[ch] {self} killed')
				break
