from threading import Thread
import time
import struct
import pickle
import json
from pickle import HIGHEST_PROTOCOL, UnpicklingError
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
	data = json.dumps(payload).encode('utf-8')
	#logger.debug(f'[send] pl={len(payload)} d={len(data)} p={payload} d={data}')
	conn.sendall(data)
	#data_id = data_id.encode('utf-8')
	#payload = payload.encode('utf-8')
	# payload2 = {'data_id': data_id, 'payload': payload}
	#serialized_payload = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
	#splen = len(serialized_payload)
	#pktlen = struct.pack('<I', len(serialized_payload))
	#pktlen = pickle.dumps(struct.pack('>I', splen), protocol=pickle.HIGHEST_PROTOCOL)
	#dpkt = struct.pack('>I', data_id)
	#conn.sendall(pktlen)
	#conn.sendall(dpkt)
	#conn.sendall(pktlen)
	#time.sleep(0.5)
	#conn.sendall(serialized_payload)
	# resp = conn.recv(4)
	# if resp == b'send':
	# 	# logger.debug(f'[send] dataok {resp} sending payload {serialized_payload}')
	# 	conn.sendall(serialized_payload)
	# elif resp == b'resend':
	# 	logger.warning(f'[send] {resp} pktlen={struct.unpack("I",pktlen)[0]} splen={splen} sp={len(serialized_payload)} p={payload2}')
	# 	splen = len(serialized_payload)
	# 	pktlen = struct.pack('I', splen)
	# 	conn.send(pktlen)
	# 	resp = conn.recv(6)
	# 	if resp == b'sendok':
	# 		logger.warning(f'[send] resend {resp} splen={splen} sp={len(serialized_payload)} pktlen={struct.unpack("I",pktlen)[0]}')
	# 		conn.send(serialized_payload)
	# 	else:
	# 		logger.error(f'[send] resend {resp} splen={splen} sp={len(serialized_payload)} pktlen={struct.unpack("I",pktlen)[0]}')

def receive_data(conn):
	rid, data = None, None
	rawdata = conn.recv(4096).decode('utf-8')
	try:
		data = json.loads(rawdata)
		#rid = data.get('data_id')
	except json.JSONDecodeError as e:
		erridx = e.colno-1 # e[e.index('char ')+5:].strip(')')
		if erridx == 0:
			return None
		elif erridx >0:
			try:
				data = json.loads(rawdata[:erridx])
				#rid = data.get('data_id')
			except (AttributeError, json.JSONDecodeError) as e2:
				logger.error(f'[recv] e:{e} e2:{e2} erridx={erridx} raw={len(rawdata)}')
				logger.error(f'data={data}')
				logger.error(f'rawdata={rawdata}')
				return None
	if data == 1:
		return None
	return data

def xxreceive_data(conn):
	#datasize = conn.recv(4)
	rawdata = []
	try:
		datasize = struct.unpack('<I', conn.recv(4))[0]
	except struct.error as e:
		logger.error(f'[recv] struct.error:{e} c:{conn}')
		return (None, None)
	if datasize == 0:
		logger.warning(f'[recv] datasize 0')
		return (None, None)
	elif datasize > 4096:
		logger.warning(f'[recv] payload oversize {datasize}')
		#resp = str.encode(f'send')
		#conn.send(resp)
		#datasize = 121
		return (None, None)
	elif 0 < datasize < 4096:
		#resp = str.encode(f'send')
		#conn.sendall(resp)	
		# remain = datasize
		# while remain < datasize:
		# 	logger.debug(f'datasize:{datasize} remain:{remain} recvdata:{len(rawdata)} d={rawdata} ')
		# 	rawdata.append(conn.recv(remain))
		# 	remain -= len(b''.join(rawdata))
		rawdata = conn.recv(datasize)
		try:
			# data = pickle.loads(b''.join(rawdata))
			data = pickle.loads(rawdata)
		except UnpicklingError as e:
			logger.error(f'[recv] UnpicklingError:{e} datasize={datasize} r={len(rawdata)} rawdata={rawdata}')
			#resp = str.encode(f'resend')
			#conn.send(resp)
			return (None, None)
		except EOFError as e:
			logger.error(f'[recv] EOFError:{e} datasize={datasize} r={len(rawdata)} rawdata={rawdata}')
			return (None, None)
		# logger.debug(f'datasize:{datasize} recvdata:{len(data)} d={data} r={rawdata} rl={len(rawdata)}')
		rid = data.get('data_id')
		payload = data.get('payload')
		return (rid, payload)

def xreceive_data(conn):
	#datasize = conn.recv(4)
	datasize = struct.unpack('I', conn.recv(4))[0]
	#datasize = conn.recv(4)
	#print(datasize)
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
		logger.error(f'[recv] UnpicklingError:{e} datasize={datasize} remain={remain} rcvdpayload={rcvdpayload}')
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
