"""
routing/tier2.py — Tier 2 Groq LLaMA Router.
~100-200ms, ~$0.0002 (80% cheaper than Haiku, 3x faster).
Falls back to Anthropic Haiku if Groq key is unavailable.

Strategy: model 5 agents as tools, force a single tool selection.
This avoids parsing free-text responses — we always get a clean agent name.
"""

import json
from groq import AsyncGroq
import anthropic
from utils.rate_limiter import groq_limiter, anthropic_limiter

# ── Tool schemas for Groq (OpenAI function-calling format) ────────────────────
# Each "function" represents routing to one agent.
# Groq uses tool_choice="required" so it MUST call one of these — never skips.

AGENT_TOOLS_GROQ = [
    {
        "type": "function",
        "function": {
            "name": "route_to_CAPTAIN",
            "description": (
                "Route to CAPTAIN when the user wants: code written, executed, or debugged; "
                "scripts, functions, or programs built; file system operations; shell commands run; "
                "architecture or technical implementation decisions; any software engineering task."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why CAPTAIN is the right agent"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_SCOUT",
            "description": (
                "Route to SCOUT when the user wants: research done; information looked up; "
                "competitive or market analysis; technical deep dives; facts gathered from the web; "
                "documents parsed or summarized; comparisons between products or technologies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why SCOUT is the right agent"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_TAMARA",
            "description": (
                "Route to TAMARA when the user wants: emails read, drafted, or sent; "
                "inbox summarized; WhatsApp messages handled; outbound communication of any kind."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why TAMARA is the right agent"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_HELEN",
            "description": (
                "Route to HELEN when the user wants: calendar checked or events created; "
                "reminders set; daily briefing; Bible reading tracked or reminded; "
                "tasks or deadlines managed; morning routine handled."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why HELEN is the right agent"}
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_BOWEN",
            "description": (
                "Route to BOWEN when the task requires orchestration across multiple agents, "
                "high-level strategy, general conversation, or when no other agent clearly fits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why BOWEN handles this directly"}
                },
                "required": ["reason"]
            }
        }
    },
]

# ── Same tools in Anthropic format (for the Haiku fallback) ───────────────────
# Anthropic uses tool_choice={"type": "any"} instead of tool_choice="required".
# Otherwise identical logic.

AGENT_TOOLS_ANTHROPIC = [
    {
        "name": "route_to_CAPTAIN",
        "description": (
            "Route to CAPTAIN when the user wants: code written, executed, or debugged; "
            "scripts, functions, or programs built; file system operations; shell commands run; "
            "architecture or technical implementation decisions; any software engineering task."
        ),
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    },
    {
        "name": "route_to_SCOUT",
        "description": (
            "Route to SCOUT when the user wants: research done; information looked up; "
            "competitive or market analysis; technical deep dives; facts gathered from the web; "
            "documents parsed or summarized."
        ),
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    },
    {
        "name": "route_to_TAMARA",
        "description": "Route to TAMARA for emails, messaging, inbox, outbound communications.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    },
    {
        "name": "route_to_HELEN",
        "description": "Route to HELEN for calendar, reminders, Bible tracking, morning briefing, tasks.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    },
    {
        "name": "route_to_BOWEN",
        "description": "Route to BOWEN for orchestration, strategy, general conversation, or no clear fit.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    },
]

# Maps function name → agent name
TOOL_TO_AGENT = {
    "route_to_CAPTAIN": "CAPTAIN",
    "route_to_SCOUT":   "SCOUT",
    "route_to_TAMARA":  "TAMARA",
    "route_to_HELEN":   "HELEN",
    "route_to_BOWEN":   "BOWEN",
}

ROUTING_SYSTEM = (
    "You are a routing assistant. Select which agent should handle the user's request. "
    "Pick the single best agent and call the appropriate routing function."
)


async def route(
    text: str,
    anthropic_client: anthropic.AsyncAnthropic,
    anthropic_model: str,
    groq_api_key: str = "",
) -> tuple[str, str]:
    """
    Returns (agent_name, reason).
    Primary: Groq LLaMA 3.1 8B (~100ms, $0.0002).
    Fallback: Anthropic Haiku (~400ms, $0.001) if Groq unavailable or errors.
    """
    if groq_api_key:
        try:
            return await _route_groq(text, groq_api_key)
        except Exception:
            pass  # Groq failed (quota, network, etc.) — fall through to Anthropic

    return await _route_anthropic(text, anthropic_client, anthropic_model)


async def _route_groq(text: str, api_key: str) -> tuple[str, str]:
    """
    Groq routing. Uses tool_choice="required" — model MUST call a function.
    max_tokens=64 is enough for the reason string; temperature=0 for determinism.
    """
    await groq_limiter.acquire()
    client = AsyncGroq(api_key=api_key)
    response = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": ROUTING_SYSTEM},
            {"role": "user", "content": text},
        ],
        tools=AGENT_TOOLS_GROQ,
        tool_choice="required",  # forces a function call — no free-text fallback
        max_tokens=64,
        temperature=0,           # deterministic routing
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        call = msg.tool_calls[0]
        agent = TOOL_TO_AGENT.get(call.function.name, "BOWEN")
        try:
            args = json.loads(call.function.arguments)
            reason = args.get("reason", "")
        except Exception:
            reason = ""
        return agent, reason

    # Should never happen with tool_choice="required", but handle defensively
    return "BOWEN", "groq-fallback"


async def _route_anthropic(
    text: str,
    client: anthropic.AsyncAnthropic,
    model: str,
) -> tuple[str, str]:
    """
    Anthropic Haiku fallback routing.
    tool_choice={"type": "any"} is Anthropic's equivalent of Groq's tool_choice="required".
    """
    await anthropic_limiter.acquire()
    response = await client.messages.create(
        model=model,
        max_tokens=64,
        tools=AGENT_TOOLS_ANTHROPIC,
        tool_choice={"type": "any"},   # force a tool call — no text response allowed
        system=ROUTING_SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    for block in response.content:
        if block.type == "tool_use":
            agent = TOOL_TO_AGENT.get(block.name, "BOWEN")
            reason = block.input.get("reason", "")
            return agent, reason

    return "BOWEN", "anthropic-fallback"
