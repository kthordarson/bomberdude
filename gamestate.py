import copy
import arcade
import random
from loguru import logger
from constants import EXTRA_HEALTH, TILE_SCALING
import time
from queue import Queue, Empty
from dataclasses import dataclass
from utils import gen_randid
from objects import Upgrade


@dataclass
class GameState:
	# player_states: List[PlayerState]
	game_seconds: int = 0
	cjsonupdate: int = 0

	def __repr__(self):
		return f'Gamestate (gs:{self.game_seconds} events:{len(self.game_events)} counters = chkpc: {self.chkp_counter} ugsc: {self.ugs_counter} tojc: {self.toj_counter} fjc: {self.fj_counter} players:{len(self.players)})'

	def __init__(self, game_seconds=0, debug=False, mapname=None):
		self.mapname = mapname
		self.players = {}
		# self.player_states = player_states
		self.game_seconds = game_seconds
		self.debug = debug
		self.debugmode_trace = False
		self.game_events = []
		self.event_queue = Queue()
		self.raw_event_queue = Queue()
		# debugstuff
		self.chkp_counter = 0
		self.ugs_counter = 0
		self.toj_counter = 0
		self.fj_counter = 0
		self.layer_options = {
			"Particles": {"use_spatial_hash": True},
			"Flames": {"use_spatial_hash": True},
			"Bullets": {"use_spatial_hash": True},
			"Netplayers": {"use_spatial_hash": True},
			"Upgrades": {"use_spatial_hash": True},
			"Bombs": {"use_spatial_hash": True},
			"Players": {"use_spatial_hash": True},
			"Blocks": {"use_spatial_hash": True},
			"Walls": {"use_spatial_hash": True},
			"Background": {"use_spatial_hash": True},}

	def load_tile_map(self, mapname):
		self.mapname = mapname
		self.tile_map = arcade.load_tilemap(self.mapname, layer_options=self.layer_options, scaling=TILE_SCALING, use_spatial_hash=True)
		for block in self.tile_map.sprite_lists['Blocks']:
			block.hit_count = 0
		self.scene = arcade.Scene.from_tilemap(self.tile_map)
		logger.debug(f'loading {self.mapname} done')

	def get_players(self, skip):
		for p in self.players:
			if p == skip:
				pass
			else:
				playerdata = self.players[p]
				yield {'client_id':p, 'playerdata':playerdata}

	def check_players(self):
		self.chkp_counter += 1
		dt = time.time()
		playerscopy = copy.copy(self.players)
		# old_len = len(self.players)
		# pops = []
		for p in playerscopy:
			dt_diff = dt - self.players[p].get('msg_dt',0)
			# playerhealth = self.players[p].get('health',0)
			if dt_diff > 10:  # player timeout
				self.players[p]['timeout'] = True
				self.event_queue.put_nowait({'event_time':0, 'event_type':'playerquit', 'client_id': p, 'reason':'timeout','eventid': gen_randid()})  # update other clients about playerquit
				if not self.players[p]['timeout']:
					logger.info(f'player timeout {p} dt_diff={dt_diff} selfplayers={self.players}')

	def create_upgrade_block(self,upgradetype, blkpos):
		match upgradetype:
			case 1:
				upgrade = Upgrade(upgradetype, 'data/heart.png', blkpos, scale=0.8, timer=2000)
			case 2:
				upgrade = Upgrade(upgradetype, 'data/bombpwr.png', blkpos, scale=0.8, timer=1500)
			case 3:
				upgrade = Upgrade(upgradetype, 'data/bomb2.png', blkpos, scale=0.8, timer=3000)
			case _:
				upgrade = Upgrade(upgradetype, 'data/skull.png', blkpos, scale=0.8, timer=5000)
				logger.warning(f'unknown upgradetype {upgradetype=} {blkpos=}')
		return upgrade

	def update_game_state(self, clid, msg):
		self.ugs_counter += 1
		self.game_seconds += 1
		if self.debugmode_trace:
			logger.debug(f' from: {clid} msg={msg}')
		msghealth = msg.get('health')
		msgtimeout = msg.get('timeout')
		msgkilled = msg.get('killed')
		playerdict = {
			'client_id':clid,
			'name': msg.get('name', 'ugsmissing'),
			'position': msg.get('position'),
			'angle': msg.get('angle'),
			'score': msg.get('score'),
			'health': msghealth,
			'msg_dt': msg.get('msg_dt'),
			'timeout': msgtimeout,
			'killed': msgkilled,
			'msgsource': 'update_game_state',
			'bombsleft': msg.get('bombsleft'),

		}
		self.players[clid] = playerdict
		# game_events = msg.get('game_events', None)
		# if game_events:
		# self.game_events = []

	def update_game_events(self, msg):
		game_event = msg.get('game_events')
		event_type = game_event.get('event_type')
		game_event['event_time'] += 1
		eventid = game_event.get('eventid')
		evntchk = [k for k in self.game_events if k.get('eventid') == eventid]
		if len(evntchk) > 0:
			logger.warning(f'dupeevntchk {len(evntchk)} eventid {eventid} {game_event} already in game_events')  # :  msg={msg} selfgameevents:{self.game_events}')
		match event_type:
			# logger.debug(f'self.game_events={self.game_events}')
			case 'playerquit':  # playerquit
				clid = game_event['client_id']
				self.players[clid]['playerquit'] = True
				self.event_queue.put_nowait(game_event)  # update other clients about playerquit
			case 'newconnection':
				game_event['handled'] = True
				game_event['handledby'] = 'ugsnc'
				game_event['event_type'] = 'acknewconn'
				clid = game_event['client_id']
				name = game_event['name']
				self.players[clid] = {'client_id':clid, 'name': name,'timeout':False,'msg_dt':time.time(),}
				self.event_queue.put_nowait(game_event)
				if self.debug:
					logger.info(f'{event_type} from {clid} {name}')
			case 'blkxplode':  # todo make upgradeblock here....
				# game_event['handled'] = True
				uptype = random.choice([1,2,3])
				newevent = {'event_time':0, 'event_type': 'upgradeblock', 'client_id': game_event.get("client_id"), 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
				self.event_queue.put_nowait(newevent)
				if self.debug:
					logger.info(f'{event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
			case 'takeupgrade':  # todo decide on somethingsomething..
				game_event['handledby'] = 'ugstakeupgrade'
				upgradetype = game_event.get("upgradetype")
				clid = game_event['client_id']
				match upgradetype:
					case 1:  # extra health
						self.players[clid]['health'] += EXTRA_HEALTH
						logger.debug(f'{clid} got extrahealth -> {self.players[clid].get("health")}')
						event = {'event_time':0, 'event_type': 'extrahealth', 'amount':EXTRA_HEALTH, 'client_id': clid, 'eventid': gen_randid()}
						self.event_queue.put_nowait(event)
					case 2:  # extra bomb
						self.players[clid]['bombsleft'] += 1
						logger.debug(f'{clid} got extrabomb -> {self.players[clid].get("bombsleft")}')
						event = {'event_time':0, 'event_type': 'extrabomb', 'client_id': clid, 'eventid': gen_randid()}
						self.event_queue.put_nowait(event)
					case 3:  # bigger bomb
						pass
					case _:
						logger.warning(f'unknown upgradetype {upgradetype=} {msg=}')
			case 'bombdrop':  # decide on somethingsomething..
				game_event['handledby'] = 'ugsbomb'
				bomber = game_event.get("bomber")
				eventid = game_event.get('eventid')
				name = self.players[bomber]['name']
				if self.players[bomber].get("bombsleft") > 0:
					game_event['event_type'] = 'ackbombdrop'
					self.players[bomber]['bombsleft'] -= 1
					self.event_queue.put_nowait(game_event)
					if self.debug:
						logger.debug(f'{event_type} from {name=} {bomber} {eventid=} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')
				else:
					if self.debug:
						logger.debug(f'nobombsleft ! {event_type} {name=}  from {bomber} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')

			case 'bulletfired':  # decide on somethingsomething..
				game_event['handledby'] = 'ugsbomb'
				# shooter = game_event.get("shooter")
				# if self.players[bomber].get("bulletsleft")>0:  # maybe ?
				# self.players[bomber]['bulletsleft'] -= 1
				game_event['event_type'] = 'ackbullet'
				self.event_queue.put_nowait(game_event)
				if self.debug:
					pass  # logger.debug(f'{event_type} from {shooter}')
			case 'bombxplode':  # decide on somethingsomething..
				game_event['handledby'] = 'ugsbomb'
				game_event['event_type'] = 'ackbombxplode'
				eventid = game_event.get('eventid')
				bomber = game_event.get("bomber")
				self.players[bomber]['bombsleft'] += 1
				self.event_queue.put_nowait(game_event)
				if self.debug:
					logger.debug(f'{event_type} from {bomber}  bl={self.players[bomber].get("bombsleft")} {eventid=}')
			case 'playerkilled':  # increase score for dmgfrom
				dmgfrom = game_event.get("dmgfrom")
				dmgto = game_event.get("dmgto")
				self.players[dmgfrom]['score'] += 1
				game_event['handled'] = True
				game_event['handledby'] = 'ugskill'
				self.event_queue.put_nowait(game_event)
				if self.debug:
					logger.debug(f'{event_type} {dmgfrom=} {dmgto=} {self.players[dmgfrom]}')
			case 'takedamage':  # increase score for dmgfrom
				dmgfrom = game_event.get("dmgfrom")
				dmgto = game_event.get("dmgto")
				damage = game_event.get("damage")
				self.players[dmgto]['health'] -= damage
				game_event['handled'] = True
				game_event['handledby'] = 'ugskill'
				self.players[dmgfrom]['score'] += 1
				if self.players[dmgto]['health'] > 0:
					game_event['event_type'] = 'acktakedamage'
					self.players[dmgfrom]['score'] += 1
					logger.info(f'{event_type} {dmgfrom=} {dmgto=} killerscore={self.players[dmgfrom]["score"]}')
				else:
					self.players[dmgfrom]['score'] += 10
					game_event['event_type'] = 'dmgkill'
					game_event['killtimer'] = 5
					game_event['killstart'] = game_event.get("msg_dt")
					logger.debug(f'{event_type} {dmgfrom=} {dmgto=} ')
				self.event_queue.put_nowait(game_event)

			case 'respawn':  # increase score for dmgfrom
				clid = game_event.get("client_id")
				self.players[clid]['health'] = 100
				self.players[clid]['killed'] = False
				game_event['handled'] = True
				game_event['handledby'] = 'ugsrspwn'
				game_event['event_type'] = 'ackrespawn'
				self.event_queue.put_nowait(game_event)
				# if self.debug:
				logger.debug(f'{event_type} {clid=} {self.players[clid]}')
			case 'getmap':  # send map to client
				clid = game_event.get("client_id")
				payload = {'msgtype': 'scenedata', 'payload':self.scene}
				logger.info(f'{event_type} from {clid} {len(payload)} {game_event=}')
				# await sockpush.send(payload)
				# game_event['event_type'] = 'ackgetmap'
				# game_event['payload'] = pickle.dumps(self.scene)
				# self.raw_event_queue.put_nowait(pickle.dumps(self.tile_map))
			case _:
				logger.warning(f'unknown game_event:{event_type} from msg={msg}')
		# elif game_event.get('handled') == True:
		# 	logger.warning(f'game_event already handled: {game_event} msg={msg}')

	def to_json(self):
		self.toj_counter += 1
		dout = {'players':{}, 'game_events': []}
		try:
			pending_event = self.event_queue.get_nowait()
			self.event_queue.task_done()
			dout['game_events'].append(pending_event)
		except Empty:
			pass
		for player in self.players:
			playerdict = {
				'client_id':player,
				'name': self.players[player].get('name', 'fjmissing'),
				'position': self.players[player].get('position', (0,0)),
				'angle': self.players[player].get('angle',0),
				'health': self.players[player].get('health',0),
				'msg_dt': self.players[player].get('msg_dt',time.time()),
				'timeout': self.players[player].get('timeout',False),
				'killed': self.players[player].get('killed', False),
				'score': self.players[player].get('score',0),
				'bombsleft': self.players[player].get('bombsleft',0),
				'msgsource': 'to_json',
			}
			dout['players'][player] = playerdict  # Q = playerdict
		return dout

	def from_json(self, dgamest):
		self.fj_counter += 1
		for ge in dgamest.get('game_events', []):
			if ge == []:
				break
			if self.debug:
				logger.info(f'ge={ge.get("event_type")} dgamest={dgamest=}')
			self.event_queue.put_nowait(ge)
		plist = dgamest.get('players',[])
		for player in plist:
			if plist.get(player).get('timeout'):
				pass  # logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			elif plist.get(player).get('killed'):
				pass  # logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			else:
				self.players[plist.get(player).get('client_id')] = plist.get(player)
				# logger.info(f'player={player} dgamest={dgamest} selfplayers={self.players}')
		if self.debug:
			pass  # logger.debug(f'dgamest={dgamest}')# gs={self.game_seconds} selfplayers={self.players}')
