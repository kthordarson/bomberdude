import struct
import random
import pygame

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
