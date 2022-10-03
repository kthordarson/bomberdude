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
	'gridupdate': 12,
	'netplayers': 13,
	'netbomb': 14,
	'getid': 15,
	'clientquit': 16,
	'reqpos'	: 17,
	'netpos'	: 18,
	'posupdate': 19,
	'resetmap': 20,
	'auth':101,
	'error':1000,
	'errorfromserver':1001,
	'UnpicklingError':1002
	}
def send_data(conn=None, payload=None):
	if conn._closed:
		return
	if conn is None:
		logger.error(f'No connection conn:{conn} payload:{payload}')
		return
	if payload is None:
		logger.error('No payload')
		return
	data = json.dumps(payload).encode('utf-8')
	try:
		conn.sendall(data)
	except BrokenPipeError as e:
		logger.error(f'[send] BrokenPipeError:{e} conn:{conn} payload:{payload}')
		conn.close()

def receive_data(conn):
	if conn._closed:
		return None
	rid, data = None, None
	try:
		rawdata = conn.recv(4096).decode('utf-8')
	except OSError as e:
		logger.error(f'[recv] OSError:{e} conn:{conn}')
		return None
	if rawdata.count('}') >= 2:
		newrawdata = rawdata[0:rawdata.index('}')+1]
		#logger.warning(f'[recv] rawdata={rawdata} newrawdata={newrawdata}')
		rawdata = newrawdata # rawdata[0:rawdata.index('}')+1]
		#rawdata2 = rawdata[0:rawdata.indexd('}')+1]
		#logger.warning(f'[recv] netfoo rawdata={rawdata}')
	if rawdata.count('}') < rawdata.count('{'):
		diff = rawdata.count('{') - rawdata.count('}')
		#logger.warning(f'[recv] d:{diff} rawdata={rawdata}')
		rawdata += '}'*diff
	try:
		data = json.loads(rawdata)
		#rid = data.get('data_id')
	except json.JSONDecodeError as e:
		erridx = e.colno-1 # e[e.index('char ')+5:].strip(')')		
		# logger.warning(f'[recv] JSONDecodeError:{e} erridx:{erridx} conn:{conn} rawdata={rawdata}')
		if erridx == 0:
			return None
		elif erridx >0:
			logger.warning(f'[recv] JSONDecodeError:{e} erridx:{erridx} conn:{conn} rawdata={rawdata}')
			try:
				data = json.loads(rawdata[:erridx])
				#rid = data.get('data_id')
			except (AttributeError, json.JSONDecodeError) as e2:
				logger.error(f'[recv] e:{e} e2:{e2} erridx={erridx} raw={len(rawdata)}')
				logger.error(f'rawdata={rawdata}')
				return None
	if data == 1:
		return None
	return data

