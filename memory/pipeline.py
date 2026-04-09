"""
memory/pipeline.py — Sleep-time extraction pipeline.
Fires 5 minutes after session ends. Uses Haiku to extract facts.
Updates ChromaDB + user_profile.md. Decouples memory quality from response latency.
This is the Letta/MemGPT pattern.
"""

import json
import asyncio
from typing import Optional

import anthropic

from memory.store import MemoryStore


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
    Runs after each session ends. Extracts facts, stores in ChromaDB,
    and optionally refreshes user_profile.md.
    """

    def __init__(self, memory: MemoryStore, api_key: str, model: str) -> None:
        self._memory = memory
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model  # always Haiku — fast + cheap

    async def run(self, session_id: str) -> int:
        """Extract memories from session. Returns count of memories stored."""
        transcript = await self._memory.get_session_transcript(session_id)
        if not transcript or len(transcript) < 100:
            return 0

        memories = await self._extract_memories(transcript)
        if not memories:
            return 0

        stored = 0
        for mem in memories:
            try:
                await self._memory.write_memory(
                    agent_id=mem.get("agent_id", "all"),
                    memory_type=mem.get("memory_type", "fact"),
                    content=mem["content"],
                    importance=float(mem.get("importance", 0.5)),
                    tags=mem.get("tags", []),
                )
                stored += 1
            except Exception:
                continue

        # Refresh user_profile.md with high-importance memories
        high_importance = [m for m in memories if m.get("importance", 0) >= 0.7]
        if high_importance:
            await self._refresh_profile(high_importance)

        return stored

    async def _extract_memories(self, transcript: str) -> list[dict]:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=EXTRACTION_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"Extract memories from this conversation:\n\n{transcript}"
                }],
            )
            text = response.content[0].text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception:
            return []

    async def _refresh_profile(self, new_memories: list[dict]) -> None:
        current_profile = self._memory.get_core_memory()
        if not current_profile:
            return

        facts_block = "\n".join(
            f"- [{m['memory_type']}] {m['content']}" for m in new_memories
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=PROFILE_UPDATE_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Current user_profile.md:\n{current_profile}\n\n"
                        f"New facts from today's session:\n{facts_block}\n\n"
                        f"Return the updated user_profile.md."
                    )
                }],
            )
            updated = response.content[0].text.strip()
            if updated and len(updated) > 200:  # sanity check
                self._memory.update_core_memory(updated)
        except Exception:
            pass


async def run_sleep_pipeline(memory: MemoryStore, session_id: str, api_key: str, model: str) -> None:
    """Convenience function — called by scheduler 5 min after session ends."""
    agent = SleepTimeAgent(memory, api_key, model)
    count = await agent.run(session_id)
    print(f"  [sleep-time] Extracted {count} memories from session {session_id[:8]}...")
