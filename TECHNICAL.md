# BOWEN — Technical Architecture Document

**Version:** 5.0  
**Last Updated:** 2026-04-10  
**Codebase:** `/Volumes/S1/bowen/`  
**Entry Point:** `main.py`  
**Primary Author:** Praise Oyimi

---

## Table of Contents

1. [What BOWEN Is](#1-what-bowen-is)
2. [System Overview](#2-system-overview)
3. [Directory Structure](#3-directory-structure)
4. [Startup Sequence](#4-startup-sequence)
5. [Multi-User Architecture](#5-multi-user-architecture)
6. [Agent System](#6-agent-system)
7. [Routing Pipeline](#7-routing-pipeline)
8. [Memory Architecture](#8-memory-architecture)
9. [Tool System](#9-tool-system)
10. [Message Bus (Inter-Agent Communication)](#10-message-bus-inter-agent-communication)
11. [API Layer](#11-api-layer)
12. [WebSocket Gateway](#12-websocket-gateway)
13. [Voice Pipeline](#13-voice-pipeline)
14. [Scheduler](#14-scheduler)
15. [Services Layer](#15-services-layer)
16. [Security Model](#16-security-model)
17. [Data Model](#17-data-model)
18. [Configuration Reference](#18-configuration-reference)
19. [Cost Model](#19-cost-model)
20. [Scaling Path](#20-scaling-path)
21. [Key Architectural Decisions](#21-key-architectural-decisions)

---

## 1. What BOWEN Is

BOWEN is a multi-agent AI operating system. It is not a chatbot. It is a persistent, context-aware system of six specialized agents that share memory, communicate with each other, and grow smarter over time.

**Core properties:**

- **Persistent memory.** Every interaction is remembered. Memories are semantically indexed and retrieved. The system knows the user better after 1,000 conversations than after 1.
- **Specialized agents.** Each agent has a defined scope, a tool whitelist, and a model selection appropriate to its workload. No agent does everything.
- **Multi-user.** Each user gets isolated memory. All users share the same agent code, tools, and shared knowledge. Improvements to the codebase benefit everyone.
- **Fully async.** The entire backend is non-blocking. No thread pools for agent work — pure asyncio with `asyncio.to_thread()` only at the sync boundary (SQLite, ChromaDB, tool execution).
- **WebSocket streaming.** The client receives responses as a stream of typed JSON events, not a single payload. Tool calls, results, and text chunks are all visible in real time.

**Current scale:** Single-server deployment. Designed for small teams (1–50 users). Scaling path to multi-server is documented in Section 20.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  tui.py (Textual TUI)  ·  Future: Tauri desktop, mobile app     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ WebSocket ws://localhost:8000/ws/chat?key=...
                          │ REST     http://localhost:8000/api/*
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FASTAPI SERVER (main.py)                   │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  WS Gateway  │  │  REST API    │  │  Admin API           │   │
│  │  gateway.py  │  │  memory.py   │  │  admin.py            │   │
│  │              │  │  topics.py   │  │                      │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────┘   │
│         │                                                         │
│         │ per-connection                                          │
│         ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    AGENT LAYER                            │    │
│  │  BOWEN · CAPTAIN · DEVOPS · SCOUT · TAMARA · HELEN       │    │
│  │  (fresh instances per WebSocket connection)               │    │
│  └───────────────────────┬──────────────────────────────────┘    │
│                          │                                        │
│         ┌────────────────┼─────────────────┐                     │
│         ▼                ▼                 ▼                      │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐          │
│  │  Tool Layer │  │ Memory     │  │  Message Bus     │          │
│  │  registry   │  │ Store      │  │  (per-connection) │          │
│  │  per-user   │  │ per-user   │  │  PriorityQueue   │          │
│  └─────────────┘  └────────────┘  └──────────────────┘          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                   SHARED STATE (app.state)               │     │
│  │  config · user_manager · multi_store · scheduler         │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

**Per-connection isolation:** Every WebSocket connection creates its own agent instances, message bus, and user registry. There is no shared mutable state between connections. The only shared state is the app-level singletons: config, user_manager, multi_store, and the global tool registry (for stateless tools like web search).

---

## 3. Directory Structure

```
bowen/
│
├── main.py                  # FastAPI app + lifespan (startup/shutdown)
├── config.py                # All configuration, sourced from .env
├── tui.py                   # Textual terminal UI (WebSocket client)
│
├── agents/                  # Six agent implementations
│   ├── constants.py         # AgentName class — single source of truth for agent names
│   ├── base.py              # BaseAgent abstract class (streaming, tool-use, prompt assembly)
│   ├── bowen.py             # BOWEN: orchestrator + routing decisions
│   ├── captain.py           # CAPTAIN: code, builds, file ops, shell
│   ├── devops.py            # DEVOPS: code review, security audit, static analysis
│   ├── scout.py             # SCOUT: web research, document parsing
│   ├── tamara.py            # TAMARA: Gmail, drafts, outbound communications
│   ├── helen.py             # HELEN: calendar, Bible tracking, morning briefing
│   └── planner.py           # Pre-task planning layer (clarifies vague requests)
│
├── api/                     # FastAPI routers
│   ├── deps.py              # Auth dependency: get_user_memory()
│   ├── gateway.py           # WebSocket endpoint (main chat interface)
│   ├── health.py            # GET /api/health
│   ├── admin.py             # Admin-only: user management, shared knowledge
│   ├── memory.py            # GET /api/memory/* (authenticated)
│   └── topics.py            # GET/POST /api/topics/* (authenticated)
│
├── memory/                  # Persistent memory system
│   ├── store.py             # MemoryStore: SQLite + ChromaDB per user
│   ├── multi_store.py       # MultiUserStore: factory + cache for MemoryStore instances
│   ├── users.py             # UserManager: API key auth, account registry
│   ├── pipeline.py          # SleepTimeAgent: post-session memory extraction
│   └── consolidator.py      # MemoryConsolidator: nightly decay/merge/prune
│
├── bus/                     # Inter-agent communication
│   ├── message_bus.py       # Per-connection MessageBus (asyncio.PriorityQueue)
│   └── schema.py            # 13 typed Pydantic payload types
│
├── tools/                   # Tool implementations + registry
│   ├── registry.py          # Permission enforcement + UserRegistry
│   ├── captain_tools.py     # execute_code, read_file, write_file, run_shell, web_fetch
│   ├── scout_tools.py       # web_search (Brave), web_fetch, document_parse
│   ├── tamara_tools.py      # gmail_read, gmail_send, gmail_draft
│   ├── helen_tools.py       # calendar_list, calendar_create, task_create, bible_check
│   ├── bowen_tools.py       # memory_search, task_create, task_list
│   ├── google_auth.py       # OAuth 2.0 for Google APIs
│   └── qa.py                # Quality verification for CAPTAIN outputs
│
├── routing/                 # Two-tier message routing
│   ├── tier1.py             # Regex router (<1ms, $0)
│   └── tier2.py             # Groq LLaMA 3.1 8B router (~100ms, $0.0002)
│
├── scheduler/
│   └── jobs.py              # APScheduler: nightly consolidation + HELEN daily jobs
│
├── voice/                   # Voice pipeline (Phase 5)
│   ├── pipeline.py          # Coordinates wake → STT → agent → TTS
│   ├── tts.py               # Kokoro ONNX (local, zero cost)
│   ├── stt.py               # Groq Whisper (cloud, ~$0.0003/min)
│   └── wake.py              # openWakeWord ONNX (local, <5% CPU)
│
├── services/
│   ├── keep_alive.py        # Background health pings (Anthropic, ChromaDB, Groq)
│   └── monitor.py           # Response quality monitoring (banned phrases, length)
│
├── utils/
│   ├── retry.py             # Async retry with exponential backoff
│   └── rate_limiter.py      # Token bucket rate limiters (per API)
│
├── core/
│   └── logging.py           # Structured JSON + text logging, rotating file handler
│
└── memory/
    ├── shared_knowledge.md  # Git-tracked. Loaded into ALL users' agent prompts.
    └── users/               # Per-user memory directories
        └── {user_id}/
            ├── bowen.db     # SQLite: conversations, messages, tasks, memories, etc.
            ├── chroma/      # ChromaDB: semantic vector store
            └── profile.md   # Always-on core memory injected into every prompt
```

---

## 4. Startup Sequence

`main.py` uses FastAPI's `lifespan` context manager for startup and shutdown. The sequence is ordered — each step depends on the one before it.

```
1. Config validated
   └── Config() reads from .env
   └── ANTHROPIC_API_KEY checked — hard fail if missing

2. UserManager initialized
   └── Opens memory/users.db (aiosqlite)
   └── Creates users table if not exists (idempotent)

3. Admin user bootstrapped
   └── create_admin("praise", "Praise Oyimi", ADMIN_API_KEY)
   └── Idempotent — no-op if already exists

4. MultiUserStore initialized
   └── Factory for per-user MemoryStore instances
   └── In-process cache (user_id → MemoryStore)

5. Admin memory pre-warmed
   └── get_or_create("usr_admin", "praise", "Praise Oyimi")
   └── Runs legacy data migration on first start (bowen.db → users/usr_admin/)
   └── Initializes ChromaDB (SentenceTransformer load — ~60-90s cold start)

6. Global tool registry initialized
   └── CAPTAIN base tools registered (execute_code, read_file, etc.)
   └── SCOUT tools registered (web_search with Brave key)
   └── Admin user's HELEN, TAMARA, BOWEN tools registered
   └── DEVOPS schemas set (subset of CAPTAIN — no write_file)

7. Scheduler agents created (admin memory only)
   └── HelenAgent(config, admin_memory, bus)

8. APScheduler started
   └── 3am: nightly memory consolidation
   └── 6am: Bible reading reminder
   └── 7am: morning briefing

9. KeepAlive service started
   └── Pings Anthropic, ChromaDB, Groq every 60s

10. FastAPI routers mounted
    └── /api/health, /ws/chat, /api/memory, /api/topics, /api/admin

Server ready.
```

**Shutdown (reverse order):**
```
KeepAlive stopped → Scheduler stopped → MultiUserStore.close_all() → UserManager.close()
```

---

## 5. Multi-User Architecture

### Design Principles

1. **Isolated data, shared code.** Every user gets their own SQLite database, ChromaDB collection, and profile.md. Agent code, tool implementations, and shared knowledge live in git — one improvement benefits all users.

2. **Fresh instances per connection.** Every WebSocket connection creates new agent instances bound to that user's memory. No shared mutable state between users.

3. **API key authentication.** Keys are prefixed `bwn_`, 40 random alphanumeric characters. Only the SHA-256 hash is stored. The plaintext key is shown once at creation and is unrecoverable.

4. **Shared brain via git.** `memory/shared_knowledge.md` is git-tracked and loaded into every agent's system prompt for every user. When Praise adds a global insight via the admin endpoint, all users' agents immediately know it.

### User Lifecycle

```
Admin calls POST /api/admin/users
     ↓
UserManager.create_user() generates bwn_<40chars>
Returns plaintext key (once only) + user_id (usr_<8hex>)
     ↓
User stores key, connects via: ws://server/ws/chat?key=bwn_...
     ↓
gateway.py: user_manager.authenticate(key) → hashes key, looks up user
     ↓
multi_store.get_or_create(user_id) → initializes per-user MemoryStore
     ↓
UserRegistry created with user's db_path and memory_store
     ↓
6 fresh agents instantiated, bound to user's memory + registry
     ↓
auth_ok message sent to client
     ↓
Conversation begins — all data written to user's isolated store
```

### File Layout Per User

```
memory/users/
└── usr_admin/           # Praise Oyimi (migrated from legacy memory/)
│   ├── bowen.db
│   ├── chroma/
│   └── profile.md
└── usr_a1b2c3d4/        # Another user
    ├── bowen.db
    ├── chroma/
    └── profile.md
```

### Shared Knowledge

`memory/shared_knowledge.md` is a markdown file in the git repository. It is:
- Loaded into every agent's system prompt via `_load_shared_knowledge()` in `base.py`
- Updated via `POST /api/admin/knowledge` (admin only)
- Committed to git to make entries permanent and version-controlled

This is how BOWEN's collective knowledge grows as it's used by more people.

---

## 6. Agent System

### The Six Agents

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| **BOWEN** | Haiku | Orchestrator. Routes messages, synthesizes results, surfaces decisions. | memory_search, task_create, task_list |
| **CAPTAIN** | Sonnet | Code, builds, file ops, shell commands. QA verification + retry loop. | execute_code, read_file, write_file, run_shell, web_fetch, dispatch_* |
| **DEVOPS** | Sonnet | Code review, security audit, static analysis, pre-deploy checks. | execute_code, read_file, run_shell, web_fetch (read-only subset) |
| **SCOUT** | Sonnet | Web research, competitive analysis, document parsing. Chains to CAPTAIN. | web_search, web_fetch, document_parse, structured_extract |
| **TAMARA** | Sonnet | Gmail read/draft/send. Writes in Praise's voice. Approval gate on all sends. | gmail_read, gmail_send, gmail_draft |
| **HELEN** | Haiku | Calendar, tasks, Bible tracking, morning briefing. | calendar_list, calendar_create, task_create, bible_check, notify, daily_briefing |

**Model selection rationale:**
- Sonnet for complex work (code, research, review, email) — depth required
- Haiku for fast/cheap work (routing, briefings, short tasks) — speed over depth

### BaseAgent

All agents extend `BaseAgent` (`agents/base.py`). It provides:

**System prompt assembly (`build_system_prompt`):**
```
1. base_identity          ← agent's core character and role (defined per-agent)
2. topic_instructions     ← per-topic context injected if active topic has instructions
3. shared_knowledge       ← memory/shared_knowledge.md (same for all users)
4. user_profile           ← user's profile.md (personal to each user)
5. retrieved_memories     ← semantic search results relevant to current query
```

All five sections are assembled on every request. Sections 3-5 are populated asynchronously (ChromaDB search and topic lookup run in parallel via `asyncio.gather`).

**Prompt caching:** The assembled prompt is cached in an in-process LRU cache (32 entries, 2-minute TTL) keyed by `(agent_name, session_id, query_hash)`. This reduces ChromaDB queries and Anthropic token costs on repeated calls within a session.

**Anthropic prompt caching:** The full system prompt is sent with `cache_control: {"type": "ephemeral"}`. Anthropic caches the prompt on their side for ~5 minutes. On cache hit, the cached tokens are billed at 10% of normal input cost. This produces roughly 50% cost reduction on multi-turn conversations.

**Tool-use loop (`tool_use_loop`):**
```
1. Build messages array (history + current user message)
2. Call Anthropic API with tools list
3. For each tool_call in response:
   a. Emit tool_call event to client (real-time visibility)
   b. Execute tool via asyncio.to_thread (off event loop)
   c. Emit tool_result event to client
   d. Append result to messages
4. Loop until stop_reason == "end_turn" or max_iterations (10) reached
5. Log full conversation to SQLite
```

**Streaming response (`stream_response`):**
Used by agents without tools (or as fallback). Streams text chunks to client as they arrive from the Anthropic streaming API.

### Agent Identity

Each agent's `base_identity` property is a multi-paragraph system prompt that defines:
- Role and scope
- Communication style and voice
- Tool usage instructions (when and how to use each tool)
- Output format requirements
- What to never do

These are not generic instructions — they are the behavioral specification for each agent. Editing them changes how the agent behaves for all users immediately.

---

## 7. Routing Pipeline

When a message arrives at the gateway, it goes through two routing tiers before reaching an agent:

```
User message
     ↓
Tier 1: Regex patterns (<1ms, $0)
     ├── Match → agent name returned immediately
     └── No match → Tier 2
          ↓
     Tier 2: Groq LLaMA 3.1 8B (~100ms, ~$0.0002)
          ├── Groq available → tool-forced call → agent name
          └── Groq unavailable → Anthropic Haiku fallback (~400ms, ~$0.001)
               ↓
          Gateway: optional planning layer (CAPTAIN/SCOUT only)
               ↓
          Agent.respond()
```

**Tier 1 — Regex (`routing/tier1.py`):**  
~30 patterns covering explicit commands (`/code`, `/review`), direct mentions (`@captain`, `hey BOWEN`), and strong keyword signals (`calendar`, `email`, `code review`). Covers ~30% of real inputs at zero cost.

**Tier 2 — Groq LLaMA (`routing/tier2.py`):**  
Six routing functions modeled as tools in OpenAI function-calling format. `tool_choice="required"` forces the model to call exactly one. No free-text parsing needed — result is always a clean agent name. Falls back to Anthropic Haiku if Groq is unavailable.

**Planning layer (`agents/planner.py`):**  
Applies only to CAPTAIN and SCOUT requests. If the input is classified as "vague", the Planner generates clarifying questions, sends them to the client, waits up to 180 seconds for answers, and builds an enriched prompt. This improves output quality on underspecified requests.

**Override:** The client can force a specific agent by sending `target_agent` in the message payload. The routing pipeline is skipped entirely. Used by the TUI's Tab key (cycle active agent).

---

## 8. Memory Architecture

Memory is the core differentiator. Three layers work together:

### Layer 1 — User Profile (`profile.md`)

A markdown file loaded synchronously on every request. Always present in every agent's system prompt. Contains:
- User identity, role, communication style
- Active projects and priorities
- Non-negotiables and preferences
- Key people and relationships

Updated by the sleep pipeline after sessions with high-importance new information.

**Max size:** 2,000 tokens (enforced by profile update prompt).

### Layer 2 — ChromaDB (Semantic Vector Store)

**Model:** `all-MiniLM-L6-v2` (384 dimensions, SentenceTransformer). **Never change this model** — existing embeddings are incompatible with a different model.

**Collection:** `bowen_memories` per user, stored at `memory/users/{user_id}/chroma/`.

**Retrieval:** On every request, `memory.search(query, top_k=8, min_relevance=0.7)` runs cosine similarity search against the user's memories. The top results are injected into the system prompt as `## Relevant Memory`.

**Write path:**
1. Direct: agents can call `memory_search` tool (BOWEN) to read, but writing happens via the sleep pipeline
2. Sleep pipeline: after session ends, Haiku reads the transcript and writes structured memories
3. Consolidator: nightly job merges near-duplicates and applies decay

### Layer 3 — SQLite (`bowen.db`)

Structured storage for everything that needs querying. Tables:

| Table | Purpose |
|-------|---------|
| `topics` | Organizational containers (like folders). Each has optional `instructions` injected into agent prompts. |
| `conversations` | Chat sessions. Each belongs to a topic. |
| `messages` | Every message in every conversation. Role, agent, content, timestamp. |
| `memories` | Metadata for ChromaDB entries. Tracks importance, access time, agent_id. |
| `tasks` | Task tracker for all agents. Status: pending/in_progress/done/cancelled. |
| `decisions` | Logged decisions with reasoning. For audit trail. |
| `artifacts` | Files or code blocks produced by CAPTAIN. Versioned. |
| `bible_log` | Daily Bible reading completions. Date, passage, completed flag. |
| `dispatches` | CAPTAIN task dispatch tracking. |
| `schema_version` | Migration version tracking. |

**Access pattern:** All SQLite access from the async event loop goes through `aiosqlite` (async wrapper). Synchronous tool calls (captain_tools, helen_tools) run inside `asyncio.to_thread()` and use the standard `sqlite3` library directly — safe because they execute off the event loop.

### Sleep Pipeline (`memory/pipeline.py`)

Runs after every session ends (triggered by WebSocket disconnect in `gateway.py`).

```
Session ends
     ↓
gateway.py: asyncio.create_task(run_sleep_pipeline(...))
     ↓
SleepTimeAgent.run(session_id)
     ↓
Fetch full session transcript from SQLite
     ↓
Haiku: "Extract memories from this conversation" → JSON array
     ↓
For each memory: memory.write_memory() → ChromaDB + SQLite metadata
     ↓
High-importance memories (>= 0.7): refresh profile.md via Haiku
```

Runs asynchronously after disconnect — does not block the client.

### Nightly Consolidation (`memory/consolidator.py`)

Runs at 3am via APScheduler.

```
1. Temporal decay
   └── For each memory: importance *= 0.95^(days_unaccessed / 30)
   └── Importance change > 0.01 → update ChromaDB metadata

2. Prune
   └── importance < 0.05 AND days_unaccessed > 90 → delete from ChromaDB + SQLite

3. Merge near-duplicates
   └── Query each memory against collection
   └── cosine similarity > 0.95 → Haiku merges two sentences into one
   └── Delete both, write merged with averaged importance
```

---

## 9. Tool System

### Permission Model

Every tool call goes through three gates before execution:

```
1. TOOL_REGISTRY permission check
   └── Is this tool in the allowed list for this agent?
   └── If not → {"success": false, "error": "not permitted"}

2. Implementation check
   └── Is there a registered function for this tool name?
   └── If not → {"success": false, "error": "not implemented"}

3. Input validation
   └── Required fields present and non-empty?
   └── Field types match schema?
   └── String length under 100K chars?
   └── If not → {"success": false, "error": "validation error"}

4. Execute fn(**kwargs)
   └── Returns dict with "success" key
   └── TypeError caught separately (wrong argument types)
   └── All other exceptions caught, logged, returned as error dict
```

### Tool Registry

`tools/registry.py` manages two registries:

**Global registry:** Initialized once at startup. Holds stateless tools (SCOUT web search, CAPTAIN base tools, DEVOPS schemas). Tools that don't depend on a specific user's data.

**UserRegistry:** Created per WebSocket connection. Holds user-specific tools (BOWEN memory search, CAPTAIN dispatch tracking, HELEN calendar, TAMARA Gmail) — all bound to the user's database path and credentials. Falls back to global registry for stateless tools.

**Shared factory (`_build_user_tool_maps`):** Both the global registry and UserRegistry call this same function to build user-scoped tools. No duplicated logic.

### CAPTAIN Tool Sandboxing

File operations (`read_file`, `write_file`) check the resolved path against a blocklist before executing:

```python
BLOCKED_ROOTS = [
    Path("/System"), Path("/etc"), Path("/Library"),
    Path("/usr"), Path("/sbin"), Path("/bin"), Path("/private/etc"),
]
```

Any path resolving into these trees is rejected before the filesystem is touched. `run_shell` has a separate command blocklist for destructive commands (`rm -rf /`, `mkfs`, `shutdown`, etc.).

`execute_code` runs arbitrary Python in a subprocess with a 30-second timeout. This is a trusted tool — it should only be exposed to users who are authorized to run code on the server.

### Available Tools Per Agent

**BOWEN:** `memory_search`, `task_create`, `task_list`  
**CAPTAIN:** `execute_code`, `read_file`, `write_file`, `run_shell`, `web_fetch`, `dispatch_create`, `dispatch_update`, `dispatch_list`  
**DEVOPS:** `execute_code`, `read_file`, `run_shell`, `web_fetch` (no write_file, no dispatch — read-only)  
**SCOUT:** `web_search`, `web_fetch`, `document_parse`, `structured_extract`  
**TAMARA:** `gmail_read`, `gmail_send`, `gmail_draft`  
**HELEN:** `calendar_list`, `calendar_create`, `task_create`, `bible_check`, `notify`, `daily_briefing`  

---

## 10. Message Bus (Inter-Agent Communication)

### Purpose

Agents can dispatch work to other agents without waiting for a synchronous response. The canonical use case: SCOUT completes research and chains the findings to CAPTAIN to build something.

### Architecture

```
MessageBus (per WebSocket connection)
├── _queues: {agent_name: asyncio.PriorityQueue}
└── _message_log: list[AgentMessage]   (in-memory audit trail)

AgentMessage:
├── sender: str
├── recipient: str (or "broadcast")
├── msg_type: str ("request", "chain", "approval", etc.)
├── payload: one of 13 typed Pydantic classes
├── priority: int (1=low, 5=urgent)
├── requires_approval: bool
└── correlation_id: str (UUID for tracing)
```

### Message Flow

```
Agent A calls: await self.dispatch_to("CAPTAIN", payload, msg_type="chain")
     ↓
MessageBus.send(msg) → puts msg in CAPTAIN's PriorityQueue
     ↓
Agent A finishes its response to client (send "done" event)
     ↓
gateway.py: await _drain_bus(agents, bus, send)
     ↓
_drain_bus pulls all pending messages:
  └── For each msg:
      ├── requires_approval? → send "approval_required" event to client, skip
      └── else → send "routing" event, call target.handle(msg, send=send)
          └── _drain_bus called recursively (depth limit: 10)
```

### Payload Types

13 typed payload classes in `bus/schema.py`:

- `TextPayload` — general text routing
- `CodeRequestPayload` / `CodeResponsePayload` — CAPTAIN work
- `ResearchRequestPayload` / `ResearchResponsePayload` — SCOUT work
- `EmailReadPayload` / `EmailSendPayload` / `EmailSummaryPayload` — TAMARA work
- `CalendarRequestPayload` / `CalendarResponsePayload` — HELEN work
- `BriefingPayload` / `BibleCheckPayload` — HELEN scheduled work
- `ChainPayload` — SCOUT → CAPTAIN chaining (research → build)
- `ApprovalRequestPayload` — any agent → user approval gate
- `ErrorPayload` — error propagation

---

## 11. API Layer

### Endpoint Map

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/health` | None | Liveness + readiness check |
| WS | `/ws/chat` | API key (query param) | Main chat interface |
| GET | `/api/memory/profile` | X-Api-Key | User's profile.md |
| GET | `/api/memory/search` | X-Api-Key | Semantic memory search |
| GET | `/api/memory/stats` | X-Api-Key | Memory + task counts |
| GET | `/api/topics` | X-Api-Key | List user's topics |
| POST | `/api/topics` | X-Api-Key | Create topic |
| GET | `/api/topics/{id}` | X-Api-Key | Get topic details |
| PATCH | `/api/topics/{id}/instructions` | X-Api-Key | Update topic instructions |
| GET | `/api/topics/{id}/conversations` | X-Api-Key | List conversations |
| POST | `/api/topics/{id}/conversations` | X-Api-Key | Create conversation |
| GET | `/api/conversations/{id}/messages` | X-Api-Key | Paginated messages |
| POST | `/api/admin/users` | X-Admin-Key | Create user |
| GET | `/api/admin/users` | X-Admin-Key | List all users |
| POST | `/api/admin/users/{id}/regen` | X-Admin-Key | Regenerate user key |
| GET | `/api/admin/users/active` | X-Admin-Key | Currently connected users |
| POST | `/api/admin/knowledge` | X-Admin-Key | Add to shared_knowledge.md |
| GET | `/api/admin/knowledge` | X-Admin-Key | Read shared_knowledge.md |

### Authentication

**WebSocket:** API key in query param — `?key=bwn_...`  
**REST user endpoints:** `X-Api-Key: bwn_...` header, resolved via `api/deps.py:get_user_memory()`  
**Admin endpoints:** `X-Admin-Key: bwn_...` header, must match `config.ADMIN_API_KEY`

**Auth flow (`api/deps.py`):**
```
X-Api-Key header present?
  └── No → 401 "X-Api-Key header required"
  └── Yes → user_manager.authenticate(key) → hash key, look up user
       └── Not found → 401 "Invalid API key"
       └── Found → multi_store.get_cached(user_id)
            └── Cached → return MemoryStore immediately
            └── Not cached → multi_store.get_or_create() → initialize → return
```

### Health Endpoint

`GET /api/health` returns:
```json
{
  "status": "ok",
  "agents": ["BOWEN", "CAPTAIN", "DEVOPS", "SCOUT", "TAMARA", "HELEN"],
  "memory_count": 142,
  "services": {
    "anthropic": true,
    "groq": true,
    "tavily": true,
    "tts_kokoro": true,
    "stt_groq": true,
    "supabase": false,
    "google": true
  },
  "probes": {
    "anthropic": {"healthy": true, "latency_ms": 234},
    "chromadb": {"healthy": true},
    "groq": {"healthy": true, "latency_ms": 89}
  }
}
```

Used by start scripts to wait for server readiness before launching the TUI.

---

## 12. WebSocket Gateway

### Connection Lifecycle

```
Client connects: ws://server/ws/chat?key=bwn_...
     ↓
websocket.accept()
     ↓
Authenticate (user_manager.authenticate)
     └── Fail → send error JSON, close(code=4001)
     └── Pass → continue
     ↓
Initialize user memory (multi_store.get_or_create)
     ↓
Create UserRegistry (bound to user's db_path + config)
     ↓
Create 6 fresh agents + MessageBus (_make_agents)
     ↓
Send: {"type": "auth_ok", "user": "Praise Oyimi", "user_id": "usr_admin"}
     ↓
Message loop (while True):
     ├── receive_text() → parse JSON
     ├── "ping" → send "pong"
     └── "message" → process (see below)
     ↓
WebSocketDisconnect:
     ├── memory.end_conversation(active_conversation_id)
     └── asyncio.create_task(run_sleep_pipeline(...))
```

### Message Processing

```
User sends: {"type": "message", "content": "...", "topic_id": "...", "conversation_id": "..."}
     ↓
Conversation ID:
  └── provided → use existing conversation
  └── missing → create new conversation, send "conversation_created" event
     ↓
agent.set_session(conversation_id, topic_id) for all 6 agents
     ↓
Routing:
  └── target_agent in payload → use it directly
  └── else → agents[BOWEN].route(content) via tier1 + tier2
     ↓
Send: {"type": "routing", "from": "user", "to": "CAPTAIN"}
     ↓
Planning (CAPTAIN/SCOUT only):
  └── planner.classify(content) == "vague"?
       └── Yes → send questions, wait for answers, build enriched prompt
       └── No → use original content
     ↓
agent[target].respond(content, send=monitored_send)
  └── Streams: {"type": "chunk", "agent": "CAPTAIN", "content": "..."}
  └── Streams: {"type": "tool_call", "agent": "CAPTAIN", "tool": "execute_code", ...}
  └── Streams: {"type": "tool_result", "agent": "CAPTAIN", "tool": "execute_code", ...}
     ↓
_drain_bus(agents, bus, send)
  └── Handles any inter-agent messages dispatched during the response
     ↓
Send: {"type": "done", "agent": "CAPTAIN"}
```

### Client Message Protocol

**Client → Server:**
```json
{"type": "message", "content": "...", "topic_id": "...", "conversation_id": "...", "target_agent": "..."}
{"type": "ping"}
{"type": "planning_answer", "question": "...", "answer": "..."}
```

**Server → Client:**
```json
{"type": "auth_ok",         "user": "...", "user_id": "..."}
{"type": "conversation_created", "conversation_id": "...", "topic_id": "..."}
{"type": "routing",         "from": "user", "to": "CAPTAIN"}
{"type": "chunk",           "agent": "CAPTAIN", "content": "..."}
{"type": "tool_call",       "agent": "CAPTAIN", "tool": "execute_code", "args": {...}}
{"type": "tool_result",     "agent": "CAPTAIN", "tool": "execute_code", "status": "OK", "preview": "..."}
{"type": "planning_start",  "agent": "BOWEN"}
{"type": "planning_question", "question": "..."}
{"type": "planning_end"}
{"type": "approval_required", "from": "TAMARA", "action": "gmail_send", "description": "..."}
{"type": "done",            "agent": "CAPTAIN"}
{"type": "error",           "message": "..."}
{"type": "pong"}
```

---

## 13. Voice Pipeline

**Status:** Implemented and wired into `tui.py`. Activate with `Ctrl+V`.

### Stack

| Component | Technology | Cost | Notes |
|-----------|-----------|------|-------|
| Wake Word | openWakeWord ONNX | $0 | `hey_jarvis` model as "hey BOWEN" proxy. <5% CPU at idle. |
| STT | Groq Whisper (`whisper-large-v3-turbo`) | ~$0.0003/min | 200ms latency. 98% cheaper than OpenAI Whisper. |
| TTS | Kokoro ONNX (`am_adam` voice) | $0 | Fully local. Apache 2.0. Runs offline. |

### Flow

```
Idle: openWakeWord listening on microphone
     ↓
Wake word detected → play acknowledgment tone
     ↓
Record until silence detected
     ↓
Audio → Groq Whisper → transcript text
     ↓
pipeline._ws_send(transcript) → WebSocket → backend
     ↓
Backend processes as normal text message, streams response
     ↓
On "done" event: TUI accumulates all chunks → Kokoro TTS → speaker
```

### Model Files

Kokoro requires two files that are not in git (too large):
```
voice/kokoro/kokoro-v0_19.onnx   (~300MB)
voice/kokoro/voices.bin          (~20MB)
```

Download separately. `config.status()` checks for these files and reports `tts_kokoro: true/false`.

---

## 14. Scheduler

APScheduler with `AsyncIOExecutor` (required — default ThreadPoolExecutor blocks async jobs).

**Three jobs:**

| Job | Time | What It Does |
|-----|------|-------------|
| `nightly_consolidation` | 3:00am | MemoryConsolidator.run() for admin memory |
| `bible_reminder` | 6:00am | Checks bible_log — sends notify() if not done |
| `morning_briefing` | 7:00am | HELEN.morning_briefing() → daily briefing to stdout |

**Limitation:** Currently runs only against admin memory (Praise's). Per-user scheduling (each user gets their briefing at their configured time) is a future enhancement.

**Configuration:** Times are set in `config.py`:
```python
BRIEFING_HOUR: int = 7
BIBLE_CHECK_HOUR: int = 6
MEMORY_CONSOLIDATE_HOUR: int = 3
```

---

## 15. Services Layer

### KeepAlive (`services/keep_alive.py`)

Background loop that pings critical dependencies every 60 seconds:
- **Anthropic:** Lightweight test message to verify API key is valid and service is reachable
- **ChromaDB:** Query the admin user's collection to verify it's operational
- **Groq:** Test routing call to verify Groq is available

Results are exposed via `GET /api/health` under `probes`. Allows the client to show degraded state warnings without hitting the APIs on every health check.

### Monitor (`services/monitor.py`)

Wraps the `send` callback for agent responses. Inspects outgoing chunks for quality signals:
- Responses exceeding `VOICE_MAX_CHARS` (600) get flagged (voice output should be brief)
- Banned phrases detected in chunks (AI slop patterns, excessive hedging)

Used to inform future fine-tuning quality filtering — flagged responses are candidates for exclusion from the training pool.

---

## 16. Security Model

### API Key Security

- Keys are `bwn_` + 40 random alphanumeric characters = 62^40 possibilities
- Only SHA-256 hash stored in `users.db`. Plaintext is never persisted.
- Key shown once at creation. Irrecoverable after that (use regen endpoint for lost keys).
- Admin key stored in `.env`, never committed to git.

### User Data Isolation

- Each user's SQLite and ChromaDB live in separate directories
- Per-connection `UserRegistry` ensures tool calls always target the correct user's DB
- No SQL queries that mix user data. Every tool injects `user_id` at construction time.
- REST endpoints authenticate via `X-Api-Key` header and resolve to a specific user's `MemoryStore`

### Tool Sandboxing

- `read_file` and `write_file` reject paths resolving into: `/System`, `/etc`, `/Library`, `/usr`, `/sbin`, `/bin`
- `run_shell` blocks: `rm -rf /`, `rm -rf ~`, fork bombs, `mkfs`, `fdisk`, `shutdown`, `reboot`, `halt`
- `execute_code` runs arbitrary Python in a subprocess with 30s timeout. **Trusted tool — admin / authorized users only.**
- Tool permission whitelist (TOOL_REGISTRY) enforced before every execution. DEVOPS cannot call `write_file`. TAMARA cannot call `execute_code`.

### Transport Security

- WebSocket and REST currently on `localhost` only (single-server deployment)
- Production deployment should add TLS termination at nginx/Caddy in front of uvicorn
- CORS configured for Tauri (`tauri://localhost`) and dev React (`localhost:3000`, `localhost:5173`)

---

## 17. Data Model

### users.db (User Account Registry)

```sql
CREATE TABLE users (
    id           TEXT PRIMARY KEY,    -- "usr_admin" or "usr_<8hex>"
    username     TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE, -- SHA-256 of API key
    is_admin     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    last_seen_at TEXT
);
```

### bowen.db (Per-User Memory + Activity)

```sql
-- Organizational containers
CREATE TABLE topics (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT DEFAULT '',
    color        TEXT DEFAULT '#C4963A',
    instructions TEXT DEFAULT '',    -- injected into agent prompts when active
    created_at   TEXT NOT NULL
);

-- Chat sessions
CREATE TABLE conversations (
    id         TEXT PRIMARY KEY,
    topic_id   TEXT REFERENCES topics(id),
    title      TEXT,
    created_at TEXT NOT NULL,
    ended_at   TEXT
);

-- Every message
CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id),
    turn            INTEGER,
    role            TEXT,   -- "user" or "assistant"
    agent           TEXT,   -- which agent responded
    content         TEXT,
    timestamp       TEXT,
    topic_id        TEXT
);

-- ChromaDB entry metadata (mirrors what's in ChromaDB)
CREATE TABLE memories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chroma_id    TEXT UNIQUE,
    agent_id     TEXT,         -- which agent this memory is most relevant to
    memory_type  TEXT,         -- "fact", "preference", "decision", "research"
    importance   REAL,         -- 0.0 to 1.0, decays over time
    tags         TEXT,         -- JSON array
    topic_id     TEXT,
    created_at   TEXT,
    last_accessed TEXT
);

-- Task tracker
CREATE TABLE tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    agent      TEXT,
    status     TEXT DEFAULT 'pending',  -- pending/in_progress/done/cancelled
    context    TEXT,
    topic_id   TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Logged decisions
CREATE TABLE decisions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    context   TEXT,
    decision  TEXT,
    reasoning TEXT,
    agent     TEXT,
    topic_id  TEXT,
    created_at TEXT
);

-- Files/code produced by CAPTAIN
CREATE TABLE artifacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER,
    conversation_id TEXT,
    filename        TEXT,
    file_type       TEXT,
    content         TEXT,
    version         INTEGER DEFAULT 1,
    created_at      TEXT
);

-- Daily Bible reading log
CREATE TABLE bible_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date  TEXT NOT NULL UNIQUE,  -- ISO date: "2026-04-10"
    completed INTEGER DEFAULT 0,
    passage   TEXT DEFAULT '',
    logged_at TEXT
);

-- CAPTAIN task dispatch tracking
CREATE TABLE dispatches (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    agent       TEXT,
    status      TEXT DEFAULT 'pending',
    description TEXT,
    result      TEXT,
    topic_id    TEXT,
    created_at  TEXT,
    updated_at  TEXT
);
```

---

## 18. Configuration Reference

All configuration lives in `config.py`, sourced from `.env`. Never use `os.getenv()` outside `config.py`.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | **Yes** | — | Core AI. Hard-required at startup. |
| `GROQ_API_KEY` | No | — | Tier 2 routing + Whisper STT. Fallback to Haiku if missing. |
| `OPENAI_API_KEY` | No | — | STT fallback (Phase 5). |
| `PERPLEXITY_API_KEY` | No | — | Reserved for future research tools. |
| `TAVILY_API_KEY` | No | — | SCOUT web search. Falls back to direct fetch if missing. |
| `BRAVE_API_KEY` | No | — | Alternative web search. |
| `ADMIN_API_KEY` | No | — | Praise's API key. Bootstraps admin account. |
| `GOOGLE_CLIENT_ID` | No | — | Google OAuth (Calendar, Gmail). |
| `GOOGLE_CLIENT_SECRET` | No | — | Google OAuth. |
| `KOKORO_VOICE` | No | `am_adam` | TTS voice name. |
| `KOKORO_SPEED` | No | `0.95` | TTS playback speed. |
| `USER_NAME` | No | `Praise Oyimi` | Display name for admin user. |
| `USER_TIMEZONE` | No | `America/Detroit` | Timezone for calendar and briefings. |

**Model constants (not env vars):**
```python
SONNET_MODEL = "claude-sonnet-4-6"         # Deep work agents
HAIKU_MODEL  = "claude-haiku-4-5-20251001"  # Fast agents, routing, pipeline
GROQ_ROUTING_MODEL = "llama-3.1-8b-instant" # Tier 2 routing
GROQ_STT_MODEL = "whisper-large-v3-turbo"   # Voice STT
```

---

## 19. Cost Model

Per 1,000 messages (rough estimates, varies by complexity):

| Component | Model | Cost |
|-----------|-------|------|
| Routing (Tier 1) | None | $0 |
| Routing (Tier 2, Groq) | LLaMA 3.1 8B | ~$0.20 |
| Agent responses (Sonnet) | Claude Sonnet 4.6 | ~$15–40 |
| Agent responses (Haiku) | Claude Haiku 4.5 | ~$1–3 |
| Memory extraction (Haiku) | Claude Haiku 4.5 | ~$0.50 |
| TTS | Kokoro (local) | $0 |
| STT | Groq Whisper | ~$0.18/hour of audio |
| Web search | Brave API | $0 (first 1,000/mo free) |

**Prompt caching impact:** On multi-turn conversations, system prompt tokens (typically 2,000–4,000 tokens) hit the Anthropic cache after the first turn. Cached tokens billed at 10% of input price. Real-world saving: ~30–50% on conversation costs.

---

## 20. Scaling Path

Current architecture is single-server. The following changes enable horizontal scaling when the time comes:

### Bottlenecks to Address

| Component | Current | Scaled Version |
|-----------|---------|----------------|
| Memory store | Per-user SQLite + ChromaDB on local disk | Supabase (PostgreSQL + pgvector) |
| Session state | In-process per-connection | Redis (session state, message bus) |
| Agent instances | Created per connection in-process | Agent pool with user context injection |
| Scheduler | APScheduler in single process | Celery beat or dedicated scheduler service |
| Voice | Local ONNX models | Dedicated voice service |

### Migration Path

**Step 1 — Supabase backend (when multiple servers needed)**  
Replace `MemoryStore(db_path, chroma_path)` with a `SupabaseMemoryStore` implementing the same interface. ChromaDB → pgvector (same embedding model, different storage). No agent code changes.

**Step 2 — Redis message bus**  
Replace in-process `MessageBus` with `RedisMessageBus` implementing the same `send()`/`drain_all()` interface. Agent-to-agent messages survive server restarts and work across processes.

**Step 3 — Stateless gateway**  
With Supabase + Redis, the gateway becomes stateless. Load balancer can route connections to any server. Horizontal scaling is trivial.

**The key design decision that makes this possible:** the `MemoryStore` and `MessageBus` interfaces are narrow and well-defined. Swapping the implementation doesn't require touching the agents.

---

## 21. Key Architectural Decisions

**Why per-connection agents instead of shared agents?**  
Agents hold in-memory state (session_id, current turn, stream buffer). Sharing them across users would require locking and careful state management. Fresh instances per connection are simpler, safer, and fast (instantiation is <1ms — the expensive work is ChromaDB load, which happens once in MultiUserStore).

**Why two routing tiers instead of one?**  
Tier 1 (regex) handles unambiguous cases in <1ms at zero cost. Running LLaMA on "review this code" is wasteful. Tier 2 (Groq) handles everything else with better accuracy than regex but at 80% lower cost than using Claude Haiku directly.

**Why Kokoro instead of ElevenLabs for TTS?**  
ElevenLabs has ongoing API costs and requires internet access. Kokoro is an Apache 2.0 ONNX model that runs locally. Zero ongoing cost, works offline, no third-party dependency for TTS. For a system that runs 24/7, the difference compounds significantly.

**Why SQLite instead of PostgreSQL?**  
Single-server deployment with one active user per connection. SQLite in WAL mode handles this with no operational overhead. When the system scales to need Supabase (Step 1 above), the migration path is clear.

**Why ChromaDB instead of pgvector?**  
ChromaDB runs locally with no setup. For the current scale, it is more than sufficient and has zero operational overhead. When Supabase becomes the DB backend, pgvector is a direct drop-in replacement using the same `all-MiniLM-L6-v2` embeddings.

**Why shared_knowledge.md in git instead of a database table?**  
Git provides version history, diff viewing, and easy rollback. The shared knowledge file is meant to be reviewed, edited, and committed deliberately — not accumulated silently in a database. It is a curated knowledge base, not an automatic log.

**Why `asyncio.to_thread()` for tool execution instead of making tools async?**  
All tool implementations (SQLite queries, Google Calendar calls, file I/O) are synchronous libraries. Wrapping them in `asyncio.to_thread()` in one place (`base.py:tool_use_loop`) is cleaner than converting every tool to async and dealing with thread-safety implications throughout the tool layer.

---

*This document reflects the codebase as of version 5.0. Update it when significant architectural changes are made. The BOWEN_MASTER.md covers product context and phase history; this document covers technical implementation.*
