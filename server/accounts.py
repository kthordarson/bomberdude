"""SQLite-backed player account storage with argon2-hashed passwords.

Passwords are hashed one-way (argon2), never encrypted/decrypted: a leaked
database only exposes hashes, not recoverable plaintext passwords.
"""
import sqlite3
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class AccountStore:
	def __init__(self, db_path: str):
		self.db_path = db_path
		self.hasher = PasswordHasher()
		self._init_db()

	def _connect(self) -> sqlite3.Connection:
		return sqlite3.connect(self.db_path)

	def _init_db(self) -> None:
		conn = self._connect()
		try:
			conn.execute(
				"CREATE TABLE IF NOT EXISTS players ("
				"username TEXT PRIMARY KEY, "
				"password_hash TEXT NOT NULL, "
				"created_at REAL NOT NULL)"
			)
			conn.commit()
		finally:
			conn.close()

	def create_player(self, username: str, password: str) -> tuple[bool, str]:
		conn = self._connect()
		try:
			conn.execute(
				"INSERT INTO players (username, password_hash, created_at) VALUES (?, ?, ?)",
				(username, self.hasher.hash(password), time.time()),
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
			row = conn.execute("SELECT password_hash FROM players WHERE username = ?", (username,)).fetchone()
		finally:
			conn.close()
		if row is None:
			return False, "not_found"
		try:
			self.hasher.verify(row[0], password)
		except VerifyMismatchError:
			return False, "invalid_credentials"
		return True, "ok"
