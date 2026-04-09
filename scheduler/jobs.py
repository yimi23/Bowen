"""
scheduler/jobs.py — APScheduler v3.11.x with AsyncIOExecutor.
MUST use AsyncIOExecutor — default ThreadPoolExecutor blocks async jobs.

build_scheduler() — nightly memory consolidation (no agents needed)
wire_helen_jobs() — morning briefing + Bible check (requires HELEN agent)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

from config import Config
from memory.store import MemoryStore
from memory.consolidator import MemoryConsolidator


def build_scheduler(config: Config, memory: MemoryStore) -> AsyncIOScheduler:
    """Build scheduler with nightly consolidation. Call wire_helen_jobs() then scheduler.start()."""

    scheduler = AsyncIOScheduler(
        executors={"default": AsyncIOExecutor()}
    )

    # Nightly memory consolidation at 3am
    async def nightly_consolidation():
        consolidator = MemoryConsolidator(memory, config.ANTHROPIC_API_KEY, config.HAIKU_MODEL)
        stats = await consolidator.run()
        print(
            f"  [consolidator] decayed={stats['decayed']} "
            f"merged={stats['merged']} pruned={stats['pruned']}"
        )

    scheduler.add_job(
        nightly_consolidation,
        "cron",
        hour=config.MEMORY_CONSOLIDATE_HOUR,
        minute=config.MEMORY_CONSOLIDATE_MINUTE,
        id="memory_consolidation",
        replace_existing=True,
    )

    return scheduler


def wire_helen_jobs(scheduler: AsyncIOScheduler, helen_agent, config: Config) -> None:
    """
    Add HELEN's proactive jobs to an existing scheduler.
    Called after agents are initialized, before scheduler.start().
    """

    # ── 7am morning briefing ──────────────────────────────────────────────────
    async def morning_briefing_job():
        print("\n\033[36m[HELEN] Good morning — generating your daily briefing...\033[0m")
        try:
            await helen_agent.morning_briefing()
        except Exception as e:
            print(f"  [HELEN] Briefing failed: {type(e).__name__}: {e}")

    scheduler.add_job(
        morning_briefing_job,
        "cron",
        hour=config.BRIEFING_HOUR,
        minute=config.BRIEFING_MINUTE,
        id="morning_briefing",
        replace_existing=True,
    )

    # ── 6am Bible reading reminder (if not yet logged) ───────────────────────
    async def bible_reminder_job():
        """Check if Bible reading is done. Nudge if not."""
        try:
            from tools.helen_tools import bible_check
            result = bible_check(config.DB_PATH, action="check")
            if not result.get("completed", False):
                from tools.helen_tools import notify
                notify(
                    "Good morning, Praise. Have you done your Bible reading today? "
                    "Tell HELEN what you read to log it.",
                    urgency="normal",
                )
        except Exception as e:
            print(f"  [HELEN] Bible reminder failed: {type(e).__name__}: {e}")

    scheduler.add_job(
        bible_reminder_job,
        "cron",
        hour=config.BIBLE_CHECK_HOUR,
        minute=config.BIBLE_CHECK_MINUTE,
        id="bible_reminder",
        replace_existing=True,
    )

    print(
        f"  [scheduler] HELEN jobs wired: briefing at {config.BRIEFING_HOUR:02d}:{config.BRIEFING_MINUTE:02d}, "
        f"bible check at {config.BIBLE_CHECK_HOUR:02d}:{config.BIBLE_CHECK_MINUTE:02d}"
    )
