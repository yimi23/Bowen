"""
memory/consolidator.py — Nightly memory consolidation (3am job).
Merges near-duplicate memories (cosine sim > 0.95).
Applies temporal decay: importance × 0.95 per 30 days unaccessed.
Prunes memories below 0.05 importance that haven't been accessed in 90+ days.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic

from memory.store import MemoryStore

logger = logging.getLogger(__name__)


MERGE_SYSTEM = """
You are given two memory statements that are near-duplicates.
Merge them into one single, precise sentence that captures the combined meaning.
Return ONLY the merged sentence. No preamble.
"""


class MemoryConsolidator:
    def __init__(self, memory: MemoryStore, api_key: str, model: str) -> None:
        self._memory = memory
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def run(self) -> dict:
        """Full nightly consolidation. Returns stats."""
        stats = {"decayed": 0, "merged": 0, "pruned": 0}

        all_memories = self._memory.get_all_memories_for_consolidation()
        if not all_memories:
            return stats

        now = datetime.now(timezone.utc)

        # 1. Apply temporal decay — importance × 0.95 per 30 days unaccessed
        for mem in all_memories:
            if not mem.get("chroma_id"):
                continue
            try:
                last = datetime.fromisoformat(mem["last_accessed"])
                # DB stores naive UTC strings — make aware before subtracting
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                days_since = (now - last).days
                periods = days_since // 30
                current_importance = float(mem.get("importance", 0.5))

                if periods > 0:
                    decayed = current_importance * (0.95 ** periods)
                    if abs(decayed - current_importance) > 0.01:
                        await self._memory.update_memory_importance(mem["chroma_id"], decayed)
                        stats["decayed"] += 1
                else:
                    decayed = current_importance

                # Prune memories below 0.05 importance unaccessed for 90+ days
                if decayed < 0.05 and days_since > 90:
                    await self._memory.delete_memory(mem["chroma_id"])
                    stats["pruned"] += 1

            except ValueError as e:
                logger.warning(
                    "Consolidation: invalid date for memory %s: %s",
                    mem.get("chroma_id", "?"), e,
                )
                continue
            except Exception as e:
                logger.error(
                    "Consolidation: error processing memory %s: %s: %s",
                    mem.get("chroma_id", "?"), type(e).__name__, e,
                )
                continue

        # 2. Find and merge near-duplicates (cosine sim > 0.95)
        merged_ids: set[str] = set()
        for mem in all_memories:
            cid = mem.get("chroma_id")
            if not cid or cid in merged_ids:
                continue

            try:
                results = self._memory._collection.query(
                    query_texts=[mem["content"]],
                    n_results=min(3, self._memory._collection.count()),
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as e:
                logger.warning(
                    "Consolidation: ChromaDB query failed for memory %s: %s: %s",
                    cid, type(e).__name__, e,
                )
                continue

            docs  = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]

            for doc, meta, dist in zip(docs, metas, dists):
                other_id = meta.get("chroma_id", "")
                if other_id == cid or other_id in merged_ids:
                    continue
                similarity = 1.0 - dist
                if similarity > 0.95:
                    merged = await self._merge(mem["content"], doc)
                    if merged:
                        try:
                            await self._memory.delete_memory(cid)
                            await self._memory.delete_memory(other_id)
                            avg_importance = (
                                float(mem.get("importance", 0.5)) +
                                float(meta.get("importance", 0.5))
                            ) / 2
                            await self._memory.write_memory(
                                agent_id=meta.get("agent_id", "all"),
                                memory_type=meta.get("memory_type", "fact"),
                                content=merged,
                                importance=avg_importance,
                            )
                            merged_ids.update([cid, other_id])
                            stats["merged"] += 1
                        except Exception as e:
                            logger.error(
                                "Consolidation: merge write failed for %s + %s: %s: %s",
                                cid, other_id, type(e).__name__, e,
                            )
                        break

        logger.info(
            "Nightly consolidation complete",
            extra=stats,
        )
        return stats

    async def _merge(self, a: str, b: str) -> Optional[str]:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=100,
                system=MERGE_SYSTEM,
                messages=[{"role": "user", "content": f"Memory 1: {a}\nMemory 2: {b}"}],
            )
            return response.content[0].text.strip()
        except anthropic.APIError as e:
            logger.warning("Consolidation: merge API error: %s", e)
            return None
        except Exception as e:
            logger.error("Consolidation: unexpected merge error: %s: %s", type(e).__name__, e)
            return None
