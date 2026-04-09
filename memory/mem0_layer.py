"""
memory/mem0_layer.py — Mem0 integration layer.
Runs alongside the existing ChromaDB store as an enhancement.
Uses Ollama (qwen3:4b) for LLM extraction + nomic-embed-text for vectors.
Fully local, no API keys.

Architecture:
  Existing store (store.py):  SQLite history + ChromaDB similarity search
  Mem0 layer (this file):     LLM-powered fact extraction + ranked retrieval

Both work together. The base store handles raw history.
Mem0 handles "what should BOWEN remember about Praise?"

Usage:
    mem0 = Mem0Layer(user_id="praise")
    mem0.initialize()
    mem0.add_conversation(messages)          # extract + store facts
    results = mem0.search("Remi competitor") # retrieve relevant memories
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Ollama endpoints
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "qwen3:4b"
EMBED_MODEL = "nomic-embed-text"

# ChromaDB path on S1 (reuses existing path — separate collection)
import os
CHROMA_PATH = os.environ.get(
    "BOWEN_MEM0_CHROMA_PATH",
    "/Volumes/S1/bowen/memory/chroma_mem0"  # separate from main store's chroma/
)


class Mem0Layer:
    """
    LLM-powered memory extraction using Mem0 + local Ollama.
    Wraps Mem0's Memory class with our config.
    Falls back gracefully if Ollama isn't running.
    """

    def __init__(self, user_id: str = "praise") -> None:
        self._user_id = user_id
        self._memory = None
        self._ready = False

    def initialize(self) -> bool:
        """Configure and initialize Mem0 with local models. Returns True if ready."""
        try:
            from mem0 import Memory

            config = {
                "llm": {
                    "provider": "ollama",
                    "config": {
                        "model": LLM_MODEL,
                        "ollama_base_url": OLLAMA_BASE_URL,
                        "temperature": 0,
                        "max_tokens": 2000,
                    }
                },
                "embedder": {
                    "provider": "ollama",
                    "config": {
                        "model": EMBED_MODEL,
                        "ollama_base_url": OLLAMA_BASE_URL,
                    }
                },
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "collection_name": "bowen_mem0",
                        "path": CHROMA_PATH,
                    }
                },
            }

            self._memory = Memory.from_config(config)
            self._ready = True
            logger.info("Mem0 ready — Ollama qwen3:4b + nomic-embed-text + ChromaDB")
            return True

        except Exception as e:
            logger.warning(f"Mem0 init failed (Ollama may not be running): {e}")
            return False

    def add_conversation(self, messages: list[dict]) -> list[dict]:
        """
        Extract and store facts from a conversation.
        messages: list of {"role": "user"|"assistant", "content": str}
        Returns list of stored memory objects.
        """
        if not self._ready:
            return []
        try:
            result = self._memory.add(messages, user_id=self._user_id)
            stored = result if isinstance(result, list) else []
            if stored:
                logger.debug(f"Mem0: stored {len(stored)} memories")
            return stored
        except Exception as e:
            logger.warning(f"Mem0 add failed: {e}")
            return []

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search memories by semantic similarity.
        Returns list of {memory: str, score: float} dicts.
        """
        if not self._ready:
            return []
        try:
            results = self._memory.search(query, user_id=self._user_id, limit=limit)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"Mem0 search failed: {e}")
            return []

    def get_all(self) -> list[dict]:
        """Return all stored memories for this user."""
        if not self._ready:
            return []
        try:
            result = self._memory.get_all(user_id=self._user_id)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"Mem0 get_all failed: {e}")
            return []

    def format_for_prompt(self, query: str, limit: int = 5) -> str:
        """
        Search and format memories as a prompt-ready string.
        Returns empty string if nothing relevant found.
        """
        results = self.search(query, limit=limit)
        if not results:
            return ""
        lines = []
        for r in results:
            mem = r.get("memory", r.get("text", ""))
            if mem:
                lines.append(f"- {mem}")
        return "\n".join(lines)

    @property
    def ready(self) -> bool:
        return self._ready
