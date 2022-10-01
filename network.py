from threading import Thread
import json
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

