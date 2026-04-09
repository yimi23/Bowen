"""
memory/store.py — Unified async memory interface.
Phase 5+: Full aiosqlite migration for FastAPI compatibility.
ChromaDB stays sync (fast enough, <5ms per query, called from async context safely).

Architecture:
  - SQLite (aiosqlite): structured data — topics, conversations, messages, tasks, artifacts
  - ChromaDB: vector embeddings — one 'bowen_memories' collection, topic_id as filter
  - user_profile.md: always-on core memory, injected into every agent system prompt

NEVER change the embedding model (all-MiniLM-L6-v2) — existing vectors are incompatible.
Schema version 3: adds topics, conversations (replaces sessions), artifacts, input_mode.
"""

import aiosqlite
import asyncio
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions


# ── Schema ────────────────────────────────────────────────────────────────────
# Version 3: adds topics, artifacts, input_mode. Backward-compatible via ALTER TABLE.

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS topics (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    color       TEXT DEFAULT '#C4963A',
    instructions TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    topic_id    TEXT NOT NULL DEFAULT 'default',
    title       TEXT DEFAULT 'New conversation',
    created_at  TEXT NOT NULL,
    ended_at    TEXT,
    turn_count  INTEGER DEFAULT 0,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    topic_id        TEXT DEFAULT 'default',
    turn            INTEGER NOT NULL,
    role            TEXT NOT NULL,
    agent           TEXT NOT NULL,
    content         TEXT NOT NULL,
    input_mode      TEXT DEFAULT 'text',
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chroma_id       TEXT UNIQUE,
    agent_id        TEXT NOT NULL,
    memory_type     TEXT NOT NULL,
    content         TEXT NOT NULL,
    importance      REAL DEFAULT 0.5,
    tags            TEXT DEFAULT '[]',
    topic_id        TEXT DEFAULT 'all',
    created_at      TEXT NOT NULL,
    last_accessed   TEXT NOT NULL,
    access_count    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    agent       TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    context     TEXT,
    topic_id    TEXT DEFAULT 'default',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    context     TEXT NOT NULL,
    decision    TEXT NOT NULL,
    reasoning   TEXT,
    outcome     TEXT,
    agent       TEXT NOT NULL,
    topic_id    TEXT DEFAULT 'default',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER,
    conversation_id TEXT,
    topic_id        TEXT DEFAULT 'default',
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    content         TEXT,
    disk_path       TEXT,
    version         INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bible_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date    TEXT NOT NULL UNIQUE,
    completed   INTEGER DEFAULT 0,
    passage     TEXT DEFAULT '',
    logged_at   TEXT
);
"""

SEED_DATA = """
INSERT OR IGNORE INTO schema_version VALUES (3);
INSERT OR IGNORE INTO topics (id, name, description, color, created_at)
VALUES ('default', 'General', 'Default topic for all conversations', '#C4963A', datetime('now'));
"""

# NEVER change this model — embeddings are incompatible across models
EMBED_MODEL = "all-MiniLM-L6-v2"


class MemoryStore:
    """
    Async memory interface. Call await memory.initialize() after construction.
    Lazy DB init: _ensure_db() opens connection on first use if initialize() wasn't called.
    """

    def __init__(self, db_path: Path, chroma_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # aiosqlite connection — opened lazily or via initialize()
        self._db: Optional[aiosqlite.Connection] = None
        self._db_lock = asyncio.Lock()

        # ChromaDB — sync, fast, called from async context safely
        chroma_dir = chroma_path or (Path(self._db_path).parent / "chroma")
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._chroma = chromadb.PersistentClient(path=str(chroma_dir))
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
        self._collection = self._chroma.get_or_create_collection(
            name="bowen_memories",
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        self._profile_path: Optional[Path] = None

    async def initialize(self) -> None:
        """Open DB, apply schema, seed default data. Call once at startup."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.executescript(SEED_DATA)
        await self._db.commit()
        await self._migrate_v3()

    async def _ensure_db(self) -> None:
        """Lazy init — opens DB if initialize() wasn't called explicitly."""
        if self._db is None:
            await self.initialize()

    async def _migrate_v3(self) -> None:
        """
        Safe migration from schema v1/v2 to v3.
        Handles column renames (session_id → conversation_id) and new column additions.
        Uses try/except throughout — SQLite has no IF NOT EXISTS for ALTER TABLE.
        Requires SQLite 3.25.0+ for RENAME COLUMN (Python 3.8+ ships with 3.31+).
        """
        # Step 1: Rename session_id → conversation_id in messages (v1/v2 → v3 rename)
        # Also copy any old sessions rows into the new conversations table
        try:
            await self._db.execute(
                "ALTER TABLE messages RENAME COLUMN session_id TO conversation_id"
            )
        except Exception:
            pass  # already renamed or column doesn't exist

        # Step 2: Seed conversations from old sessions table if it exists
        try:
            await self._db.execute(
                """INSERT OR IGNORE INTO conversations (id, topic_id, title, created_at)
                   SELECT id, 'default', 'Migrated session', COALESCE(started_at, datetime('now'))
                   FROM sessions"""
            )
        except Exception:
            pass  # sessions table doesn't exist or already migrated

        # Step 3: Add new columns introduced in v3
        new_columns = [
            "ALTER TABLE messages ADD COLUMN topic_id TEXT DEFAULT 'default'",
            "ALTER TABLE messages ADD COLUMN input_mode TEXT DEFAULT 'text'",
            "ALTER TABLE memories ADD COLUMN chroma_id TEXT",
            "ALTER TABLE memories ADD COLUMN topic_id TEXT DEFAULT 'all'",
            "ALTER TABLE tasks ADD COLUMN topic_id TEXT DEFAULT 'default'",
        ]
        for sql in new_columns:
            try:
                await self._db.execute(sql)
            except Exception:
                pass  # column already exists

        await self._db.commit()

    def set_profile_path(self, path: Path) -> None:
        self._profile_path = path

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _exec(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Async write — acquires lock, executes, commits."""
        await self._ensure_db()
        async with self._db_lock:
            cursor = await self._db.execute(sql, params)
            await self._db.commit()
            return cursor

    async def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Async read — acquires lock, returns list of dicts."""
        await self._ensure_db()
        async with self._db_lock:
            cursor = await self._db.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Core Memory (user_profile.md) ─────────────────────────────────────────

    def get_core_memory(self) -> str:
        """Load user_profile.md — sync file read, called from sync context in build_system_prompt."""
        if self._profile_path and self._profile_path.exists():
            return self._profile_path.read_text()
        return ""

    def update_core_memory(self, new_content: str) -> None:
        """Overwrite user_profile.md. Called by sleep-time agent after session."""
        if self._profile_path:
            self._profile_path.write_text(new_content)

    # ── Topics (Notebooks) ────────────────────────────────────────────────────

    async def create_topic(
        self,
        name: str,
        description: str = "",
        color: str = "#C4963A",
        instructions: str = "",
    ) -> str:
        """Create a new topic/notebook. Returns topic_id."""
        topic_id = str(uuid.uuid4())
        await self._exec(
            "INSERT INTO topics (id, name, description, color, instructions, created_at) VALUES (?,?,?,?,?,?)",
            (topic_id, name, description, color, instructions, _now()),
        )
        return topic_id

    async def get_topics(self) -> list[dict]:
        """Return all topics with conversation count and last active time."""
        return await self._query(
            """SELECT t.id, t.name, t.description, t.color, t.instructions, t.created_at,
                      COUNT(c.id) as conversation_count,
                      MAX(c.created_at) as last_active
               FROM topics t
               LEFT JOIN conversations c ON c.topic_id = t.id
               GROUP BY t.id ORDER BY last_active DESC"""
        )

    async def get_topic(self, topic_id: str) -> Optional[dict]:
        rows = await self._query("SELECT * FROM topics WHERE id = ?", (topic_id,))
        return rows[0] if rows else None

    async def update_topic_instructions(self, topic_id: str, instructions: str) -> None:
        await self._exec(
            "UPDATE topics SET instructions = ? WHERE id = ?",
            (instructions, topic_id),
        )

    # ── Conversations ─────────────────────────────────────────────────────────

    async def create_conversation(
        self,
        topic_id: str = "default",
        title: str = "New conversation",
    ) -> str:
        """Create a new conversation within a topic. Returns conversation_id."""
        conv_id = str(uuid.uuid4())
        await self._exec(
            "INSERT INTO conversations (id, topic_id, title, created_at) VALUES (?,?,?,?)",
            (conv_id, topic_id, title, _now()),
        )
        return conv_id

    async def get_conversations(self, topic_id: str) -> list[dict]:
        """Return all conversations in a topic, most recent first."""
        return await self._query(
            "SELECT * FROM conversations WHERE topic_id = ? ORDER BY created_at DESC",
            (topic_id,),
        )

    async def end_conversation(self, conversation_id: str) -> None:
        await self._exec(
            "UPDATE conversations SET ended_at = ? WHERE id = ?",
            (_now(), conversation_id),
        )

    async def update_conversation_title(self, conversation_id: str, title: str) -> None:
        await self._exec(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )

    # ── Legacy session compatibility (clawdbot.py CLI) ────────────────────────

    async def create_session(self, session_id: str, topic_id: str = "default") -> None:
        """Create conversation — alias for CLI compatibility."""
        await self._exec(
            "INSERT OR IGNORE INTO conversations (id, topic_id, title, created_at) VALUES (?,?,?,?)",
            (session_id, topic_id, "CLI Session", _now()),
        )

    async def end_session(self, session_id: str) -> None:
        await self.end_conversation(session_id)

    # ── Semantic Memory (ChromaDB) ────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 8,
        min_relevance: float = 0.7,
        time_decay: bool = True,
        topic_id: Optional[str] = None,
    ) -> str:
        """
        Vector search with optional time decay and topic filtering.
        Sync — ChromaDB is fast (<5ms) and safe to call from async context.
        Score = cosine_similarity × exp(-0.01 × age_days) × importance
        """
        count = self._collection.count()
        if count == 0:
            return ""

        k = min(top_k, count)
        query_kwargs: dict = {
            "query_texts": [query],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        # Filter to topic if provided, or search globally
        if topic_id and topic_id != "all":
            query_kwargs["where"] = {"topic_id": {"$in": [topic_id, "all"]}}

        results = self._collection.query(**query_kwargs)

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        now = datetime.now(timezone.utc)
        scored = []
        for doc, meta, dist in zip(docs, metas, distances):
            similarity = 1.0 - dist
            if similarity < min_relevance:
                continue

            score = similarity
            if time_decay and "created_at" in meta:
                try:
                    created = datetime.fromisoformat(meta["created_at"])
                    age_days = (now - created).days
                    score *= math.exp(-0.01 * age_days)
                except Exception:
                    pass

            score *= float(meta.get("importance", 0.5))
            scored.append((score, doc, meta))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)

        # Update access stats for retrieved memories (fire-and-forget, sync)
        chroma_ids = [m.get("chroma_id") for _, _, m in scored if m.get("chroma_id")]
        if chroma_ids:
            try:
                asyncio.create_task(self._update_access(chroma_ids))
            except RuntimeError:
                pass  # called from asyncio.to_thread; access stats skipped

        lines = []
        for _, doc, meta in scored:
            mtype = meta.get("memory_type", "fact")
            agent = meta.get("agent_id", "")
            lines.append(f"- [{mtype}|{agent}] {doc}")

        return "\n".join(lines)

    async def _update_access(self, chroma_ids: list[str]) -> None:
        """Update last_accessed for retrieved memories — async fire-and-forget."""
        try:
            await self._exec(
                f"UPDATE memories SET last_accessed = ?, access_count = access_count + 1 "
                f"WHERE chroma_id IN ({','.join('?' * len(chroma_ids))})",
                tuple([_now()] + chroma_ids),
            )
        except Exception:
            pass

    async def write_memory(
        self,
        agent_id: str,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
        topic_id: str = "all",
    ) -> str:
        """Write to ChromaDB + SQLite. Returns chroma_id."""
        chroma_id = str(uuid.uuid4())
        now = _now()

        metadata = {
            "chroma_id": chroma_id,
            "agent_id": agent_id,
            "memory_type": memory_type,
            "importance": importance,
            "tags": json.dumps(tags or []),
            "topic_id": topic_id,
            "created_at": now,
        }

        self._collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[chroma_id],
        )

        await self._exec(
            """INSERT INTO memories
               (chroma_id, agent_id, memory_type, content, importance, tags, topic_id, created_at, last_accessed)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (chroma_id, agent_id, memory_type, content, importance,
             json.dumps(tags or []), topic_id, now, now),
        )
        return chroma_id

    def get_all_memories_for_consolidation(self) -> list[dict]:
        """Sync — called from consolidator which runs in async job context."""
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(self._db_path)
        conn.row_factory = _sqlite3.Row
        cursor = conn.execute(
            "SELECT chroma_id, content, importance, created_at, last_accessed, access_count, topic_id FROM memories"
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    async def delete_memory(self, chroma_id: str) -> None:
        self._collection.delete(ids=[chroma_id])
        await self._exec("DELETE FROM memories WHERE chroma_id = ?", (chroma_id,))

    async def update_memory_importance(self, chroma_id: str, importance: float) -> None:
        await self._exec(
            "UPDATE memories SET importance = ? WHERE chroma_id = ?",
            (importance, chroma_id),
        )
        existing = self._collection.get(ids=[chroma_id], include=["metadatas"])
        if existing["metadatas"]:
            meta = existing["metadatas"][0]
            meta["importance"] = importance
            self._collection.update(ids=[chroma_id], metadatas=[meta])

    # ── Messages ──────────────────────────────────────────────────────────────

    async def log_message(
        self,
        conversation_id: str,
        turn: int,
        role: str,
        agent: str,
        content: str,
        input_mode: str = "text",
        topic_id: str = "default",
    ) -> None:
        await self._ensure_db()
        async with self._db_lock:
            await self._db.execute(
                """INSERT INTO messages
                   (conversation_id, topic_id, turn, role, agent, content, input_mode, timestamp)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (conversation_id, topic_id, turn, role, agent, content, input_mode, _now()),
            )
            await self._db.execute(
                "UPDATE conversations SET turn_count = turn_count + 1 WHERE id = ?",
                (conversation_id,),
            )
            await self._db.commit()

    async def get_recent_history(
        self,
        conversation_id: str,
        n: int = 10,
    ) -> list[dict]:
        """Return last N messages in chronological order (id ordering = true insertion order)."""
        rows = await self._query(
            "SELECT role, agent, content, timestamp FROM messages "
            "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, n),
        )
        return list(reversed(rows))

    async def get_messages(self, conversation_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
        """Paginated message history for API."""
        return await self._query(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC LIMIT ? OFFSET ?",
            (conversation_id, limit, offset),
        )

    async def get_session_transcript(self, conversation_id: str) -> str:
        """Full transcript for sleep-time extraction."""
        rows = await self.get_recent_history(conversation_id, n=999)
        lines = []
        for r in rows:
            prefix = "User" if r["role"] == "user" else r["agent"]
            lines.append(f"{prefix}: {r['content']}")
        return "\n".join(lines)

    # ── Tasks ─────────────────────────────────────────────────────────────────

    async def create_task(
        self,
        title: str,
        agent: str,
        context: str = "",
        topic_id: str = "default",
    ) -> int:
        cursor = await self._exec(
            "INSERT INTO tasks (title, agent, context, topic_id, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (title, agent, context, topic_id, _now(), _now()),
        )
        return cursor.lastrowid

    async def update_task(self, task_id: int, status: str) -> None:
        await self._exec(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), task_id),
        )

    async def get_open_tasks(self) -> list[dict]:
        return await self._query(
            "SELECT * FROM tasks WHERE status NOT IN ('done','cancelled') ORDER BY created_at DESC"
        )

    # ── Artifacts (generated files) ───────────────────────────────────────────

    async def save_artifact(
        self,
        filename: str,
        file_type: str,
        content: str,
        disk_path: str = "",
        conversation_id: str = "",
        topic_id: str = "default",
        message_id: int = 0,
    ) -> int:
        cursor = await self._exec(
            """INSERT INTO artifacts (message_id, conversation_id, topic_id, filename, file_type, content, disk_path, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (message_id, conversation_id, topic_id, filename, file_type, content, disk_path, _now()),
        )
        return cursor.lastrowid

    async def get_artifacts(self, topic_id: Optional[str] = None) -> list[dict]:
        if topic_id:
            return await self._query(
                "SELECT * FROM artifacts WHERE topic_id = ? ORDER BY created_at DESC",
                (topic_id,),
            )
        return await self._query("SELECT * FROM artifacts ORDER BY created_at DESC")

    async def get_artifact(self, artifact_id: int) -> Optional[dict]:
        rows = await self._query("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
        return rows[0] if rows else None

    # ── Decisions ─────────────────────────────────────────────────────────────

    async def log_decision(
        self,
        context: str,
        decision: str,
        reasoning: str,
        agent: str,
        topic_id: str = "default",
    ) -> int:
        cursor = await self._exec(
            "INSERT INTO decisions (context, decision, reasoning, agent, topic_id, created_at) VALUES (?,?,?,?,?,?)",
            (context, decision, reasoning, agent, topic_id, _now()),
        )
        return cursor.lastrowid

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Dashboard stats."""
        tasks = await self._query("SELECT COUNT(*) as n FROM tasks WHERE status != 'done'")
        convs = await self._query("SELECT COUNT(*) as n FROM conversations")
        files = await self._query("SELECT COUNT(*) as n FROM artifacts")
        return {
            "memory_count": self._collection.count(),
            "open_tasks": tasks[0]["n"] if tasks else 0,
            "conversations": convs[0]["n"] if convs else 0,
            "files_generated": files[0]["n"] if files else 0,
        }

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
