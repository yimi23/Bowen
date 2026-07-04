"""
memory/pipeline.py — Sleep-time extraction pipeline.
Fires after session ends. Uses Haiku to extract facts.
Updates ChromaDB + user_profile.md. Decouples memory quality from response latency.

Two-step process (Mem0 pattern):
  Step 1 — Extraction: Haiku finds facts, preferences, decisions from transcript.
  Step 2 — Conflict check: For each fact, search existing memories. If conflict found,
            Haiku decides: ADD (new distinct fact), UPDATE (supersedes existing), or NOOP.
"""

import json
import asyncio
import logging
from typing import Optional

from llm import AnthropicProvider
from memory.store import MemoryStore

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM = """
You are a memory extraction assistant. Given a conversation transcript, extract
facts, preferences, decisions, and context worth remembering long-term.

Output ONLY a JSON array of memory objects. No other text.

Each object must have:
{
  "content": "The fact to remember (one complete sentence)",
  "memory_type": "fact" | "preference" | "decision" | "research",
  "importance": 0.0-1.0,
  "agent_id": "which agent this is most relevant to: BOWEN|CAPTAIN|SCOUT|TAMARA|HELEN|all",
  "tags": ["tag1", "tag2"]
}

Rules:
- Only extract things that are genuinely useful to remember across future sessions.
- Skip pleasantries, filler, and transient task details.
- Preferences and non-negotiables get importance >= 0.8.
- Decisions that affect ongoing projects get importance >= 0.7.
- Facts about key people get importance >= 0.6.
- Research findings get importance 0.4-0.6.
- If nothing is worth extracting, return [].
"""

CONFLICT_CHECK_SYSTEM = """
You are a memory conflict resolver. You receive a NEW FACT and up to 3 EXISTING MEMORIES
that may conflict with or duplicate it.

Decide what to do. Output ONLY JSON. No other text.

{
  "action": "ADD" | "UPDATE" | "NOOP",
  "update_id": "chroma_id of the memory to update (only if action=UPDATE)",
  "reason": "one sentence explaining the decision"
}

Rules:
- ADD: the new fact is distinct and genuinely adds information.
- UPDATE: the new fact supersedes or corrects an existing memory (more recent, more specific, or contradicts).
  Set update_id to the chroma_id of the memory being replaced.
- NOOP: the new fact is already captured by existing memories — no action needed.

Be conservative: prefer NOOP over duplicate ADD.
"""

PROFILE_UPDATE_SYSTEM = """
You are a memory consolidation assistant. You will receive:
1. The current user_profile.md
2. New facts extracted from a recent session

Your job: update user_profile.md to reflect new information.
Rules:
- Preserve the existing structure and sections.
- Add or update facts that are new or changed.
- Remove facts that are now outdated if a newer fact contradicts them.
- Keep it concise — under 2,000 tokens total.
- Return ONLY the updated markdown. No preamble, no explanation.
"""


class SleepTimeAgent:
    """
    Runs after each session ends. Extracts facts, conflict-checks against existing
    memories, stores in ChromaDB, and optionally refreshes user_profile.md.
    """

    def __init__(self, memory: MemoryStore, api_key: str, model: str) -> None:
        self._memory = memory
        self._llm = AnthropicProvider(api_key)
        self._model = model  # always Haiku — fast + cheap

    async def run(self, session_id: str) -> int:
        """Extract memories from session. Returns count of memories stored."""
        transcript = await self._memory.get_session_transcript(session_id)
        if not transcript or len(transcript) < 100:
            return 0

        candidates = await self._extract_memories(transcript)
        if not candidates:
            return 0

        stored = 0
        for mem in candidates:
            try:
                stored += await self._process_memory(mem)
            except (ValueError, KeyError) as e:
                logger.warning("Skipping malformed memory: %s: %s", type(e).__name__, e)
            except Exception as e:
                logger.error("Failed to process memory: %s: %s", type(e).__name__, e)

        # Refresh user_profile.md with high-importance memories
        high_importance = [m for m in candidates if m.get("importance", 0) >= 0.7]
        if high_importance:
            await self._refresh_profile(high_importance)

        return stored

    async def _process_memory(self, mem: dict) -> int:
        """
        Conflict-check a candidate memory against existing memories.
        Returns 1 if stored, 0 if NOOP.
        """
        content = mem["content"]
        importance = float(mem.get("importance", 0.5))

        # Skip low-importance memories without conflict check (performance)
        if importance < 0.4:
            await self._memory.write_memory(
                agent_id=mem.get("agent_id", "all"),
                memory_type=mem.get("memory_type", "fact"),
                content=content,
                importance=importance,
                tags=mem.get("tags", []),
            )
            return 1

        # Search for similar existing memories
        existing_text = self._memory.search(content, top_k=3, min_relevance=0.75)
        if not existing_text:
            # No conflicts possible — just write
            chroma_id = await self._memory.write_memory(
                agent_id=mem.get("agent_id", "all"),
                memory_type=mem.get("memory_type", "fact"),
                content=content,
                importance=importance,
                tags=mem.get("tags", []),
            )
            await self._memory.log_memory_event(chroma_id, "ADD", content, "no existing memories")
            return 1

        # Conflict check via Haiku
        decision = await self._check_conflict(content, existing_text)
        action = decision.get("action", "ADD")
        reason = decision.get("reason", "")

        if action == "NOOP":
            logger.debug("Memory NOOP: %s | reason: %s", content[:60], reason)
            return 0

        if action == "UPDATE":
            update_id = decision.get("update_id", "")
            if update_id:
                # Delete the old memory, write the updated one
                try:
                    await self._memory.delete_memory(update_id)
                    await self._memory.log_memory_event(update_id, "DELETE", content, f"superseded: {reason}")
                except Exception:
                    pass
            chroma_id = await self._memory.write_memory(
                agent_id=mem.get("agent_id", "all"),
                memory_type=mem.get("memory_type", "fact"),
                content=content,
                importance=importance,
                tags=mem.get("tags", []),
            )
            await self._memory.log_memory_event(chroma_id, "UPDATE", content, reason)
            return 1

        # action == "ADD"
        chroma_id = await self._memory.write_memory(
            agent_id=mem.get("agent_id", "all"),
            memory_type=mem.get("memory_type", "fact"),
            content=content,
            importance=importance,
            tags=mem.get("tags", []),
        )
        await self._memory.log_memory_event(chroma_id, "ADD", content, reason)
        return 1

    async def _check_conflict(self, new_content: str, existing_text: str) -> dict:
        """Call Haiku to decide: ADD / UPDATE / NOOP."""
        try:
            response = await self._llm.complete(
                [{
                    "role": "user",
                    "content": (
                        f"NEW FACT:\n{new_content}\n\n"
                        f"EXISTING MEMORIES:\n{existing_text}"
                    )
                }],
                model=self._model,
                max_tokens=256,
                system=CONFLICT_CHECK_SYSTEM,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            logger.warning("Conflict check failed (%s) — defaulting to ADD", e)
            return {"action": "ADD", "reason": "conflict check failed"}

    async def _extract_memories(self, transcript: str) -> list[dict]:
        try:
            response = await self._llm.complete(
                [{
                    "role": "user",
                    "content": f"Extract memories from this conversation:\n\n{transcript}"
                }],
                model=self._model,
                max_tokens=1024,
                system=EXTRACTION_SYSTEM,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("Memory extraction: invalid JSON: %s", e)
            return []
        except Exception as e:
            logger.error("Memory extraction: error: %s: %s", type(e).__name__, e)
            return []

    async def _refresh_profile(self, new_memories: list[dict]) -> None:
        current_profile = self._memory.get_core_memory()
        if not current_profile:
            return

        facts_block = "\n".join(
            f"- [{m['memory_type']}] {m['content']}" for m in new_memories
        )

        try:
            response = await self._llm.complete(
                [{
                    "role": "user",
                    "content": (
                        f"Current user_profile.md:\n{current_profile}\n\n"
                        f"New facts from today's session:\n{facts_block}\n\n"
                        f"Return the updated user_profile.md."
                    )
                }],
                model=self._model,
                max_tokens=2048,
                system=PROFILE_UPDATE_SYSTEM,
            )
            updated = response.text.strip()
            if updated and len(updated) > 200:
                self._memory.update_core_memory(updated)
        except Exception as e:
            logger.error("Profile refresh: error: %s: %s", type(e).__name__, e)


async def run_sleep_pipeline(memory: MemoryStore, session_id: str, api_key: str, model: str) -> None:
    """Convenience function — called by gateway after session ends."""
    agent = SleepTimeAgent(memory, api_key, model)
    count = await agent.run(session_id)
    logger.info(
        "Sleep pipeline complete",
        extra={"session_id": session_id[:8], "memories_extracted": count},
    )
