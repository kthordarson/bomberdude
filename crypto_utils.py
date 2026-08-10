"""AES-GCM helpers for encrypting short secrets (account passwords) at rest.

Each caller (client, server) loads its own key file via `load_or_create_key`
and never shares it with the other side.
"""
import base64
import os
import secrets

from Crypto.Cipher import AES

KEY_LENGTH = 32
NONCE_LENGTH = 16
TAG_LENGTH = 16


def load_or_create_key(path: str) -> bytes:
	"""Read a 32-byte key from `path`, generating and saving one (0o600) if missing."""
	if os.path.exists(path):
		with open(path, "rb") as f:
			key = f.read()
		if len(key) == KEY_LENGTH:
			return key
	key = secrets.token_bytes(KEY_LENGTH)
	with open(path, "wb") as f:
		f.write(key)
	os.chmod(path, 0o600)
	return key


def encrypt_secret(plaintext: str, key: bytes) -> str:
	cipher = AES.new(key, AES.MODE_GCM, nonce=secrets.token_bytes(NONCE_LENGTH))
	ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
	return base64.b64encode(cipher.nonce + tag + ciphertext).decode("ascii")


def decrypt_secret(blob: str, key: bytes) -> str:
	raw = base64.b64decode(blob)
	nonce, tag, ciphertext = raw[:NONCE_LENGTH], raw[NONCE_LENGTH:NONCE_LENGTH + TAG_LENGTH], raw[NONCE_LENGTH + TAG_LENGTH:]
	cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
	return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
