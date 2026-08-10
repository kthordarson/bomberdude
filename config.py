"""Persisted, player-editable settings (name, resolution, bullet color, particle count).

Loaded once at startup: if the config file is missing it's created with
defaults; if it exists its values (merged over defaults, so old/short files
stay forward-compatible) are used.
"""
import json
import os
from dataclasses import dataclass, field

from loguru import logger

from constants import PARTICLE_COUNT, SCREEN_HEIGHT, SCREEN_WIDTH
from utils import generate_name

DEFAULT_CONFIG_PATH = "bdude_config.json"
DEFAULT_BULLET_COLOR = (255, 0, 0)
DEFAULT_FOG_RADIUS = 200
DEFAULT_FOG_COLOR = (0, 0, 0)
DEFAULT_FOG_ALPHA = 220
DEFAULT_MINIMAP_SIZE = 150
DEFAULT_MINIMAP_ALPHA = 255
DEFAULT_MINIMAP_ANCHOR = "bottom_right"
MINIMAP_ANCHORS = ("top_left", "top_right", "bottom_left", "bottom_right")


@dataclass
class Config:
	player_name: str = field(default_factory=generate_name)
	screen_width: int = SCREEN_WIDTH
	screen_height: int = SCREEN_HEIGHT
	bullet_color: tuple[int, int, int] = DEFAULT_BULLET_COLOR
	particle_count: int = PARTICLE_COUNT
	fog_radius: int = DEFAULT_FOG_RADIUS
	fog_color: tuple[int, int, int] = DEFAULT_FOG_COLOR
	fog_alpha: int = DEFAULT_FOG_ALPHA
	minimap_size: int = DEFAULT_MINIMAP_SIZE
	minimap_alpha: int = DEFAULT_MINIMAP_ALPHA
	minimap_anchor: str = DEFAULT_MINIMAP_ANCHOR

	def to_dict(self) -> dict:
		return {
			"player_name": self.player_name,
			"screen_width": self.screen_width,
			"screen_height": self.screen_height,
			"bullet_color": list(self.bullet_color),
			"particle_count": self.particle_count,
			"fog_radius": self.fog_radius,
			"fog_color": list(self.fog_color),
			"fog_alpha": self.fog_alpha,
			"minimap_size": self.minimap_size,
			"minimap_alpha": self.minimap_alpha,
			"minimap_anchor": self.minimap_anchor,
		}

	@classmethod
	def from_dict(cls, data: dict) -> "Config":
		defaults = cls()
		bullet_color = data.get("bullet_color", list(defaults.bullet_color))
		try:
			bullet_color = tuple(int(c) for c in bullet_color)[:3]
			if len(bullet_color) != 3:
				bullet_color = defaults.bullet_color
		except (TypeError, ValueError):
			bullet_color = defaults.bullet_color
		fog_color = data.get("fog_color", list(defaults.fog_color))
		try:
			fog_color = tuple(int(c) for c in fog_color)[:3]
			if len(fog_color) != 3:
				fog_color = defaults.fog_color
		except (TypeError, ValueError):
			fog_color = defaults.fog_color
		minimap_anchor = data.get("minimap_anchor", defaults.minimap_anchor)
		if minimap_anchor not in MINIMAP_ANCHORS:
			minimap_anchor = defaults.minimap_anchor
		return cls(
			player_name=str(data.get("player_name") or defaults.player_name),
			screen_width=int(data.get("screen_width", defaults.screen_width)),
			screen_height=int(data.get("screen_height", defaults.screen_height)),
			bullet_color=bullet_color,  # type: ignore[arg-type]
			particle_count=int(data.get("particle_count", defaults.particle_count)),
			fog_radius=int(data.get("fog_radius", defaults.fog_radius)),
			fog_color=fog_color,  # type: ignore[arg-type]
			fog_alpha=int(data.get("fog_alpha", defaults.fog_alpha)),
			minimap_size=int(data.get("minimap_size", defaults.minimap_size)),
			minimap_alpha=int(data.get("minimap_alpha", defaults.minimap_alpha)),
			minimap_anchor=minimap_anchor,
		)


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Config:
	"""Load config from `path`, creating it with defaults if it doesn't exist."""
	if not os.path.exists(path):
		config = Config()
		save_config(config, path)
		logger.info(f"No config file at '{path}'; created one with default values: {config}")
		return config
	try:
		with open(path) as f:
			data = json.load(f)
		config = Config.from_dict(data)
		logger.info(f"Loaded config from '{path}': {config}")
		return config
	except Exception as e:
		logger.error(f"Error loading config from '{path}': {e} {type(e)}; using defaults.")
		return Config()


def save_config(config: Config, path: str = DEFAULT_CONFIG_PATH) -> bool:
	try:
		with open(path, "w") as f:
			json.dump(config.to_dict(), f, indent=2)
		logger.info(f"Saved config to '{path}': {config}")
		return True
	except Exception as e:
		logger.error(f"Error saving config to '{path}': {e} {type(e)}")
		return False
