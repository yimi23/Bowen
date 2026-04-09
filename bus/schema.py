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
    """
    Any agent → any agent: pass a work product forward.
    Primary use: SCOUT → CAPTAIN when research implies code needs writing.
    SCOUT ends response with 'CHAIN_TO_CAPTAIN: <task>', scout.py parses and dispatches this.
    """
    from_agent: str
    original_task: str    # the user's original request
    work_product: str     # what the sending agent produced (research, analysis, etc.)
    next_action: str      # what the receiving agent should do with the work product


class ApprovalRequestPayload(BaseModel):
    """
    Any agent → BOWEN: surface a high-risk action for user approval.
    BOWEN prompts the user; agents check payload.data["approved"] before executing.
    """
    action_type: str
    description: str
    data: dict
    risk_level: Literal["low", "medium", "high"] = "medium"


class ErrorPayload(BaseModel):
    """Any agent → BOWEN: report an error that BOWEN should be aware of."""
    agent: str
    error_type: str
    message: str
    recoverable: bool = True


# ── Message Envelope ──────────────────────────────────────────────────────────

AGENT_NAMES = Literal["BOWEN", "CAPTAIN", "SCOUT", "TAMARA", "HELEN", "broadcast"]
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
    | ApprovalRequestPayload
    | ErrorPayload
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
