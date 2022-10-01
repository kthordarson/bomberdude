import pygame
import struct
import socket
import sys
from loguru import logger
from threading import Thread

# from things import Block
from constants import GRIDSIZE, FPS
from map import Gamemap
from globals import gen_randid
from network import receive_data, send_data, dataid

from queue import Queue

class Sender(Thread):
	def __init__(self, client_id):
		Thread.__init__(self)
		self.kill = False
		self.queue = Queue()
		self.sendcount = 0
		self.client_id = client_id
		logger.info(f'[BC] {self} senderthread init')

	def __str__(self):
		return f'[sender] clid={self.client_id} count={self.sendcount} sq:{self.queue.qsize()}'

	def set_clid(self, clid):
		self.client_id = clid
		logger.info(f'{self} set_clid {clid}')

	def run(self):
		logger.info(f'{self} run')
		while True:
			if self.kill:
				logger.warning(f'{self} killed')
				break
			if not self.queue.empty():
				conn, payload = self.queue.get()
				# logger.debug(f'{self} senderthread sending payload:{payload}')
				try:
					# send_data(conn, payload={'msgtype':'bcnetupdate', 'payload':payload})
					send_data(conn, payload)
				except (BrokenPipeError, ConnectionResetError) as e:
					logger.error(f'{self} senderr {e}')
					self.kill = True
					break
				self.sendcount += 1
				# self.queue.task_done()

class Servercomm(Thread):
	def __init__(self, serverqueue=None):
		Thread.__init__(self)
		self.kill = False
		self.serverqueue = serverqueue
		self.queue = Queue()
		self.netplayers = {}
		self.srvcount = 0
		logger.info(f'[BC] {self} server_comm init')

	def __str__(self):
		return f'[scomm] count={self.srvcount} np={len(self.netplayers)} sq:{self.queue.qsize()}'

	def run(self):
		logger.info(f'{self} server_comm run')
		while True:
			if self.kill:
				logger.warning(f'{self} server_comm killed')
				break
			payload = None
			if not self.queue.empty():
				payload = self.queue.get()
				self.srvcount += 1
				if payload:
					if payload.get('msgtype') == 'netplayers':
						netplayers = payload.get('netplayers')
						for np in netplayers:
							self.netplayers[np] = netplayers[np]
					elif payload.get('msgtype') == 'netbomb':
						#logger.debug(f'{self} bomb payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'netgrid':
						#logger.debug(f'{self} bomb payload:{payload}')
						self.serverqueue.put(payload)
					elif payload.get('msgtype') == 'clientquit':
						logger.debug(f'{self} quit payload:{payload}')
						self.serverqueue.put(payload)
				#logger.debug(f'{self} payload:{payload}')


class BombClientHandler(Thread):
	def __init__(self, conn=None,  addr=None, gamemap=None, srvcomm=None):
		Thread.__init__(self)
		self.queue = Queue()
		self.sendq = Queue() # multiprocessing.Manager().Queue()
		self.client_id = None
		self.kill = False
		self.conn = conn
		self.addr = addr
		self.netplayers = {}
		self.pos = (0,0)
		self.centerpos = (0,0)
		self.gamemap = gamemap
		self.sender = Sender(client_id=self.client_id)
		self.srvcomm = srvcomm #Servercomm(self.queue)
		self.start_time = pygame.time.get_ticks()
		self.lastupdate = self.start_time
		self.maxtimeout = 300
		logger.info(f'[BC] {self} BombClientHandler init conn:{self.conn} addr:{self.addr} client_id:{self.client_id}')

	def __str__(self):
		return f'[BCH] {self.client_id} t:{pygame.time.get_ticks()-self.start_time} l:{self.lastupdate} sq:{self.queue.qsize()} sqs:{self.sendq.qsize()} {self.sender} {self.srvcomm}'

	def quitplayer(self, quitter):
		logger.info(f'{self} quitplayer quitter:{quitter}')
		if quitter == self.client_id:
			self.kill = True
			self.sender.kill = True
			self.conn.close()

	def send_map(self):
		logger.info(f'{self} send_map')
		payload = {'msgtype':'mapfromserver', 'gamemapgrid':self.gamemap.grid, 'data_id':dataid['gamegrid']}
		#self.sender.send(self.conn, payload)
		self.sender.queue.put_nowait((self.conn, payload))

	def gridupdate(self, data):
		logger.debug(f'{self} griddata:{len(data)}')
		self.sender.queue.put_nowait((self.conn, data))

	def bombevent(self, data):
		logger.debug(f'{self} bombevent bomber:{data.get("client_id")} pos:{data.get("bombpos")}')
		self.sender.queue.put_nowait((self.conn, data))

	def get_client_id(self):
		payload = {'msgtype':'bcgetid', 'payload':'sendclientid', 'data_id':dataid['getid']}
		self.sender.queue.put_nowait((self.conn, payload))
		logger.debug(f'{self} sent payload:{payload}')
		#self.sender.send(self.conn, payload)
		rid, resp = None, None
		try:
			resp = receive_data(self.conn)
			rid = resp.get('data_id')
			if resp or rid:
				logger.debug(f'{self} rid:{rid} resp:{resp}')
				clid = resp.get('client_id')
				self.client_id = clid
				self.sender.set_clid(clid)
				#logger.info(f'{self} rid:{rid} resp:{resp}')
				if resp == 'reqmap':
					self.send_map()
		except (ConnectionResetError, BrokenPipeError, struct.error, EOFError) as e:
			logger.error(f'{self} receive_data error:{e}')
		#self.sendq.put_nowait(payload)

	def run(self):
		self.get_client_id()
		logger.debug(f'[BC] {self.client_id} run ')
		#st = Thread(target=self.sender, daemon=True)
		#st.start()
		#srvcomm = Thread(target=self.server_comms, daemon=True)
		#srvcomm.start()
		self.sender.start()
		#self.srvcomm.start()
		while True:
			self.netplayers = self.srvcomm.netplayers
			# logger.debug(f'{self} np={self.netplayers}')
			if self.client_id is None:
				self.get_client_id()
			rid, resp = None, None
			if self.kill or self.sender.kill:
				logger.debug(F'{self} killed')
				self.sender.kill = True
				self.kill = True
				self.conn.close()
				break
			#if len(self.netplayers) >= 1:
			payload = {'msgtype':dataid['netplayers'], 'client_id':self.client_id, 'netplayers':self.netplayers, 'data_id':dataid['netplayers']}
			self.sender.queue.put_nowait((self.conn, payload))
			try:
				resp = receive_data(self.conn)
				
				# logger.debug(f'{self} rid:{rid} resp:{resp}')
			except (ConnectionResetError, BrokenPipeError, struct.error, EOFError, OSError) as e:
				logger.error(f'{self} receive_data error:{e}')
				self.conn.close()
				self.kill = True
				break
			rtype = None
			if resp:
				self.lastupdate = pygame.time.get_ticks()
				rid = resp.get('data_id')
				rtype = dataid.get(rid, None)
			if rid == dataid.get('info') or rid == 0:
				self.srvcomm.queue.put({'msgtype':'playerpos', 'client_id':self.client_id, 'pos':self.pos, 'centerpos':self.centerpos})
			elif rtype == dataid.get('playerpos') or rid == 3:
				#logger.debug(f'{self} {rtype} {rid} {resp}')
				s_clid = resp.get('client_id')
				s_pos = resp.get('pos')
				c_pos = resp.get('centerpos')
				#logger.debug(f"[BC] {self} playerpos {s_clid} {s_pos} {self.pos}")
				self.pos = s_pos
				self.centerpos = c_pos
				posmsg = {'msgtype':'playerpos', 'client_id':s_clid, 'pos':s_pos, 'centerpos':c_pos}
				self.srvcomm.queue.put(posmsg)
			elif rtype == dataid.get('update') or rid == 4:
				pass
				# logger.debug(f'{self} received id:{rid} resp={resp}')
			elif rtype == dataid['reqmap'] or rid == 7:
				self.send_map()
			elif rtype == dataid['gridupdate'] or rid == 12:
				# new grid and send update to clients
				senderid = resp.get('client_id')
				newgrid = resp.get('gamemapgrid')
				gridmsg = {'msgtype': 'netgrid', 'client_id': senderid, 'gamemapgrid': newgrid, 'data_id': dataid['gridupdate']}
				self.srvcomm.queue.put(gridmsg)
				#self.gamemap.grid = newgrid
				#self.send_map()
				logger.debug(f'{self} gridupdate senderid:{senderid} newgrid:{len(newgrid)}')

			elif rtype == dataid.get('gameevent') or rid == 9:
				logger.debug(f'{self} gamevent received id:{rid} resp={resp}')
			elif rtype == dataid['gridupdate'] or rid == 12:
				# new grid and send update to clients
				senderid = resp.get('client_id')
				newgrid = resp.get('gamemapgrid')
				gridmsg = {'msgtype': 'netgrid', 'client_id': senderid, 'gamemapgrid': newgrid, 'data_id': dataid['gridupdate']}
				self.srvcomm.queue.put(gridmsg)
				#self.gamemap.grid = newgrid
				#self.send_map()
				logger.debug(f'{self} gridupdate senderid:{senderid} newgrid:{len(newgrid)}')
			elif rtype == dataid.get('netbomb') or rid == 14:
				updatemsg = {'msgtype':'netbomb', 'client_id':self.client_id, 'bombpos':resp.get('bombpos'), 'data_id':dataid['netbomb']}
				self.srvcomm.queue.put(updatemsg)

			elif rtype == dataid.get('clientquit') or rid == 16:
				qmsg = {'msgtype':'clientquit', 'client_id':self.client_id}
				self.srvcomm.queue.put(qmsg)

			elif rtype == dataid['auth'] or rid == 101:
				logger.debug(f'{self} auth received id:{rid} resp={resp}')
				clid = resp.get('client_id')
				self.client_id = clid
			elif rtype == dataid['UnpicklingError'] or rid == 1002:
				logger.warning(f'{self} UnpicklingError rid:{rid}')
			else:
				if resp:
					logger.warning(f'{self} unknownevent rid:{rid} rtype:{rtype}  resp={len(resp)} resp={resp}')
				else:
					pass
					#logger.error(f'{self} unknownevent noresp rid:{rid} rtype:{rtype}  resp={type(resp)}')

class BombServer(Thread):
	def __init__(self):
		Thread.__init__(self, daemon=True)
		self.bombclients  = []
		self.gamemap = Gamemap()
		self.kill = False
		self.queue = Queue() # multiprocessing.Manager().Queue()
		self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.netplayers = {}

	def run(self):
		logger.debug(f'[server] run')
		#self.srvcomm.start()
		while not self.kill:
			for bc in self.bombclients:
				if bc.client_id:
					np = {'client_id':bc.client_id, 'pos':bc.pos, 'centerpos':bc.centerpos,'kill':bc.kill}
					self.netplayers[bc.client_id] = np
					payload = {'msgtype':'netplayers', 'netplayers':self.netplayers}
					bc.srvcomm.queue.put(payload)
					if pygame.time.get_ticks()-bc.lastupdate > 3000:
						bc.kill = True
						bc.netplayers[bc.client_id] = {'kill':True}
						self.netplayers[bc.client_id] = {'kill':True}
						logger.warning(f'[server] {bc} timeout')						
						self.bombclients.pop(self.bombclients.index(bc))
				else:
					logger.warning(f'[server] {bc} no client_id')
			if self.kill:
				logger.debug(f'[server] killed')
				for c in self.bombclients:
					logger.debug(f'[server] killing {c}')
					c.kill = True
				break
			if not self.queue.empty():
				data = self.queue.get()
				# logger.debug(f'[server] getq data:{data}')
				type = data.get('msgtype')
				# self.queue.task_done()
				if type == 'newclient':
					# logger.debug(f'[server] q: {data}')
					conn = data.get('conn')
					addr = data.get('addr')
					# clid = data.get('clid')
					srvcomm = Servercomm(serverqueue=self.queue)
					bc = BombClientHandler(conn=conn, addr=addr, gamemap=self.gamemap, srvcomm=srvcomm)
					srvcomm.start()
					logger.debug(f'[server] new player:{bc} cl:{len(self.bombclients)}')
					self.bombclients.append(bc)
					bc.start()
				elif type == 'playerpos':
					for bc in self.bombclients:
						clid = data.get('client_id')
						pos = data.get('pos')
						centerpos = data.get('centerpos')
						ckill = data.get('kill')
						if clid != bc.client_id:
							np = {'pos':pos, 'centerpos':centerpos, 'kill':ckill}
							bc.netplayers[clid] = np
							self.netplayers[clid] = np
						if ckill:
							bc.kill = True
							logger.warning(f'[server] {bc} kill')
							bc.netplayers[clid] = {'kill':True}
							self.netplayers[clid] = {'kill':True}
				elif type == 'netplayers':
					pass
				elif type == 'netbomb':
					logger.debug(f'[server] netbomb from {data.get("client_id")} pos={data.get("bombpos")}')
					for bc in self.bombclients:
						bc.bombevent(data)
				elif type == 'netgrid':
					self.gamemap.grid = data.get('gamemapgrid')
					# logger.debug(f'[server] netgrid {len(data)}')
					for bc in self.bombclients:
						bc.gridupdate(data)
				elif type == 'clientquit':
					logger.debug(f'[server] quit {data}')
					quitter = data.get('client_id')
					for bc in self.bombclients:
						bc.quitplayer(quitter)
				else:
					logger.warning(f'[server] data={data}')


def main():
	pygame.init()
	mainthreads = []
	key_message = 'bomberdude'
	logger.debug(f'[bombserver] started')
	clients = 0
	# serverq = Queue()
	server = BombServer()
	server.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server.conn.bind(('127.0.0.1', 9696))
	server.conn.listen()
	server.start()
	while True:
		logger.debug(f'[bombserver] waiting for connection clients:{clients}')
		try:
			if server.kill:
				break
			conn, addr = server.conn.accept()
			server.queue.put({'msgtype':'newclient', 'conn':conn, 'addr':addr})
		except KeyboardInterrupt as e:
			server.conn.close()
			logger.warning(f'KeyboardInterrupt:{e} serverq:{server.queue} server:{server}')
			for bc in server.bombclients:
				logger.warning(f'kill bc:{bc}')
				bc.kill = True
				bc.join()
			server.kill = True
			server.join()
			logger.warning(f'kill server:{server}')
			return

if __name__ == '__main__':
	logger.info('start')
	main()
	logger.info('done')
	sys.exit(0)
