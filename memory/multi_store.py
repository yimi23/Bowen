"""
memory/multi_store.py — Per-user MemoryStore factory.

Each BOWEN user gets isolated memory:
  memory/users/{user_id}/bowen.db    — SQLite (conversations, tasks, bible_log, etc.)
  memory/users/{user_id}/chroma/     — ChromaDB vector store
  memory/users/{user_id}/profile.md  — User identity loaded into every agent prompt

MultiUserStore caches open MemoryStore instances so we don't re-initialize
ChromaDB on every WebSocket connection (SentenceTransformer load is expensive).

Migration: if Praise's legacy data exists at memory/bowen.db (pre-multi-user),
it is copied into memory/users/usr_admin/ on first access for that user_id.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

from config import Config
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

_PROFILE_TEMPLATE = """\
## Identity
Name: {display_name}
Username: {username}
BOWEN user since: {since}

## How I work
BOWEN is my personal AI chief of staff. I use it to get things done — code, research, email, calendar.

## Non-negotiables
(Fill these in as you interact with BOWEN — it learns your preferences.)

## What I'm working on
(Updated automatically as you use BOWEN.)
"""


class MultiUserStore:
    """
    Factory + in-process cache for per-user MemoryStore instances.
    Thread-safe (one instance per user, lock prevents double-initialization).
    """

    def __init__(self, users_base_dir: Path, config: Config) -> None:
        self._base = users_base_dir      # memory/users/
        self._config = config
        self._stores: dict[str, MemoryStore] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()      # guards _stores + _locks creation

    async def get_or_create(self, user_id: str, username: str = "", display_name: str = "") -> MemoryStore:
        """
        Return cached MemoryStore for user_id, or create and initialize a new one.
        Safe to call concurrently — uses per-user lock to prevent double-init.
        """
        # Fast path: already initialized
        if user_id in self._stores:
            return self._stores[user_id]

        # Get or create the per-user lock
        async with self._lock:
            if user_id not in self._locks:
                self._locks[user_id] = asyncio.Lock()
            user_lock = self._locks[user_id]

        async with user_lock:
            # Double-check after acquiring lock
            if user_id in self._stores:
                return self._stores[user_id]

            store = await self._initialize_user(user_id, username, display_name)
            self._stores[user_id] = store
            return store

    async def _initialize_user(self, user_id: str, username: str, display_name: str) -> MemoryStore:
        """Create directory, profile, migrate legacy data, initialize MemoryStore."""
        user_dir = self._base / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        db_path = user_dir / "bowen.db"
        chroma_path = user_dir / "chroma"
        profile_path = user_dir / "profile.md"

        # Migrate legacy data for admin user (pre-multi-user Praise data)
        if user_id == "usr_admin" and not db_path.exists():
            await self._migrate_legacy(db_path, chroma_path, profile_path)

        # Create starter profile if none exists
        if not profile_path.exists():
            from datetime import datetime, timezone
            since = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            profile_path.write_text(
                _PROFILE_TEMPLATE.format(
                    display_name=display_name or username or user_id,
                    username=username or user_id,
                    since=since,
                )
            )
            logger.info(f"Created starter profile for {user_id}")

        store = MemoryStore(db_path, chroma_path)
        store.set_profile_path(profile_path)
        await store.initialize()
        logger.info(f"MemoryStore initialized for {user_id}")
        return store

    async def _migrate_legacy(self, db_path: Path, chroma_path: Path, profile_path: Path) -> None:
        """
        One-time migration: copy legacy memory/bowen.db and memory/chroma/ into
        the admin user's directory. Runs only once (skipped if target already exists).
        """
        legacy_db = self._config.DB_PATH            # memory/bowen.db
        legacy_chroma = self._config.CHROMA_PATH    # memory/chroma/
        legacy_profile = self._config.PROFILE_PATH  # memory/user_profile.md

        migrated_any = False

        if legacy_db.exists():
            shutil.copy2(str(legacy_db), str(db_path))
            logger.info(f"Migrated legacy DB → {db_path}")
            migrated_any = True

        if legacy_chroma.exists() and legacy_chroma.is_dir():
            if chroma_path.exists():
                shutil.rmtree(str(chroma_path))
            shutil.copytree(str(legacy_chroma), str(chroma_path))
            logger.info(f"Migrated legacy ChromaDB → {chroma_path}")
            migrated_any = True

        if legacy_profile.exists() and not profile_path.exists():
            shutil.copy2(str(legacy_profile), str(profile_path))
            logger.info(f"Migrated legacy profile → {profile_path}")
            migrated_any = True

        if migrated_any:
            # Write a marker so future starts skip the migration check
            marker = db_path.parent / ".migrated"
            marker.write_text("legacy data migrated to multi-user layout\n")

    async def close_all(self) -> None:
        for user_id, store in list(self._stores.items()):
            try:
                await store.close()
            except Exception as e:
                logger.warning(f"Error closing store for {user_id}: {e}")
        self._stores.clear()

    def get_cached(self, user_id: str) -> Optional[MemoryStore]:
        return self._stores.get(user_id)

    def active_users(self) -> list[str]:
        return list(self._stores.keys())
