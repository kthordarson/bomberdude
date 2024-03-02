from pyvex.utils import stable_hash
from pymunk import Vec2d
import copy
import arcade
from arcade.gui.style import UIStyleBase, UIStyledWidget
from arcade.tilemap import TileMap
from arcade.gui import UIManager, UIBoxLayout, UITextArea, UIFlatButton, UIGridLayout
from arcade.gui import UILabel
from arcade.math import (get_angle_radians, rotate_point, get_angle_degrees,)
import random
import math
from loguru import logger
from constants import *
import time
import hashlib
from queue import Queue, Empty
from typing import List, Dict
import json
from dataclasses import dataclass, asdict, field
from arcade.types import Point
from utils import gen_randid
from objects import Upgrade


@dataclass
class GameState:
	# player_states: List[PlayerState]
	game_seconds: int = 0
	cjsonupdate: int = 0

	def __repr__(self):
		return f'Gamestate (gs:{self.game_seconds} events:{len(self.game_events)} counters = chkpc: {self.chkp_counter} ugsc: {self.ugs_counter} tojc: {self.toj_counter} fjc: {self.fj_counter} players:{len(self.players)})'

	def __init__(self,  game_seconds=0, debugmode=False, mapname=None):
		self.mapname = mapname
		self.players = {}
		# self.player_states = player_states
		self.game_seconds = game_seconds
		self.debugmode = debugmode
		self.debugmode_trace = False
		self.game_events = []
		self.event_queue = Queue()
		self.raw_event_queue = Queue()
		# debugstuff
		self.chkp_counter = 0
		self.ugs_counter = 0
		self.toj_counter = 0
		self.fj_counter = 0
		self.layer_options={
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
		self.tile_map = arcade.load_tilemap(self.mapname, layer_options=self.layer_options, scaling=TILE_SCALING, use_spatial_hash=True)
		for block in self.tile_map.sprite_lists['Blocks']:
			block.hit_count = 0
		self.scene = arcade.Scene.from_tilemap(self.tile_map)

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
		old_len = len(self.players)
		pops = []
		for p in playerscopy:
			dt_diff = dt - self.players[p].get('msg_dt')
			playerhealth = self.players[p].get('health')
			if dt_diff > 10: # player timeout
				self.players[p]['timeout'] = True
				self.event_queue.put_nowait({'event_time':0, 'event_type':'playerquit', 'client_id': p, 'reason':'timeout','eventid': gen_randid()}) # update other clients about playerquit
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
		for game_event in msg.get('game_events'):
			event_type = None
			if game_event == []:
				continue
			else:
				event_type = game_event.get('event_type')
			game_event['event_time'] += 1
			eventid = game_event.get('eventid')
			evntchk =  [k for k in self.game_events if k.get('eventid') == eventid]
			if len(evntchk) > 0:
				continue # logger.warning(f'dupeevntchk {len(evntchk)} eventid {eventid} {game_event} already in game_events')# :  msg={msg} selfgameevents:{self.game_events}')
				# r = [self.game_events.remove(k) for k in evntchk]
			else:
				match event_type:
					# logger.debug(f'self.game_events={self.game_events}')
					case 'playerquit': # playerquit
						clid = game_event['client_id']
						self.players[clid]['playerquit'] = True
						self.event_queue.put_nowait(game_event) # update other clients about playerquit
					case 'newconnection':
						game_event['handled'] = True
						game_event['handledby'] = f'ugsnc'
						game_event['event_type'] = 'acknewconn'
						clid = game_event['client_id']
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.info(f'{event_type} from {clid} ')
					case 'blkxplode': # todo make upgradeblock here....
						# game_event['handled'] = True
						uptype = random.choice([1,2,3])
						newevent = {'event_time':0, 'event_type': 'upgradeblock', 'client_id': game_event.get("client_id"), 'upgradetype': uptype, 'hit': game_event.get("hit"), 'fpos': game_event.get('flame'), 'handled': False, 'handledby': 'uge', 'eventid': gen_randid()}
						self.event_queue.put_nowait(newevent)
						if self.debugmode:
							logger.info(f'{event_type} from {game_event.get("fbomber")}, uptype:{uptype}')
					case 'takeupgrade': # todo decide on somethingsomething..
						game_event['handledby'] = f'ugstakeupgrade'
						upgradetype = game_event.get("upgradetype")
						clid = game_event['client_id']
						match upgradetype:
							case 1: # extra health
								self.players[clid]['health'] += EXTRA_HEALTH
								logger.debug(f'{clid} got extrahealth -> {self.players[clid].get("health")}')
								event = {'event_time':0, 'event_type': 'extrahealth', 'amount':EXTRA_HEALTH, 'client_id': clid,  'eventid': gen_randid()}
								self.event_queue.put_nowait(event)
							case 2: # extra bomb
								self.players[clid]['bombsleft'] += 1
								logger.debug(f'{clid} got extrabomb -> {self.players[clid].get("bombsleft")}')
								event = {'event_time':0, 'event_type': 'extrabomb', 'client_id': clid,  'eventid': gen_randid()}
								self.event_queue.put_nowait(event)
							case 3: # bigger bomb
								pass
							case _:
								logger.warning(f'unknown upgradetype {upgradetype=} {msg=}')
					case 'bombdrop': # decide on somethingsomething..
						game_event['handledby'] = f'ugsbomb'
						bomber = game_event.get("bomber")
						eventid = game_event.get('eventid')
						if self.players[bomber].get("bombsleft")>0:
							game_event['event_type'] = f'ackbombdrop'
							self.players[bomber]['bombsleft'] -= 1
							self.event_queue.put_nowait(game_event)
							if self.debugmode:
								logger.debug(f'{event_type} from {bomber} {eventid=} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')
						else:
							if self.debugmode:
								logger.debug(f'nobombsleft ! {event_type} from {bomber} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')

					case 'bulletfired': # decide on somethingsomething..
						game_event['handledby'] = f'ugsbomb'
						shooter = game_event.get("shooter")
						# if self.players[bomber].get("bulletsleft")>0: # maybe ?
						# self.players[bomber]['bulletsleft'] -= 1
						game_event['event_type'] = f'ackbullet'
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'{event_type} from {shooter}')
					case 'bombxplode': # decide on somethingsomething..
						game_event['handledby'] = f'ugsbomb'
						game_event['event_type'] = f'ackbombxplode'
						eventid = game_event.get('eventid')
						bomber = game_event.get("bomber")
						self.players[bomber]['bombsleft'] += 1
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'{event_type} from {bomber}  bl={self.players[bomber].get("bombsleft")} {eventid=}')
					case 'playerkilled': # increase score for dmgfrom
						dmgfrom = game_event.get("dmgfrom")
						dmgto = game_event.get("dmgto")
						self.players[dmgfrom]['score'] += 1
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {dmgfrom=} {dmgto=} {self.players[dmgfrom]}')
					case 'takedamage': # increase score for dmgfrom
						dmgfrom = game_event.get("dmgfrom")
						dmgto = game_event.get("dmgto")
						damage = game_event.get("damage")
						self.players[dmgto]['health'] -= damage
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
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
						#if self.debugmode:

					case 'respawn': # increase score for dmgfrom
						clid = game_event.get("client_id")
						self.players[clid]['health'] = 100
						self.players[clid]['killed'] = False
						game_event['handled'] = True
						game_event['handledby'] = f'ugsrspwn'
						game_event['event_type'] = 'ackrespawn'
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {clid=} {self.players[clid]}')
					case 'getmap': # send map to client
						clid = game_event.get("client_id")
						payload = {'msgtype': 'scenedata', 'payload':self.scene}
						logger.info(f'{event_type} from {clid} {len(payload)} {game_event=}')
						#await sockpush.send(payload)
						# game_event['event_type'] = 'ackgetmap'
						# game_event['payload'] = pickle.dumps(self.scene)
						# self.raw_event_queue.put_nowait(pickle.dumps(self.tile_map))
					case _: #
						logger.warning(f'unknown game_event:{event_type} from msg={msg}')
				#elif game_event.get('handled') == True:
				#	logger.warning(f'game_event already handled: {game_event} msg={msg}')


	def to_json(self):
		self.toj_counter += 1
		dout = {'players':{}, 'game_events': []}
		try:
			pending_event = self.event_queue.get_nowait()
			self.event_queue.task_done()
			dout['game_events'].append(pending_event)
		except Empty:
			pending_events = []
		for player in self.players:
			playerdict = {
			'client_id':player,
			'position': self.players[player].get('position'),
			'angle': self.players[player].get('angle'),
			'health': self.players[player].get('health'),
			'msg_dt': self.players[player].get('msg_dt'),
			'timeout': self.players[player].get('timeout'),
			'killed': self.players[player].get('killed'),
			'score': self.players[player].get('score'),
			'bombsleft': self.players[player].get('bombsleft'),
			'msgsource': 'to_json',
			}
			dout['players'][player] = playerdict #Q = playerdict
		return dout

	def from_json(self, dgamest):
		self.fj_counter += 1
		for ge in dgamest.get('game_events', []):
			if ge == []:
				break
			if self.debugmode:
				logger.info(f'ge={ge.get("event_type")} dgamest={dgamest=}')
			self.event_queue.put_nowait(ge)
		plist = dgamest.get('players',[])
		for player in plist:
			if plist.get(player).get('timeout'):
				pass # logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			elif plist.get(player).get('killed'):
				pass # logger.warning(f'timeoutfromjson: p={player} dgamest:{dgamest} selfplayers={self.players}')
			else:
				self.players[plist.get(player).get('client_id')] = plist.get(player)
				# logger.info(f'player={player} dgamest={dgamest} selfplayers={self.players}')
		if self.debugmode:
			pass # logger.debug(f'dgamest={dgamest}')# gs={self.game_seconds} selfplayers={self.players}')
