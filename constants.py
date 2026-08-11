DEFAULT_HEALTH = 100
BULLETDEBUG = False
BLOCK = 32
BULLET_SPEED = 14
BULLET_TIMER = 2
CAMERA_SPEED = 0.1
FLAME_SPEED = 3
PARTICLE_COUNT = 20
PARTICLE_GRAVITY = 0.05
PARTICLE_MIN_SPEED = 2.5
PARTICLE_RADIUS = 3
PARTICLE_SPEED_RANGE = 2.5
PLAYER_MOVEMENT_SPEED = 4
PLAYER_SCALING = 0.8
BOMB_SCALING = 0.7
RECT_HEIGHT:int = BLOCK
RECT_WIDTH:int = BLOCK
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_TITLE = "bdude"
UPDATE_TICK:int = 60
# ...existing constants...
SHOCKWAVE_EXPANSION_RATE = 150  # pixels per second
SHOCKWAVE_MAX_RADIUS_PRIMARY = 150
SHOCKWAVE_MAX_RADIUS_SECONDARY = 100
INITIAL_BOMBS = 3
INITIAL_BOMB_POWER = 3
COOLDOWN_PERIOD = 0.5
# _base_frame_snapshot only backs the paused Configure-menu backdrop, so it
# doesn't need per-frame freshness; refreshing it at this cadence instead of
# every frame avoids a full-screen Surface.copy() on every single frame.
BASE_FRAME_SNAPSHOT_REFRESH_INTERVAL = 5

# Upgrade tile GIDs (must match the Tiled map's tileset).
UPGRADE_HEALTH = 20   # restores player health
UPGRADE_BOMBS  = 21   # grants an extra bomb slot
UPGRADE_POWER  = 22   # increases bomb blast radius
UPGRADE_SPEED  = 23   # speed boost (tile GID reserved; not yet applied)
# Convenience set for "is this GID an upgrade tile?" checks.
UPGRADE_TILE_GIDS: frozenset[int] = frozenset({UPGRADE_HEALTH, UPGRADE_BOMBS, UPGRADE_POWER, UPGRADE_SPEED})
