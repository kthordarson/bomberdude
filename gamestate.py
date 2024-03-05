import copy
import random
from loguru import logger
from constants import *
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
		return f'Gamestate (gs:{self.game_seconds} log:{len(self.event_log)} counters = chkpc: {self.chkp_counter} ugsc: {self.ugs_counter} tojc: {self.toj_counter} fjc: {self.fj_counter} players:{len(self.players)})'

	def __init__(self, game_seconds=0, debugmode=False, mapname=None):
		self.mapname = mapname
		self.players = {}
		# self.player_states = player_states
		self.game_seconds = game_seconds
		self.debugmode = debugmode
		self.debugmode_trace = False
		self.game_events = []
		self.gs_event_queue = Queue()
		# debugstuff
		self.chkp_counter = 0
		self.ugs_counter = 0
		self.toj_counter = 0
		self.fj_counter = 0
		self.scene = None
		self.tile_map = None
		self.event_log = []
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
			"Background": {"use_spatial_hash": True},
		}

	def load_tile_map(self, mapname):
		self.mapname = mapname
		logger.debug(f'loading {self.mapname}')
		self.tile_map = arcade.load_tilemap(self.mapname, layer_options=self.layer_options, scaling=TILE_SCALING,
		                                    use_spatial_hash=True)
		for block in self.tile_map.sprite_lists['Blocks']:
			block.hit_count = 0
		self.scene = arcade.Scene.from_tilemap(self.tile_map)

	def get_players(self, skip):
		for p in self.players:
			if p == skip:
				pass
			else:
				playerdata = self.players[p]
				yield {'client_id': p, 'playerdata': playerdata}

	def get_player(self, clid):
		playerdata = self.players[clid]
		return {'client_id': clid, 'playerdata': playerdata}

	def check_players(self):
		self.chkp_counter += 1
		dt = time.time()
		playerscopy = copy.copy(self.players)
		for p in playerscopy:
			dt_diff = dt - self.players[p].get('msg_dt', 0)
			if dt_diff > 10:  # player timeout
				self.players[p]['timeout'] = True
				self.gs_event_queue.put_nowait({'event_time': 0, 'event_type': 'playerquit', 'client_id': p, 'reason': 'timeout', 'eventid': gen_randid()})  # update other clients about playerquit
				if not self.players[p]['timeout']:
					logger.info(f'player timeout {p} dt_diff={dt_diff} selfplayers={self.players}')

	@staticmethod
	def create_upgrade_block(upgradetype, blkpos):
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
		msghealth = msg.get('health', -22)
		msgtimeout = msg.get('timeout')
		msgkilled = msg.get('killed')
		playerdict = {
			'client_id': clid,
			'name': msg.get('name', 'ugsmissing'),
			'position': msg.get('position'),
			'angle': msg.get('angle'),
			'score': msg.get('score', -23),
			'health': msghealth,
			'msg_dt': msg.get('msg_dt'),
			'timeout': msgtimeout,
			'killed': msgkilled,
			'msgsource': 'update_game_state',
			'bombsleft': msg.get('bombsleft', -24),

		}
		self.players[clid] = playerdict

	def update_game_events(self, game_event):
		self.event_log = self.event_log[1:MAXEVENTS]
		try:
			event_type = game_event.get('event_type')
			handled = game_event['handled']
			handledby = game_event['handledby']
			game_event['handledby'] = f'ugs-{handledby}'
			game_event['event_time'] += time.time()
			eventid = game_event.get('eventid')
			if self.debugmode:
				logger.info(f'event_type={event_type} id:{eventid} {handled=} {handledby=} log:{len(self.event_log)}')  # game_event={game_event}')
			if eventid in self.event_log:
				logger.warning(f'{eventid=} already in event_log! events: {len(self.event_log)} {game_event=} ')
				game_event['handled'] = True
				game_event['handledby'] = 'ugsdupe'
				game_event['event_type'] = 'dupeevent'
				#self.gs_event_queue.put_nowait(game_event)
				#return
			else:
				self.event_log.append(eventid)
				clid = game_event['client_id']
				match event_type:
					# logger.debug(f'self.game_events={self.game_events}')
					case 'playerquit':  # playerquit
						self.players[clid]['playerquit'] = True
						self.gs_event_queue.put_nowait(game_event)  # update other clients about playerquit
					case 'newconnection':  # new player connected, inform others
						game_event['handled'] = True
						if game_event['handledby'] == 'ugsnc':
							logger.warning(f'dupeacknewconn {game_event=}')
							game_event['event_type'] = 'dupeevent'
							return
						game_event['handledby'] = 'ugsnc'
						game_event['event_type'] = 'acknewconn'
						name = game_event['name']
						self.gs_event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.info(f'{event_type} id {eventid} from {clid} {name}')
					case 'blkxplode':  # todo make upgradeblock here....
						# game_event['handled'] = True
						uptype = random.choice([1, 2, 3])
						upgradeblockevent = {'event_time': 0, 'event_type': 'upgradeblock', 'client_id': game_event.get("client_id"), 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'blkxplodeuge', 'eventid': gen_randid()}
						self.gs_event_queue.put_nowait(upgradeblockevent)
						if self.debugmode:
							logger.info(f'{event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
					case 'takeupgrade':  # todo decide on somethingsomething..
						game_event['handledby'] = f'ugstakeupgrade'
						upgradetype = game_event.get("upgradetype")
						match upgradetype:
							case 1:  # extra health
								self.players[clid]['health'] += EXTRA_HEALTH
								logger.debug(f'{clid} got extrahealth -> {self.players[clid].get("health")}')
								extrahealthevent = {'event_time': 0, 'event_type': 'extrahealth', 'amount': EXTRA_HEALTH, 'client_id': clid, 'eventid': gen_randid()}
								self.gs_event_queue.put_nowait(extrahealthevent)
							case 2:  # extra bomb
								self.players[clid]['bombsleft'] += 1
								logger.debug(f'{clid} got extrabomb -> {self.players[clid].get("bombsleft")}')
								extrabombevent = {'event_time': 0, 'event_type': 'extrabomb', 'client_id': clid, 'eventid': gen_randid()}
								self.gs_event_queue.put_nowait(extrabombevent)
							case 3:  # bigger bomb
								pass
							case _:
								logger.warning(f'unknown upgradetype {upgradetype=} {game_event=}')
					case 'bombdrop':  # decide on somethingsomething
						game_event['handledby'] = f'ugsbomb'
						game_event['handled'] = True
						bomber = game_event.get("bomber")
						name = self.players[bomber]['name']
						game_event['event_type'] = f'ackbombdrop'
						self.players[bomber]['bombsleft'] -= 1
						self.gs_event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'{event_type} from {name=} {bomber} {eventid=} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')

					case 'bulletfired':  # decide on somethingsomething
						game_event['handledby'] = f'ugsackbullet'
						game_event['event_type'] = f'ackbullet'
						self.gs_event_queue.put_nowait(game_event)
						if self.debugmode:
							pass  # logger.debug(f'{event_type} from {shooter}')
					case 'bombxplode':  # decide on somethingsomething
						game_event['handledby'] = f'ugsackbombxplode'
						game_event['handled'] = True
						if game_event['event_type'] == 'ackbombxplode':
							logger.warning(f'dupeackbombxplode {game_event=}')
							return
						game_event['event_type'] = f'ackbombxplode'
						bomber = game_event.get("bomber")
						self.players[bomber]['bombsleft'] += 1
						self.gs_event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'{event_type} from {bomber}  bl={self.players[bomber].get("bombsleft")} {eventid=}')

					case 'playerkilled':  # increase score for dmgfrom
						dmgfrom = game_event.get("dmgfrom")
						dmgto = game_event.get("dmgto")
						self.players[dmgfrom]['score'] += 1
						game_event['handled'] = True
						game_event['handledby'] = f'ugskillplayerkilled'
						self.gs_event_queue.put_nowait(game_event)
						# if self.debugmode:
						logger.debug(f'{event_type} {dmgfrom=} {dmgto=} {self.players[dmgfrom]}')

					case 'takedamage':  # increase score for dmgfrom
						dmgfrom = game_event.get("dmgfrom")
						dmgto = game_event.get("dmgto")
						damage = game_event.get("damage")
						game_event['handled'] = True
						game_event['handledby'] = f'ugskilltakedamage'
						self.players[dmgfrom]['score'] += 1
						self.players[dmgto]['health'] -= damage
						logger.info(f'{event_type} {dmgfrom=} {dmgto=} killerscore={self.players[dmgfrom]["score"]}')
						self.gs_event_queue.put_nowait(game_event)

					case 'respawn':  # increase score for dmgfrom
						clid = game_event.get("client_id")
						self.players[clid]['health'] = 100
						self.players[clid]['killed'] = False
						game_event['handled'] = True
						game_event['handledby'] = f'ugsrspwn'
						game_event['event_type'] = 'ackrespawn'
						self.gs_event_queue.put_nowait(game_event)
						# if self.debugmode:
						logger.debug(f'{event_type} {clid=} {self.players[clid]}')
					case 'getmap':  # send map to client
						clid = game_event.get("client_id")
						payload = {'msgtype': 'scenedata', 'payload': self.scene}
						logger.info(f'{event_type} from {clid} {len(payload)} {game_event=}')
					case _:  #
						logger.warning(f'unknown game_event:{event_type} from game_event={game_event}')
		except KeyError as e:
			logger.warning(f'{type(e)} {e} {game_event=} ')
		except Exception as e:
			logger.error(f'{type(e)} {e} {game_event=} ')

	def to_json(self):
		self.toj_counter += 1
		dout = {'players': {}}
		for player in self.players:
			playerdict = dict(client_id=player, name=self.players[player].get('name', 'fjmissing'),
			                  position=self.players[player].get('position', (0, 0)),
			                  angle=self.players[player].get('angle', -11),
			                  health=self.players[player].get('health', -12),
			                  msg_dt=self.players[player].get('msg_dt', time.time()),
			                  timeout=self.players[player].get('timeout', False),
			                  killed=self.players[player].get('killed', False),
			                  score=self.players[player].get('score', -13),
			                  bombsleft=self.players[player].get('bombsleft', -14), msgsource='to_json')
			dout['players'][player] = playerdict  # Q = playerdict
		return dout

	def from_json(self, gamestatedata):
		self.fj_counter += 1
		plist = gamestatedata.get('players', [])
		for player in plist:
			if plist.get(player).get('timeout'):
				pass  # logger.warning(f'timeoutfromjson: p={player} gamestatedata:{gamestatedata} selfplayers={self.players}')
			elif plist.get(player).get('killed'):
				pass  # logger.warning(f'timeoutfromjson: p={player} gamestatedata:{gamestatedata} selfplayers={self.players}')
			else:
				self.players[plist.get(player).get('client_id')] = plist.get(player)
		# logger.info(f'player={player} gamestatedata={gamestatedata} selfplayers={self.players}')
		if self.debugmode:
			pass  # logger.debug(f'gamestatedata={gamestatedata}')# gs={self.game_seconds} selfplayers={self.players}')
