# BOWEN — Master Knowledge File
**Last Updated:** 2026-04-10
**Location:** `/Volumes/S1/bowen/`
**Status:** Active development. Multi-user capable. Praise's instance is primary.

---

## What BOWEN Is

BOWEN is a personal AI operating system built exclusively for Praise Oyimi.

Not a chatbot. Not an assistant you open when you need something. An always-present system of five specialized agents running simultaneously as one unified operating system for his life. Each agent has a defined job. BOWEN sits on top routing everything, and surfaces only the decisions that actually require Praise.

Named after Captain Bowen — Praise's grandfather. The name carries weight: wisdom, authority, presence, legacy. The product is meant to embody the same.

**Core difference from everything else: context persistence.**
Every interaction feeds a growing picture of who Praise is. Across days, weeks, months. BOWEN on day one is helpful. BOWEN on day 365 is indispensable because it knows him better than any tool on the planet.

---

## The Five Agents (One System)

This is not four personalities you choose from. This is five agents running simultaneously as one chief of staff with five departments. BOWEN is the orchestrator. The other four are the departments.

### BOWEN — Lead Orchestrator
- Routes all tasks to the right agent
- Synthesizes results from sub-agents
- Surfaces only decisions that need Praise
- Never writes code, does research, sends emails, or manages calendar directly
- Model: Claude Haiku (fast routing, cheap)
- Voice: deep, calm, authoritative. Measured pace. Never wastes words.

### CAPTAIN — Builder & Executor
- All code, builds, file operations, shell commands, architecture
- Always delivers finished working implementations — no placeholders, no TODOs
- Languages: Python, TypeScript, JavaScript, Shell, SQL
- SCOUT → CAPTAIN chain: research flows directly into builds
- Model: Claude Sonnet (code quality demands it)
- Voice: focused, clipped, minimal words

### SCOUT — Deep Researcher
- Web research, competitive analysis, market research, technical deep dives, document parsing
- Leads with the most important finding. Specific — names, numbers, dates, quotes. No vague summaries.
- Always includes source URLs
- Ends responses with `CHAIN_TO_CAPTAIN: <task>` when research implies something needs to be built
- Model: Claude Sonnet
- Voice: clear, neutral, analytical. Speaks in findings.

### TAMARA — Communications
- All email, messaging, outbound communications
- Writes in Praise's voice — not corporate language. Direct, short sentences, active voice.
- NEVER sends without explicit approval. Approval gate enforced at tool level, not just system prompt.
- Gmail read/draft/send
- Model: Claude Sonnet
- Voice: warm but efficient. Gets to the point fast.

### HELEN — Personal Life Agent
- Calendar, reminders, daily briefings, Bible accountability, tasks, deadlines
- Non-negotiables tracked every day: Bible reading, morning prayer
- Morning briefing at 7am: date + Bible status + calendar + deadlines + single focus + one line of encouragement
- Model: Claude Haiku (briefings are short, speed matters)
- Voice: gentle, grounding. Warm. Firm on the non-negotiables.

---

## What Makes BOWEN Different

**vs ChatGPT:** Conversation resets. No persistence of emotional context. Remembers facts not patterns. BOWEN builds a continuous, evolving understanding across days, weeks, months.

**vs Siri/Alexa:** Command executors. No depth, no context, no relationship. BOWEN knows Praise's projects, people, goals, struggles. When he says "I need to get this done today" BOWEN already knows what "this" is.

**vs Google Assistant/Gemini:** Search engines with a voice. Good at finding information. Terrible at knowing YOU. BOWEN knows exactly what answer Praise needs right now based on everything it knows about his life.

---

## Memory Architecture

Three layers:

**Layer 1 — user_profile.md**
Plain markdown. Loaded into every agent's system prompt on every call. Contains: identity, active priorities, projects, non-negotiables, key people, communication style.

**Layer 2 — ChromaDB**
Semantic vector store. Model: `all-MiniLM-L6-v2` (384 dimensions). NEVER CHANGE THIS MODEL — existing vectors are incompatible. Top-K=8, min relevance=0.7. Time decay applied.

**Layer 3 — SQLite (aiosqlite)**
Tables: topics, conversations, messages, memories, tasks, decisions, bible_log, artifacts, schema_version (v3). Thread-safe.

**Sleep-time extraction:** After each session ends, Haiku reads the full transcript and extracts memories into ChromaDB. Pattern from Letta/MemGPT.

**Nightly consolidation (3am):** Temporal decay, pruning (importance < 0.05 AND 90+ days unaccessed), duplicate merging (cosine similarity > 0.95).

---

## Technical Architecture

**Backend:** FastAPI v5.0.0 + WebSocket streaming
**Frontend target:** Tauri (desktop app)
**Entry point:** `main.py` — FastAPI lifespan starts memory, registry, agents, scheduler
**WebSocket:** `ws://localhost:8000/ws/chat`
**Health:** `http://localhost:8000/api/health`

**Routing:**
- Tier 1: Regex (<1ms, $0) — catches ~30% of inputs
- Tier 2: Groq LLaMA 3.1 8B (~100ms) — catches everything else
- Fallback: Anthropic Haiku

**Tool system:** Three-layer enforcement — permission check → implementation check → input validation → execute

**Prompt caching:** `cache_control: ephemeral` on all system prompts. ~50% cost reduction.

**Rate limiting:** Anthropic 30/min, Groq 25/min, Tavily 10/min.

**Scheduler (APScheduler):**
- 3am: memory consolidation
- 6am: Bible reading check
- 7am: morning briefing

---

## Current Phase Status

**Last verified:** 2026-04-10

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Multi-agent foundation, routing, message bus | ✅ Complete |
| 2 | Memory architecture (ChromaDB + SQLite + user_profile.md) | ✅ Complete |
| 3 | CAPTAIN tools (code, files, shell) + SCOUT tools (search, fetch, parse) | ✅ Complete |
| 4 | TAMARA tools (Gmail) + HELEN tools (Calendar, Bible, briefing) + DEVOPS agent | ✅ Complete |
| 5 | Voice pipeline (Groq Whisper STT + Kokoro ONNX TTS + openWakeWord) | ✅ Complete |
| 6 | Tauri desktop UI | 🔲 Not built — TUI (tui.py) is the current interface |

---

## Phase 5 Voice Pipeline — Built and Working

Architecture changed from original plan. No LiveKit, no ElevenLabs. Fully local.

- **STT:** Groq Whisper (`whisper-large-v3-turbo`) — 98% cheaper than OpenAI, ~200ms latency
- **TTS:** Kokoro ONNX local model (`am_adam` voice) — Apache 2.0, zero API cost, runs offline
- **Wake word:** openWakeWord ONNX (`hey_jarvis` as "hey BOWEN" proxy) — <5% CPU at idle
- **Transport:** Direct sounddevice — half-duplex (mic muted while TTS plays)
- **Integration:** Voice routes through WebSocket to backend, same path as text input

**Cost:** ~$0/hour for TTS (local). STT costs ~$0.0003/minute via Groq.

**Activate:** `Ctrl+V` in TUI to toggle wake word listening.

**Critical notes:**
- NEVER use faster-whisper on CPU — 18+ seconds per utterance. Groq Whisper only.
- Kokoro model files must exist at `voice/kokoro/kokoro-v0_19.onnx` and `voice/kokoro/voices.bin`
- Cold start takes ~90s due to SentenceTransformer loading from S1 drive

---

## Sixth Agent: DEVOPS

Added post-Phase 4. Undocumented until now.

- **Role:** Code review, static analysis, security audit, architecture, pre-deploy checks
- **Tools:** execute_code, read_file, run_shell, web_fetch (read-only subset of CAPTAIN)
- **Format:** `[SEVERITY] file:line — issue — fix`. Verdict: `SHIP / NEEDS WORK / DO NOT SHIP`
- **Route keywords:** review, audit, lint, security scan, pre-deploy check

---

## Multi-User Architecture

BOWEN now supports multiple users. Each user gets isolated memory; all users share the same agent code, tools, and shared knowledge.

**How it works:**

- **Auth:** Each user has an API key (`bwn_<40chars>`). Sent as `?key=<key>` in WebSocket URL. SHA-256 hashed, never stored in plaintext.
- **User accounts:** `memory/users.db` — managed by `UserManager`. Admin = Praise (bootstrapped from `ADMIN_API_KEY` in `.env`).
- **Per-user memory:** `memory/users/{user_id}/` — separate `bowen.db`, `chroma/`, `profile.md` per user.
- **Per-connection agents:** Every WebSocket connection creates fresh agent instances bound to that user's memory. The `MessageBus` is also per-connection.
- **UserRegistry:** Each connection gets a `UserRegistry` that routes DB-sensitive tools (memory search, task management, calendar) to the correct user's data. Stateless tools (SCOUT web search, DEVOPS analysis) use the global registry.
- **Shared knowledge:** `memory/shared_knowledge.md` is git-tracked and loaded into ALL users' agent prompts. Grows via `POST /api/admin/knowledge`. This IS the shared brain.

**Admin endpoints** (`X-Admin-Key: <ADMIN_API_KEY>` header required):
- `POST /api/admin/users` — create user, get API key once
- `GET /api/admin/users` — list all users
- `POST /api/admin/users/{id}/regen` — regenerate key
- `GET /api/admin/users/active` — currently connected users
- `POST /api/admin/knowledge` — add entry to shared_knowledge.md
- `GET /api/admin/knowledge` — read current shared knowledge

**Legacy migration:** Praise's existing data at `memory/bowen.db` is automatically copied to `memory/users/usr_admin/` on first start.

**Shared brain model:** Improving the agent code, tools, or prompts benefits ALL users. Adding to `shared_knowledge.md` shares insights across all users. Git tracks it all.

---

## Known Issues — All Resolved

All five pre-Phase 5 issues have been fixed in the current codebase:

1. ~~AGENT_TIMEOUT not enforced~~ — fixed: `asyncio.timeout()` wraps both stream_response and tool_use_loop
2. ~~Tool executor blocks event loop~~ — fixed: `asyncio.to_thread()` in base.py tool_use_loop
3. ~~ChromaDB search blocks event loop~~ — fixed: `asyncio.to_thread()` in build_system_prompt
4. ~~No error boundary in tool_use_loop~~ — fixed: per-tool try/except + outer error boundary
5. ~~BOWEN has no tools~~ — fixed: memory_search, task_create, task_list in bowen_tools.py

---

## BOWEN and Remi

Remi is the student version of the BOWEN brain. Students start with Remi in college. When they graduate they don't lose their assistant — they upgrade to BOWEN. All context Remi built carries forward. BOWEN already knows how they learn, think, what subjects they struggled with. Remi is the entry point. BOWEN is the destination.

---

## The Hardware (Future)

Not cracked yet. The question is not "how do I carry one assistant." It's "how do I carry this entire system — five agents, one device, always running."

First hardware will be built for The Deck (ShipRite office) and The Vault (Praise's personal loft) as a smart environment system before it becomes anything else. Hardware follows software. BOWEN as software must be perfect first.

Hardware timeline: 2028+ depending on what the software reveals is needed.

---

## Release Plan

BOWEN is personal. Built for Praise. Perfected for Praise.

It does not get released until it is perfect. No exceptions.

When it is ready: software first, desktop + mobile for personal use. Cross-device context sync requires cloud memory architecture (SQLite + ChromaDB goes to Supabase + pgvector). That migration happens when BOWEN is ready to leave the single machine.

---

## File Locations

| What | Where |
|------|-------|
| Active codebase | `/Volumes/S1/BOWEN/` |
| Desktop copy | `/Users/yimi/Desktop/BOWEN REAL/` |
| Research docs | `/Volumes/S1/bowen/` (old research folder) |
| User profile | `/Volumes/S1/BOWEN/memory/user_profile.md` |
| Memory DB | `/Volumes/S1/BOWEN/memory/bowen.db` |
| ChromaDB | `/Volumes/S1/BOWEN/memory/chroma/` |
