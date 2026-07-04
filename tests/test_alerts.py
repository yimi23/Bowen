"""
tests/test_alerts.py — The OS-wide alert gate (core/alerts.py).

The gate section is a faithful pytest migration of GENI's 9 vitest gate
tests (geni/backend/src/services/__tests__/notifications.test.ts), plus
new cases for the OS-wide event types (TAMARA approval, HELEN reminder,
morning briefing) and per-tenant quiet hours.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.alerts import (
    AlertEvent,
    AlertGate,
    Decision,
    SentRecord,
    evaluate_alert,
)
from core.tenants import TenantConfig, load_tenant


# ── Factories (mirrors the vitest helpers) ─────────────────────────────────────


def at(hour: int) -> datetime:
    return datetime(2026, 7, 3, hour, 0, 0)


def make_event(**overrides) -> AlertEvent:
    defaults = dict(type="general_concern", priority="medium", message="test")
    defaults.update(overrides)
    return AlertEvent(**defaults)


def sent(minutes_ago: float, priority: str, now: datetime) -> SentRecord:
    return SentRecord(at_ms=now.timestamp() * 1000 - minutes_ago * 60_000, priority=priority)


# ── Quiet hours (GENI tests 1-4) ───────────────────────────────────────────────


class TestQuietHours:
    def test_critical_always_sends_even_at_3am(self):
        result = evaluate_alert(
            make_event(type="fall_detected", priority="critical"), at(3), {}
        )
        assert result.decision is Decision.DELIVER

    def test_high_blocked_at_6am_allowed_at_8am(self):
        blocked = evaluate_alert(make_event(priority="high"), at(6), {})
        assert (blocked.decision, blocked.reason) == (Decision.DEFER, "quiet_hours")

        allowed = evaluate_alert(make_event(priority="high"), at(8), {})
        assert allowed.decision is Decision.DELIVER

    def test_low_medium_blocked_at_8am_allowed_at_10am(self):
        assert evaluate_alert(make_event(priority="low"), at(8), {}).decision is Decision.DEFER
        assert evaluate_alert(make_event(priority="medium"), at(8), {}).decision is Decision.DEFER
        assert evaluate_alert(make_event(priority="low"), at(10), {}).decision is Decision.DELIVER

    def test_force_bypasses_quiet_hours(self):
        result = evaluate_alert(make_event(priority="low", force=True), at(3), {})
        assert (result.decision, result.reason) == (Decision.DELIVER, "forced")


# ── Dedup and escalation (GENI tests 5-9) ──────────────────────────────────────


class TestDedupAndEscalation:
    def test_suppresses_duplicate_within_cooldown(self):
        now = at(12)
        history = {"medication_check": sent(1, "low", now)}
        result = evaluate_alert(
            make_event(type="medication_check", priority="low"), now, history
        )
        assert (result.decision, result.reason) == (Decision.SUPPRESS, "duplicate")

    def test_allows_same_type_after_cooldown_expires(self):
        now = at(12)
        history = {"medication_check": sent(11, "low", now)}
        result = evaluate_alert(
            make_event(type="medication_check", priority="low"), now, history
        )
        assert result.decision is Decision.DELIVER

    def test_critical_fall_escalation_passes_dedup(self):
        # An impact warning (high) went out 30s ago; the confirmed fall
        # (critical) must NOT be suppressed as a duplicate.
        now = at(12)
        history = {"fall_detected": sent(0.5, "high", now)}
        result = evaluate_alert(
            make_event(type="fall_detected", priority="critical"), now, history
        )
        assert result.decision is Decision.DELIVER

    def test_repeated_same_priority_falls_within_2min_merge(self):
        now = at(12)
        history = {"fall_detected": sent(0.5, "critical", now)}
        result = evaluate_alert(
            make_event(type="fall_detected", priority="critical"), now, history
        )
        assert (result.decision, result.reason) == (Decision.SUPPRESS, "duplicate")

    def test_separate_dedup_keys_do_not_collide(self):
        now = at(12)
        history = {"medication_missed:Lisinopril": sent(1, "high", now)}
        result = evaluate_alert(
            make_event(
                type="medication_missed",
                priority="high",
                dedup_key="medication_missed:Metformin",
            ),
            now,
            history,
        )
        assert result.decision is Decision.DELIVER


# ── OS-wide event types (new) ──────────────────────────────────────────────────


class TestOSWideEvents:
    def test_tamara_approval_request_respects_sleep(self):
        # A high-priority send-approval at 2am waits for morning.
        result = evaluate_alert(
            make_event(type="approval_request", priority="high"), at(2), {}
        )
        assert result.decision is Decision.DEFER

    def test_helen_medium_reminder_at_2am_is_deferred(self):
        result = evaluate_alert(make_event(type="reminder", priority="medium"), at(2), {})
        assert (result.decision, result.reason) == (Decision.DEFER, "quiet_hours")

    def test_morning_briefing_dedups_hard(self):
        now = at(9)
        history = {"morning_briefing": sent(90, "low", now)}   # sent 1.5h ago
        result = evaluate_alert(
            make_event(type="morning_briefing", priority="low"), now, history
        )
        assert result.decision is Decision.SUPPRESS

    def test_unknown_future_type_gets_default_cooldown(self):
        now = at(12)
        history = {"quantum_ping": sent(1, "medium", now)}
        result = evaluate_alert(make_event(type="quantum_ping"), now, history)
        assert result.decision is Decision.SUPPRESS   # within 5-min default

    def test_tenant_quiet_hours_override(self):
        # Night-shift tenant: medium allowed at 2am by config, not code.
        night_windows = {"medium": {"start": 0, "end": 24}}
        result = evaluate_alert(
            make_event(priority="medium"), at(2), {}, quiet_hours=night_windows
        )
        assert result.decision is Decision.DELIVER


# ── Stateful gate: dispatch, defer queue, delivery routing ─────────────────────


class RecordingChannel:
    name = "recording"

    def __init__(self):
        self.sent: list = []

    async def send(self, event, tenant) -> None:
        self.sent.append((event, tenant.tenant_id))


class TestAlertGate:
    @pytest.fixture
    def channel(self):
        return RecordingChannel()

    @pytest.fixture
    def gate(self, tmp_path, channel):
        for tenant in ("default", "alpha", "beta"):
            (tmp_path / f"{tenant}.yaml").write_text("channels: [recording]\n")
        return AlertGate(tmp_path, channels={"recording": channel})

    async def test_deliver_records_history_and_sends(self, gate, channel):
        decision = await gate.dispatch(
            make_event(type="fall_detected", priority="critical"), now=at(12)
        )
        assert decision.decision is Decision.DELIVER
        assert len(channel.sent) == 1
        # Immediate repeat is suppressed via recorded history
        repeat = await gate.dispatch(
            make_event(type="fall_detected", priority="critical"), now=at(12)
        )
        assert repeat.decision is Decision.SUPPRESS
        assert len(channel.sent) == 1

    async def test_helen_2am_reminder_defers_then_flushes_in_morning(self, gate, channel):
        # THE acceptance case: a medium HELEN reminder generated at 2am is
        # deferred, then delivered when the morning window opens.
        decision = await gate.dispatch(
            make_event(type="reminder", priority="medium", message="Pay tuition"),
            now=at(2),
        )
        assert decision.decision is Decision.DEFER
        assert channel.sent == []
        assert len(gate.deferred) == 1

        delivered = await gate.flush_deferred(now=at(9))
        assert delivered == 1
        assert len(channel.sent) == 1
        assert channel.sent[0][0].message == "Pay tuition"

    async def test_tenant_isolation_of_dedup_history(self, gate, channel):
        await gate.dispatch(make_event(type="reminder", tenant_id="alpha"), now=at(12))
        other = await gate.dispatch(make_event(type="reminder", tenant_id="beta"), now=at(12))
        assert other.decision is Decision.DELIVER   # beta's history is separate
        assert len(channel.sent) == 2


# ── Tenant config loading ──────────────────────────────────────────────────────


class TestTenantConfig:
    def test_missing_file_yields_geni_default_semantics(self, tmp_path):
        cfg = load_tenant("nobody", tmp_path)
        assert cfg.window("high") == (7, 23)
        assert cfg.window("medium") == (9, 21)
        assert cfg.elder_voice is False
        assert cfg.channels == ["log"]

    def test_yaml_overrides_apply(self, tmp_path):
        (tmp_path / "casa.yaml").write_text(
            "quiet_hours:\n  medium: {start: 8, end: 22}\n"
            "channels: [twilio_whatsapp, log]\n"
            "caregiver_phone: '+15550001111'\n"
            "elder_voice: true\n"
        )
        cfg = load_tenant("casa", tmp_path)
        assert cfg.window("medium") == (8, 22)
        assert cfg.window("high") == (7, 23)   # untouched key keeps default
        assert cfg.channels == ["twilio_whatsapp", "log"]
        assert cfg.elder_voice is True

    def test_corrupt_yaml_falls_back_to_defaults(self, tmp_path):
        (tmp_path / "bad.yaml").write_text("{{{{not yaml")
        cfg = load_tenant("bad", tmp_path)
        assert cfg.window("medium") == (9, 21)
