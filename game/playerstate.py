import pygame
from loguru import logger
from dataclasses import dataclass, field, InitVar
from utils import gen_randid, generate_name
from constants import DEFAULT_HEALTH, BLOCK

@dataclass
class PlayerState:
	position: tuple
	client_id: str = 'client_idnotset'
	client_name: str = 'client_namenotset'
	score: int = 0
	# bombs_left: InitVar[int] = 3  # Use InitVar for constructor param
	initial_bombs: InitVar[int] = 3  # Use InitVar for constructor param
	health: int = DEFAULT_HEALTH
	prev_position: tuple | None = None
	target_position: tuple | None = None
	interp_time: float | None = None
	position_updated: bool = False
	msg_dt: float | None = None
	timeout: bool | None = None
	killed: bool | None = None
	event_type: str | None = None
	event_time: int | None = None
	handled: bool = False
	handledby: str = 'PlayerState'
	playerlist: list = field(default_factory=list)
	eventid: str = field(default_factory=gen_randid)

	def __post_init__(self, initial_bombs):
		# Initialize the private attribute for the property
		self._bombsleft = initial_bombs

	@property
	def rect(self):
		"""Create a rect on-demand for collision detection"""
		return pygame.Rect(self.position[0], self.position[1], BLOCK, BLOCK)

	@property
	def bombs_left(self):
		return self._bombsleft

	@bombs_left.setter
	def bombs_left(self, value):
		# Never exceed 3 bombs
		self._bombsleft = min(3, max(0, value))

	def to_dict(self):
		return {
			'client_id': self.client_id,
			'position': self.position,
			'health': self.health,
			'bombs_left': self.bombs_left,
			'score': self.score,
			'msg_dt': self.msg_dt,
			'timeout': self.timeout,
			'killed': self.killed,
			'event_type': self.event_type}

	def take_damage(self, damage, attacker_id):
		"""Handle damage to player state"""
		old_health = self.health
		self.health = max(0, self.health - damage)
		if self.health <= 0:
			self.killed = True
		logger.info(f"Player {self.client_id} hit by {attacker_id} for {damage} damage: {old_health} -> {self.health}")
