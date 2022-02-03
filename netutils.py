from pickle import dumps, loads
from struct import pack, unpack
from loguru import logger

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
	logger.debug(f'send_data {type(payload)} {len(payload)} {payload[:10]}')


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
	data_size = unpack('>I', conn.recv(4))[0]
	# receive next 4 bytes of data as data identifier
	data_id = unpack('>I', conn.recv(4))[0]
	# receive payload till received payload size is equal to data_size received
	received_payload = b""
	reamining_payload_size = data_size
	while reamining_payload_size != 0:
		received_payload += conn.recv(reamining_payload_size)
		reamining_payload_size = data_size - len(received_payload)
	payload = loads(received_payload)
	logger.debug(f'receive_data id: {data_id} payload: {payload[:10]}')
	return (data_id, payload)
