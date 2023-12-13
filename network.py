import json
import re
from queue import Queue
from threading import Thread
import re
from loguru import logger

from globals import gen_randid
from constants import PKTLEN

def packet_parser(rawdata):
	results = []
	rawdata_sock = re.sub('^0+','',rawdata)
	# try:
	# 	rawdata_sock = rawdata[rawdata.index('{'):]
	# except (AttributeError, ValueError) as e:
	# 	logger.error(f'[recv] {e} {type(e)} rawdata:\n\n{rawdata}\n{type(rawdata)}\n')
	# 	results.append({'msgtype': 'parsererror', 'rawdata': rawdata})
	# except TypeError as e:
	# 	logger.error(f'[recv] {e} {type(e)} rawdata:\n\n{rawdata}\n{type(rawdata)}\n')
	#	results.append({'msgtype': 'parsererror', 'rawdata': rawdata})
	if rawdata_sock.count('{') + rawdata_sock.count('}') == 2:
		# logger.info(f'rawdatasock {len(rawdata_sock)} {type(rawdata_sock)}: {rawdata_sock}\nrawdata {len(rawdata)} {type(rawdata)}: {rawdata}\n')
		results.append(rawdata_sock)
		return results
	if rawdata_sock.count('{') + rawdata_sock.count('}') < 2:
		logger.warning(f'parsererrorcnt\nrs: {rawdata_sock}\nraw: {rawdata}\n')
		results.append({'msgtype': 'parsererror'})
		return results
	if rawdata_sock.count('{') + rawdata_sock.count('}') >= 2: #rawdata_sock.count('}{') >= 2:
		rawsplit = rawdata_sock.split('}{') # .strip('}').strip('{')
		for rawpart in rawsplit:
			if len(rawpart) == 0:
				break
			else:
				msgtype = None
				try:
					if rawpart[0] != '{':
						rawpart = '{' + rawpart
					if rawpart[-1] != '}':
						rawpart = rawpart + '}'
				except IndexError as e:
					logger.error(f'{e} rawp:\n{rawpart}\nsplit:\n{rawsplit}\nrawdata_sock:\n{rawdata_sock}')
					results.append({'msgtype': 'parserindexerror'})
				if not 'msgtype' in rawpart:
					# logger.error(f'NO msgtype rawp: {rawpart}\nsplit {len(rawsplit)} {type(rawsplit)}:\n{rawsplit[:100]}\nrawdata_sock {type(rawdata_sock)}:\n{rawdata_sock[:100]}\n\n')
					results.append({'msgtype': 'parsermissingmsg'})
					break
				if rawpart.count('msgtype') != 1:
					logger.error(f'msgtypecount! rawp:\n{rawpart}\nsplit:\n{rawsplit}\nrawdata_sock:\n{rawdata_sock}')
					results.append({'msgtype': 'parsertyperrormsgtypecount'})
					break
				if len(rawpart) < 10:
					results.append({'msgtype': 'parserpartlen'})
					break
				try:
					msgtype = json.loads(rawpart).get('msgtype')
				except TypeError as e:
					logger.error(f'TypeError {e} rawp: {rawpart}\nsplit: {rawsplit}\nrawdata_sock: {rawdata_sock}\n')
					results.append({'msgtype': 'parsertyperror'})
				except json.decoder.JSONDecodeError as e:
					if 'Expecting' in str(e) or 'Unterminated' in str(e):
						logger.warning(f'JSONDecodeError {e} rawp {len(rawpart)} :\n{rawpart}\nsplit:\n{rawsplit} rawdata_sock:\n{rawdata_sock}')
						results.append({'msgtype': 'parserjsonerror'})
						break
					else:
						logger.error(f'JSONDecodeError {e} rawp:\n{rawpart}\nsplit:\n{rawsplit} rawdata_sock:\n{rawdata_sock}')
						results.append({'msgtype': 'parserjsonerror'})
						break
				except Exception as e:
					logger.error(f'unhandled {e} {type(e)} rawdata_sock: {rawdata_sock}')
					results.append({'msgtype': 'parsererror', 'errorpayload' : 'unknown'})
					break
				if msgtype:
					if msgtype == 's_ping':
						# logger.info(f's_ping: {rawdata}')
						results.append(rawpart)
					elif msgtype == 'cl_newplayer':
						logger.info(f'newplayer {rawpart}')
						results.append(rawpart)
					elif msgtype == 'bcsetclid':
						logger.info(f'bcsetclid {rawpart}')
						results.append(rawpart)
					elif msgtype == 'msgokack':
						# pass
						# logger.info(f'msgokack {rawdata}')
						results.append(rawpart)
					elif msgtype == 'cl_playerpos':
						# logger.info(f'cl_playerpos {rawpart}')
						results.append(rawpart)
					elif msgtype == 'cl_playermove':
						# logger.info(f'cl_playerpos {rawpart}')
						results.append(rawpart)
					elif msgtype == 'gamemsg':
						results.append(rawpart)
						# logger.info(f'cl_playerpos {rawpart}')
					else:
						logger.warning(f'unknownmsgtype {msgtype} rawpart: {rawpart} rawsplit: {rawsplit} rawdata_sock: {rawdata_sock}')
						results.append({'msgtype': 'unknownmsgtype'})
						# return {'msgtype': 'parserunknownmsgtype', 'unknownpart': msgtype, 'rawpart': rawpart, 'rawsplit': rawsplit}
		return results


def send_data(conn, payload, pktid):
	# if isinstance(payload, str):
	# 	payload = json.loads(payload)
	# try:
	# 	payload['pktid'] = pktid
	# except TypeError as e:
	# 	logger.error(f'[sd] {e} {type(e)} payload={payload} {type(payload)}')
	# 	return
	try:
		data = json.dumps(payload).encode('utf-8')
	except TypeError as e:
		logger.error(f'[sd] TypeError:{e} payload:{payload} {type(payload)}')
		return
	# logger.debug(f'[sd] c: {conn} dpl: {len(data)} {type(data)}\n{data}\n')
	data = data.zfill(PKTLEN)
	conn.sendall(data)

def old_receive_data(conn):
	if not conn:
		return None
	rid = None
	data = []
	rawdata = None
	try:
		rawdata = conn.recv(PKTLEN).decode('utf-8')
		logger.debug(f'[r] {len(rawdata)} {type(rawdata)}\n{rawdata}\n')
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
		self.receivecount = 0
		self.client_id = client_id
		self.socket = socket

	def __repr__(self):
		return f'Receiver({self.s_type} clid={self.client_id} count={self.receivecount} sq:{self.queue.qsize()})'

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
				rawdata_sock = self.socket.recv(PKTLEN).decode('utf-8')
				self.receivecount += 1
				# logger.debug(f'rcnt: {self.receivecount} raw {len(rawdata_sock)} {type(rawdata_sock)}\nr:{rawdata_sock}\n\n')
			except OSError as e:
				logger.error(f'[recv] {self} OSError:{e} ')
			if rawdata_sock:
				# logger.debug(f'raw {len(rawdata_sock)}\n\nr:{rawdata_sock}\n\n')
				rawdata = packet_parser(rawdata_sock)
				# logger.debug(f'rawparsed: {len(rawdata)}\n\n{rawdata}\n\n')
				try:
					for rawpart in rawdata:
						if len(rawpart) > 1:
							# logger.debug(f'rawpart: {len(rawpart)}\n{rawpart}\n')
							self.queue.put(rawpart)
						# data = json.dumps({'msgtype':'msgokack', 'client_id':self.client_id}).encode('utf-8')
						# self.socket.sendall(data)
				except TypeError as e:
					logger.error(f'[recv] {self} TypeError:{e} rawdata:{rawdata} {type(rawdata)} rawdata_sock: {rawdata_sock}')

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
					self.queue.task_done()
				except (TypeError, ValueError) as e:
					logger.error(f'senderrunqueue {e} {type(e)}')
				try:
					# send_data(self.socket, payload=payload, pktid=gen_randid())
					send_data(conn=conn, payload=payload, pktid=gen_randid())
					self.sendcount += 1
				except BrokenPipeError as e:
					logger.warning(f'{self} {e} conn:{conn} payload:{payload} q: {self.queue.qsize()}')
					self.queue = Queue()
					# return
					# raise(e)
				# 	self.queue = Queue()
				except ConnectionResetError as e:
					logger.error(f'{self} senderr {e}')
					self.kill = True
					break
