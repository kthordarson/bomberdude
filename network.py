import re
import json
from loguru import logger
from queue import SimpleQueue as Queue
from threading import Thread
def send_data(conn=None, payload=None):
	if conn:
		if conn._closed:
			return
	sendcheck = False
	try:
		sendcheck = isinstance(payload, dict) # payload[0] == '{' and payload[-1] == '}'
	except (KeyError, IndexError, TypeError) as e:
		logger.warning(f'[send] err={e} sendcheck={sendcheck} t:{type(payload)} payload={payload}')
		sendcheck = False
	if not sendcheck:
		if isinstance(payload, list):
			sendcheck = isinstance(payload[0], dict)
			payload = payload[0]
	if sendcheck:
		if conn is None:
			logger.error(f'No connection conn:{conn} payload:{payload}')
			return
		if payload is None:
			logger.error('No payload')
			return
		data = json.dumps(payload, skipkeys=True).encode('utf-8')
		try:
			conn.sendall(data)
		except (OSError, BrokenPipeError) as e:
			logger.error(f'[send] BrokenPipeError:{e} conn:{conn} payload:{payload}')
			conn.close()
	else:
		logger.warning(f'[send] bracketsmismatch payload={payload}')

def receive_data(conn):
	if not conn:
		return None
	rid = None
	data = []
	rawdata = None
	try:
		rawdata = conn.recv(9000).decode('utf-8')
	except OSError as e:
		#logger.error(f'[recv] OSError:{e} conn:{conn}')
		return None
	parts = len(rawdata.split('}{'))
	rawcheck = False
	if parts == 1 and len(rawdata)>1: # rawdata.count('{') + rawdata.count('}') == 2 or 'netplayers' in rawdata:
		try:
			rawcheck = rawdata[0] == '{' and rawdata[-1] == '}'
		except (KeyError, IndexError, TypeError) as e:
			logger.warning(f'[recv] err {e} payload={rawdata}')
			rawcheck = False
		if rawcheck:
			try:
				data.append(json.loads(rawdata))
			except json.decoder.JSONDecodeError as e:
				logger.error(f'[recv] JSONDecodeError:{e} rawcheck={rawcheck} data={data} rawlen={len(rawdata)} t:{type(rawdata)} rawdata={rawdata}')
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
					logger.error(f'[recv] idx={idx} d={data} rc:{rawcheck} dc:{datapartcheck} JSONDecodeError:{e} parts={parts} startpos={startpos} endpos={endpos} datapart={datapart} rawdata={rawdata}')				
				if jsondata:
					data.append(jsondata)
					idx += 1
			else:
				if idx >= 1:
					logger.warning(f'[recv] rawcheck2 fail idx={idx} d={data} rc:{rawcheck} dc:{datapartcheck}  parts={parts} startpos={startpos} endpos={endpos} rwsplit={rawsplit} datapart={datapart} rawdata={rawdata}')
			startpos = rawsplit.span()[1] - 1
		return data
	return None


class Sender(Thread):
	def __init__(self, client_id):
		Thread.__init__(self, daemon=True)
		self.kill = False
		self.queue = Queue()
		self.sendcount = 0
		self.client_id = client_id
		logger.info(f'{self} init')

	def __str__(self):
		return f'[sender clid={self.client_id} count={self.sendcount} sq:{self.queue.qsize()}]'

	def run(self):
		logger.info(f'{self} run')
		while not self.kill:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			while not self.queue.empty():
				try:
					conn, payload = self.queue.get()
				except ValueError as e:
					logger.error(f'valueerror {e}')
				#self.queue.task_done()
				# logger.debug(f'{self} senderthread sending payload:{payload}')
				try:
					# send_data(conn, payload={'msgtype':'bcnetupdate', 'payload':payload})
					send_data(conn, payload)
					self.sendcount += 1
				except (BrokenPipeError, ConnectionResetError) as e:
					logger.error(f'{self} senderr {e}')
					self.kill = True
					break				
