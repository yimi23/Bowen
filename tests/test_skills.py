"""
tests/test_skills.py — Progressive disclosure, proven at each tier.

Tier 1: Y carries the index (names + descriptions), NOT the bodies.
Tier 2: standing skills ride full-body in each agent's system prompt.
Tier 3: mounted skills load at dispatch-brief receipt, for that task only.
Plus: the DEVOPS structural audit, and tenant skill walls.
"""

from __future__ import annotations

import pytest

from bus.message_bus import MessageBus
from bus.schema import DispatchBriefPayload
from core.skills import SkillLibrary, house_library, validate_skill
from llm import resolve_agent_skills
from tests.conftest import make_config


# ── Library mechanics ──────────────────────────────────────────────────────────


def write_skill(base, name: str, description: str, body: str) -> None:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n")


class TestLibrary:
    def test_index_is_names_and_descriptions_only(self, tmp_path):
        write_skill(tmp_path, "test-skill", "When testing things.", "SECRET-BODY-CONTENT")
        lib = SkillLibrary(tmp_path)
        index = lib.index_text()
        assert "- test-skill: When testing things." in index
        assert "SECRET-BODY-CONTENT" not in index   # tier 1 never carries bodies

    def test_load_returns_body_without_frontmatter(self, tmp_path):
        write_skill(tmp_path, "a-skill", "desc", "## The rule\nDo the thing.")
        lib = SkillLibrary(tmp_path)
        body = lib.load("a-skill")
        assert "Do the thing." in body
        assert "description:" not in body

    def test_load_many_skips_unknown_skills(self, tmp_path):
        write_skill(tmp_path, "real", "desc", "body")
        lib = SkillLibrary(tmp_path)
        combined = lib.load_many(["real", "imaginary"])
        assert "### Skill: real" in combined
        assert "imaginary" not in combined

    def test_house_library_covers_the_authored_inventory(self):
        lib = house_library()
        for expected in [
            "delegating-and-scaling", "synthesizing-one-voice", "git-discipline",
            "test-first-legacy", "condensed-returns", "praise-voice",
            "approval-protocol", "bible-accountability", "verdict-format",
            "skill-audit", "elder-voice", "fall-response-protocol", "speaking-pidgin",
        ]:
            assert expected in lib.names(), f"{expected} missing from house library"

    def test_index_stays_cheap_per_skill(self):
        lib = house_library()
        lines = lib.index_text().splitlines()
        # ~80 tokens ≈ 320 chars; keep a hard ceiling so descriptions stay lean
        for line in lines:
            assert len(line) < 400, f"index line too fat: {line[:60]}..."


class TestSkillAudit:
    def test_valid_skill_passes(self, tmp_path):
        write_skill(tmp_path, "clean-skill", "A clean description.", "Real instructions.")
        assert validate_skill(tmp_path / "clean-skill") == []

    def test_missing_description_is_caught(self, tmp_path):
        d = tmp_path / "bad-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: bad-skill\n---\n\nbody")
        assert any("description" in e for e in validate_skill(d))

    def test_name_folder_mismatch_is_caught(self, tmp_path):
        d = tmp_path / "folder-name"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: other-name\ndescription: d\n---\n\nbody")
        assert any("differ" in e for e in validate_skill(d))

    def test_empty_body_is_caught(self, tmp_path):
        d = tmp_path / "hollow"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: hollow\ndescription: d\n---\n\n")
        assert any("empty body" in e for e in validate_skill(d))

    def test_every_house_skill_passes_the_audit(self):
        from pathlib import Path

        skills_dir = Path(__file__).parent.parent / "skills"
        errors = []
        for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            errors.extend(validate_skill(d))
        assert errors == []


# ── Tier 2: standing skills in agent prompts ───────────────────────────────────


class TestStandingSkills:
    def test_yaml_declares_standing_skills_for_all_seven(self):
        for agent, expected_first in [
            ("BOWEN", "delegating-and-scaling"), ("CAPTAIN", "buildspec-planning"),
            ("SCOUT", "research-methodology"), ("TAMARA", "praise-voice"),
            ("HELEN", "morning-briefing-format"), ("DEVOPS", "security-audit-checklist"),
            ("GENI", "elder-voice"),
        ]:
            skills, _ = resolve_agent_skills(agent)
            assert expected_first in skills, f"{agent} missing {expected_first}"

    async def test_captain_prompt_carries_git_discipline_full_body(self, store):
        from agents.captain import CaptainAgent

        agent = CaptainAgent(make_config(), store, MessageBus())
        prompt = await agent.build_system_prompt("build a parser")
        assert "### Skill: git-discipline" in prompt
        assert "NEVER push without being asked" in prompt      # full body, not index
        assert "## Skill Library Index" not in prompt          # workers don't carry the index

    async def test_tamara_prompt_carries_the_writing_law(self, store):
        from agents.tamara import TamaraAgent

        agent = TamaraAgent(make_config(), store, MessageBus())
        prompt = await agent.build_system_prompt("draft an email")
        assert "### Skill: praise-voice" in prompt
        assert "NO em dashes" in prompt

    async def test_bowen_carries_index_but_not_worker_bodies(self, store):
        from agents.bowen import BOWENAgent

        agent = BOWENAgent(make_config(), store, MessageBus())
        prompt = await agent.build_system_prompt("plan my week")
        # Tier 1: the discovery index is present...
        assert "## Skill Library Index" in prompt
        assert "- verdict-format:" in prompt
        # ...tier 2: Y's OWN standing skills are full-body...
        assert "### Skill: delegating-and-scaling" in prompt
        assert "four-part contract" in prompt.lower()
        # ...but OTHER agents' bodies are NOT loaded (progressive disclosure).
        assert "DO NOT SHIP — any CRITICAL" not in prompt      # verdict-format body absent


# ── Tier 3: mounted skills ride the dispatch brief ─────────────────────────────


class TestDispatchBrief:
    async def test_brief_travels_bus_and_mounts_skills(self, store):
        from agents.bowen import BOWENAgent
        from agents.scout import ScoutAgent

        config = make_config()
        bus = MessageBus()
        bowen = BOWENAgent(config, store, bus)
        scout = ScoutAgent(config, store, bus)

        received: dict = {}

        async def capture(text, send=None):
            received["text"] = text
            return "ok"

        scout.respond = capture   # test seam: capture the composed task text

        await bowen.dispatch_brief(
            "SCOUT",
            objective="Find the three strongest Pidgin corpora online.",
            output_format="FINDINGS / CONFIDENCE / SOURCES / NOT FOUND, under 400 words.",
            tools_permitted=["web_search", "web_fetch"],
            boundaries="Public sources only. Stop after two dry queries.",
            mounted_skills=["speaking-pidgin"],
        )

        msg = await bus.receive("SCOUT", timeout=0.1)
        assert isinstance(msg.payload, DispatchBriefPayload)
        result = await scout.handle(msg)
        assert result == "ok"

        text = received["text"]
        # All four parts of the contract are present...
        assert "## Objective" in text and "strongest Pidgin corpora" in text
        assert "## Output format (hard contract)" in text
        assert "web_search, web_fetch" in text
        assert "## Boundaries" in text and "two dry queries" in text
        # ...and the mounted skill's FULL BODY rode in (tier 3).
        assert "### Skill: speaking-pidgin" in text
        assert "GROUND TRUTH" in text

    def test_brief_requires_the_contract_core(self):
        with pytest.raises(Exception):
            DispatchBriefPayload(objective="only an objective")   # no output_format


# ── Tenant skill walls ─────────────────────────────────────────────────────────


class TestTenantSkillIsolation:
    def test_tenant_skill_is_invisible_to_other_tenants(self, tmp_path):
        house = tmp_path / "house"
        write_skill(house, "shared-skill", "House-wide.", "house body")
        tenant_a = tmp_path / "a" / "skills"
        write_skill(tenant_a, "bank-integration", "Tenant A's private bank flow.", "A-PRIVATE")

        lib_a = SkillLibrary(house, tenant_a)
        lib_b = SkillLibrary(house, tmp_path / "b" / "skills")   # B has no skills dir

        assert "bank-integration" in lib_a.names()
        assert "bank-integration" not in lib_b.names()
        assert lib_b.load("bank-integration") is None
        assert "A-PRIVATE" not in lib_b.index_text()

    def test_tenant_skill_cannot_shadow_a_house_skill(self, tmp_path):
        house = tmp_path / "house"
        write_skill(house, "approval-protocol", "The constitution.", "HOUSE LAW")
        tenant = tmp_path / "t" / "skills"
        write_skill(tenant, "approval-protocol", "Loosened rules.", "TENANT OVERRIDE")

        lib = SkillLibrary(house, tenant)
        assert "HOUSE LAW" in lib.load("approval-protocol")
        assert "TENANT OVERRIDE" not in lib.load("approval-protocol")
