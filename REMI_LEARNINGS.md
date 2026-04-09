# What BOWEN Can Learn from Remi's Architecture

**Date:** March 8, 2026  
**Source:** `/Users/yimi/Desktop/🚀 Remi/remi_ai/`

---

## 🔑 New APIs Added to BOWEN

### GROQ API (key in .env — GROQ_API_KEY)
**What it is:** Fast LLM inference (Whisper, LLaMA)  
**Why useful:**
- **Faster than Haiku** for routing decisions
- **Cheaper** for high-volume requests
- **Good for STT** (Whisper-large-v3-turbo)

**Recommended use in BOWEN:**
- Tier 2 routing (replace Haiku with Groq LLaMA for 3x speed)
- Voice-to-text transcription
- Low-cost agent responses when quality isn't critical

---

### TAVILY API (key in .env — TAVILY_API_KEY)
**What it is:** AI-optimized web search & research  
**Why better than Brave Search:**
- Returns **structured summaries** instead of raw links
- Built for **LLM consumption** (no parsing needed)
- **Source citations** included
- **Handles complex queries** better

**Recommended use in BOWEN:**
- **SCOUT's primary research tool** (replace Brave)
- Deep research requests
- Fact-checking and source validation

**Example from Remi:**
```python
from agno.tools.tavily import TavilyTools
search_tools = TavilyTools(api_key=settings.TAVILY_API_KEY)
```

---

### LiveKit (Real-time Voice)
**Credentials:**
- URL: set LIVEKIT_URL in .env
- API Key: set LIVEKIT_API_KEY in .env
- Secret: set LIVEKIT_API_SECRET in .env

**What it is:** Real-time voice communication platform  
**Why useful:**
- **Sub-second latency** for voice agents
- **Built-in VAD** (Voice Activity Detection)
- **Noise cancellation** included
- **Multi-user support** (group calls, rooms)

**Use in BOWEN Phase 5:**
- Real-time voice conversations with all 5 agents
- Voice mode switching (BOWEN → CAPTAIN → SCOUT in one call)
- Hands-free operation

---

## 🧠 Architectural Patterns from Remi

### 1. **Mode-Based Tool Filtering**

**What Remi does:**
```python
def create_study_tools(user_id: str, mode: str = "general"):
    if mode == "exam":
        # No web search, read-only materials, quiz/exam tools only
        return [QuizTools, MockExamTools, MemoryTools, ...]
    else:
        # Full suite: flashcards, whiteboard, file access, search
        return [TavilyTools, FlashcardTools, FileTools, ...]
```

**How BOWEN can use this:**
- **Work Mode:** CAPTAIN (code) + SCOUT (research) only
- **Email Mode:** TAMARA only
- **Planning Mode:** HELEN (calendar) + SCOUT (research)
- **Emergency Mode:** BOWEN direct (skip routing, fastest response)

---

### 2. **Agno Framework for Agent Orchestration**

**What Remi uses:**
```python
from agno.agent import Agent as AgnoAgent
from agno.db.postgres import PostgresDb

agent = AgnoAgent(
    model=Claude(id="claude-haiku-4-5-20251001", cache_system_prompt=True),
    tools=[search_tools] + study_tools,
    db=history_db,  # PostgresDb for session persistence
    add_history_to_context=True,
    num_history_runs=5,  # Last 5 exchanges remembered
)
```

**Key features BOWEN should adopt:**
- **System prompt caching** (`cache_system_prompt=True`) → saves 50% cost
- **Session persistence in Postgres** → survives restarts
- **Context window management** (`num_history_runs=5`) → prevents bloat
- **Extended cache time** for long-running sessions

---

### 3. **Voice-Optimized System Prompt**

**Remi's rules for TTS output:**
```
RULES: Never use markdown, bullets, numbered lists, asterisks, dashes, headers, 
or special formatting. Write natural spoken sentences only. Use transition words 
like "first", "next", "also" instead of lists.
```

**Why this matters for BOWEN:**
- Current agents use markdown (broken in TTS)
- Need separate `voice_style` system prompt injection
- ElevenLabs reads "*" as "asterisk" (sounds terrible)

**BOWEN Phase 5 Implementation:**
```python
if output_mode == "voice":
    system_prompt += "\n\nOUTPUT FORMAT: Spoken English only. No markdown."
```

---

### 4. **Proactive Memory Updates**

**Remi's approach:**
```
MEMORY: Silently update learning memory after every exchange. 
Call record_discussed_topics, mark_topic_struggling, mark_topic_mastered.
```

**BOWEN should adopt:**
- After each task, agents **silently** log to memory:
  - What was discussed
  - What worked / didn't work
  - User preferences revealed
- No "I'll remember that" → just do it

---

### 5. **User Guard for Tool Execution**

**Remi's security pattern:**
```python
from app.tools._user_guard import UserGuard

class CourseTools(UserGuard):
    def __init__(self, supabase, user_id):
        self.user_id = user_id  # All DB queries scoped to user
```

**Why BOWEN needs this:**
- Prevents data leakage between users
- Multi-user BOWEN (family/team plan)
- Each agent action scoped to correct user context

---

## 🚀 Phase 3 Recommendations for BOWEN

### Immediate Wins:
1. **Replace Haiku routing with Groq LLaMA** → 3x faster, 5x cheaper
2. **Use Tavily instead of Brave** for SCOUT → better research quality
3. **Add system prompt caching** → 50% cost reduction
4. **Implement mode-based tool filtering** → faster, more focused responses

### Phase 5 (Voice):
1. **Integrate LiveKit** for real-time voice
2. **Separate voice prompts** (no markdown)
3. **Use Groq Whisper** for STT (faster than OpenAI)
4. **Voice interruption handling** (VAD from LiveKit)

---

## 📊 Cost Comparison

| Task | Current (BOWEN) | With Remi APIs | Savings |
|------|----------------|----------------|---------|
| Routing decision | Haiku ($0.001) | Groq LLaMA ($0.0002) | 80% |
| Web research | Brave + parsing ($0.005) | Tavily ($0.005) | 0% but better quality |
| Voice transcription | OpenAI Whisper ($0.006/min) | Groq Whisper ($0.0001/min) | 98% |
| System prompt (100K tokens) | $0.25 | Cached: $0.025 | 90% |

**Total monthly savings estimate:** ~$20-40/mo (30-50% reduction)

---

## 🔧 Action Items

**Before Phase 3:**
- [ ] Test Groq LLaMA for Tier 2 routing
- [ ] Integrate Tavily into SCOUT's tool registry
- [ ] Add system prompt caching to all agents

**Before Phase 5:**
- [ ] Set up LiveKit room for BOWEN
- [ ] Test Groq Whisper latency
- [ ] Create voice-optimized system prompts
- [ ] Implement VAD (silero from LiveKit)

---

**Key Takeaway:** Remi's architecture is production-grade. BOWEN can adopt:
1. Faster/cheaper inference (Groq)
2. Better research (Tavily)
3. Real-time voice (LiveKit)
4. Cost optimization (prompt caching)
5. Multi-user security (user guards)

All these patterns are proven at scale with Remi's 100+ beta users. 🐾
