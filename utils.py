import struct
import random
import pygame

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
