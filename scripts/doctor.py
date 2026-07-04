#!/usr/bin/env python3
"""
scripts/doctor.py — Full-body checkup for the OS. Live, honest, one command.

    .venv/bin/python scripts/doctor.py

Checks every configured API key against its real provider, every skill in
the library, the corpus, the voice models, and the running services.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from config import Config

OK, BAD, SKIP = "✅", "❌", "➖"


def line(name: str, status: str, detail: str = "") -> None:
    print(f"  {status} {name:24s} {detail}")


async def check_keys(config: Config) -> None:
    print("\n── API keys (live-tested against each provider) ──────────────")

    # Anthropic
    try:
        from llm import get_provider
        await get_provider("anthropic", config).health_check(model=config.HAIKU_MODEL)
        line("ANTHROPIC_API_KEY", OK, "count_tokens ping accepted")
    except Exception as e:
        line("ANTHROPIC_API_KEY", BAD, f"{type(e).__name__}: {str(e)[:70]}")

    # Groq
    if config.GROQ_API_KEY:
        try:
            from llm import get_provider
            await get_provider("groq", config).health_check()
            line("GROQ_API_KEY", OK, "models.list accepted")
        except Exception as e:
            line("GROQ_API_KEY", BAD, f"{str(e)[:80]}")
    else:
        line("GROQ_API_KEY", SKIP, "not set (routing falls back to Haiku; STT off)")

    async with httpx.AsyncClient(timeout=10) as client:
        # Brave
        if config.BRAVE_API_KEY:
            try:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": "ping", "count": 1},
                    headers={"X-Subscription-Token": config.BRAVE_API_KEY},
                )
                line("BRAVE_API_KEY", OK if r.status_code == 200 else BAD, f"http {r.status_code}")
            except Exception as e:
                line("BRAVE_API_KEY", BAD, str(e)[:70])
        else:
            line("BRAVE_API_KEY", SKIP, "not set (SCOUT cannot search)")

        # ElevenLabs (optional elder voice)
        el_key = os.getenv("ELEVENLABS_API_KEY", "")
        if el_key:
            try:
                r = await client.get(
                    "https://api.elevenlabs.io/v1/user",
                    headers={"xi-api-key": el_key},
                )
                line("ELEVENLABS_API_KEY", OK if r.status_code == 200 else BAD, f"http {r.status_code}")
            except Exception as e:
                line("ELEVENLABS_API_KEY", BAD, str(e)[:70])
        else:
            line("ELEVENLABS_API_KEY", SKIP, "not set (elder_voice tenants fall back to Kokoro)")

        # Twilio (the gate's delivery layer)
        sid, token = os.getenv("TWILIO_ACCOUNT_SID", ""), os.getenv("TWILIO_AUTH_TOKEN", "")
        if sid and token:
            try:
                r = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
                    auth=(sid, token),
                )
                line("TWILIO", OK if r.status_code == 200 else BAD, f"account fetch http {r.status_code}")
            except Exception as e:
                line("TWILIO", BAD, str(e)[:70])
        else:
            line("TWILIO", SKIP, "not set (caregiver alerts land on the log channel)")

    # Perplexity/Tavily are unused by the core loop — report honestly
    for unused in ("PERPLEXITY_API_KEY", "TAVILY_API_KEY"):
        if os.getenv(unused):
            line(unused, SKIP, "set but UNUSED by the core loop (audit 2026-07-03)")


def check_skills(config: Config) -> None:
    print("\n── Skills (library + per-agent standing assignments) ─────────")
    from core.skills import house_library, validate_skill
    from llm import resolve_agent_skills

    skills_dir = Path(__file__).parent.parent / "skills"
    errors = []
    count = 0
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        count += 1
        errors.extend(validate_skill(d))
    line("library structure", OK if not errors else BAD,
         f"{count} skills, {len(errors)} violations" + (f": {errors[:2]}" if errors else ""))

    lib = house_library()
    idx = lib.index_text()
    line("discovery index", OK, f"~{len(idx)//4} tokens for {len(lib.names())} skills")

    for agent in ["BOWEN", "CAPTAIN", "SCOUT", "TAMARA", "HELEN", "DEVOPS", "GENI"]:
        names, has_index = resolve_agent_skills(agent)
        missing = [n for n in names if lib.load(n) is None]
        status = OK if names and not missing else BAD
        detail = f"{len(names)} standing" + (" + index" if has_index else "")
        if missing:
            detail += f" — MISSING: {missing}"
        line(f"{agent} skills", status, detail)


def check_voice_and_corpus(config: Config) -> None:
    print("\n── Voice + Foundry ────────────────────────────────────────────")
    kokoro = (config.KOKORO_MODEL_DIR / "kokoro-v0_19.onnx").exists() and \
             (config.KOKORO_MODEL_DIR / "voices.bin").exists()
    line("Kokoro TTS models", OK if kokoro else BAD,
         "local, zero-cost" if kokoro else "model files missing")

    wake = (Path(__file__).parent.parent / "voice" / "models").exists()
    line("wake-word models", OK if wake else SKIP)

    from corpus.schema import LANGUAGES
    import json
    total_v = total_p = 0
    for lang in LANGUAGES:
        d = config.CORPUS_DATA_DIR / lang
        if not d.exists():
            continue
        for f in d.glob("*.jsonl"):
            for ln in f.read_text().splitlines():
                if not ln.strip():
                    continue
                total_p += 1
                try:
                    if json.loads(ln).get("verified"):
                        total_v += 1
                except Exception:
                    pass
    enabled = config.CORPUS_ENABLED_LANGS or "none"
    line("corpus", OK, f"{total_v} verified / {total_p} proposed; enabled: {enabled}")


async def check_services(config: Config) -> None:
    print("\n── Running services ───────────────────────────────────────────")
    async with httpx.AsyncClient(timeout=4) as client:
        try:
            r = await client.get("http://127.0.0.1:8000/api/health")
            agents = r.json().get("agents", [])
            line("BOWEN server", OK, f"{len(agents)} agents on :8000")
        except Exception:
            line("BOWEN server", SKIP, "not running")
        try:
            headers = {"x-api-key": config.GENI_API_KEY} if config.GENI_API_KEY else {}
            r = await client.get("http://127.0.0.1:5001/api/status", headers=headers)
            line("GENI backend", OK if r.status_code == 200 else BAD, f"http {r.status_code} on :5001")
        except Exception:
            line("GENI backend", SKIP, "not running (GENI degraded chat-only)")


async def main() -> None:
    config = Config()
    print("BOWEN doctor — full-body checkup")
    await check_keys(config)
    check_skills(config)
    check_voice_and_corpus(config)
    await check_services(config)
    print()


if __name__ == "__main__":
    asyncio.run(main())
