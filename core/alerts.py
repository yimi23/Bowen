"""
core/alerts.py — THE single doorway for every outbound human interruption.

Ported from GENI's proven notification gate (geni/backend/src/services/
notifications.ts) and promoted to OS scope: GENI caregiver alerts, TAMARA
send-approval requests, HELEN reminders and briefings, and any future agent
ping all pass through evaluate_alert() before a human's phone buzzes.

The gate is a PURE function: (event, priority, history, clock, tenant) →
DELIVER | DEFER | SUPPRESS. Semantics preserved exactly from GENI:
  - critical sends 24/7
  - high respects sleeping hours (default 7:00-23:00)
  - medium/low wait for daytime (default 9:00-21:00)
  - per-type cooldowns dedup repeats
  - an escalation (strictly higher priority than the last send of the same
    key) always breaks through dedup
  - force bypasses everything (manual/test sends)

Delivery (Twilio, push, websocket) lives ONLY in core/alert_delivery.py.
Nothing else in the OS may talk to a push channel — grep enforces this.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ── Event vocabulary ───────────────────────────────────────────────────────────

PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Per-type dedup cooldowns (ms). GENI's care types keep GENI's exact numbers;
# OS-wide types added below with matching philosophy.
COOLDOWN_MS: dict[str, int] = {
    # GENI care domain (unchanged)
    "fall_detected": 2 * 60_000,
    "unusual_activity": 10 * 60_000,
    "medication_check": 10 * 60_000,
    "medication_taken": 5 * 60_000,
    "medication_missed": 30 * 60_000,
    "symptom_reported": 10 * 60_000,
    "inactivity": 60 * 60_000,
    "daily_summary": 60_000,
    "weekly_summary": 60_000,
    "reassurance": 60_000,
    "general_concern": 60_000,
    # OS-wide types
    "approval_request": 60_000,        # TAMARA: send-approval — near-realtime, tiny dedup
    "reminder": 10 * 60_000,           # HELEN: task/calendar reminders
    "morning_briefing": 6 * 60 * 60_000,  # HELEN: once per morning, hard dedup
    "wellness_check": 30 * 60_000,     # GENI cycle observations
    "daily_report": 60 * 60_000,       # GENI end-of-day report
    "agent_ping": 5 * 60_000,          # default for future agent types
}

DEFAULT_COOLDOWN_MS = COOLDOWN_MS["agent_ping"]


class Decision(str, Enum):
    DELIVER = "deliver"
    DEFER = "defer"        # quiet hours — try again in the morning window
    SUPPRESS = "suppress"  # duplicate within cooldown


@dataclass
class AlertEvent:
    type: str
    priority: str                      # low | medium | high | critical
    message: str
    tenant_id: str = "default"
    dedup_key: Optional[str] = None    # e.g. "medication_missed:Lisinopril"
    should_call: bool = False
    force: bool = False
    details: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.dedup_key or self.type


@dataclass
class SentRecord:
    at_ms: float
    priority: str


@dataclass
class GateDecision:
    decision: Decision
    reason: str                        # ok | forced | quiet_hours | duplicate


# ── The pure gate ──────────────────────────────────────────────────────────────


def evaluate_alert(
    event: AlertEvent,
    now: datetime,
    history: dict[str, SentRecord],
    quiet_hours: Optional[dict] = None,
) -> GateDecision:
    """
    Pure decision: no I/O, no globals, clock injected. Port of GENI's
    evaluateNotification with per-tenant quiet-hour windows.
    """
    if event.force:
        return GateDecision(Decision.DELIVER, "forced")

    hour = now.hour
    windows = quiet_hours or {
        "high": {"start": 7, "end": 23},
        "medium": {"start": 9, "end": 21},
        "low": {"start": 9, "end": 21},
    }

    if event.priority == "critical":
        in_window = True
    else:
        w = windows.get(event.priority, {"start": 9, "end": 21})
        in_window = int(w["start"]) <= hour < int(w["end"])

    if not in_window:
        return GateDecision(Decision.DEFER, "quiet_hours")

    last = history.get(event.key)
    if last:
        cooldown = COOLDOWN_MS.get(event.type, DEFAULT_COOLDOWN_MS)
        within_cooldown = (now.timestamp() * 1000 - last.at_ms) < cooldown
        escalated = PRIORITY_RANK.get(event.priority, 0) > PRIORITY_RANK.get(last.priority, 0)
        if within_cooldown and not escalated:
            return GateDecision(Decision.SUPPRESS, "duplicate")

    return GateDecision(Decision.DELIVER, "ok")


# ── Stateful gate wrapper (history + tenant config + delivery) ─────────────────


class AlertGate:
    """
    Owns dedup history per tenant and hands DELIVER decisions to the delivery
    layer. The only object in the OS allowed to touch alert channels.
    """

    def __init__(self, tenants_dir, channels=None) -> None:
        from core.alert_delivery import default_channels

        self._tenants_dir = tenants_dir
        self._history: dict[str, dict[str, SentRecord]] = {}   # tenant → key → record
        self._deferred: list[AlertEvent] = []
        self._channels = channels if channels is not None else default_channels()

    def history_for(self, tenant_id: str) -> dict[str, SentRecord]:
        return self._history.setdefault(tenant_id, {})

    async def dispatch(self, event: AlertEvent, now: Optional[datetime] = None) -> GateDecision:
        """Evaluate, record, and deliver (or defer/suppress) one event."""
        from core.tenants import load_tenant

        now = now or datetime.now()
        tenant = load_tenant(event.tenant_id, self._tenants_dir)
        history = self.history_for(event.tenant_id)

        decision = evaluate_alert(event, now, history, tenant.quiet_hours)

        if decision.decision is Decision.DELIVER:
            history[event.key] = SentRecord(at_ms=now.timestamp() * 1000, priority=event.priority)
            await self._deliver(event, tenant)
        elif decision.decision is Decision.DEFER:
            self._deferred.append(event)
            logger.info(
                "alert deferred to daytime",
                extra={"type": event.type, "priority": event.priority, "tenant": event.tenant_id},
            )
        else:
            logger.info(
                "alert suppressed as duplicate",
                extra={"type": event.type, "key": event.key, "tenant": event.tenant_id},
            )
        return decision

    async def flush_deferred(self, now: Optional[datetime] = None) -> int:
        """Re-run deferred events (scheduler calls this when windows open)."""
        pending, self._deferred = self._deferred, []
        delivered = 0
        for event in pending:
            result = await self.dispatch(event, now=now)
            if result.decision is Decision.DELIVER:
                delivered += 1
        return delivered

    @property
    def deferred(self) -> list[AlertEvent]:
        return list(self._deferred)

    async def _deliver(self, event: AlertEvent, tenant) -> None:
        for name in tenant.channels:
            channel = self._channels.get(name)
            if channel is None:
                logger.warning("unknown alert channel %r for tenant %s", name, tenant.tenant_id)
                continue
            try:
                await channel.send(event, tenant)
                logger.info(
                    "alert delivered",
                    extra={"type": event.type, "channel": name, "tenant": tenant.tenant_id},
                )
                return   # first successful channel wins
            except Exception as exc:
                logger.error("channel %s failed: %s: %s — trying next", name, type(exc).__name__, exc)
        logger.error("all channels failed for alert %s (tenant %s)", event.type, tenant.tenant_id)
