"""
agents/constants.py — Agent name constants. Single source of truth.

Use these instead of raw strings ("CAPTAIN", "SCOUT", etc.) throughout the codebase.
Prevents typo-based bugs and makes refactoring a one-file change.

Usage:
    from agents.constants import AgentName

    agents = {AgentName.CAPTAIN: CaptainAgent(...), ...}
    if target == AgentName.SCOUT: ...
"""


class AgentName:
    BOWEN   = "BOWEN"
    CAPTAIN = "CAPTAIN"
    DEVOPS  = "DEVOPS"
    SCOUT   = "SCOUT"
    TAMARA  = "TAMARA"
    HELEN   = "HELEN"

    # Ordered list — used by TUI sidebar and gateway agent map
    ALL: list[str] = [BOWEN, CAPTAIN, DEVOPS, SCOUT, TAMARA, HELEN]
