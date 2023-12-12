import json
import re
from queue import SimpleQueue as Queue
from threading import Thread

from loguru import logger

from globals import gen_randid

def packet_parser(rawdata_sock):
	results = []
	if rawdata_sock.count('{') + rawdata_sock.count('}') == 2:
		return rawdata_sock
	if rawdata_sock.count('{') + rawdata_sock.count('}') < 2:
		logger.warning(f'parsererror {rawdata_sock}')
		return {'msgtype': 'parsererror0'}
	if rawdata_sock.count('{') + rawdata_sock.count('}') >= 2: #rawdata_sock.count('}{') >= 2:
		rawsplit = rawdata_sock.split('}{') # .strip('}').strip('{')
		for rawpart in rawsplit:
			if isinstance(rawpart, dict):
				logger.info(f'rawpart is dict {rawpart}')
				results.append(rawpart)
			elif isinstance(rawpart, list):
				logger.warning(f'rawpart is list {len(rawpart)}\nrawpart: {rawpart}\n')
				break
			elif isinstance(rawpart, str):
				msgtype = None
				if rawpart[0] != '{':
					rawpart = '{' + rawpart
				if rawpart[-1] != '}':
					rawpart = rawpart + '}'
				if not 'msgtype' in rawpart:
					# logger.error(f'NO msgtype rawp: {rawpart}\nsplit {len(rawsplit)} {type(rawsplit)}:\n{rawsplit[:100]}\nrawdata_sock {type(rawdata_sock)}:\n{rawdata_sock[:100]}\n\n')
					break
					# return {'msgtype': 'parsermissingmsg'}
				if rawpart.count('"') % 2 != 0:
					break
				if rawpart.count('msgtype') != 1:
					logger.error(f'{e} rawp: {rawpart} split: {rawsplit} rawdata_sock: {rawdata_sock}')
					break
					# return {'msgtype': 'parsertomanymsgtype'}
				try:
					msgtype = json.loads(rawpart).get('msgtype')
				except TypeError as e:
					logger.error(f'{e} rawp: {rawpart} split: {rawsplit} rawdata_sock: {rawdata_sock}')
					# return {'msgtype': 'parsertyperror'}
				except json.decoder.JSONDecodeError as e:
					logger.error(f'{e} rawp: {rawpart} split: {rawsplit} rawdata_sock: {rawdata_sock}')
					# return {'msgtype': 'parserjsonerror'}
				except Exception as e:
					logger.error(f'unhandled {e} {type(e)} rawdata_sock: {rawdata_sock}')
					# return {'msgtype': 'parserunhandlederror'}
				if msgtype:
					if msgtype == 's_ping':
						# logger.info(f's_ping: {rawdata}')
						results.append(rawpart)
					elif msgtype == 'cl_newplayer':
						logger.info(f'newplayer {rawpart}')
						results.append(rawpart)
					elif msgtype == 'msgokack':
						pass
						# logger.info(f'msgokack {rawdata}')
						results.append(rawpart)
					elif msgtype == 'cl_playerpos':
						# logger.info(f'cl_playerpos {rawpart}')
						results.append(rawpart)
					elif msgtype == 'cl_playermove':
						# logger.info(f'cl_playerpos {rawpart}')
						results.append(rawpart)
					else:
						logger.warning(f'unknownmsgtype {msgtype} rawpart: {rawpart} rawsplit: {rawsplit} rawdata_sock: {rawdata_sock}')
						# return {'msgtype': 'parserunknownmsgtype', 'unknownpart': msgtype, 'rawpart': rawpart, 'rawsplit': rawsplit}
			else:
				logger.warning(f'unknownraw {type(rawpart)} part: {rawpart} rawsplit: {rawsplit} rawdata_sock: {rawdata_sock}')
		return results


def send_data(conn, payload, pktid):
	if isinstance(payload, str):
		payload = json.loads(payload)
	try:
		payload['pktid'] = pktid
	except TypeError as e:
		logger.error(f'senddata {e} {type(e)} payload={payload} {type(payload)}')
		return
	try:
		data = json.dumps(payload).encode('utf-8')
	except TypeError as e:
		logger.error(f'[send] TypeError:{e} payload:{payload} {type(payload)}')
		return
	conn.sendall(data)

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
				logger.warning(f'[recv] JSONDecodeError:{e} rchk={rawcheck} data:{type(data)} len={len(data)} raw:{type(rawdata)} len={len(rawdata)}')
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


class Receiver(Thread):
	def __init__(self, socket, client_id, s_type):
		Thread.__init__(self, daemon=True)
		self.socket = socket
		self.s_type = s_type
		self.kill = False
		self.queue = Queue()
		self.sendcount = 0
		self.client_id = client_id
		self.socket = socket

	def __repr__(self):
		return f'Receiver({self.s_type} clid={self.client_id} count={self.sendcount} sq:{self.queue.qsize()})'

	def run(self):
		logger.info(f'{self} run')
		while not self.kill:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			rid = None
			data = []
			rawdata_sock = None
			rawdata = None
			jsondata = None
			try:
				rawdata_sock = self.socket.recv(9000).decode('utf-8')
			except OSError as e:
				logger.error(f'[recv] OSError:{e} ')
			if rawdata_sock:
				data = json.dumps({'msgtype':'msgokack', 'client_id':self.client_id}).encode('utf-8')
				self.socket.sendall(data)
				# logger.debug(f'raw {len(rawdata_sock)} r:{rawdata_sock[:100]}')
				rawdata = packet_parser(rawdata_sock)
				try:
					for rawpart in rawdata:
						self.queue.put(rawpart)
				except TypeError as e:
					logger.error(f'[recv] TypeError:{e} rawdata:{rawdata} {type(rawdata)} rawdata_sock: {rawdata_sock}')

class Sender(Thread):
	def __init__(self, client_id, s_type, socket):
		Thread.__init__(self, daemon=True)
		self.s_type = s_type
		self.kill = False
		self.queue = Queue() # put socket and payload here, eg:  sender.queue.put((self.socket, payload))
		self.sendcount = 0
		self.client_id = client_id
		self.socket = socket

	def __repr__(self):
		return f'Sender({self.s_type} clid={self.client_id} count={self.sendcount} sq:{self.queue.qsize()})'


	def run(self):
		logger.info(f'{self} run')
		while not self.kill:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			while not self.queue.empty():
				conn, payload = None, None
				try:
					conn, payload = self.queue.get()
				except (TypeError, ValueError) as e:
					logger.error(f'senderrunqueue {e} {type(e)}')
				#
				try:
					if payload.get('msgtype') != 's_ping':
						pass
						# logger.debug(f'{self} sending type:{type(payload)} payload:{payload} to {conn}')
					send_data(conn, payload=payload, pktid=gen_randid())
					# send_data(conn=conn, payload=payload, pktid=gen_randid())
					self.sendcount += 1
				except BrokenPipeError as e:
					self.queue = Queue()
					return
					# logger.warning(f'{self} {e} conn:{conn} payload:{payload} q: {self.queue.qsize()}')
					# raise(e)
				# 	self.queue = Queue()
				except ConnectionResetError as e:
					logger.error(f'{self} senderr {e}')
					self.kill = True
					break
