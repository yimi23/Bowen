"""
memory/users.py — User account management.

Handles user registration, API key generation, and authentication.
Users are stored in memory/users.db (separate from any user's personal DB).

API key flow:
  1. Admin (Praise) calls POST /api/admin/users to create a user
  2. System generates a UUID key, returns it ONCE (plaintext)
  3. Key is hashed (SHA-256) and stored — only the hash is persisted
  4. User sends key in WS URL: ws://localhost:8000/ws/chat?key=<api_key>
  5. Server hashes incoming key, looks up hash in users.db

Users table:
  id            TEXT PRIMARY KEY  (usr_<8 hex chars>, e.g. usr_a1b2c3d4)
  username      TEXT UNIQUE
  display_name  TEXT
  key_hash      TEXT UNIQUE
  is_admin      INTEGER (0 or 1)
  created_at    TEXT
  last_seen_at  TEXT
"""

from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    username     TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    last_seen_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def _make_user_id() -> str:
    return "usr_" + secrets.token_hex(4)


def _make_api_key() -> str:
    alphabet = string.ascii_letters + string.digits
    return "bwn_" + "".join(secrets.choice(alphabet) for _ in range(40))


class UserManager:
    """
    Manages BOWEN user accounts. Async, backed by aiosqlite.
    Single-writer — safe for the single-server deployment.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # ── User creation ─────────────────────────────────────────────────────────

    async def create_admin(self, username: str, display_name: str, api_key: str) -> str:
        """
        Create the admin user with a known API key (from .env).
        Idempotent — silently succeeds if admin already exists.
        Returns the admin's user_id.
        """
        existing = await self.get_by_username(username)
        if existing:
            return existing["id"]

        user_id = "usr_admin"
        key_hash = _hash_key(api_key)
        now = _now()
        await self._db.execute(
            "INSERT OR IGNORE INTO users (id, username, display_name, key_hash, is_admin, created_at) "
            "VALUES (?,?,?,?,1,?)",
            (user_id, username, display_name, key_hash, now),
        )
        await self._db.commit()
        return user_id

    async def create_user(
        self,
        username: str,
        display_name: str,
    ) -> dict:
        """
        Create a new user. Returns user metadata + plaintext API key (shown once).
        Raises ValueError if username already taken.
        """
        existing = await self.get_by_username(username)
        if existing:
            raise ValueError(f"Username '{username}' already exists")

        user_id = _make_user_id()
        api_key = _make_api_key()
        key_hash = _hash_key(api_key)
        now = _now()

        await self._db.execute(
            "INSERT INTO users (id, username, display_name, key_hash, is_admin, created_at) "
            "VALUES (?,?,?,?,0,?)",
            (user_id, username, display_name, key_hash, now),
        )
        await self._db.commit()

        return {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "api_key": api_key,   # plaintext — shown once, then unrecoverable
            "is_admin": False,
        }

    # ── Authentication ────────────────────────────────────────────────────────

    async def authenticate(self, api_key: str) -> Optional[dict]:
        """
        Validate an API key. Returns user dict or None.
        Updates last_seen_at on success.
        """
        if not api_key:
            return None
        key_hash = _hash_key(api_key)
        async with self._db.execute(
            "SELECT id, username, display_name, is_admin FROM users WHERE key_hash = ?",
            (key_hash,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        user = dict(row)
        # Update last_seen_at (fire-and-forget)
        await self._db.execute(
            "UPDATE users SET last_seen_at = ? WHERE id = ?",
            (_now(), user["id"]),
        )
        await self._db.commit()
        return user

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_by_username(self, username: str) -> Optional[dict]:
        async with self._db.execute(
            "SELECT id, username, display_name, is_admin, created_at, last_seen_at "
            "FROM users WHERE username = ?",
            (username,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        async with self._db.execute(
            "SELECT id, username, display_name, is_admin, created_at, last_seen_at "
            "FROM users WHERE id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def list_users(self) -> list[dict]:
        async with self._db.execute(
            "SELECT id, username, display_name, is_admin, created_at, last_seen_at "
            "FROM users ORDER BY created_at"
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def user_count(self) -> int:
        async with self._db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
        return row[0] if row else 0

    async def regenerate_key(self, user_id: str) -> Optional[str]:
        """Generate a new API key for a user. Returns plaintext key (shown once)."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        api_key = _make_api_key()
        key_hash = _hash_key(api_key)
        await self._db.execute(
            "UPDATE users SET key_hash = ? WHERE id = ?",
            (key_hash, user_id),
        )
        await self._db.commit()
        return api_key
