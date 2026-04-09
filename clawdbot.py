"""
clawdbot.py — BOWEN entry point.
Single asyncio event loop. All agents, memory, bus, scheduler share this loop.

Run: source .venv/bin/activate && python clawdbot.py
"""

import asyncio
import uuid
import sys

from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from agents.bowen import BOWENAgent
from agents.captain import CaptainAgent
from agents.scout import ScoutAgent
from agents.tamara import TamaraAgent
from agents.helen import HelenAgent
from scheduler.jobs import build_scheduler, wire_helen_jobs
from memory.pipeline import run_sleep_pipeline
import tools.registry as registry


def check_env(config: Config) -> bool:
    """Verify required env vars are present before starting. Only ANTHROPIC_API_KEY is hard-required."""
    missing = config.validate()
    if missing:
        print(f"\n[ERROR] Missing required environment variables: {', '.join(missing)}")
        print("Fill them in .env and restart.\n")
        return False
    return True


async def drain_bus(agents: dict, bus: MessageBus, depth: int = 0) -> None:
    """
    Process all pending inter-agent messages after each user turn.

    Recursive up to depth 10 — agents responding to messages can themselves
    dispatch new messages, which need another drain pass.
    Depth cap prevents infinite loops (e.g. SCOUT chains to CAPTAIN which chains back).

    CRITICAL: approval check happens BEFORE calling handle(). If the user denies,
    we skip handle() entirely — we do NOT call it and then ignore the result.
    That was bug #6 in the original system.
    """
    if depth > 10:
        print("  [bus] Max chain depth (10) reached. Stopping to prevent loops.")
        return

    pending = await bus.drain_all()
    if not pending:
        return  # Nothing to process — base case for recursion

    for msg in pending:
        # Approval gate: check BEFORE executing, not after
        if msg.requires_approval:
            approved = await _request_approval(agents["BOWEN"], msg)
            if not approved:
                print(f"  \033[33m[bus] Action denied by user. Skipping.\033[0m")
                continue  # skip handle() — this is the critical fix

        target = agents.get(msg.recipient)
        if not target:
            print(f"  \033[31m[bus] Unknown recipient: {msg.recipient}. Dropping message.\033[0m")
            continue

        print(f"  \033[90m[bus] {msg.sender} → {msg.recipient} ({msg.msg_type})\033[0m")

        # Isolate failures — one bad message can't crash the rest of the bus
        try:
            async with asyncio.timeout(120):
                await target.handle(msg)
        except asyncio.TimeoutError:
            print(f"  \033[31m[bus] {msg.recipient} timed out handling message. Skipping.\033[0m")
        except Exception as e:
            print(f"  \033[31m[bus] {msg.recipient} crashed handling message: {type(e).__name__}: {e}\033[0m")

    # Recursive drain — handle() calls may have enqueued new messages
    await drain_bus(agents, bus, depth=depth + 1)


async def _request_approval(bowen_agent, msg) -> bool:
    """
    Surface a requires_approval message to the user. Returns True if approved.
    Uses blocking input() — acceptable since this is a single-user CLI.
    """
    print(f"\n\033[33m[BOWEN] Approval required before executing:\033[0m")
    print(f"  From:    {msg.sender}")
    print(f"  To:      {msg.recipient}")
    print(f"  Type:    {msg.msg_type}")
    if hasattr(msg.payload, "action_type"):
        # ApprovalRequestPayload — structured fields
        print(f"  Action:  {msg.payload.action_type}")
        print(f"  Details: {msg.payload.description}")
        print(f"  Risk:    {msg.payload.risk_level.upper()}")
    else:
        # Other payload types — show a preview
        preview = str(msg.payload)[:120]
        print(f"  Payload: {preview}")
    try:
        answer = input("  Approve? (y/n): ").strip().lower()
        return answer == "y"
    except (EOFError, KeyboardInterrupt):
        return False  # Non-interactive context or Ctrl+C = deny


async def main() -> None:
    config = Config()

    if not check_env(config):
        sys.exit(1)

    # Memory must initialize before agents — agents load profile on first respond()
    memory = MemoryStore(config.DB_PATH, config.CHROMA_PATH)
    memory.set_profile_path(config.PROFILE_PATH)
    await memory.initialize()  # opens aiosqlite connection, applies schema v3

    # Initialize tool registry with all API keys and paths bound.
    # This runs make_*_tool_map() for each agent, creating closures with keys embedded.
    # Must happen before agents are instantiated since agents call get_schemas() on respond().
    registry.initialize(
        brave_api_key=config.BRAVE_API_KEY,
        google_credentials_path=config.GOOGLE_CREDENTIALS_PATH,
        google_token_path=config.GOOGLE_TOKEN_PATH,
        db_path=config.DB_PATH,
        user_timezone=config.USER_TIMEZONE,
    )

    bus = MessageBus()

    # All 5 agents share the same memory, bus, and config.
    # They only differ in identity, model, and allowed tools.
    agents = {
        "BOWEN":   BOWENAgent(config, memory, bus),
        "CAPTAIN": CaptainAgent(config, memory, bus),
        "SCOUT":   ScoutAgent(config, memory, bus),
        "TAMARA":  TamaraAgent(config, memory, bus),
        "HELEN":   HelenAgent(config, memory, bus),
    }

    # One session per CLI run. Session ID links all messages in SQLite.
    session_id = str(uuid.uuid4())
    await memory.create_session(session_id)
    for agent in agents.values():
        agent.set_session(session_id)

    # Build scheduler first (no agents needed for nightly consolidation),
    # then wire HELEN's agent-dependent jobs (7am briefing, 6am Bible check).
    scheduler = build_scheduler(config, memory)
    wire_helen_jobs(scheduler, agents["HELEN"], config)
    scheduler.start()

    print("\n\033[1mBOWEN online.\033[0m  [Phase 4 — Gmail + Calendar active]")
    print("Commands: /code /search /email /calendar | @CAPTAIN @SCOUT @TAMARA @HELEN")
    print("/status  /memory <query>  /agents  exit\n")

    while True:
        try:
            user_input = input("\033[36m→ \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "bye"):
            print("\n[BOWEN] Session complete.")
            break

        # ── Built-in slash commands ────────────────────────────────────────────

        if user_input.lower() == "/status":
            tasks = await memory.get_open_tasks()
            mem_count = memory._collection.count()
            print(f"  Memories in ChromaDB: {mem_count}")
            print(f"  Open tasks: {len(tasks)}")
            for t in tasks:
                print(f"    [{t['status']}] {t['title']} ({t['agent']})")
            continue

        if user_input.lower().startswith("/memory "):
            query = user_input[8:].strip()
            results = memory.search(query, top_k=5, min_relevance=0.5)  # search() is sync
            print(results or "  No memories found.")
            continue

        if user_input.lower() == "/agents":
            for name, agent in agents.items():
                print(f"  {name}: {agent.voice_style}")
            continue

        # ── Route → respond → drain ────────────────────────────────────────────

        # Routing is capped at 10s — Groq should respond in ~100ms, Haiku in ~400ms.
        # If both fail/hang, we default to BOWEN rather than hanging the CLI.
        try:
            async with asyncio.timeout(10):
                target_name = await agents["BOWEN"].route(user_input)
        except asyncio.TimeoutError:
            print("  [router] Routing timed out. Defaulting to BOWEN.")
            target_name = "BOWEN"
        except Exception as e:
            print(f"  [router] Routing error: {e}. Defaulting to BOWEN.")
            target_name = "BOWEN"

        # Agent responds — capped at 120s for long tool-use chains (e.g. CAPTAIN building a feature)
        try:
            async with asyncio.timeout(120):
                await agents[target_name].respond(user_input)
        except asyncio.TimeoutError:
            print(f"\n  [{target_name}] Response timed out after 120s.")
        except Exception as e:
            print(f"\n  [{target_name}] Error: {type(e).__name__}: {e}")

        # Process any inter-agent messages generated during this turn
        await drain_bus(agents, bus)

    # ── Session teardown ───────────────────────────────────────────────────────

    await memory.end_session(session_id)
    scheduler.shutdown(wait=False)

    # Sleep-time extraction: runs directly (no asyncio.create_task delay) because
    # the event loop will exit immediately after main() returns.
    # A 5-min delay only makes sense in a persistent daemon, not a CLI session.
    print("\n  [sleep-time] Extracting memories from session...")
    await run_sleep_pipeline(memory, session_id, config.ANTHROPIC_API_KEY, config.HAIKU_MODEL)

    await memory.close()


if __name__ == "__main__":
    asyncio.run(main())
