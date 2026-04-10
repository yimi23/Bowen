"""
agents/planner.py — Pre-task planning layer for CAPTAIN and SCOUT.

Detects vague requests before routing. If a request is ambiguous, asks
targeted clarifying questions, gathers project context, and returns an
enriched prompt. Clear requests pass through unchanged.

Inspired by Jarvis's planner.py — adapted for BOWEN's 5-agent architecture.

Usage (in gateway.py + clawdbot.py):
    from agents.planner import maybe_enrich
    enriched, asked = await maybe_enrich(text, target_agent, config, send)
    # enriched = enriched prompt string (or original if no planning needed)
    # asked = True if questions were asked (TUI already showed Q&A)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# Agents that benefit from pre-task planning
_PLANNING_AGENTS = {"CAPTAIN", "SCOUT"}

# Keywords that suggest a build/code task (worth planning)
_BUILD_KEYWORDS = {
    "build", "create", "make", "write", "implement", "develop", "code",
    "script", "app", "tool", "api", "function", "class", "module",
    "website", "server", "bot", "fix", "debug", "refactor",
}

# These patterns signal the request is already specific enough
_SPECIFIC_SIGNALS = [
    r"\bin\s+(python|typescript|javascript|ts|js|bash|shell|sql|go|rust)\b",
    r"\busing\s+\w+",
    r"\bwith\s+(fastapi|flask|django|express|react|vue|nextjs|postgres|sqlite)\b",
    r"^\s*/",          # slash command
    r"^\s*@",          # direct mention
    r"\bfile:\s*\S+",  # file path mentioned
    r"\bpath:\s*\S+",
]

_CLASSIFICATION_SYSTEM = """\
You are a request classifier for an AI coding assistant.

Classify this request as either:
- "clear": the request has enough detail to act on immediately
- "vague": needs clarification (missing tech stack, unclear scope, or too broad)

Rules:
- Short commands ("fix the bug in auth.py") = clear
- Vague broad requests ("build an app") = vague
- Requests with file paths, tech stacks, or clear scope = clear
- Research requests are usually clear (SCOUT can find what it needs)

Reply with only: clear
or: vague
"""

_QUESTIONS_SYSTEM = """\
You are helping clarify a software development request before building.
Generate 2-3 focused clarifying questions to gather missing information.

Reply with a JSON array of question strings only. Example:
["What language/framework?", "Should it have a UI or be a CLI tool?"]

Rules:
- Max 3 questions
- Skip if the information is obvious or irrelevant
- Focus on: language, framework, data source, scope, integration points
"""


class Planner:
    """
    Stateless planning helper. Call maybe_enrich() for the full flow.
    """

    def __init__(self, api_key: str, haiku_model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = haiku_model

    async def classify(self, text: str) -> str:
        """Returns 'clear' or 'vague'. Fast Haiku call (max_tokens=8)."""
        # Quick heuristic checks first — avoid LLM call when possible
        text_lower = text.lower()

        if not any(kw in text_lower for kw in _BUILD_KEYWORDS):
            return "clear"  # not a build task

        for pattern in _SPECIFIC_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                return "clear"

        if len(text.split()) > 20:
            return "clear"  # detailed enough

        # Use Haiku for ambiguous cases
        try:
            msg = await asyncio.wait_for(
                self._client.messages.create(
                    model=self._model,
                    max_tokens=8,
                    system=_CLASSIFICATION_SYSTEM,
                    messages=[{"role": "user", "content": text}],
                ),
                timeout=8,
            )
            result = msg.content[0].text.strip().lower() if msg.content else "clear"
            return "vague" if "vague" in result else "clear"
        except Exception:
            return "clear"  # fail open

    async def get_questions(self, text: str) -> list[str]:
        """Generate clarifying questions for a vague request."""
        try:
            msg = await asyncio.wait_for(
                self._client.messages.create(
                    model=self._model,
                    max_tokens=200,
                    system=_QUESTIONS_SYSTEM,
                    messages=[{"role": "user", "content": text}],
                ),
                timeout=10,
            )
            raw = msg.content[0].text.strip() if msg.content else "[]"
            questions = json.loads(raw)
            return questions[:3] if isinstance(questions, list) else []
        except Exception:
            return []

    @staticmethod
    def gather_context(cwd: Optional[str] = None) -> str:
        """
        Look for project context files in cwd or common locations.
        Returns a string summary for injection into the enriched prompt.
        """
        search_dirs = [Path(cwd)] if cwd else []
        search_dirs += [Path.home() / "Desktop", Path.home() / "Documents"]

        context_parts: list[str] = []

        for d in search_dirs:
            if not d.is_dir():
                continue

            # CLAUDE.md — Jarvis pattern
            for name in ("CLAUDE.md", "claude.md", ".claude.md"):
                p = d / name
                if p.exists():
                    content = p.read_text(errors="replace")[:500]
                    context_parts.append(f"CLAUDE.md:\n{content}")
                    break

            # package.json — Node/JS project
            p = d / "package.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                    name = data.get("name", "")
                    deps = list(data.get("dependencies", {}).keys())[:6]
                    context_parts.append(f"Node project: {name} | deps: {', '.join(deps)}")
                except Exception:
                    pass

            # requirements.txt or pyproject.toml — Python project
            for req_file in ("requirements.txt", "pyproject.toml"):
                p = d / req_file
                if p.exists():
                    content = p.read_text(errors="replace")[:200]
                    context_parts.append(f"{req_file}:\n{content}")
                    break

            if context_parts:
                break  # stop after first dir with context

        return "\n\n".join(context_parts) if context_parts else ""


async def maybe_enrich(
    text: str,
    target_agent: str,
    config,
    send,
    ask_questions: bool = True,
) -> tuple[str, bool]:
    """
    Entry point. Returns (enriched_prompt, did_ask_questions).

    If the request is clear or not a planning-eligible agent, returns (text, False).
    If vague: asks questions via send callback, builds enriched prompt, returns it.

    The send callback is used to display Q&A in the TUI/frontend in real-time.
    """
    if target_agent not in _PLANNING_AGENTS:
        return text, False

    planner = Planner(config.ANTHROPIC_API_KEY, config.HAIKU_MODEL)

    clarity = await planner.classify(text)
    if clarity == "clear":
        return text, False

    if not ask_questions:
        return text, False

    questions = await planner.get_questions(text)
    if not questions:
        return text, False

    # Ask questions and collect answers via the send callback
    qa_pairs: list[tuple[str, str]] = []

    await send({"type": "planning_start", "agent": "BOWEN"})

    for question in questions:
        await send({
            "type": "chunk",
            "agent": "BOWEN",
            "content": f"\n**{question}**\n",
        })
        # Signal TUI to wait for answer
        await send({
            "type": "planning_question",
            "question": question,
        })
        # Answer comes back as next message — handled by gateway's planning_answer queue
        # For now, we yield and the gateway will inject the answer
        qa_pairs.append((question, ""))  # placeholder; gateway fills in answers

    # Gateway fills answers in; here we just flag that questions were asked
    # The enriched prompt is assembled by the gateway once all answers arrive
    await send({"type": "planning_end"})

    return text, True


def build_enriched_prompt(
    original_text: str,
    qa_pairs: list[tuple[str, str]],
    context: str = "",
) -> str:
    """
    Assemble the enriched prompt from original request + Q&A + project context.
    Called by gateway.py once all answers are collected.
    """
    parts = [f"## Request\n{original_text}"]

    if qa_pairs:
        parts.append("## Clarifications")
        for q, a in qa_pairs:
            if a.strip():
                parts.append(f"Q: {q}\nA: {a}")

    if context:
        parts.append(f"## Project Context\n{context}")

    return "\n\n".join(parts)
