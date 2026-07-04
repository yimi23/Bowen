"""
bus/schema.py — AgentMessage dataclass + all Pydantic payload types.

DESIGN RULE: Never pass raw strings between agents. Always use a typed payload.
This prevents the most common multi-agent bug: agents misinterpreting each other's output.

Add new payload types here before writing any new inter-agent functionality.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from pydantic import BaseModel


# ── Payload Types ─────────────────────────────────────────────────────────────
# One Pydantic model per inter-agent action type.

class TextPayload(BaseModel):
    """General text request/response between agents."""
    text: str
    context: Optional[str] = None


class CodeRequestPayload(BaseModel):
    """BOWEN → CAPTAIN: write or execute code."""
    task: str
    language: str = "python"
    context: Optional[str] = None
    execute: bool = False


class CodeResponsePayload(BaseModel):
    """CAPTAIN → BOWEN: code result."""
    code: str
    output: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class ResearchRequestPayload(BaseModel):
    """BOWEN → SCOUT: research a topic."""
    query: str
    depth: Literal["quick", "deep"] = "quick"
    context: Optional[str] = None
    chain_to: Optional[str] = None  # agent to forward findings to after research


class ResearchResponsePayload(BaseModel):
    """SCOUT → BOWEN: research findings."""
    query: str
    summary: str
    sources: list[str] = []
    raw_findings: Optional[str] = None


class EmailReadPayload(BaseModel):
    """BOWEN → TAMARA: read inbox."""
    max_results: int = 10
    unread_only: bool = True
    label: str = "INBOX"


class EmailSendPayload(BaseModel):
    """BOWEN → TAMARA: send or draft email. Always draft first — approval required."""
    to: str
    subject: str
    body: str
    draft_only: bool = True  # safety default: draft mode, not send


class EmailSummaryPayload(BaseModel):
    """TAMARA → BOWEN: inbox summary."""
    count: int
    summaries: list[dict]
    urgent: Optional[dict] = None


class CalendarRequestPayload(BaseModel):
    """BOWEN → HELEN: fetch or create calendar events."""
    action: Literal["list", "create"]
    date_range_days: int = 7
    event: Optional[dict] = None


class CalendarResponsePayload(BaseModel):
    """HELEN → BOWEN: calendar data."""
    events: list[dict]
    summary: str


class BriefingPayload(BaseModel):
    """HELEN → BOWEN: morning briefing package."""
    date: str
    calendar_summary: str
    task_summary: str
    bible_complete: bool
    urgent_emails: list[str] = []
    briefing_text: str


class BibleCheckPayload(BaseModel):
    """HELEN internal: track daily Bible reading in the bible_log table."""
    date: str
    complete: bool = False
    passage: Optional[str] = None


class ChainPayload(BaseModel):
    """Legacy: use HandoffPayload for new code."""
    from_agent: str
    original_task: str
    work_product: str
    next_action: str


class HandoffPayload(BaseModel):
    """
    Any agent → any agent: typed work handoff.
    Replaces the CHAIN_TO_CAPTAIN magic string pattern.
    The sending agent dispatches this via the bus; the receiving agent handles it.
    """
    from_agent: str
    target: str           # recipient agent name
    original_task: str    # the user's original request
    work_product: str     # what the sending agent produced (research, analysis, etc.)
    task: str             # what the receiving agent should do
    reason: str = ""      # why this handoff is happening


class ApprovalRequestPayload(BaseModel):
    """
    Any agent → BOWEN: surface a high-risk action for user approval.
    BOWEN prompts the user; agents check payload.data["approved"] before executing.
    """
    action_type: str
    description: str
    data: dict
    risk_level: Literal["low", "medium", "high"] = "medium"


class ReviewPayload(BaseModel):
    """CAPTAIN → DEVOPS: code review request after build."""
    code_summary: str
    files_changed: list[str]
    task: str
    agent: str = "CAPTAIN"


class ReviewResultPayload(BaseModel):
    """DEVOPS → CAPTAIN/BOWEN: review verdict."""
    verdict: Literal["SHIP", "NEEDS_WORK", "DO_NOT_SHIP"]
    issues: list[str] = []
    summary: str = ""


class ErrorPayload(BaseModel):
    """Any agent → BOWEN: report an error that BOWEN should be aware of."""
    agent: str
    error_type: str
    message: str
    recoverable: bool = True


# ── GENI (elder-care) event payloads ──────────────────────────────────────────

class FallConfirmedPayload(BaseModel):
    """GENI → TAMARA/BOWEN: a fall passed the confirmation window. Always critical."""
    tenant_id: str = "default"
    patient_name: str
    message: str                       # caregiver-facing text, GENI's voice
    confidence: float = 1.0
    detected_at: str                   # ISO timestamp from the monitoring core
    should_call: bool = True


class MedicationMissedPayload(BaseModel):
    """GENI → TAMARA/BOWEN: a medication is overdue. Priority scales with elapsed time."""
    tenant_id: str = "default"
    patient_name: str
    medication: str
    due_at: str                        # scheduled time, e.g. "9:00 AM"
    elapsed_minutes: int
    message: str
    priority: Literal["low", "medium", "high"] = "medium"


class WellnessCheckPayload(BaseModel):
    """GENI → BOWEN: periodic wellness observation from the monitoring cycle."""
    tenant_id: str = "default"
    patient_name: str
    activity_level: Literal["normal", "quiet", "concerning"] = "normal"
    observations: str = ""
    concern: bool = False
    message: str = ""


class DailyReportPayload(BaseModel):
    """GENI → BOWEN/TAMARA: end-of-day caregiver summary."""
    tenant_id: str = "default"
    patient_name: str
    date: str
    meds_taken: int
    meds_total: int
    message: str


# ── Message Envelope ──────────────────────────────────────────────────────────

AGENT_NAMES = Literal["BOWEN", "CAPTAIN", "SCOUT", "TAMARA", "HELEN", "DEVOPS", "GENI", "broadcast"]
MSG_TYPES = Literal["request", "response", "inform", "error", "chain", "approval"]

PAYLOAD_TYPES = (
    TextPayload
    | CodeRequestPayload
    | CodeResponsePayload
    | ResearchRequestPayload
    | ResearchResponsePayload
    | EmailReadPayload
    | EmailSendPayload
    | EmailSummaryPayload
    | CalendarRequestPayload
    | CalendarResponsePayload
    | BriefingPayload
    | BibleCheckPayload
    | ChainPayload
    | HandoffPayload
    | ApprovalRequestPayload
    | ReviewPayload
    | ReviewResultPayload
    | ErrorPayload
    | FallConfirmedPayload
    | MedicationMissedPayload
    | WellnessCheckPayload
    | DailyReportPayload
)


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    msg_type: str
    payload: Any          # one of PAYLOAD_TYPES
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 3     # 1 (low) → 5 (urgent)
    requires_approval: bool = False
    session_id: Optional[str] = None

    def __lt__(self, other: "AgentMessage") -> bool:
        # asyncio.PriorityQueue uses heapq which puts SMALLEST value first.
        # We invert so that priority 5 (urgent) comes out BEFORE priority 1 (low).
        # Without the inversion, "low priority" messages would be processed first.
        return self.priority > other.priority

    def __le__(self, other: "AgentMessage") -> bool:
        return self.priority >= other.priority
