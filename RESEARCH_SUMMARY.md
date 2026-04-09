# BOWEN Research Summary (Executive Brief)

**Full Document:** `/Volumes/Untitled/bowen/BOWEN_RESEARCH.md` (93KB, comprehensive)

---

## Key Findings from Remi Guardian

### 🏗️ Architecture That Worked

**Remi's Evolved Stack:**
- **AI Agent:** Python + Agno framework (tool-based architecture)
- **Backend:** NestJS (Node.js) for CRUD + WebSocket
- **Frontend:** React 18 + Vite (migrated from Next.js for speed)
- **Database:** Supabase (PostgreSQL + Auth + RLS)
- **Voice:** LiveKit + AssemblyAI (STT) + Cartesia (TTS)
- **Desktop:** Electron (though Tauri would be lighter)

**Critical Insight:** AI agent is a **separate Python service** with direct database access. Not embedded in backend. This pattern scales well for BOWEN's 4 personalities.

---

## What Worked ✅

1. **Tool-Based AI (Agno):** Each capability = a tool. Easy to extend (add tool = add feature)
2. **Direct DB Access for AI:** No API layer between AI and data = faster, simpler
3. **Supabase RLS:** Security by default (users can't see others' data)
4. **React Query:** Automatic caching, no duplicate API calls
5. **Monorepo:** Shared types/code between frontend/backend
6. **LiveKit Voice:** Handles WebRTC complexity, works well

---

## What Didn't Work ❌

1. **No Caching Layer:** Analytics computed on every request → slow
2. **No Rate Limiting:** Risk of AI cost explosion
3. **Poor OCR (Tesseract.js):** 60-70% accuracy → use GPT-4 Vision instead
4. **No Usage Tracking:** Can't track per-user AI costs
5. **Duplicate API Calls:** Multiple components fetch same data
6. **No E2E Tests:** Regressions go unnoticed
7. **Voice Latency:** 1-3 second delay (STT + LLM + TTS)
8. **No Analytics/Telemetry:** Can't make data-driven decisions

---

## BOWEN Architecture Recommendation

```
┌─────────────────────────────────────┐
│         FRONTEND (Next.js)          │
│  [CAPTAIN] [HELEN] [SCOUT] [TAMARA] │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │   BOWEN Router       │
    │   (FastAPI/Python)   │
    └──────────────────────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
┌──────────┐      ┌──────────┐
│ CAPTAIN  │      │  HELEN   │  ... (4 personality agents)
│ Agent    │      │  Agent   │
│          │      │          │
│ Tools:   │      │ Tools:   │
│ - Tasks  │      │ - Career │
│ - Goals  │      │ - Resume │
└──────────┘      └──────────┘
      │                 │
      └────────┬────────┘
               │
               ▼
    ┌──────────────────────┐
    │   PostgreSQL         │
    │   (Supabase)         │
    │   + Redis (cache)    │
    └──────────────────────┘
```

---

## BOWEN-Specific Recommendations

### 1. Personality Implementation

**Each personality gets:**
- Unique system prompt (defines personality/tone)
- Unique voice (Cartesia TTS voices)
- Shared tools (calendar, email, notes, web search)
- Personality-specific tools:
  - **CAPTAIN:** Tasks, goals, projects, team coordination
  - **HELEN:** Career planning, resume, interview prep, networking
  - **SCOUT:** Learning resources, skill assessment, hobby exploration
  - **TAMARA:** Mental wellness, mood tracking, habits, journaling

**Memory Strategy:**
- Personality-specific memory (CAPTAIN remembers goals, HELEN remembers career status)
- Shared memory (all know user's name, timezone, preferences)
- Schema: `personality_memories(user_id, personality, key, value)`

---

### 2. Tech Stack for BOWEN

**Backend (Python):**
- FastAPI for API
- Agno for agent framework
- OpenAI GPT-4o-mini (or Anthropic Claude)
- Supabase Python client for DB
- Redis for caching + rate limiting

**Frontend:**
- Next.js (or Vite + React)
- React Query for data fetching
- Radix UI + Tailwind for components
- Socket.io or SSE for streaming

**Voice:**
- LiveKit for infrastructure
- AssemblyAI or Deepgram for STT
- Cartesia for TTS (4 unique voices)

**Database:**
- PostgreSQL (Supabase hosted)
- Redis (Upstash)

---

### 3. Pricing Model ($9/mo)

**Free Tier:**
- 100 messages/month per personality (400 total)
- 30 minutes voice/month
- Basic memory (30 days)

**Pro Tier ($9/mo):**
- Unlimited text
- Unlimited voice
- Full long-term memory
- Priority latency

**Cost Estimates:**
- AI: $0.50-2/user/month (text), +$1-2 per voice hour
- Infrastructure: $200-700/mo base
- At 1,000 users (50% pro): $4,500 revenue, ~$1,500-2,000 costs = **60-70% margin**

---

### 4. Development Roadmap

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 0: Foundation** | 2 weeks | Auth, DB, empty dashboard |
| **Phase 1: CAPTAIN** | 3-4 weeks | First personality working (text only) |
| **Phase 2: Multi-Personality** | 4-5 weeks | Add HELEN, SCOUT, TAMARA |
| **Phase 3: Voice** | 3-4 weeks | Add voice to all 4 personalities |
| **Phase 4: Polish** | 4-5 weeks | Analytics, integrations, billing |
| **Phase 5: Launch** | 2-3 weeks | Testing, beta, public launch |

**Total: 18-23 weeks (4.5-6 months)**

**Minimum viable:** 16 weeks (4 months) if aggressive

---

## Critical Success Factors

### Do This First

1. ✅ **Start with CAPTAIN only** (text chat) to prove concept
2. ✅ **Implement memory system early** (critical for bonding)
3. ✅ **Add rate limiting from day 1** (protect costs)
4. ✅ **Track AI usage per user** (know your unit economics)
5. ✅ **Use React Query** (data fetching game changer)

### Avoid These Mistakes

1. ❌ **Building all 4 personalities at once** → Start with 1, expand
2. ❌ **Adding voice before text works** → Voice is expensive/complex
3. ❌ **No caching** → Add Redis early
4. ❌ **No usage limits on free tier** → You'll lose money
5. ❌ **Complex frontend state** → Keep it simple with React Query

---

## Example: CAPTAIN Implementation

```python
# personalities/captain/agent.py
from agno import Agent
from shared.tools import CalendarTools, EmailTools, NoteTools
from personalities.captain.tools import TaskTools, GoalTools

def create_captain_agent(user_id: str):
    agent = Agent(
        name="CAPTAIN",
        model="openai:gpt-4o-mini",
        instructions=CAPTAIN_PROMPT,
        tools=[
            CalendarTools(user_id),
            EmailTools(user_id),
            NoteTools(user_id),
            TaskTools(user_id),
            GoalTools(user_id)
        ]
    )
    return agent

CAPTAIN_PROMPT = """
You are CAPTAIN, a disciplined and strategic AI assistant.

**Personality:** Military precision but friendly. Goal-oriented.
Uses tactical language ("mission", "objective", "execute").

**Capabilities:** Task management, goal setting, project planning.

**Tone:** Encouraging but firm. "Let's get it done" energy.

**Example:**
User: "I need to finish my thesis"
CAPTAIN: "Understood. Let's break this mission into tactical objectives.
What's your deadline? We'll create a battle plan with daily targets."
"""
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Voice costs too high** | Strict free limits (30min/month), push pro tier |
| **LLM costs explode** | Rate limit free tier, use cheaper models (Groq) |
| **Low retention** | Strong onboarding, personality bonding, notifications |
| **Personality confusion** | Clear UI separation, unique voices, different colors |
| **Privacy concerns** | GDPR compliance, data export, conversation deletion |

---

## Next Steps

1. **Review full research doc** (`BOWEN_RESEARCH.md`) for technical depth
2. **Set up monorepo** structure (packages for each personality + shared)
3. **Build CAPTAIN first** (single personality MVP)
4. **Add memory system** (personality_memories table)
5. **Test with real users** before adding more personalities
6. **Expand to 4 personalities** once CAPTAIN validated
7. **Add voice** after text chat works well

---

## Resources in Full Document

- Complete database schema (10 tables)
- Full code examples (agent creation, tools, memory)
- Voice pipeline implementation (LiveKit + STT/TTS)
- Frontend architecture (React Query patterns)
- Backend patterns (NestJS service/controller)
- Cost breakdown (per user, per 1000 users)
- Team recommendations (2-3 engineers for 6mo timeline)

---

**Research by:** Captain (BOWEN Subagent)  
**Date:** March 7, 2026  
**Full doc:** 93KB, 1,500+ lines of analysis
