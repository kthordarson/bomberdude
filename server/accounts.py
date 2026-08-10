"""SQLite-backed player account storage with AES-encrypted passwords."""
import secrets
import sqlite3
import time

from crypto_utils import decrypt_secret, encrypt_secret, load_or_create_key


class AccountStore:
	def __init__(self, db_path: str, key_path: str):
		self.db_path = db_path
		self.key = load_or_create_key(key_path)
		self._init_db()

	def _connect(self) -> sqlite3.Connection:
		return sqlite3.connect(self.db_path)

	def _init_db(self) -> None:
		conn = self._connect()
		try:
			conn.execute(
				"CREATE TABLE IF NOT EXISTS players ("
				"username TEXT PRIMARY KEY, "
				"password_enc TEXT NOT NULL, "
				"created_at REAL NOT NULL)"
			)
			conn.commit()
		finally:
			conn.close()

	def create_player(self, username: str, password: str) -> tuple[bool, str]:
		conn = self._connect()
		try:
			conn.execute(
				"INSERT INTO players (username, password_enc, created_at) VALUES (?, ?, ?)",
				(username, encrypt_secret(password, self.key), time.time()),
			)
			conn.commit()
			return True, "ok"
		except sqlite3.IntegrityError:
			return False, "username_taken"
		finally:
			conn.close()

	def authenticate(self, username: str, password: str) -> tuple[bool, str]:
		conn = self._connect()
		try:
			row = conn.execute("SELECT password_enc FROM players WHERE username = ?", (username,)).fetchone()
		finally:
			conn.close()
		if row is None:
			return False, "not_found"
		try:
			stored_password = decrypt_secret(row[0], self.key)
		except (ValueError, KeyError):
			return False, "invalid_credentials"
		if not secrets.compare_digest(stored_password, password):
			return False, "invalid_credentials"
		return True, "ok"
