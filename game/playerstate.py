from dataclasses import dataclass, field
from utils import gen_randid
from constants import DEFAULT_HEALTH

@dataclass
class PlayerState:
	client_id: str
	position: tuple
	score: int = 0
	bombsleft: int = 3
	health: int = DEFAULT_HEALTH
	prev_position: tuple | None = None
	target_position: tuple | None = None
	interp_time: float | None = None
	position_updated: bool = False
	msg_dt: float | None = None
	timeout: bool | None = None
	killed: bool | None = None
	msgtype: str | None = None
	event_time: int | None = None
	event_type: str | None = None
	handled: bool = False
	handledby: str = 'PlayerState'
	playerlist: list = field(default_factory=list)
	eventid: str = field(default_factory=gen_randid)

	def to_dict(self):
		return {
			'client_id': self.client_id,
			'position': self.position,
			'health': self.health,
			'bombsleft': self.bombsleft,
			'score': self.score,
			'msg_dt': self.msg_dt,
			'timeout': self.timeout,
			'killed': self.killed,
			'msgtype': self.msgtype}
