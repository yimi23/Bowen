"""
routing/tier1.py — Tier 1 Regex Router.
< 1ms, $0 cost. Covers ~30% of inputs via explicit commands.
"""

import re
from typing import Optional

from agents.constants import AgentName


# Patterns ordered by specificity. First match wins.
# BOWEN direct-address must come FIRST — prevents sub-agent misroute on "hey BOWEN..."
ROUTING_PATTERNS: list[tuple[str, re.Pattern]] = [
    (AgentName.BOWEN, re.compile(
        r"""
        (^/bowen\b)             |
        (^@bowen\b)             |
        (^hey\s+bowen\b)        |   # "hey BOWEN what do you think..."
        (^bowen[,\s])               # "BOWEN, what's your take..."
        """,
        re.IGNORECASE | re.VERBOSE
    )),
    (AgentName.CAPTAIN, re.compile(
        r"""
        (^/code\b)              |   # slash command
        (^@captain\b)           |   # mention
        \b(execute|run\s+code|write\s+(a\s+)?(\w+\s+)?(script|function|class|module)|
           debug|fix\s+(the\s+)?code|build\s+(a\s+)?(function|class|app|tool)|
           implement|refactor|file\s+ops?|shell\s+command|create\s+(a\s+)?(\w+\s+)?script)
        """,
        re.IGNORECASE | re.VERBOSE
    )),
    (AgentName.HELEN, re.compile(
        r"""
        (^/calendar\b)          |
        (^@helen\b)             |
        \b(calendar|schedule\s+(a\s+)?(meeting|call|event)|remind(er)?|
           morning\s+briefing|bible\s+(reading|check|tracker)|
           what('s|\s+is)\s+(on|happening)\s+(today|tomorrow)|deadline(s)?|
           task(s)?\s+for\s+today|today's\s+tasks)
        """,
        re.IGNORECASE | re.VERBOSE
    )),
    (AgentName.SCOUT, re.compile(
        r"""
        (^/search\b)            |
        (^@scout\b)             |
        \b(research|look\s+up|find\s+out|competitive\s+analysis|
           market\s+research|investigate|deep\s+dive|gather\s+info|
           what\s+is\b|who\s+is\b|compare\s+\w+\s+(vs|versus))
        """,
        re.IGNORECASE | re.VERBOSE
    )),
    (AgentName.TAMARA, re.compile(
        r"""
        (^/email\b)             |
        (^@tamara\b)            |
        \b(email|gmail|inbox|send\s+a\s+message|draft|
           check\s+my\s+(email|mail)|whatsapp|message\s+\w+)
        """,
        re.IGNORECASE | re.VERBOSE
    )),
    (AgentName.DEVOPS, re.compile(
        r"""
        (^/review\b)            |   # slash command
        (^/audit\b)             |
        (^@devops\b)            |   # mention
        \b(code\s+review|review\s+(the\s+)?(code|pr|pull\s+request)|
           audit|lint|run\s+(ruff|mypy|eslint|tsc)|type\s+check|
           security\s+(scan|audit|check)|static\s+analysis|
           check\s+(for\s+)?(bugs|vulnerabilities|issues)|
           performance\s+(review|audit|check)|
           pre.?deploy\s+check|dockerfile|ci\s+pipeline|
           is\s+(this\s+)?safe\s+to\s+(ship|deploy|merge))
        """,
        re.IGNORECASE | re.VERBOSE
    )),
]


def route(text: str) -> Optional[str]:
    """
    Returns agent name if a pattern matches, else None (fall through to Tier 2).
    """
    text = text.strip()
    for agent, pattern in ROUTING_PATTERNS:
        if pattern.search(text):
            return agent
    return None
