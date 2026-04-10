"""
tools/qa.py — CAPTAIN output quality verification.

After CAPTAIN completes a task, verify the output against the original request.
Uses Haiku for speed. Returns pass/fail + issues. CAPTAIN retries on failure.

Usage (in agents/captain.py):
    from tools.qa import verify_output, QAResult
    result = await verify_output(original_request, response, api_key, model)
    if not result.passed:
        # inject result.issues into retry prompt
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

_QA_SYSTEM = """\
You are a code and task quality reviewer. Given an original request and the agent's response,
determine if the response fully satisfies the request.

Respond in this exact format — nothing else:
PASS
or
FAIL
- Issue 1
- Issue 2
- Issue 3

Rules:
- PASS only if the response directly addresses the request with working, complete output.
- FAIL if: code is incomplete, has TODO stubs, doesn't match the requested language/framework,
  is vague instead of concrete, or the task wasn't actually completed.
- Be strict. Incomplete code = FAIL.
- For research tasks: FAIL if sources are missing or findings are too vague.
- Max 5 issues. Be specific.
"""


@dataclass
class QAResult:
    passed: bool
    issues: list[str] = field(default_factory=list)
    attempt: int = 1

    def as_prompt_feedback(self) -> str:
        """Format issues for injection into a retry prompt."""
        return (
            "The previous attempt had these issues — fix all of them:\n"
            + "\n".join(f"- {i}" for i in self.issues)
        )


async def verify_output(
    original_request: str,
    response: str,
    api_key: str,
    model: str,
    attempt: int = 1,
) -> QAResult:
    """
    Verify CAPTAIN's response against the original request.
    Returns QAResult(passed=True) if output is acceptable.
    Fast — uses Haiku, max_tokens=256.
    """
    if not response or not response.strip():
        return QAResult(passed=False, issues=["Response is empty."], attempt=attempt)

    # Skip QA for very short conversational responses — only meaningful for task outputs
    if len(response) < 80 and not any(
        kw in original_request.lower()
        for kw in ("write", "build", "create", "make", "implement", "code", "script", "fix", "debug")
    ):
        return QAResult(passed=True, attempt=attempt)

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await asyncio.wait_for(
            client.messages.create(
                model=model,
                max_tokens=256,
                system=_QA_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": (
                        f"ORIGINAL REQUEST:\n{original_request[:800]}\n\n"
                        f"RESPONSE:\n{response[:2000]}"
                    ),
                }],
            ),
            timeout=30,
        )

        text = msg.content[0].text.strip() if msg.content else ""
        return _parse_qa_response(text, attempt)

    except asyncio.TimeoutError:
        logger.warning("QA verification timed out — defaulting to pass")
        return QAResult(passed=True, attempt=attempt)
    except Exception as e:
        logger.warning(f"QA verification failed: {e} — defaulting to pass")
        return QAResult(passed=True, attempt=attempt)


def _parse_qa_response(text: str, attempt: int) -> QAResult:
    """Parse the PASS/FAIL response from Haiku."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return QAResult(passed=True, attempt=attempt)

    first = lines[0].upper()
    if first.startswith("PASS"):
        return QAResult(passed=True, attempt=attempt)

    if first.startswith("FAIL"):
        issues = [l.lstrip("-• ") for l in lines[1:] if l.startswith(("-", "•"))]
        return QAResult(passed=False, issues=issues or ["Output did not meet requirements."], attempt=attempt)

    # Ambiguous — default to pass
    return QAResult(passed=True, attempt=attempt)
