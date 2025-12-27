import random
import pygame
import asyncio

_RAW_IMAGE_CACHE: dict[str, pygame.Surface] = {}
_PROCESSED_IMAGE_CACHE: dict[tuple[str, float, str], pygame.Surface] = {}


async def load_image_cached(path: str) -> pygame.Surface:
	"""Load an image from disk once and reuse the same Surface.

	Returns the raw, unconverted Surface (safe even when no video mode is set).
	"""
	surf = _RAW_IMAGE_CACHE.get(path)
	if surf is None:
		# surf = pygame.image.load(path)
		surf = await asyncio.to_thread(pygame.image.load, path)
		_RAW_IMAGE_CACHE[path] = surf
	return surf


async def get_cached_image(path: str, *, scale: float = 1.0, convert: bool = True) -> pygame.Surface:
	"""Get a cached image Surface.

	- `convert=True` will use `convert()` / `convert_alpha()` when a display surface exists.
	- If no video mode is set yet, conversion is skipped automatically.
	- `scale` caches scaled surfaces keyed by (path, scale, mode).
	"""
	mode = "raw"
	base = await load_image_cached(path)
	if convert and pygame.display.get_init() and pygame.display.get_surface() is not None:
		mode = "alpha" if base.get_alpha() else "opaque"
	key = (path, float(scale), mode)
	cached = _PROCESSED_IMAGE_CACHE.get(key)
	if cached is not None:
		return cached

	# Convert only when safe.
	processed = base
	if mode == "alpha":
		processed = base.convert_alpha()
	elif mode == "opaque":
		processed = base.convert()

	if scale != 1.0:
		processed = pygame.transform.scale(
			processed,
			(
				int(processed.get_width() * scale),
				int(processed.get_height() * scale),
			),
		)

	_PROCESSED_IMAGE_CACHE[key] = processed
	return processed

def gen_randid() -> int:
	return int(''.join([str(random.randint(0,9)) for k in range(10)]))

def generate_name(style="bomber"):
	"""
	Generate a funny random name for players

	Args:
		style: The style of name to generate ("bomber", "animal", "food", "random")

	Returns:
		A randomly generated funny name string
	"""
	adjectives = [
		"Blasting", "Explosive", "Wobbly", "Dizzy", "Sleepy", "Confused", "Quirky",
		"Jumpy", "Speedy", "Sneaky", "Cranky", "Clumsy", "Sparkly", "Radioactive",
		"Chaotic", "Panicky", "Jittery", "Squishy", "Bouncy", "Fluffy"
	]

	animals = [
		"Penguin", "Giraffe", "Panda", "Sloth", "Platypus", "Raccoon", "Wombat",
		"Walrus", "Hippo", "Koala", "Narwhal", "Badger", "Quokka", "Llama",
		"Hedgehog", "Lemur", "Opossum", "Otter", "Armadillo", "Alpaca"
	]

	bomber_nouns = [
		"Bomber", "Dynamite", "Kaboom", "Explosion", "Nuke", "Grenade", "Firecracker",
		"Rocket", "Missile", "TNT", "Blast", "Powder", "Detonator", "Fuse",
		"Demolisher", "Boomer", "Blaster", "Bombadier", "Bang", "Boom"
	]

	food_nouns = [
		"Muffin", "Pancake", "Waffle", "Cupcake", "Donut", "Cookie", "Burrito",
		"Pizza", "Noodle", "Taco", "Burger", "Tofu", "Nugget", "Biscuit",
		"Dumpling", "Pickle", "Sandwich", "Potato", "Banana", "Avocado"
	]

	# Choose collection based on style
	if style == "bomber":
		nouns = bomber_nouns
	elif style == "animal":
		nouns = animals
	elif style == "food":
		nouns = food_nouns
	else:  # random style - mix all nouns
		nouns = bomber_nouns + animals + food_nouns

	# Generate the name
	adj = random.choice(adjectives)
	noun = random.choice(nouns)
	idnum = int(''.join([str(random.randint(0,9)) for k in range(3)]))
	# Add random number suffix 25% of the time
	if random.random() < 0.25:
		suffix = str(random.randint(1, 99))
		return f"{adj}{noun}{suffix}{idnum}"

	return f"{adj}{noun}{idnum}"
