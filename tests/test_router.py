"""
tests/test_router.py — Characterization: two-tier routing.

Tier 1 is pure regex: correct agent, zero model calls (no_network proves it).
Tier 2 is Groq behind a mock, with the Anthropic Haiku fallback behind a fake,
and every unparseable shape lands safely on BOWEN.
"""

from __future__ import annotations

import pytest

import agents  # noqa: F401 — agents must load before routing (mirrors main.py import order)
import routing.tier2 as tier2
from routing.tier1 import route as tier1_route
from tests.conftest import FakeProvider, llm_text, llm_tool_use, make_config


def wire_tier2(monkeypatch, primary=None, fallback=None):
    """Point tier2 at fake providers, bypassing agents.yaml resolution."""
    table = {
        "tier2_primary": (primary, "llama-test", 0),
        "tier2_fallback": (fallback, "haiku-test", None),
    }

    def fake_resolve(role, config):
        provider = table[role][0]
        if provider is None:
            raise AssertionError(f"{role} should not have been used")
        return table[role]

    monkeypatch.setattr(tier2, "resolve_routing_llm", fake_resolve)


class TestTier1Regex:
    """Explicit commands and obvious keywords route with no model call."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("@captain fix the login bug", "CAPTAIN"),
            ("/code write me a parser", "CAPTAIN"),
            ("write a python script to rename files", "CAPTAIN"),
            ("refactor the payment module", "CAPTAIN"),
            ("@scout what changed in the market", "SCOUT"),
            ("research competitors for elder care apps", "SCOUT"),
            ("look up the pricing for Twilio", "SCOUT"),
            ("@tamara draft a reply", "TAMARA"),
            ("check my email please", "TAMARA"),
            ("@helen what's my day look like", "HELEN"),
            ("schedule a meeting with the team", "HELEN"),
            ("morning briefing", "HELEN"),
            ("/review this pull request", "DEVOPS"),
            ("code review the auth changes", "DEVOPS"),
            ("run a security audit", "DEVOPS"),
        ],
    )
    def test_keyword_routes_to_expected_agent(self, text, expected):
        assert tier1_route(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "hey bowen what do you think about this plan",
            "bowen, give me your take",
            "@bowen summarize where we are",
        ],
    )
    def test_bowen_direct_address_wins_over_subagent_keywords(self, text):
        # "hey BOWEN research this" must NOT leak to SCOUT — BOWEN pattern is first.
        assert tier1_route(text) == "BOWEN"

    def test_bowen_pattern_beats_embedded_keyword(self):
        assert tier1_route("hey bowen research this for me") == "BOWEN"

    @pytest.mark.parametrize(
        "text",
        ["hello there", "thanks!", "tell me a joke", "I appreciate you"],
    )
    def test_no_match_falls_through_to_tier2(self, text):
        assert tier1_route(text) is None


class TestTier2Groq:
    """Tier 2 primary path: mocked Groq provider tool call selects the agent."""

    async def test_groq_tool_call_routes_agent_and_reason(self, monkeypatch):
        primary = FakeProvider([llm_tool_use("route_to_SCOUT", {"reason": "needs research"})])
        wire_tier2(monkeypatch, primary=primary, fallback=None)

        agent, reason = await tier2.route("find the best price", make_config(GROQ_API_KEY="gsk_test"))

        assert agent == "SCOUT"
        assert reason == "needs research"
        assert len(primary.calls) == 1
        assert primary.calls[0]["tool_choice"] == "required"

    async def test_groq_unparseable_arguments_still_routes_with_empty_reason(self, monkeypatch):
        # The Groq adapter turns unparseable JSON arguments into input={} —
        # tier2 must still route the agent, with an empty reason.
        primary = FakeProvider([llm_tool_use("route_to_CAPTAIN", {})])
        wire_tier2(monkeypatch, primary=primary, fallback=None)

        agent, reason = await tier2.route("x", make_config(GROQ_API_KEY="gsk_test"))
        assert agent == "CAPTAIN"
        assert reason == ""

    async def test_groq_unknown_tool_name_falls_back_to_bowen(self, monkeypatch):
        primary = FakeProvider([llm_tool_use("route_to_NOBODY", {"reason": "?"})])
        wire_tier2(monkeypatch, primary=primary, fallback=None)

        agent, _ = await tier2.route("x", make_config(GROQ_API_KEY="gsk_test"))
        assert agent == "BOWEN"

    async def test_groq_no_tool_calls_defaults_to_bowen(self, monkeypatch):
        primary = FakeProvider([llm_text("plain text, no tool")])
        wire_tier2(monkeypatch, primary=primary, fallback=None)

        agent, reason = await tier2.route("x", make_config(GROQ_API_KEY="gsk_test"))
        assert (agent, reason) == ("BOWEN", "groq-fallback")


class BrokenProvider(FakeProvider):
    async def complete(self, messages, **kwargs):
        raise RuntimeError("groq is down")


class TestTier2AnthropicFallback:
    """Groq down or absent → Haiku fallback; unparseable Haiku → BOWEN."""

    async def test_groq_error_falls_back_to_anthropic(self, monkeypatch):
        fallback = FakeProvider([llm_tool_use("route_to_CAPTAIN", {"reason": "build request"})])
        wire_tier2(monkeypatch, primary=BrokenProvider(), fallback=fallback)

        agent, reason = await tier2.route("build it", make_config(GROQ_API_KEY="gsk_test"))
        assert agent == "CAPTAIN"
        assert reason == "build request"
        assert len(fallback.calls) == 1

    async def test_no_groq_key_skips_straight_to_anthropic(self, monkeypatch):
        fallback = FakeProvider([llm_tool_use("route_to_HELEN", {"reason": "calendar"})])
        wire_tier2(monkeypatch, primary=None, fallback=fallback)

        agent, _ = await tier2.route("plan my day", make_config(GROQ_API_KEY=""))
        assert agent == "HELEN"

    async def test_anthropic_reply_without_tool_use_falls_back_to_bowen(self, monkeypatch):
        fallback = FakeProvider([llm_text("I think CAPTAIN maybe?")])
        wire_tier2(monkeypatch, primary=None, fallback=fallback)

        agent, reason = await tier2.route("x", make_config(GROQ_API_KEY=""))
        assert (agent, reason) == ("BOWEN", "anthropic-fallback")
