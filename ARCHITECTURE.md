# BOWEN Architecture Reference

Deep technical reference for the BOWEN multi-agent system.
Read this when coming back after a break, onboarding a new developer, or debugging.

---

## System Overview

```
User types a message
       │
       ▼
  clawdbot.py (main loop)
       │
       ▼
  BOWEN.route()
  ┌────────────────────────────────┐
  │  Tier 1: Regex (< 1ms, $0)    │
  │  → catches ~30% of inputs     │
  │                                │
  │  Tier 2: Groq LLaMA (~100ms)  │
  │  → catches everything else    │
  │  → fallback: Anthropic Haiku  │
  └────────────────────────────────┘
       │
       ▼
  Target agent.respond(user_text)
  ┌────────────────────────────────┐
  │  tool_use_loop (if has tools) │
  │   1. Claude picks tools       │
  │   2. Tools execute            │
  │   3. Results back to Claude   │
  │   4. Repeat until end_turn    │
  └────────────────────────────────┘
       │
       ▼
  drain_bus()
  → any inter-agent messages sent during respond()
  → approval check before handle()
  → recursive up to depth 10

  Session ends (user types "exit")
       │
       ▼
  run_sleep_pipeline()
  → Haiku reads full transcript
  → extracts facts → writes to ChromaDB
  → refreshes user_profile.md
```

---

## Message Bus

**File:** `bus/message_bus.py`, `bus/schema.py`

Every agent has its own `asyncio.PriorityQueue`. Messages flow:
- `agent.dispatch_to(recipient, payload)` → `bus.send(msg)` → recipient's queue
- After each user turn, `clawdbot.py` calls `drain_bus()` to process all pending messages
- Recursive drain with max depth 10 (prevents infinite loops)

### AgentMessage envelope

```python
@dataclass
class AgentMessage:
    sender: str              # Which agent sent it
    recipient: str           # Which agent receives it (or "broadcast")
    msg_type: str            # "request" | "response" | "inform" | "error" | "chain" | "approval"
    payload: Any             # One of 15 typed Pydantic models (see schema.py)
    priority: int = 3        # 1 (low) → 5 (urgent). Higher priority = dequeued first.
    requires_approval: bool  # If True, user must approve before handle() is called
    correlation_id: str      # UUID, auto-generated
    session_id: str          # Links message to current session
```

### Priority Queue ordering

```python
def __lt__(self, other):
    return self.priority > other.priority  # INVERTED — higher number = higher priority
```

This is correct. Python's `heapq` (used by PriorityQueue) puts the smallest value first,
so we invert so that priority 5 (urgent) comes out before priority 1 (low).

### The 15 payload types

```
TextPayload               — general text between agents
CodeRequestPayload        — BOWEN → CAPTAIN: write or execute code
CodeResponsePayload       — CAPTAIN → BOWEN: result
ResearchRequestPayload    — BOWEN → SCOUT: research a topic
ResearchResponsePayload   — SCOUT → BOWEN: findings
EmailReadPayload          — BOWEN → TAMARA: read inbox
EmailSendPayload          — BOWEN → TAMARA: send or draft
EmailSummaryPayload       — TAMARA → BOWEN: inbox summary
CalendarRequestPayload    — BOWEN → HELEN: fetch or create events
CalendarResponsePayload   — HELEN → BOWEN: calendar data
BriefingPayload           — HELEN → BOWEN: morning briefing package
BibleCheckPayload         — HELEN internal: daily reading tracking
ChainPayload              — any → any: pass work product forward (SCOUT → CAPTAIN)
ApprovalRequestPayload    — any → BOWEN: surface high-risk action for user approval
ErrorPayload              — any → BOWEN: report a recoverable/fatal error
```

---

## Memory Architecture

**Files:** `memory/store.py`, `memory/pipeline.py`, `memory/consolidator.py`

### Three layers

**Layer 1 — user_profile.md**
- Plain markdown file at `memory/user_profile.md`
- Loaded into every agent's system prompt via `memory.get_core_memory()`
- Contains: identity, active priorities, projects, non-negotiables, key people, communication style
- Updated by sleep-time pipeline when importance >= 0.7 memories are extracted

**Layer 2 — ChromaDB**
- Semantic vector store at `memory/chroma/`
- Embedding model: `all-MiniLM-L6-v2` (384 dimensions)
- `NEVER CHANGE THIS MODEL` — existing vectors are incompatible with any other model
- Each agent retrieves top-k most relevant memories at query time (k=8, min_relevance=0.7)
- Time decay applied: relevance score penalizes memories not accessed recently

**Layer 3 — SQLite**
- Database at `memory/bowen.db`
- Tables: `sessions`, `messages`, `memories`, `tasks`, `decisions`, `bible_log`, `schema_version`
- Thread-safe via `threading.RLock` — all ops go through `_exec()` / `_query()` helpers
- History ordering uses `id` column (auto-increment) not `turn` (per-agent counter)

### Sleep-time extraction pipeline

Triggered by `run_sleep_pipeline()` when the user exits.
Pattern is from Letta/MemGPT — extract after the session, not during.

1. Load full session transcript from SQLite
2. Send to Haiku with extraction prompt (outputs JSON array of memory objects)
3. Each memory: `{content, memory_type, importance, agent_id, tags}`
4. Write all to ChromaDB
5. If any memory has importance >= 0.7, also refresh user_profile.md

### Nightly consolidation (3am)

1. **Temporal decay** — for each memory: `importance × 0.95^(days_since_access / 30)`
2. **Pruning** — delete memories with importance < 0.05 AND not accessed in 90+ days
3. **Duplicate merging** — query each memory against collection; if cosine similarity > 0.95,
   send both to Haiku to produce one merged sentence, delete originals, write merged

---

## Routing

**Files:** `routing/tier1.py`, `routing/tier2.py`

### Tier 1 — Regex

```python
ROUTING_PATTERNS = [
    ("BOWEN",   re.compile(r"^hey\s+bowen\b | ^bowen[,\s] | ^/bowen | ^@bowen")),
    ("CAPTAIN", re.compile(r"^/code | ^@captain | \b(execute|write a script|debug|implement|refactor)")),
    ("HELEN",   re.compile(r"^/calendar | ^@helen | \b(calendar|morning briefing|bible reading|deadline)")),
    ("SCOUT",   re.compile(r"^/search | ^@scout | \b(research|look up|competitive analysis)")),
    ("TAMARA",  re.compile(r"^/email | ^@tamara | \b(email|gmail|inbox|draft)")),
]
```

Order matters. BOWEN direct-address MUST be first — prevents "hey BOWEN, research X"
from matching SCOUT's research pattern.

### Tier 2 — Groq LLaMA 3.1 8B

- Uses `tool_choice="required"` — LLM is forced to call one of 5 routing functions
- 5 routing functions: `route_to_CAPTAIN`, `route_to_SCOUT`, etc.
- Returns `(agent_name, reason)` tuple
- If Groq unavailable or errors, falls back to Anthropic Haiku with same tool structure
- Rate limited: 25 req/min (Groq), 30 req/min (Anthropic)

---

## Tool System

**Files:** `tools/registry.py`, `tools/captain_tools.py`, `tools/scout_tools.py`,
`tools/tamara_tools.py`, `tools/helen_tools.py`, `tools/google_auth.py`

### Three-layer enforcement

```
call_tool(agent_name, tool_name, **kwargs)
    │
    ├── 1. Permission check: is tool_name in TOOL_REGISTRY[agent_name]?
    │       → if not: return {success: False, error: "not permitted"}
    │
    ├── 2. Implementation check: is tool_name in _TOOL_IMPLEMENTATIONS?
    │       → if not: return {success: False, error: "not implemented"}
    │
    ├── 3. Input validation via _validate_inputs():
    │       → required fields present and non-empty?
    │       → correct types (str/int/list)?
    │       → string length <= 100K chars?
    │
    └── 4. Execute fn(**kwargs) with try/except
```

### Tool registration at startup

`registry.initialize()` is called once in `clawdbot.py` before any agents run:

```python
registry.initialize(
    tavily_api_key=...,           # binds Tavily key into SCOUT tools
    google_credentials_path=...,  # Path to credentials.json
    google_token_path=...,        # Path to token.json (auto-created on first auth)
    db_path=...,                  # SQLite path (for HELEN's task_create, bible_check)
    user_timezone=...,            # e.g. "America/Detroit" (for calendar time boundaries)
)
```

If `credentials.json` doesn't exist, TAMARA and HELEN schemas still register
(so Claude knows what tools exist and can explain the setup requirement),
but calls will return a helpful "credentials not found" error.

### SCOUT → CAPTAIN chaining

SCOUT's identity instructs it to end responses with `CHAIN_TO_CAPTAIN: <task>`
when research implies code needs to be written.

```python
# In scout.py after tool_use_loop completes:
if "CHAIN_TO_CAPTAIN:" in response:
    # Parse next_action from the chain line
    # Dispatch ChainPayload via bus to CAPTAIN
    # CAPTAIN.handle() sees ChainPayload and responds with context

# In captain.py:
async def handle(self, msg):
    if isinstance(msg.payload, ChainPayload):
        task = f"Task: {msg.payload.next_action}\n\nContext from SCOUT:\n{msg.payload.work_product}"
        return await self.respond(task)
```

---

## BaseAgent — tool_use_loop

**File:** `agents/base.py`

All tool-using agents (CAPTAIN, SCOUT, TAMARA, HELEN) call `self.tool_use_loop()`:

```
1. Build messages list from history + user_text
2. Send to Claude with tools list and system prompt (cached)
3. Parse response:
   - text blocks → accumulated into final_text, printed if print_output=True
   - tool_use blocks → collected as tool_calls
4. If no tool_calls or stop_reason == "end_turn": break
5. For each tool_call:
   - print tool name + args (grayed out)
   - call tool_executor(tc.name, **tc.input) — synchronous
   - print result status + preview
   - build tool_result block
6. Append assistant response + tool_results to messages
7. Repeat from step 2 (max 10 iterations)
8. Log turn to SQLite memory
9. Return final_text
```

### Prompt caching

```python
def _cached_system(self, query=""):
    return [{
        "type": "text",
        "text": self.build_system_prompt(query),
        "cache_control": {"type": "ephemeral"},  # Anthropic caches for 5 minutes
    }]
```

System prompts are cached by Anthropic for up to 5 minutes. Repeated calls with the
same system prompt are ~50% cheaper. Requires `betas=["prompt-caching-2024-07-31"]`.

---

## Rate Limiting

**File:** `utils/rate_limiter.py`

Sliding window — tracks timestamps of last N requests, sleeps if window is full.

```python
anthropic_limiter = RateLimiter(max_calls=30, window_seconds=60)  # ~50/min allowed, 30 to be safe
groq_limiter      = RateLimiter(max_calls=25, window_seconds=60)  # 30/min on free tier
tavily_limiter    = RateLimiter(max_calls=10, window_seconds=60)  # 200 searches/month free
```

Every API call must `await limiter.acquire()` before proceeding.
Applied in: `base.py` (all Anthropic calls), `routing/tier2.py` (Groq + Anthropic routing).

---

## Scheduler

**File:** `scheduler/jobs.py`

APScheduler v3.11.0. MUST use `AsyncIOExecutor` — the default `ThreadPoolExecutor`
cannot run async job functions and will silently fail or deadlock.

```python
scheduler = AsyncIOScheduler(
    executors={"default": AsyncIOExecutor()}
)
```

Three jobs:
- `memory_consolidation` — cron, 3am, no agents needed (only MemoryStore)
- `morning_briefing` — cron, 7am, calls `helen_agent.morning_briefing()`
- `bible_reminder` — cron, 6am, checks bible_log, nudges if incomplete

`build_scheduler(config, memory)` creates the scheduler + nightly job.
`wire_helen_jobs(scheduler, helen, config)` adds the 6am/7am jobs — must be called
AFTER agents are initialized.

---

## Google OAuth

**File:** `tools/google_auth.py`

OAuth2 flow using `google-auth-oauthlib`. Handles:
- First-time browser authorization (opens a local server on a random port)
- Token refresh (automatic via `creds.refresh(Request())`)
- Token persistence to `token.json`

Scopes requested:
- `https://www.googleapis.com/auth/gmail.modify` — read + send + create drafts
- `https://www.googleapis.com/auth/calendar` — read + create events

The `google-api-python-client` library is entirely synchronous. In Phase 4 it's called
directly from inside `tool_use_loop`'s synchronous `tool_executor`. This blocks the
asyncio event loop during the network call — acceptable for a single-user CLI.

Phase 5 note: if these tools are ever called from a truly concurrent async context
(e.g. websocket handler), wrap with `asyncio.to_thread(tool_fn, **kwargs)`.

---

## TAMARA Approval Gate

TAMARA's `gmail_send` enforces the "never send without approval" rule at the tool level,
not just at the identity level. The tool itself:

1. Formats and prints the email (To, Subject, Body)
2. Calls `input("  Send this email? (y/n): ")`
3. Only calls the Gmail API if the user types "y"
4. Returns `{success: False, sent: False, error: "cancelled"}` if denied

This means even if Claude somehow bypasses TAMARA's system prompt instruction,
the tool physically cannot send without the user pressing "y".

---

## SQLite Schema

```sql
sessions    (id TEXT PK, started_at, ended_at, turn_count)
messages    (id AUTOINCREMENT, session_id FK, turn, role, agent, content, timestamp)
memories    (id AUTOINCREMENT, chroma_id UNIQUE, agent_id, memory_type, content,
             importance REAL, tags TEXT, created_at, last_accessed, access_count)
tasks       (id AUTOINCREMENT, title, agent, status DEFAULT 'pending', context,
             created_at, updated_at)
decisions   (id AUTOINCREMENT, context, decision, reasoning, outcome, agent, created_at)
bible_log   (id AUTOINCREMENT, log_date TEXT UNIQUE, completed INTEGER, passage,
             logged_at)
schema_version (version INTEGER PK)  -- currently 2
```

Thread safety: all writes go through `_exec(sql, params)`, all reads through
`_query(sql, params)`, both wrapped in `threading.RLock`. This prevents corruption
from scheduler jobs running concurrently with user turns.

---

## Adding a New Tool

1. Write the function in the appropriate `tools/` file
2. Add its Anthropic schema to the `*_TOOL_SCHEMAS` list
3. Add it to the `make_*_tool_map()` dictionary
4. Add its name to `TOOL_REGISTRY["AGENT_NAME"]` in `registry.py`
5. Restart BOWEN — registry.initialize() picks it up automatically

Tools must:
- Return a `dict` with at minimum `{"success": bool}`
- Be synchronous (they run inside the synchronous `tool_executor` callback)
- Handle all exceptions internally and return `{"success": False, "error": str}`

---

## What's Next (Phase 5 — Voice)

Phase 5 adds real-time voice conversation. Key components:
- **LiveKit** — real-time audio room (credentials already in .env)
- **Groq Whisper STT** — `whisper-large-v3-turbo`, ~$0.001/min, fastest available
- **ElevenLabs WebSocket TTS** — each agent has a distinct voice ID in .env
- **Silero VAD** — voice activity detection to know when user stops speaking
- **Half-duplex echo gate** — `is_speaking` boolean prevents agent from responding to its own TTS

Critical voice notes:
- NEVER use faster-whisper on CPU — 18+ seconds per utterance, unusable
- ElevenLabs WebSocket auto-closes after 20s idle — send `' '` keep-alive every 15s
- Use Groq Whisper (cloud) or Deepgram if no GPU for local STT
