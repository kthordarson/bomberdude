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
from objects import gen_randid


@dataclass
class GameState:
	# player_states: List[PlayerState]
	game_seconds: int = 0
	cjsonupdate: int = 0

	def __repr__(self):
		return f'Gamestate (gs:{self.game_seconds} events:{len(self.game_events)} counters = chkpc: {self.chkp_counter} ugsc: {self.ugs_counter} tojc: {self.toj_counter} fjc: {self.fj_counter} players:{len(self.players)})'

	def __init__(self,  game_seconds=0, debugmode=False):
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
		layer_options={
			"Particles": {"use_spatial_hash": True},
			"Flames": {"use_spatial_hash": True},
			"Bullets": {"use_spatial_hash": True},
			"Netplayers": {"use_spatial_hash": True},
			"Bombs": {"use_spatial_hash": True},
			"Players": {"use_spatial_hash": True},
			"Blocks": {"use_spatial_hash": True},
			"Walls": {"use_spatial_hash": True},
			"Background": {"use_spatial_hash": False},
			}
		self.tile_map:TileMap = arcade.load_tilemap('data/map3.json', layer_options=layer_options , scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)

	def load_tile_map(self, mapname):
		logger.debug(f'loading {mapname}')
		self.tile_map = arcade.load_tilemap(mapname, layer_options={"Blocks": {"use_spatial_hash": True},}, scaling=TILE_SCALING)
		self.scene = arcade.Scene.from_tilemap(self.tile_map)


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
				if not self.players[p]['timeout']:
					logger.info(f'player timeout {p} dt_diff={dt_diff} selfplayers={self.players}')

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
			if self.debugmode:
				logger.info(f'{game_event=}')
			else:
				logger.debug(f'{event_type=}')
			game_event['event_time'] += 1
			eventid = game_event.get('eventid')
			evntchk =  [k for k in self.game_events if k.get('eventid') == eventid]
			if len(evntchk) > 0:
				continue # logger.warning(f'dupeevntchk {len(evntchk)} eventid {eventid} {game_event} already in game_events')# :  msg={msg} selfgameevents:{self.game_events}')
				# r = [self.game_events.remove(k) for k in evntchk]
			else:
				match event_type:
					# logger.debug(f'self.game_events={self.game_events}')
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
					case 'bombdrop': # decide on somethingsomething..
						game_event['handledby'] = f'ugsbomb'
						bomber = game_event.get("bomber")
						if self.players[bomber].get("bombsleft")>0:
							game_event['event_type'] = f'ackbombdrop'
							self.players[bomber]['bombsleft'] -= 1
							self.event_queue.put_nowait(game_event)
							if self.debugmode:
								logger.debug(f'{event_type} from {bomber} pos:{game_event.get("pos")} bl={self.players[bomber].get("bombsleft")}')
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
						bomber = game_event.get("bomber")
						# self.players[bomber]['bombsleft'] += 1
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'{event_type} from {bomber}  bl={self.players[bomber].get("bombsleft")}')
					case 'upgradeblock': # decide on somethingsomething..
						game_event['handled'] = True
						game_event['handledby'] = f'ugsupgr'
						self.event_queue.put_nowait(game_event)
						if self.debugmode:
							logger.debug(f'{event_type} {game_event.get("upgradetype")} pos:{game_event.get("fpos")} from {game_event.get("client_id")}')
					case 'playerkilled': # increase score for killer
						killer = game_event.get("killer")
						killed = game_event.get("killed")
						self.players[killer]['score'] += 1
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {killer=} {killed=} {self.players[killer]}')
					case 'takedamage': # increase score for killer
						killer = game_event.get("killer")
						killed = game_event.get("killed")
						damage = game_event.get("damage")
						self.players[killed]['health'] -= damage
						game_event['handled'] = True
						game_event['handledby'] = f'ugskill'
						if self.players[killed]['health'] > 0:
							game_event['event_type'] = 'acktakedamage'
						else:
							self.players[killer]['score'] += 1
							game_event['event_type'] = 'dmgkill'
							game_event['killtimer'] = 5
							game_event['killstart'] = game_event.get("msg_dt")
						self.event_queue.put_nowait(game_event)
						#if self.debugmode:
						logger.debug(f'{event_type} {killer=} {killed=} ')
					case 'respawn': # increase score for killer
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
