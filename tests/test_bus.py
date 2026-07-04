"""
tests/test_bus.py — Characterization: the inter-agent message bus.

Priority ordering, typed payload validation, exactly-once delivery of a
SCOUT→CAPTAIN handoff — and the current recipient whitelist as it stands.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bus.message_bus import MessageBus
from bus.schema import (
    AgentMessage,
    HandoffPayload,
    ReviewResultPayload,
    TextPayload,
)


# ── Factories ──────────────────────────────────────────────────────────────────


def make_message(**overrides) -> AgentMessage:
    defaults = dict(
        sender="BOWEN",
        recipient="CAPTAIN",
        msg_type="request",
        payload=TextPayload(text="do the thing"),
        priority=3,
    )
    defaults.update(overrides)
    return AgentMessage(**defaults)


def make_handoff(**overrides) -> HandoffPayload:
    defaults = dict(
        from_agent="SCOUT",
        target="CAPTAIN",
        original_task="research then build a scraper",
        work_product="Findings: the site is static HTML, easy to parse.",
        task="Build the scraper using the findings above.",
        reason="research complete",
    )
    defaults.update(overrides)
    return HandoffPayload(**defaults)


# ── Priority ordering ──────────────────────────────────────────────────────────


class TestPriorityOrdering:
    async def test_urgent_messages_come_out_first(self):
        bus = MessageBus()
        await bus.send(make_message(priority=1, payload=TextPayload(text="low")))
        await bus.send(make_message(priority=5, payload=TextPayload(text="urgent")))
        await bus.send(make_message(priority=3, payload=TextPayload(text="normal")))

        received = [await bus.receive("CAPTAIN") for _ in range(3)]
        assert [m.payload.text for m in received] == ["urgent", "normal", "low"]

    async def test_equal_priority_does_not_crash_ordering(self):
        bus = MessageBus()
        await bus.send(make_message(priority=3, payload=TextPayload(text="a")))
        await bus.send(make_message(priority=3, payload=TextPayload(text="b")))
        texts = {(await bus.receive("CAPTAIN")).payload.text for _ in range(2)}
        assert texts == {"a", "b"}


# ── Typed payload validation ───────────────────────────────────────────────────


class TestPayloadValidation:
    def test_handoff_requires_all_core_fields(self):
        with pytest.raises(ValidationError):
            HandoffPayload(from_agent="SCOUT", target="CAPTAIN")  # missing task fields

    def test_review_verdict_is_a_closed_enum(self):
        with pytest.raises(ValidationError):
            ReviewResultPayload(verdict="MAYBE")

        ok = ReviewResultPayload(verdict="SHIP", summary="clean")
        assert ok.verdict == "SHIP"

    def test_text_payload_rejects_missing_text(self):
        with pytest.raises(ValidationError):
            TextPayload()


# ── Delivery semantics ─────────────────────────────────────────────────────────


class TestDelivery:
    async def test_scout_to_captain_handoff_delivered_exactly_once(self):
        bus = MessageBus()
        msg = make_message(
            sender="SCOUT",
            recipient="CAPTAIN",
            msg_type="chain",
            payload=make_handoff(),
            priority=4,
        )
        await bus.send(msg)

        first = await bus.receive("CAPTAIN")
        assert first is msg
        assert first.payload.work_product.startswith("Findings:")

        # Exactly once: queue is now empty, second receive times out to None
        assert bus.empty("CAPTAIN")
        assert await bus.receive("CAPTAIN", timeout=0.05) is None
        # And it never leaked into another agent's queue
        assert await bus.receive("SCOUT", timeout=0.05) is None

    async def test_send_logs_message_for_audit(self):
        bus = MessageBus()
        msg = make_message()
        await bus.send(msg)
        assert msg in bus.log

    async def test_broadcast_reaches_everyone_except_sender(self):
        bus = MessageBus()
        await bus.send(make_message(sender="BOWEN", recipient="broadcast"))
        for name in ["CAPTAIN", "SCOUT", "TAMARA", "HELEN", "DEVOPS"]:
            assert await bus.receive(name, timeout=0.05) is not None
        assert await bus.receive("BOWEN", timeout=0.05) is None

    async def test_captain_auto_review_reaches_devops(self):
        # Regression guard for the bug where DEVOPS was missing from
        # bus.AGENT_NAMES and CAPTAIN's auto-review dispatch raised.
        bus = MessageBus()
        await bus.send(make_message(sender="CAPTAIN", recipient="DEVOPS"))
        received = await bus.receive("DEVOPS", timeout=0.05)
        assert received is not None
        assert received.sender == "CAPTAIN"

    async def test_unknown_recipient_is_rejected(self):
        bus = MessageBus()
        with pytest.raises(ValueError, match="Unknown recipient"):
            await bus.send(make_message(recipient="NOBODY"))
