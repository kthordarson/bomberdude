import re
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
	sendcheck = False
	try:
		sendcheck = isinstance(payload, dict) # payload[0] == '{' and payload[-1] == '}'
	except (KeyError, IndexError, TypeError) as e:
		logger.warning(f'[send] err={e} sendcheck={sendcheck} t:{type(payload)} payload={payload}')
		sendcheck = False
	if sendcheck:
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
	else:
		logger.warning(f'[send] bracketsmismatch payload={payload}')

def receive_data(conn):
	if conn._closed:
		return None
	rid = None
	data = []
	rawdata = None
	try:
		rawdata = conn.recv(1024).decode('utf-8')
	except OSError as e:
		logger.error(f'[recv] OSError:{e} conn:{conn}')
		return None
	parts = len(rawdata.split('}{'))
	rawcheck = False
	if parts == 1: # rawdata.count('{') + rawdata.count('}') == 2 or 'netplayers' in rawdata:
		try:
			rawcheck = rawdata[0] == '{' and rawdata[-1] == '}'
		except (KeyError, IndexError, TypeError) as e:
			logger.warning(f'[recv] err {e} payload={rawdata}')
			rawcheck = False
		if rawcheck:
			try:
				data.append(json.loads(rawdata))
			except json.decoder.JSONDecodeError as e:
				logger.error(f'[recv] JSONDecodeError:{e} rawdata={rawdata}')
			return data
	elif parts > 1:
		data = []
		splits = [k for k in re.finditer('}{', rawdata)]
		startpos=0
		idx = 0
		for rawsplit in splits:
			rawcheck, datapartcheck = False, False
			endpos = rawsplit.span()[0] + 1
			datapart = rawdata[startpos:endpos]
			rawcheck = datapart[0] == '{' and datapart[-1] == '}'
			datapartcheck = datapart.count('{') == datapart.count('}')
			if rawcheck and datapartcheck:
				jsondata = None
				try:
					jsondata = json.loads(datapart)
				except json.decoder.JSONDecodeError as e:
					logger.error(f'[recv] idx={idx} d={len(data)} rc:{rawcheck} dc:{datapartcheck} JSONDecodeError:{e} parts={parts} startpos={startpos} endpos={endpos} datapart={datapart} rawdata={rawdata}')				
				if jsondata:
					data.append(jsondata)
					idx += 1
			else:
				if idx >= 1:
					logger.warning(f'[recv] rawcheck2 fail idx={idx} d={len(data)} rc:{rawcheck} dc:{datapartcheck}  parts={parts} startpos={startpos} endpos={endpos} rwsplit={rawsplit} datapart={datapart} rawdata={rawdata}')
			startpos = rawsplit.span()[1] - 1
		return data
	else:
		logger.warning(f'[recv] d={len(data)} parts={parts} rawcheck={rawcheck} rawdata={rawdata}')
	#logger.info(f'[recv] d={len(data)} parts={parts} rawcheck={rawcheck} rawdata={rawdata}')
	return None
	# elif rawdata.count('{') + rawdata.count('}') > 4:
	# 	# parts = int(rawdata.count('{') + rawdata.count('}') / 2)
	# 	#len(rawdata.split('}{'))
	# 	rawsplit = ['{'+k.replace('{','').replace('}','')+'}' for k in rawdata.split('}{')]
	# 	for rs in rawsplit:
	# 		#logger.info(f'raw={len(rawsplit)} rs={rs}')
	# 		try:
	# 			data.append(json.loads(rs))
	# 		except json.decoder.JSONDecodeError as e:
	# 			logger.warning(f'[recv]JSONDecodeError:{e} d:{len(data)}  rawdata={rawdata}')

	# 	rs1 = rawdata.split('}{')[0]+'}'
	# 	rs2 = '{'+rawdata.split('}{')[1]
	# 	data.append(json.loads(rs1))
	# 	data.append(json.loads(rs2))
	# elif rawdata.count('{') + rawdata.count('}') == 4:
	# 	rs1 = rawdata.split('}{')[0]+'}'
	# 	rs2 = '{'+rawdata.split('}{')[1]+'}'
	# 	rs3 = '{'+rawdata.split('}{')[2]
	# 	data.append(json.loads(rs1))
	# 	data.append(json.loads(rs2))
	# 	data.append(json.loads(rs3))
	# elif rawdata.count('{') + rawdata.count('}') > 7:
	# 	rs1 = rawdata.split('}{')[0]+'}'
	# 	data.append(json.loads(rs1))
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

