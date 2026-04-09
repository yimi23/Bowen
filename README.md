# BOWEN — Built On Wisdom, Excellence, and Nobility

Personal AI operating system for Praise Oyimi, CEO of Twine Campus Inc.
Five specialized agents. Shared semantic memory. Voice pipeline. Proactive scheduler.

Built at `/Volumes/S1/bowen/`. Runs entirely on the S1 external drive.

---

## Quick Start

```bash
cd /Volumes/S1/bowen
source .venv/bin/activate

# TUI (primary — Summit aesthetic, voice support, Ctrl+V to toggle wake word)
python tui.py

# CLI fallback
python clawdbot.py
```

All API keys live in `.env`. The system boots in about 3 seconds.

---

## The Five Agents

| Agent | Role | Model | Tools |
|-------|------|-------|-------|
| BOWEN | Orchestrator, router, chief of staff | Haiku | memory_search, task_create, task_list |
| CAPTAIN | Code, builds, file ops, shell | Sonnet | execute_code, read_file, write_file, run_shell, web_fetch |
| SCOUT | Web research, competitive analysis | Sonnet | web_search (Brave), web_fetch, document_parse, structured_extract |
| TAMARA | Gmail, drafts, outbound comms | Sonnet | gmail_read, gmail_draft, gmail_send (approval required) |
| HELEN | Calendar, tasks, Bible tracking, briefings | Haiku | calendar_list, calendar_create, task_create, bible_check, notify, daily_briefing |

---

## TUI Shortcuts

| Key | Action |
|-----|--------|
| Enter | Send message |
| Tab | Cycle active agent (BOWEN → CAPTAIN → SCOUT → TAMARA → HELEN) |
| Ctrl+V | Toggle voice pipeline (wake word + mic + TTS) |
| Escape | Clear input |
| Ctrl+C | Quit cleanly |

---

## Routing

Every message passes through two tiers:

**Tier 1 — Regex** (`routing/tier1.py`) — under 1ms, zero cost
- Covers ~30% of inputs via explicit patterns
- Examples: `/code`, `@SCOUT`, `research`, `check my email`, `morning briefing`

**Tier 2 — Groq LLaMA 3.1 8B** (`routing/tier2.py`) — ~100ms, $0.0002/call
- Forces a single tool selection — always returns a clean agent name
- Falls back to Anthropic Haiku if Groq key is missing or errors

---

## Voice Pipeline

Three components, all local or Groq-based:

| Component | Implementation | Notes |
|-----------|---------------|-------|
| Wake word | openWakeWord (ONNX) | hey_jarvis model as "Hey BOWEN" proxy. <5% CPU idle. |
| STT | Groq Whisper large-v3-turbo | Records until 1.5s silence. Max 30s. |
| TTS | Kokoro ONNX (am_adam voice) | 310MB model at `voice/kokoro/`. No API key. |

Flow: wake word detected → ack phrase → record speech → transcribe → BOWEN.route() → agent.respond() → TTS speaks response → back to listening.

Half-duplex: mic is logically off while TTS plays. 1.5s cooldown before wake word restarts.

---

## Memory System

Three layers, always active:

**Layer 1 — user_profile.md** (always-on)
- Praise's permanent profile: identity, faith, projects, non-negotiables, family, team
- Injected into every agent's system prompt on every turn
- Updated by SleepTimeAgent after high-importance sessions

**Layer 2 — ChromaDB semantic search** (relevant context)
- Vector embeddings via `all-MiniLM-L6-v2` (384 dimensions, cosine similarity)
- Top 8 most relevant memories per query, filtered by topic
- Score = cosine_similarity * time_decay * importance
- 50 memories seeded from The Captain's Brain document (`seed_brain.py`)

**Layer 3 — SQLite** (structured data)
- Topics, conversations, messages, tasks, decisions, Bible log, artifacts
- Schema version 3. Migration runs automatically at startup.

**Mem0** (conversation-level extraction)
- Ollama qwen3:4b + nomic-embed-text (local, no API key)
- Separate ChromaDB collection at `memory/chroma_mem0/`
- Runs after every TUI conversation — extracts facts automatically
- Falls back silently if Ollama is offline

**Nightly consolidation** (3am scheduler job, `memory/consolidator.py`)
- Applies temporal decay: importance * 0.95 per 30 days unaccessed
- Merges near-duplicate memories (cosine similarity > 0.95) via Haiku
- Prunes memories below 0.05 importance not accessed in 90+ days

---

## Scheduler Jobs

| Job | Time | Handler |
|-----|------|---------|
| Bible reminder | 6:00am | Checks bible_log. Nudges via `notify()` if not logged. |
| Morning briefing | 7:00am | HELEN.morning_briefing() — calendar + tasks + Bible status |
| Memory consolidation | 3:00am | MemoryConsolidator.run() — decay, merge, prune |

APScheduler v3.11 with AsyncIOExecutor. The scheduler runs inside both the TUI and FastAPI server.

---

## Google OAuth Setup (TAMARA + HELEN)

Gmail and Calendar require a one-time setup:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable **Gmail API** and **Google Calendar API**
3. Credentials → Create **OAuth 2.0 Client ID** → type: Desktop app
4. Download the JSON → save as `credentials.json` in `/Volumes/S1/bowen/`
5. OAuth consent screen → set to **In Production** (not Testing — tokens expire every 7 days)
6. Run: `.venv/bin/python3 tools/google_auth.py`
7. Browser opens, authorize, `token.json` is saved automatically

TAMARA and HELEN operate in degraded mode (no Gmail/Calendar) until this is complete.

---

## Project Structure

```
/Volumes/S1/bowen/
├── tui.py                   Primary entry. Textual TUI with Summit aesthetic.
├── clawdbot.py              CLI fallback. Same agents, terminal I/O.
├── main.py                  FastAPI server (WebSocket chat, REST API).
├── config.py                All configuration. Reads from .env. Never use os.getenv() elsewhere.
├── seed_brain.py            One-time seeder. Writes The Captain's Brain into ChromaDB.
├── requirements.txt         Python dependencies (Python 3.14.3, venv at .venv/).
│
├── agents/
│   ├── base.py              BaseAgent: system prompt, streaming, tool_use_loop, bus dispatch.
│   ├── bowen.py             Orchestrator. Routes via tier1 → tier2. Tool-use loop.
│   ├── captain.py           Code + builds. Handles ChainPayload from SCOUT.
│   ├── scout.py             Research. Auto-chains to CAPTAIN if output includes CHAIN_TO_CAPTAIN.
│   ├── tamara.py            Gmail. Falls back to stream_response if Google not configured.
│   └── helen.py             Calendar + personal. Falls back if Google not configured.
│
├── bus/
│   ├── schema.py            AgentMessage envelope + 15 typed Pydantic payload models.
│   └── message_bus.py       Per-agent asyncio.PriorityQueue. Priority 5 = urgent, 1 = low.
│
├── memory/
│   ├── store.py             Unified async interface. ChromaDB + aiosqlite. Schema v3.
│   ├── pipeline.py          SleepTimeAgent: post-session fact extraction via Haiku.
│   ├── consolidator.py      Nightly decay, merge, prune.
│   ├── mem0_layer.py        Mem0 integration (Ollama local LLM). Separate chroma_mem0/ collection.
│   └── user_profile.md      Praise's permanent profile. Always injected into system prompts.
│
├── routing/
│   ├── tier1.py             Regex router. First match wins. BOWEN direct-address checked first.
│   └── tier2.py             Groq LLaMA (primary) + Anthropic Haiku (fallback). tool_choice forced.
│
├── scheduler/
│   └── jobs.py              build_scheduler() + wire_helen_jobs(). Call in this order.
│
├── tools/
│   ├── registry.py          Per-agent permission enforcement. Agents cannot call outside their list.
│   ├── captain_tools.py     execute_code (uses sys.executable), read_file, write_file, run_shell, web_fetch.
│   ├── scout_tools.py       web_search (Brave Search API), web_fetch, document_parse, structured_extract.
│   ├── tamara_tools.py      gmail_read, gmail_draft, gmail_send (requires terminal approval).
│   ├── helen_tools.py       calendar_list, calendar_create, task_create, bible_check, notify, daily_briefing.
│   ├── bowen_tools.py       memory_search, task_create, task_list.
│   └── google_auth.py       OAuth2 flow. build_gmail() / build_calendar().
│
├── voice/
│   ├── pipeline.py          VoicePipeline coordinator. wake → STT → agent → TTS.
│   ├── wake.py              WakeWordDetector. openWakeWord ONNX. hey_jarvis model.
│   ├── stt.py               STTEngine. Groq Whisper. Records until silence.
│   └── tts.py               TTSEngine. Kokoro ONNX am_adam. speak() + speak_streaming().
│
├── api/
│   ├── gateway.py           WebSocket /ws/chat. Streams chunks, drains bus between turns.
│   ├── health.py            GET /api/health. Returns agent + service status.
│   ├── memory.py            REST endpoints for memory CRUD.
│   └── topics.py            REST endpoints for topic/notebook management.
│
└── utils/
    └── rate_limiter.py      Sliding window. 30/min Anthropic, 25/min Groq, 10/min Tavily.
```

---

## How Agents Work (For Developers)

Every agent inherits from `BaseAgent` (`agents/base.py`). The flow for every user message:

1. `build_system_prompt(query)` — assembles identity + user_profile.md + top-8 relevant memories
2. Memory search runs in `asyncio.to_thread()` — SentenceTransformer embedding is sync, ~10-50ms
3. `stream_response()` for simple agents (no tools), `tool_use_loop()` for agents with tools
4. Tool execution runs in `asyncio.to_thread()` — Google API calls are sync
5. `_log()` writes user + assistant messages to SQLite
6. Chunks stream to TUI via `send` callback, or print to terminal if `send` is None

**Adding a new agent:**
1. Create `agents/yourname.py` extending `BaseAgent`
2. Define `name`, `base_identity`, and override `respond()`
3. Add tool schemas in `tools/yourname_tools.py`
4. Register in `tools/registry.py` `TOOL_REGISTRY` dict
5. Add to `agents` dict in `tui.py`, `main.py`, and `clawdbot.py`
6. Add routing patterns in `routing/tier1.py` and `routing/tier2.py`

**Adding a new tool to an existing agent:**
1. Write the function in the relevant `tools/agent_tools.py`
2. Add the Anthropic tool schema to the `AGENT_TOOL_SCHEMAS` list
3. Add the tool name to `TOOL_REGISTRY["AGENTNAME"]` in `registry.py`
4. Add to `make_agent_tool_map()` return dict

---

## Remi Learnings (What Shaped This Architecture)

See `REMI_LEARNINGS.md` for the full breakdown. Key patterns adopted from Remi's production codebase:

- **Groq LLaMA for routing** — 80% cheaper than Haiku, 3x faster. Remi used it for low-stakes inference.
- **System prompt caching** — `cache_control: ephemeral` on system blocks. Remi saved ~50% cost this way.
- **Voice-optimized output** — `voice_style` property on each agent. Remi's TTS rules (no markdown in spoken output) informed how BOWEN formats voice responses.
- **Tool-choice forced routing** — Remi used `tool_choice="required"` on Groq and `{"type": "any"}` on Anthropic to force deterministic routing without parsing free text.
- **Mode-based tool filtering** — Remi filtered tools by study mode (exam vs general). BOWEN uses per-agent tool registries with the same principle.

---

## Critical Developer Notes

```
NEVER change the ChromaDB embedding model (all-MiniLM-L6-v2).
Existing vectors become incompatible. Must wipe chroma/ and re-seed.

APScheduler MUST use AsyncIOExecutor.
Default ThreadPoolExecutor silently blocks all async scheduler jobs.

Google OAuth consent screen MUST be "In Production" mode.
Testing mode tokens expire every 7 days — silent auth failures in production.

All Google API calls (google-api-python-client) are synchronous.
They run inside tool_use_loop which calls them via asyncio.to_thread().
If adding new Google tools, follow the same pattern.

SSL on macOS with Homebrew Python 3.14: verify="/etc/ssl/cert.pem".
certifi.where() does not work with Homebrew Python 3.14 on macOS.

execute_code uses sys.executable (not "python3") so code runs inside the venv.
If you change this, CAPTAIN loses access to all installed packages.

gmail_send uses input() for approval — works in TUI/CLI, blocks in WebSocket mode.
Phase 6: replace with WebSocket approval_required event + UI confirmation.
```

---

## Services and API Keys

All keys in `.env`. Current status:

| Service | Used for | Key env var |
|---------|---------|-------------|
| Anthropic | All 5 agents (Sonnet + Haiku) | `ANTHROPIC_API_KEY` |
| Groq | Tier 2 routing (LLaMA) + STT (Whisper) | `GROQ_API_KEY` |
| Brave Search | SCOUT web_search | `BRAVE_API_KEY` |
| Google OAuth | TAMARA Gmail, HELEN Calendar | `credentials.json` + `token.json` |
| Ollama (local) | Mem0 extraction (qwen3:4b + nomic-embed-text) | none — local |

---

## Models

| Model | ID | Used for |
|-------|----|---------|
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | CAPTAIN, SCOUT, TAMARA |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | BOWEN, HELEN, sleep extraction, routing fallback |
| Groq LLaMA 3.1 8B | `llama-3.1-8b-instant` | Tier 2 routing (primary) |
| Groq Whisper | `whisper-large-v3-turbo` | STT transcription |
| Kokoro ONNX | `kokoro-v0_19.onnx` (local) | TTS (am_adam voice) |
| openWakeWord | `hey_jarvis_v0.1.onnx` (local) | Wake word detection |

---

## Phase Status

- **Phase 1** — Agent contracts, orchestrator, message bus, two-tier routing ✓
- **Phase 2** — Memory: ChromaDB, SQLite, sleep-time extraction, nightly consolidation ✓
- **Phase 3** — CAPTAIN tools (code/file/shell), SCOUT tools (Brave Search) ✓
- **Phase 4** — TAMARA Gmail, HELEN Calendar + Bible tracker + morning briefing ✓
- **Phase 5** — Voice pipeline: openWakeWord + Groq Whisper + Kokoro ONNX TTS + Textual TUI ✓
- **Phase 6** — WebSocket approval UI, LiveKit real-time voice, self-improvement loop ⏳

---

## Troubleshooting

**Boot fails with "Missing required env vars"**
```bash
cat .env   # verify ANTHROPIC_API_KEY is set
```

**"Google credentials not found"**
Follow Google OAuth Setup above. credentials.json must be at `/Volumes/S1/bowen/credentials.json`.

**ChromaDB "instance already exists" error**
Two processes are trying to open the same ChromaDB path. Only one process can hold ChromaDB at a time. Stop the other process first.

**Voice not activating on Ctrl+V**
Check mic permissions in System Settings. openWakeWord models must be downloaded:
```bash
.venv/bin/python3 -c "import openwakeword; openwakeword.utils.download_models()"
```

**Kokoro TTS silent (no audio)**
Model files must be at `voice/kokoro/kokoro-v0_19.onnx` and `voice/kokoro/voices.bin`. Check they exist.

**Agent hangs / no response**
Agents time out after 120s, routing after 10s. If a tool keeps hanging, check rate limiter — may be throttled. Check `.env` for correct API keys.

**Wipe memory and start fresh**
```bash
rm -rf memory/chroma memory/chroma_mem0 memory/bowen.db
.venv/bin/python3 seed_brain.py   # re-seed The Captain's Brain
```
