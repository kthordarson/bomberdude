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
	data = json.dumps(payload, skipkeys=True).encode('utf-8')
	try:
		conn.sendall(data)
	except BrokenPipeError as e:
		logger.error(f'[send] BrokenPipeError:{e} conn:{conn} payload:{payload}')
		conn.close()

def receive_data(conn):
	if conn._closed:
		return None
	rid = None
	data = []
	try:
		rawdata = conn.recv(4096).decode('utf-8')
	except OSError as e:
		logger.error(f'[recv] OSError:{e} conn:{conn}')
		return data
	if rawdata.count('{') != rawdata.count('}'):
		diff = rawdata.count('{') - rawdata.count('}')
		logger.warning(f'[recv] d:{diff} rawdata={rawdata}')
		rawdata += '}'*diff
	if rawdata.count('{') + rawdata.count('}') == 4:
		rs1 = rawdata.split('}{')[0]+'}'
		rs2 = '{'+rawdata.split('}{')[1]
		data.append(json.loads(rs1))
		data.append(json.loads(rs2))
	elif rawdata.count('{') + rawdata.count('}') == 4:
		rs1 = rawdata.split('}{')[0]+'}'
		rs2 = '{'+rawdata.split('}{')[1]+'}'
		rs3 = '{'+rawdata.split('}{')[2]
		data.append(json.loads(rs1))
		data.append(json.loads(rs2))
		data.append(json.loads(rs3))
	elif rawdata.count('{') + rawdata.count('}') > 7:
		rs1 = rawdata.split('}{')[0]+'}'
		data.append(json.loads(rs1))
	return data
	# else:
	# 	try:
	# 		data.append(json.loads(rawdata))
	# 		#rid = data.get('data_id')
	# 	except json.JSONDecodeError as e:
	# 		erridx = e.colno-1 # e[e.index('char ')+5:].strip(')')		
	# 		logger.warning(f'[recv] JSONDecodeError:{e} erridx:{erridx} conn:{conn} rawdata={rawdata}')
	# 		if erridx == 0:
	# 			logger.warning(f'[recv] JSONDecodeError:{e} erridx:{erridx} conn:{conn} rawdata={rawdata}')
	# 			return data
	# 		elif erridx >0:			
	# 			try:
	# 				data.append(json.loads(rawdata[:erridx]))
	# 				#rid = data.get('data_id')
	# 			except (AttributeError, json.JSONDecodeError) as e2:
	# 				logger.error(f'[recv] e:{e} e2:{e2} erridx={erridx} raw={len(rawdata)}')
	# 				logger.error(f'rawdata={rawdata}')
	# 				return data
	# 	return data

