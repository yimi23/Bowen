"""
config.py — All configuration and API keys.
Reads from .env at startup. Never hardcode secrets.

Accessing config: instantiate Config() in main() and pass it to agents/services.
Do NOT use os.getenv() anywhere else in the codebase — go through this class.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent


class Config:
    # ── Core AI ───────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")      # Tier 2 routing + Phase 5 STT
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # Phase 5 fallback STT
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")

    # ── Research ──────────────────────────────────────────────────────────────
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")  # SCOUT web search
    BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")    # Phase 6 optional backup

    # ── Voice (Phase 5) ───────────────────────────────────────────────────────
    # TTS: Kokoro ONNX local model (Apache 2.0, zero API cost)
    # STT: Groq Whisper (uses GROQ_API_KEY above)
    # Wake word: openWakeWord ONNX (fully local, <5% CPU)
    KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "am_adam")      # deep male voice
    KOKORO_SPEED: float = float(os.getenv("KOKORO_SPEED", "0.95"))
    KOKORO_MODEL_DIR: Path = BASE_DIR / "voice" / "kokoro"

    # ── Storage (future) ──────────────────────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # ── Models ────────────────────────────────────────────────────────────────
    # Sonnet: deep work, complex reasoning, code, research
    SONNET_MODEL: str = "claude-sonnet-4-6"
    # Haiku: fast tasks, routing, briefings, sleep extraction (3x cheaper than Sonnet)
    HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
    # Groq LLaMA: Tier 2 routing — 80% cheaper than Haiku, 3x faster
    GROQ_ROUTING_MODEL: str = "llama-3.1-8b-instant"
    # Groq Whisper: Phase 5 STT — 98% cheaper than OpenAI Whisper
    GROQ_STT_MODEL: str = "whisper-large-v3-turbo"

    # ── Paths ─────────────────────────────────────────────────────────────────
    DB_PATH: Path = BASE_DIR / "memory" / "bowen.db"
    CHROMA_PATH: Path = BASE_DIR / "memory" / "chroma"
    PROFILE_PATH: Path = BASE_DIR / "memory" / "user_profile.md"

    # Google OAuth (Phase 4)
    # credentials.json: download from Google Cloud Console → Credentials → OAuth 2.0 Client ID
    # token.json: auto-created on first browser auth run, refreshed automatically
    # IMPORTANT: OAuth consent screen must be "In Production" mode, not "Testing"
    #            Testing mode tokens expire every 7 days → silent auth failures
    GOOGLE_CREDENTIALS_PATH: Path = BASE_DIR / "credentials.json"
    GOOGLE_TOKEN_PATH: Path = BASE_DIR / "token.json"

    # ── System ────────────────────────────────────────────────────────────────
    USER_NAME: str = os.getenv("USER_NAME", "Praise Oyimi")
    USER_TIMEZONE: str = os.getenv("USER_TIMEZONE", "America/Detroit")

    # ── Multi-user ────────────────────────────────────────────────────────────
    # ADMIN_API_KEY: Praise's personal API key — also used to bootstrap the admin account.
    # Set this in .env. All other users get keys via POST /api/admin/users.
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
    # USERS_BASE_DIR: where per-user memory directories live
    USERS_BASE_DIR: Path = BASE_DIR / "memory" / "users"
    # USERS_DB_PATH: user account registry (separate from personal memory)
    USERS_DB_PATH: Path = BASE_DIR / "memory" / "users.db"

    # ── Routing ───────────────────────────────────────────────────────────────
    # If Groq misroutes > 10% of inputs, add semantic-router as Tier 1.5
    MISROUTE_THRESHOLD: float = 0.10

    # ── Memory ────────────────────────────────────────────────────────────────
    MEMORY_TOP_K: int = 8             # max memories retrieved per query
    MEMORY_MIN_RELEVANCE: float = 0.7 # cosine similarity threshold
    CORE_MEMORY_MAX_TOKENS: int = 2000

    # ── Sessions ──────────────────────────────────────────────────────────────
    SESSION_TIMEOUT_MINUTES: int = 30

    # ── Scheduler ─────────────────────────────────────────────────────────────
    BRIEFING_HOUR: int = 7       # 7am — HELEN morning briefing
    BRIEFING_MINUTE: int = 0
    BIBLE_CHECK_HOUR: int = 6    # 6am — Bible reading reminder if not logged
    BIBLE_CHECK_MINUTE: int = 0
    MEMORY_CONSOLIDATE_HOUR: int = 3    # 3am — nightly decay/merge/prune
    MEMORY_CONSOLIDATE_MINUTE: int = 0

    def validate(self) -> list[str]:
        """Return list of missing required env vars. Only ANTHROPIC_API_KEY is hard-required."""
        missing = []
        if not self.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        return missing

    def status(self) -> dict[str, bool]:
        """Show which optional services are configured. Useful for diagnostics."""
        kokoro_ready = (
            (self.KOKORO_MODEL_DIR / "kokoro-v0_19.onnx").exists()
            and (self.KOKORO_MODEL_DIR / "voices.bin").exists()
        )
        return {
            "anthropic": bool(self.ANTHROPIC_API_KEY),
            "groq":      bool(self.GROQ_API_KEY),
            "tavily":    bool(self.TAVILY_API_KEY),
            "tts_kokoro": kokoro_ready,
            "stt_groq":  bool(self.GROQ_API_KEY),
            "supabase":  bool(self.SUPABASE_URL),
            "google":    self.GOOGLE_CREDENTIALS_PATH.exists(),
        }
