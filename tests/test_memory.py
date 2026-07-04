"""
tests/test_memory.py — Characterization: the three-layer memory system.

1. user_profile.md is injected into every agent's system prompt.
2. The sleep agent extracts facts from a transcript into the vector store.
3. The nightly consolidator merges near-duplicates and prunes decayed entries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from bus.message_bus import MessageBus
from memory.consolidator import MemoryConsolidator
from memory.pipeline import SleepTimeAgent
from tests.conftest import FakeAnthropicClient, make_config, text_response

PROFILE_MARKER = "PRAISE-PROFILE-MARKER-7F3A"


# ── Factories ──────────────────────────────────────────────────────────────────


def make_memory_json(**overrides) -> dict:
    mem = {
        "content": "Praise prefers direct answers with no filler.",
        "memory_type": "preference",
        "importance": 0.9,
        "agent_id": "all",
        "tags": ["style"],
    }
    mem.update(overrides)
    return mem


async def seed_transcript(store, session_id: str) -> None:
    await store.log_message(
        session_id, 1, "user", "BOWEN",
        "I want every reply short and direct. No filler, no AI slop, active voice always.",
    )
    await store.log_message(
        session_id, 1, "assistant", "BOWEN",
        "Understood. Short and direct from here on. I will keep replies lean.",
    )


# ── 1. Profile injection ───────────────────────────────────────────────────────


class TestProfileInjection:
    """Every agent's system prompt carries user_profile.md content."""

    @pytest.fixture
    def profile_store(self, store, tmp_path):
        profile = tmp_path / "user_profile.md"
        profile.write_text(f"# Praise Oyimi\n{PROFILE_MARKER}\nCEO of Twine Campus.")
        store.set_profile_path(profile)
        return store

    async def test_all_six_agents_inject_profile(self, profile_store):
        from agents.bowen import BOWENAgent
        from agents.captain import CaptainAgent
        from agents.scout import ScoutAgent
        from agents.tamara import TamaraAgent
        from agents.helen import HelenAgent
        from agents.devops import DevOpsAgent

        config = make_config()
        bus = MessageBus()

        agent_classes = [
            BOWENAgent, CaptainAgent, ScoutAgent, TamaraAgent, HelenAgent, DevOpsAgent
        ]
        for cls in agent_classes:
            agent = cls(config, profile_store, bus)
            prompt = await agent.build_system_prompt("what should I do today")
            assert PROFILE_MARKER in prompt, f"{cls.__name__} lost the user profile"
            assert agent.base_identity.split("\n")[0] in prompt

    async def test_prompt_without_profile_omits_profile_section(self, store):
        from agents.bowen import BOWENAgent

        agent = BOWENAgent(make_config(), store, MessageBus())
        prompt = await agent.build_system_prompt("hello")
        assert PROFILE_MARKER not in prompt
        assert "## User Profile" not in prompt


# ── 2. Sleep-time extraction ───────────────────────────────────────────────────


class TestSleepPipeline:
    """Transcript → Haiku extraction (faked) → vector store writes."""

    async def test_extracts_facts_into_vector_store(self, store):
        session_id = "sess-extract"
        await seed_transcript(store, session_id)

        extracted = [
            make_memory_json(importance=0.9),
            make_memory_json(
                content="Praise is exploring a GENI and BOWEN merge.",
                memory_type="decision",
                importance=0.3,   # low importance skips the conflict check
            ),
        ]
        agent = SleepTimeAgent(store, api_key="test", model="haiku-test")
        agent._client = FakeAnthropicClient([text_response(json.dumps(extracted))])

        stored = await agent.run(session_id)

        assert stored == 2
        assert store.fake_collection.count() == 2
        docs = list(store.fake_collection.docs.values())
        assert "Praise prefers direct answers with no filler." in docs
        rows = await store._query("SELECT content FROM memories")
        assert len(rows) == 2

    async def test_short_transcript_extracts_nothing(self, store):
        await store.log_message("sess-short", 1, "user", "BOWEN", "hi")
        agent = SleepTimeAgent(store, api_key="test", model="haiku-test")
        agent._client = FakeAnthropicClient([])  # must never be called
        assert await agent.run("sess-short") == 0

    async def test_conflicting_fact_noops_instead_of_duplicating(self, store):
        session_id = "sess-conflict"
        await seed_transcript(store, session_id)

        # Existing memory that the new fact duplicates
        existing_id = await store.write_memory(
            agent_id="all", memory_type="preference",
            content="Praise wants direct answers.", importance=0.9,
        )
        # Close enough for search() to surface it (similarity 0.9 >= 0.75)
        store.fake_collection.distance_by_id[existing_id] = 0.1

        agent = SleepTimeAgent(store, api_key="test", model="haiku-test")
        agent._client = FakeAnthropicClient([
            text_response(json.dumps([make_memory_json(importance=0.9)])),  # extraction
            text_response(json.dumps({"action": "NOOP", "reason": "already known"})),
        ])

        stored = await agent.run(session_id)
        assert stored == 0
        assert store.fake_collection.count() == 1  # only the pre-existing memory

    async def test_unparseable_extraction_reply_stores_nothing(self, store):
        session_id = "sess-badjson"
        await seed_transcript(store, session_id)
        agent = SleepTimeAgent(store, api_key="test", model="haiku-test")
        agent._client = FakeAnthropicClient([text_response("I could not produce JSON, sorry")])
        assert await agent.run(session_id) == 0
        assert store.fake_collection.count() == 0


# ── 3. Nightly consolidation ───────────────────────────────────────────────────


class TestConsolidator:
    """3am job: temporal decay, near-duplicate merge, pruning."""

    async def _age_memory(self, store, chroma_id: str, days: int) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        await store._exec(
            "UPDATE memories SET last_accessed = ? WHERE chroma_id = ?", (old, chroma_id)
        )

    async def test_merges_near_duplicates(self, store):
        id_a = await store.write_memory(
            agent_id="all", memory_type="preference",
            content="Praise prefers tea over coffee.", importance=0.8,
        )
        id_b = await store.write_memory(
            agent_id="all", memory_type="preference",
            content="Praise likes tea more than coffee.", importance=0.6,
        )
        # When querying with A's content, B comes back at similarity 0.97
        store.fake_collection.distance_by_id[id_b] = 0.03

        cons = MemoryConsolidator(store, api_key="test", model="haiku-test")
        cons._client = FakeAnthropicClient([text_response("Praise prefers tea to coffee.")])

        stats = await cons.run()

        assert stats["merged"] == 1
        docs = list(store.fake_collection.docs.values())
        assert docs == ["Praise prefers tea to coffee."]
        # Merged memory averages the two importances
        merged_meta = list(store.fake_collection.metas.values())[0]
        assert merged_meta["importance"] == pytest.approx(0.7)

    async def test_decays_and_prunes_stale_memories(self, store):
        stale_id = await store.write_memory(
            agent_id="all", memory_type="research",
            content="Old research nobody has touched in ages.", importance=0.04,
        )
        fresh_id = await store.write_memory(
            agent_id="all", memory_type="fact",
            content="Fresh important fact.", importance=0.9,
        )
        await self._age_memory(store, stale_id, days=400)

        cons = MemoryConsolidator(store, api_key="test", model="haiku-test")
        cons._client = FakeAnthropicClient([])  # nothing similar enough to merge

        stats = await cons.run()

        assert stats["decayed"] >= 1
        assert stats["pruned"] == 1
        assert stale_id not in store.fake_collection.docs
        assert fresh_id in store.fake_collection.docs
        rows = await store._query("SELECT chroma_id FROM memories")
        assert [r["chroma_id"] for r in rows] == [fresh_id]

    async def test_recent_memories_are_untouched(self, store):
        cid = await store.write_memory(
            agent_id="all", memory_type="fact",
            content="Recently accessed fact.", importance=0.5,
        )
        cons = MemoryConsolidator(store, api_key="test", model="haiku-test")
        cons._client = FakeAnthropicClient([])
        stats = await cons.run()
        assert stats == {"decayed": 0, "merged": 0, "pruned": 0}
        assert cid in store.fake_collection.docs
