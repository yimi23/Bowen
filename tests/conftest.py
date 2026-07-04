"""
tests/conftest.py — Shared fixtures for the BOWEN characterization suite.

House rules (mirrors GENI's suite):
- Factory builders (make_*) with Partial-style overrides, one per domain object.
- Every external service is faked. The no_network fixture guarantees it:
  any socket connect attempt fails the test.
- Fixture database = real SQLite in tmp_path + FakeCollection standing in
  for ChromaDB (patched before MemoryStore construction — no production seam).
"""

from __future__ import annotations

import socket
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

# ── Network kill switch ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Block every outbound socket. Any live API call fails loudly."""

    def _blocked(*args, **kwargs):
        raise RuntimeError("Network call blocked by test suite (no_network fixture)")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def clear_prompt_cache():
    """BaseAgent keeps a module-global LRU prompt cache — isolate tests."""
    from agents import base

    base._PROMPT_CACHE.clear()
    yield
    base._PROMPT_CACHE.clear()


# ── Config factory ─────────────────────────────────────────────────────────────


def make_config(**overrides):
    from config import Config

    cfg = Config()
    cfg.ANTHROPIC_API_KEY = "test-key-not-real"
    cfg.GROQ_API_KEY = ""
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


@pytest.fixture
def config():
    return make_config()


# ── Fake ChromaDB collection ───────────────────────────────────────────────────


class FakeCollection:
    """
    In-memory stand-in for a ChromaDB collection.
    Distance model: 0.0 for an exact self-match, else distance_by_id[id],
    else default_distance. Tests set distance_by_id to stage similarity.
    """

    def __init__(self):
        self.docs: dict[str, str] = {}
        self.metas: dict[str, dict] = {}
        self.distance_by_id: dict[str, float] = {}
        self.default_distance: float = 0.5

    # -- chroma interface -------------------------------------------------------

    def add(self, documents, metadatas, ids):
        for doc, meta, cid in zip(documents, metadatas, ids):
            self.docs[cid] = doc
            self.metas[cid] = meta

    def count(self):
        return len(self.docs)

    def query(self, query_texts, n_results, where=None, include=None):
        query = query_texts[0]
        rows = []
        for cid, doc in self.docs.items():
            if where and not self._matches(where, self.metas[cid]):
                continue
            if doc == query:
                dist = 0.0
            else:
                dist = self.distance_by_id.get(cid, self.default_distance)
            rows.append((dist, doc, self.metas[cid]))
        rows.sort(key=lambda r: r[0])
        rows = rows[:n_results]
        return {
            "documents": [[r[1] for r in rows]],
            "metadatas": [[r[2] for r in rows]],
            "distances": [[r[0] for r in rows]],
        }

    def get(self, ids, include=None):
        metas = [self.metas[i] for i in ids if i in self.metas]
        return {"metadatas": metas}

    def update(self, ids, metadatas):
        for cid, meta in zip(ids, metadatas):
            self.metas[cid] = meta

    def delete(self, ids):
        for cid in ids:
            self.docs.pop(cid, None)
            self.metas.pop(cid, None)

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _matches(where: dict, meta: dict) -> bool:
        for field, cond in where.items():
            allowed = cond.get("$in", []) if isinstance(cond, dict) else [cond]
            if meta.get(field) not in allowed:
                return False
        return True


# ── MemoryStore fixture (real SQLite, fake Chroma) ─────────────────────────────


@pytest.fixture
async def store(tmp_path, monkeypatch):
    import memory.store as store_mod

    collection = FakeCollection()
    fake_client = SimpleNamespace(get_or_create_collection=lambda **kw: collection)
    monkeypatch.setattr(store_mod.chromadb, "PersistentClient", lambda path: fake_client)
    monkeypatch.setattr(
        store_mod.embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        lambda model_name: None,
    )

    ms = store_mod.MemoryStore(tmp_path / "test.db", chroma_path=tmp_path / "chroma")
    await ms.initialize()
    ms.fake_collection = collection  # test handle
    yield ms
    if ms._db is not None:
        await ms._db.close()


# ── Fake Anthropic client ──────────────────────────────────────────────────────


def text_response(text: str):
    """Anthropic-shaped response holding one text block."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
    )


def tool_use_response(name: str, tool_input: dict):
    """Anthropic-shaped response holding one tool_use block."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name=name, input=tool_input, id="tu_1")],
        stop_reason="tool_use",
    )


class FakeAnthropicClient:
    """Queue of canned responses returned by messages.create, in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeAnthropicClient ran out of canned responses")
        return self._responses.pop(0)


# ── Fake LLMProvider (for anything refactored onto the llm/ seam) ──────────────


class FakeProvider:
    """LLMProvider stand-in returning canned LLMResponse objects in order."""

    name = "fake"

    def __init__(self, responses=None):
        from llm.provider import LLMResponse

        self._responses = list(responses or [])
        self.calls: list[dict] = []
        self._response_cls = LLMResponse

    async def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        if not self._responses:
            raise AssertionError("FakeProvider ran out of canned responses")
        return self._responses.pop(0)

    def stream(self, messages, **kwargs):
        raise NotImplementedError("FakeProvider.stream not needed in these tests")


def llm_text(text: str):
    """LLMResponse holding one text block."""
    from llm.provider import LLMResponse

    return LLMResponse(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn")


def llm_tool_use(name: str, tool_input: dict):
    """LLMResponse holding one tool_use block."""
    from llm.provider import LLMResponse

    return LLMResponse(
        content=[SimpleNamespace(type="tool_use", name=name, input=tool_input, id="tu_1")],
        stop_reason="tool_use",
    )


# ── Fake Groq client ───────────────────────────────────────────────────────────


def groq_tool_call_response(fn_name: str, arguments: str):
    call = SimpleNamespace(
        id="call_1", function=SimpleNamespace(name=fn_name, arguments=arguments)
    )
    msg = SimpleNamespace(tool_calls=[call], content=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")])


def groq_no_tool_response():
    msg = SimpleNamespace(tool_calls=None, content="plain text, no tool")
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])


class FakeGroqClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response
