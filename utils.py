from typing import Tuple, Union
from pygame.math import Vector2 as Vec2d
import struct
import random
import hashlib as md5lib
import pygame
import os

md5_unpacker = struct.Struct("4I")

def load_image(fullname, colorkey=None):
	# fullname = os.path.join("data", name)
	try:
		image = pygame.image.load(fullname)
		image = image.convert()
		if colorkey is not None:
			if colorkey == -1:
				colorkey = image.get_at((0, 0))
			image.set_colorkey(colorkey)
		return image, image.get_rect()
	except FileNotFoundError as e:
		print(f"[load_image] {fullname} {e}")


def gen_randid() -> int:
	return int(''.join([str(random.randint(0,9)) for k in range(10)]))

def get_map_coordinates_rev(camera_vector: Union[Vec2d, tuple], camera) -> Vec2d:
	return Vec2d(*camera_vector) - Vec2d(*camera.position)

def stable_hash(t: Tuple) -> int:
	cnt = _dump_tuple(t)
	hd = md5lib.md5(cnt).digest()
	return md5_unpacker.unpack(hd)[0]  # 32 bits

def _dump_tuple(t: Tuple) -> bytes:
	cnt = b""
	for item in t:
		if item is not None:
			type_ = type(item)
			if type_ in _DUMP_BY_TYPE:
				cnt += _DUMP_BY_TYPE[type_](item)
			else:
				cnt += struct.pack("<Q", hash(item) & 0xFFFF_FFFF_FFFF_FFFF)
		cnt += b"\xf0"
	return cnt

def _dump_str(t: str) -> bytes:
	return t.encode("ascii")

def _dump_int(t: int) -> bytes:
	prefix = b"" if t >= 0 else b"-"
	t = abs(t)
	if t <= 0xFFFF:
		return prefix + struct.pack("<H", t)
	elif t <= 0xFFFF_FFFF:
		return prefix + struct.pack("<I", t)
	elif t <= 0xFFFF_FFFF_FFFF_FFFF:
		return prefix + struct.pack("<Q", t)
	else:
		cnt = b""
		while t > 0:
			cnt += _dump_int(t & 0xFFFF_FFFF_FFFF_FFFF)
			t >>= 64
		return prefix + cnt

def _dump_type(t: type) -> bytes:
	return t.__name__.encode("ascii")

_DUMP_BY_TYPE = {
	tuple: _dump_tuple,
	str: _dump_str,
	int: _dump_int,
	type: _dump_type,
}
