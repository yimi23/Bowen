# BOWEN Framework Research: Learning from Remi Guardian

**Research Date:** March 7, 2026  
**Source:** Remi Guardian Codebase Analysis  
**Target:** BOWEN Framework (4 AI Personalities, 2027 Launch, $9/mo)  
**Researcher:** Captain (Subagent)

---

## Executive Summary

Remi Guardian is a sophisticated AI study assistant built with:
- **Backend:** NestJS (Node.js framework)
- **Frontend:** React 18 + Vite (migrated from Next.js)
- **Database:** Supabase (PostgreSQL) with RLS (Row-Level Security)
- **AI Agent:** Python + Agno framework + FastAPI
- **Voice:** LiveKit + AssemblyAI (STT) + Cartesia (TTS)
- **Desktop:** Electron wrapper with screen capture (Tesseract.js OCR)

**Key Insight:** Remi's architecture evolved from a tightly coupled monolith to a **service-oriented design** where the AI agent is a separate Python service that communicates with the frontend via REST/WebSocket and has direct database access. This pattern is **highly applicable to BOWEN's multi-personality architecture**.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack Deep Dive](#tech-stack-deep-dive)
3. [Database Schema & Design Patterns](#database-schema--design-patterns)
4. [AI Agent Implementation (Agno Framework)](#ai-agent-implementation-agno-framework)
5. [Voice Integration (LiveKit)](#voice-integration-livekit)
6. [Frontend Architecture](#frontend-architecture)
7. [Backend Patterns (NestJS)](#backend-patterns-nestjs)
8. [What Worked Well](#what-worked-well)
9. [What Didn't Work / Lessons Learned](#what-didnt-work--lessons-learned)
10. [BOWEN-Specific Recommendations](#bowen-specific-recommendations)
11. [Prioritized Roadmap for BOWEN MVP](#prioritized-roadmap-for-bowen-mvp)
12. [Estimated Complexity & Timeline](#estimated-complexity--timeline)

---

## Architecture Overview

### Current Remi Architecture (Evolved)

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│                    React 18 + Vite                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Dashboard   │  │ Chat Interface│  │ Voice Room   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         │                  │                  │                 │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
    ┌─────────┐      ┌─────────────┐    ┌─────────────┐
    │ NestJS  │      │  Remi AI    │    │  LiveKit    │
    │ Backend │      │  (Python +  │    │   Server    │
    │ (REST)  │      │   Agno)     │    │  (Voice)    │
    └─────────┘      └─────────────┘    └─────────────┘
          │                  │                  │
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   Supabase     │
                    │  (PostgreSQL)  │
                    │  + Auth + RLS  │
                    └────────────────┘
```

### Key Architectural Decisions

1. **Separate AI Service**: The AI agent (`remi_ai`) is a standalone Python FastAPI service, not embedded in the NestJS backend
2. **Direct DB Access for AI**: The AI agent connects directly to the database via Supabase client — no API layer
3. **Tool-Based AI Architecture**: Uses Agno's toolkit pattern where each capability (courses, flashcards, quizzes, etc.) is a registered tool
4. **Frontend as Orchestrator**: The frontend decides whether to call NestJS REST APIs (for CRUD) or Agno agent (for conversational AI)
5. **Real-Time via WebSocket**: Socket.io for chat streaming (NestJS) and LiveKit WebRTC for voice

---

## Tech Stack Deep Dive

### Backend: NestJS (TypeScript)

**Why NestJS?**
- Enterprise-grade Node.js framework with Angular-like architecture
- Built-in dependency injection, modules, controllers, services
- Excellent TypeScript support
- WebSocket support (Socket.io integration)
- Easy to structure monorepo workspaces

**Core Dependencies:**
```json
{
  "@nestjs/common": "^10.4.15",
  "@nestjs/platform-socket.io": "^10.4.22",
  "@supabase/supabase-js": "^2.49.1",
  "@anthropic-ai/sdk": "^0.39.0",
  "socket.io": "^4.8.3",
  "pg": "^8.18.0",
  "ioredis": "^5.4.0",
  "winston": "^3.19.0"
}
```

**Module Structure:**
```
backend/src/
├── app.module.ts                # Root module
├── auth/                        # Auth module (Supabase integration)
├── chat/                        # Chat WebSocket gateway
├── course/                      # Course CRUD (service + controller)
├── flashcard/                   # Flashcard CRUD
├── quiz/                        # Quiz CRUD
├── quiz-battle/                 # Real-time multiplayer quizzes
├── pod-session/                 # Study session management
├── whiteboard/                  # Whiteboard persistence
├── achievement/                 # Gamification
├── notification/                # Real-time notifications (Socket.io)
├── common/                      # Shared services (cache, logging)
└── config/                      # Config (env vars, Supabase client)
```

**Pattern:** Each feature is a **NestJS module** with:
- `*.service.ts` - Business logic + Supabase queries
- `*.controller.ts` - REST endpoints
- `*.gateway.ts` - WebSocket handlers (if needed)
- `dto/*.dto.ts` - Data transfer objects with validation

---

### AI Agent: Python + Agno + FastAPI

**Why Python for AI?**
- Better AI/ML ecosystem (Anthropic SDK, OpenAI SDK, Agno, LiveKit agents)
- Agno framework (like LangChain but simpler) for agentic workflows
- Easier to integrate with LiveKit's Python SDK for voice

**Core Dependencies (from `remi_ai/pyproject.toml`):**
```toml
dependencies = [
    "fastapi>=0.115.12",
    "agno>=0.0.24",               # Agent framework
    "openai>=1.62.0",             # LLM provider
    "supabase>=2.12.0",           # DB access
    "livekit>=0.18.0",            # Voice agent
    "livekit-agents>=0.11.14",    # Voice framework
    "uvicorn>=0.35.2",            # ASGI server
    "pydantic>=2.10.6",           # Data validation
    "pydantic-settings>=2.7.1"
]
```

**Agno Toolkit Pattern:**
```python
# Example: course_tools.py
from agno.tools.toolkit import Toolkit

class CourseTools(Toolkit):
    def __init__(self, supabase: Client, user_id: str):
        super().__init__(name="course_tools")
        self.supabase = supabase
        self.user_id = user_id
        
        # Register tools (functions AI can call)
        self.register(self.list_courses)
        self.register(self.get_course_details)
        self.register(self.search_courses)
    
    def list_courses(self) -> str:
        """List all courses available to the current user."""
        result = self.supabase.table("remi_courses")
            .select("*")
            .eq("user_id", self.user_id)
            .execute()
        return format_courses(result.data)
```

**Why This Works:**
- The AI decides which tools to call based on user input
- Each tool is a simple Python function with a docstring (for AI context)
- Tools have direct database access — no API roundtrip
- Tools can chain together (e.g., "create flashcards from this course" → `get_course_details` → `list_materials` → `create_flashcard_set`)

---

### Database: Supabase (PostgreSQL + Auth + RLS)

**Why Supabase?**
- Managed PostgreSQL with built-in auth
- Row-Level Security (RLS) for automatic user data isolation
- Real-time subscriptions (though Remi doesn't use this much)
- Storage buckets for file uploads
- Edge functions (not used in Remi)
- Great TypeScript SDK

**Schema Design Pattern:**

All tables use `remi_` prefix and follow this pattern:
```sql
create table remi_courses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  -- ... other fields
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- RLS policies (user can only access their own data)
alter table remi_courses enable row level security;

create policy "Users can view own courses"
  on remi_courses for select using (auth.uid() = user_id);
```

**Key Tables:**

| Table | Purpose | Rows (Typical) |
|-------|---------|----------------|
| `remi_courses` | User's courses (CPS420, MATH101, etc.) | 5-10 per user |
| `remi_materials` | PDFs, slides, notes uploaded per course | 20-100 per course |
| `remi_flashcard_sets` | Collections of flashcards | 10-30 per user |
| `remi_flashcards` | Individual flashcards with spaced repetition | 100-500 per user |
| `remi_quizzes` | Quiz instances | 10-50 per user |
| `remi_quiz_questions` | Questions within quizzes | 10-20 per quiz |
| `remi_conversations` | Chat conversations | 20-100 per user |
| `remi_messages` | Individual messages | 100-1000 per user |
| `remi_pod_sessions` | "Guardian Pod" teaching sessions | 5-20 per user |
| `remi_whiteboard_sessions` | Saved whiteboards | 10-30 per user |
| `remi_study_sessions` | Pomodoro/study time tracking | 50-200 per user |
| `remi_achievements` | Gamification badges | 10-30 per user |

**Lessons:**
- **RLS is powerful** but can get complex with joins (e.g., flashcards belong to sets, sets belong to courses, courses belong to users)
- **UUID primary keys** everywhere (good for distributed systems)
- **timestamptz** for all dates (better than timestamp)
- **`on delete cascade`** extensively used (when user deletes course, all materials/flashcards/etc. auto-delete)

---

### Frontend: React 18 + Vite

**Why React + Vite (not Next.js)?**

Originally Remi used **Next.js 14**, but they migrated to **Vite + React**. From docs:
- Next.js App Router was overkill for a desktop app (no SSR needed)
- Vite is **much faster** (dev server, HMR)
- Simpler build config for Electron packaging
- No need for API routes (backend is separate)

**Core Dependencies:**
```json
{
  "react": "^18.3.1",
  "vite": "6.3.5",
  "@tanstack/react-query": "^5.90.21",  // Data fetching
  "socket.io-client": "^4.8.3",         // WebSocket
  "livekit-client": "^2.17.1",          // Voice
  "@livekit/components-react": "^2.9.19",
  "@radix-ui/*": "^1.x",                // UI components (40+ packages!)
  "tailwindcss": "^3.4.0",              // Styling
  "motion": "^12.23.26",                // Animations (Framer Motion fork)
  "lucide-react": "^0.487.0"            // Icons
}
```

**State Management:**
- **No Redux/Zustand/Context** for global state
- Uses **React Query** for server state (cache management, refetching)
- Uses **custom hooks** for feature-specific state (`useChat`, `useGuardianPod`, `useQuizBattle`)
- **localStorage** for preferences and simple persistence

**Component Structure:**
```
frontend/src/components/
├── ChatInterface.tsx             # Main chat UI
├── ChatInterfaceEnhanced.tsx     # Advanced chat with more features
├── Dashboard.tsx                 # Main dashboard
├── UnifiedDashboard.tsx          # Consolidated view
├── CourseDetail.tsx              # Course view
├── MaterialsLibrary.tsx          # File browser
├── GuardianPodChat.tsx           # Voice study sessions
├── QuizBattle.tsx                # Multiplayer quiz game
├── StudyDashboard.tsx            # Analytics
├── FlashcardReview.tsx           # Spaced repetition UI
├── OnboardingFlow.tsx            # User onboarding
└── ui/                           # Reusable UI components (100+ files)
```

**Hook Architecture:**
```
frontend/src/hooks/
├── useAuth.ts                    # Auth state + login/logout
├── useChat.ts                    # Chat message handling + WebSocket
├── useGuardianPod.ts             # Voice session logic (very complex)
├── useLiveKitVoice.ts            # LiveKit room connection
├── useQuizBattle.ts              # Multiplayer quiz state
├── useKnowledgeBase.ts           # Course/material data fetching
├── queries/                      # React Query hooks (organized by feature)
│   ├── useCourses.ts
│   ├── useFlashcards.ts
│   ├── useQuizzes.ts
│   └── ...
```

**Data Fetching Pattern (React Query):**
```typescript
// hooks/queries/useCourses.ts
import { useQuery } from '@tanstack/react-query';
import { knowledgeBaseApi } from '@/services/knowledgeBaseApi';

export const useCourses = (userId: string) => {
  return useQuery({
    queryKey: ['courses', userId],
    queryFn: () => knowledgeBaseApi.getCourses(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
```

**Service Layer:**
```typescript
// services/knowledgeBaseApi.ts
class KnowledgeBaseApi {
  private baseUrl = 'http://localhost:3001/api';
  
  async getCourses() {
    const response = await fetch(`${this.baseUrl}/courses`);
    return response.json();
  }
  
  async createCourse(data: CreateCourseDto) {
    const response = await fetch(`${this.baseUrl}/courses`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return response.json();
  }
}

export const knowledgeBaseApi = new KnowledgeBaseApi();
```

**Lesson:** Centralized API client (similar to axios instance) makes it easy to swap backends or add interceptors.

---

### Voice Integration: LiveKit

**Architecture:**

```
Student's Microphone
  │
  ▼
┌────────────────────────────────────┐
│     LiveKit Room (WebRTC)          │
│  ┌──────────────────────────────┐  │
│  │   Audio Track (Student)      │  │
│  └──────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │  Voice Pipeline (Server-Side)│  │
│  │  1. Silero VAD               │  │  Voice Activity Detection
│  │  2. AssemblyAI STT           │  │  Speech → Text
│  │  3. Agno Agent (Remi AI)     │  │  Text → AI Response
│  │  4. Cartesia TTS             │  │  Text → Speech
│  └──────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │   Audio Track (Remi)         │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
  │
  ▼
Student's Speaker
```

**Key Components:**

1. **LiveKit Server** (self-hosted or cloud)
   - WebRTC SFU (Selective Forwarding Unit)
   - Manages rooms and tracks
   - Server-side agents can join rooms and process audio

2. **LiveKit Agent (Python)**
   ```python
   # app/livekit_agent.py (simplified)
   from livekit.agents import JobContext, WorkerOptions
   from livekit.agents.pipeline import VoicePipelineAgent
   from livekit.plugins import inference
   
   async def entrypoint(ctx: JobContext):
       agent = VoicePipelineAgent(
           vad=inference.VAD(model="silero"),
           stt=inference.STT(model="assemblyai/universal"),
           llm=LLMAdapter(agno_agent),  # Wraps Agno agent
           tts=inference.TTS(model="cartesia/sonic-3", voice="..."),
       )
       await agent.start(ctx.room)
   ```

3. **Frontend Integration**
   ```typescript
   // Frontend connects to LiveKit room
   const room = new Room();
   await room.connect(livekitUrl, token);
   
   // Listen for agent audio
   room.on('trackSubscribed', (track) => {
     if (track.kind === 'audio') {
       const audioElement = track.attach();
       document.body.appendChild(audioElement);
     }
   });
   ```

**Costs (from actual usage):**
- **LiveKit Cloud:** $0.006/min/participant (~$0.36/hour/user)
- **AssemblyAI STT:** $0.00037/second (~$1.33/hour)
- **Cartesia TTS:** $0.000018/character (~$0.05/hour for typical conversation)
- **OpenAI GPT-4:** $0.01/1K input tokens, $0.03/1K output (~$0.50-2/hour depending on conversation)

**Total voice cost:** ~$2-4/hour per active user

**Lesson:** Voice is expensive. Consider tiered pricing (voice as premium feature).

---

### Desktop: Electron

**Why Electron?**
- Cross-platform (Mac/Windows/Linux)
- Easy to package web app as desktop
- Access to OS-level features (screen capture, global shortcuts)
- Auto-update functionality

**Key Features:**
- **Screen Capture:** Uses Tesseract.js for OCR (text extraction from screenshots)
- **Global Shortcuts:** Hotkeys to open Remi overlay
- **Auto-Update:** `electron-updater` for silent updates
- **Menu Bar Integration:** System tray icon

**Dependencies:**
```json
{
  "electron": "^39.1.1",
  "electron-builder": "^24.9.1",
  "electron-updater": "^6.1.7",
  "tesseract.js": "^5.0.4"
}
```

**Lesson:** Electron is **heavy** (~150MB+ unpacked). Consider alternatives like Tauri (Rust + webview, ~10MB) for BOWEN if you want lighter footprint.

---

## Database Schema & Design Patterns

### Schema Organization

Remi's database has **15 migrations** creating **30+ tables**. Key design patterns:

1. **Namespace Prefix:** All tables use `remi_` prefix to avoid conflicts
2. **User Isolation:** Every table with user data has `user_id uuid references auth.users(id) on delete cascade`
3. **RLS Everywhere:** Row-Level Security policies on every table
4. **Soft Deletes (Mostly Absent):** Uses hard deletes with cascading (simpler, but risky if you want to recover data)
5. **Timestamps:** Every table has `created_at` and often `updated_at`
6. **UUIDs:** All primary keys are UUIDs (better for distributed systems, harder to debug)

### Core Tables in Detail

#### 1. Courses & Knowledge Base

```sql
-- Main course entity
remi_courses (
  id, user_id, name, code, semester, professor,
  status, storage_level, size, color, icon,
  next_class, progress, last_accessed,
  created_at, updated_at
)

-- Topics within courses (AI-generated or manual)
remi_topics (
  id, course_id, name, subtopics, related_topics,
  student_mastery, auto_generated, color, icon,
  last_studied, created_at
)

-- Uploaded materials (PDFs, slides, notes)
remi_materials (
  id, course_id, topic_id, type, title, content,
  file_url, metadata_*, hash, referenced, size,
  storage_level, created_at
)

-- Lecture recordings + transcripts
remi_lectures (
  id, course_id, title, date, transcript,
  transcript_quality, audio_url, student_notes,
  relevance_score, storage_level, compressed,
  summary, key_points, duration, recording_url,
  created_at
)

-- Lecture slides (extracted from PDFs)
remi_slides (
  id, lecture_id, page_number, content,
  image_url, ocr_text, timestamp
)
```

**Pattern:** Hierarchical relationships with cascading deletes:
```
user → course → materials
            └→ topics → materials
            └→ lectures → slides
```

#### 2. Flashcards & Spaced Repetition

```sql
-- Flashcard sets (collections)
remi_flashcard_sets (
  id, user_id, course_id, name, topic,
  card_count, created_at, updated_at
)

-- Individual flashcards with SRS metadata
remi_flashcards (
  id, user_id, set_id, front, back,
  difficulty, mastery, review_count,
  next_review, last_reviewed, created_at
)
```

**Spaced Repetition Algorithm (from `spacedRepetition.ts`):**
```typescript
function calculateNextReview(
  quality: 1 | 2 | 3 | 4 | 5,  // User rating
  currentInterval: number,
  repetitions: number,
  easeFactor: number
) {
  // SM-2 algorithm (SuperMemo 2)
  let newEaseFactor = Math.max(1.3, easeFactor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
  
  if (quality < 3) {
    // Failed: reset
    return { interval: 1, repetitions: 0, easeFactor: newEaseFactor };
  } else {
    // Passed: increase interval
    let newInterval;
    if (repetitions === 0) newInterval = 1;
    else if (repetitions === 1) newInterval = 6;
    else newInterval = Math.round(currentInterval * newEaseFactor);
    
    return { interval: newInterval, repetitions: repetitions + 1, easeFactor: newEaseFactor };
  }
}
```

**Lesson:** This is a **proven algorithm**. Don't reinvent spaced repetition — use SM-2 or Anki's algorithm.

#### 3. Quizzes & Assessments

```sql
-- Quiz instances
remi_quizzes (
  id, user_id, course_id, title,
  question_count, difficulty, time_limit,
  score, completed_at, created_at
)

-- Questions within quizzes
remi_quiz_questions (
  id, quiz_id, question, options,
  correct_answer, explanation, topic,
  difficulty, points, user_answer,
  is_correct, time_to_answer
)

-- Mock exams (comprehensive assessments)
remi_mock_exams (
  id, user_id, course_id, title, description,
  duration_minutes, total_questions, score,
  status, scheduled_at, started_at, completed_at,
  created_at
)
```

**Pattern:** Quizzes can be:
- **Generated by AI** (via chat: "quiz me on photosynthesis")
- **Scheduled** (mock exams)
- **Multiplayer** (quiz battles via `remi_quiz_battles` table)

#### 4. Conversations & Messages

```sql
-- Chat conversations
remi_conversations (
  id, user_id, title, mode,
  last_message_at, created_at
)

-- Individual messages
remi_messages (
  id, conversation_id, role, content,
  mode, topics, confidence, timestamp
)

-- Message attachments (screen captures, files)
remi_chat_attachments (
  id, message_id, type, file_url,
  file_name, file_size, mime_type,
  caption, created_at
)
```

**Pattern:** Standard chat schema. Each conversation has a mode (`general` / `study` / `exam`) that affects AI behavior.

#### 5. Study Sessions & Analytics

```sql
-- General study sessions (pomodoro, flashcard review, etc.)
remi_study_sessions (
  id, user_id, course_id, type, duration,
  items_reviewed, score, started_at, ended_at
)

-- Pod sessions (voice teaching sessions)
remi_pod_sessions (
  id, user_id, course_id, topic, mode,
  summary, confidence_score, duration,
  transcript, audio_url, whiteboard_data,
  started_at, ended_at, created_at
)

-- Activity log (for "Recent Activity" feed)
remi_activity_log (
  id, user_id, type, course_id, course_name,
  title, icon, metadata, created_at
)
```

**Analytics Queries (from `CourseService`):**
```typescript
async computeAnalytics(courseId: string) {
  const [
    materialCount,
    quizCount,
    flashcardCount,
    studyTime,
    topicMastery
  ] = await Promise.all([
    this.getMaterialCount(courseId),
    this.getQuizCount(courseId),
    this.getFlashcardCount(courseId),
    this.getTotalStudyTime(courseId),
    this.getTopicMasteryAvg(courseId)
  ]);
  
  return { materialCount, quizCount, flashcardCount, studyTime, topicMastery };
}
```

**Problem:** Analytics are computed **on every request** (no caching). This is slow for users with lots of data.

**Lesson for BOWEN:** Pre-compute analytics in background jobs or use materialized views.

#### 6. Achievements & Gamification

```sql
remi_achievements (
  id, user_id, type, title, description,
  icon, unlocked_at, created_at
)
```

**Achievement Types:**
- `first-study-session`
- `streak-7-days`
- `flashcards-100-reviewed`
- `quiz-perfect-score`
- etc.

**Lesson:** Gamification increases engagement but adds complexity. Start simple (just badges), expand later (leaderboards, XP).

---

### RLS (Row-Level Security) Pattern

Every table follows this pattern:

```sql
-- Enable RLS
alter table remi_courses enable row level security;

-- Select policy (users can view own courses)
create policy "Users can view own courses"
  on remi_courses for select
  using (auth.uid() = user_id);

-- Insert policy (users can create courses for themselves)
create policy "Users can insert own courses"
  on remi_courses for insert
  with check (auth.uid() = user_id);

-- Update policy (users can update own courses)
create policy "Users can update own courses"
  on remi_courses for update
  using (auth.uid() = user_id);

-- Delete policy (users can delete own courses)
create policy "Users can delete own courses"
  on remi_courses for delete
  using (auth.uid() = user_id);
```

**For nested resources (e.g., materials belong to courses):**

```sql
create policy "Users can view materials in own courses"
  on remi_materials for select
  using (
    exists (
      select 1 from remi_courses
      where remi_courses.id = remi_materials.course_id
        and remi_courses.user_id = auth.uid()
    )
  );
```

**Pros of RLS:**
- ✅ Security by default (can't accidentally expose other users' data)
- ✅ No need to add `where user_id = ?` to every query
- ✅ Works even if AI agent has full DB access

**Cons of RLS:**
- ❌ Complex policies can hurt performance (subqueries on every row)
- ❌ Hard to debug ("why can't I see this row?")
- ❌ Doesn't work well for multi-tenant B2B (team permissions are complex)

**For BOWEN:** RLS is good for consumer app. If doing B2B (teams), consider app-level permissions instead.

---

## AI Agent Implementation (Agno Framework)

### What is Agno?

[Agno](https://github.com/agno-agi/agno) is a **lightweight Python framework for building AI agents**. Think of it as a simpler alternative to LangChain/LlamaIndex.

**Core Concepts:**
1. **Agent**: Wraps an LLM (OpenAI, Anthropic, Groq, etc.) with system prompt and tools
2. **Toolkit**: Collection of related tools (functions) the agent can call
3. **Tool**: A Python function with a docstring (AI reads docstring to understand what it does)
4. **Run Loop**: Agent receives user message → calls tools if needed → returns response

### Remi's Agent Structure

```python
# app/services/agno_service.py (simplified)
from agno import Agent, History
from app.tools import (
    CourseTools, MaterialTools, FlashcardTools,
    QuizTools, PodSessionTools, WhiteboardTools,
    MemoryTools, StudyAnalyticsTools
)

class AgnoService:
    def __init__(self, user_id: str, mode: str = "study"):
        self.user_id = user_id
        self.mode = mode
        
        # Initialize all toolkits
        self.tools = [
            CourseTools(supabase, user_id),
            MaterialTools(supabase, user_id),
            FlashcardTools(supabase, user_id),
            QuizTools(supabase, user_id),
            PodSessionTools(supabase, user_id),
            WhiteboardTools(supabase, user_id),
            MemoryTools(supabase, user_id),
            StudyAnalyticsTools(supabase, user_id)
        ]
        
        # Create agent with mode-specific system prompt
        self.agent = Agent(
            name="Remi",
            model="openai:gpt-4o-mini",  # or "anthropic:claude-sonnet-4"
            instructions=self.get_system_prompt(mode),
            tools=self.tools,
            markdown=True,
            show_tool_calls=True,
            storage=History(db_file=f"tmp/history_{user_id}.db")
        )
    
    def get_system_prompt(self, mode: str) -> str:
        base = "You are Remi, an AI study assistant..."
        
        if mode == "general":
            return base + "Be conversational and helpful. Use screen context when available."
        elif mode == "study":
            return base + "You're a patient teacher. Break down complex topics. Create flashcards when helpful."
        elif mode == "exam":
            return base + "You're an adaptive quiz generator. Ask questions, grade answers, track performance."
        
        return base
    
    async def chat(self, message: str, session_id: str | None = None) -> str:
        response = await self.agent.run(
            message,
            session_id=session_id or f"session_{uuid.uuid4()}"
        )
        return response.content
```

### Tool Implementation Example

```python
# app/tools/flashcard_tools.py
from agno.tools.toolkit import Toolkit

class FlashcardTools(Toolkit):
    def __init__(self, supabase, user_id):
        super().__init__(name="flashcard_tools")
        self.supabase = supabase
        self.user_id = user_id
        
        self.register(self.create_flashcard_set)
        self.register(self.add_flashcards)
        self.register(self.get_due_flashcards)
        self.register(self.review_flashcard)
    
    def create_flashcard_set(self, name: str, course_id: str, topic: str) -> str:
        """Create a new flashcard set for studying.
        
        Args:
            name: Name of the flashcard set (e.g., "Chapter 3: Photosynthesis")
            course_id: ID of the course this set belongs to
            topic: Main topic covered by these flashcards
        """
        result = self.supabase.table("remi_flashcard_sets").insert({
            "user_id": self.user_id,
            "course_id": course_id,
            "name": name,
            "topic": topic,
            "card_count": 0
        }).execute()
        
        return f"Created flashcard set '{name}' (ID: {result.data[0]['id']})"
    
    def add_flashcards(self, set_id: str, cards: list[dict]) -> str:
        """Add multiple flashcards to a set.
        
        Args:
            set_id: ID of the flashcard set
            cards: List of flashcards, each with 'front' and 'back' keys
        """
        flashcards = [
            {
                "user_id": self.user_id,
                "set_id": set_id,
                "front": card["front"],
                "back": card["back"],
                "difficulty": "medium",
                "mastery": 0.0,
                "next_review": "now()"
            }
            for card in cards
        ]
        
        result = self.supabase.table("remi_flashcards").insert(flashcards).execute()
        
        # Update card count in set
        self.supabase.table("remi_flashcard_sets").update({
            "card_count": len(result.data)
        }).eq("id", set_id).execute()
        
        return f"Added {len(result.data)} flashcards to set"
    
    def get_due_flashcards(self, set_id: str, limit: int = 10) -> str:
        """Get flashcards that are due for review (spaced repetition).
        
        Args:
            set_id: ID of the flashcard set
            limit: Maximum number of cards to return (default 10)
        """
        result = self.supabase.table("remi_flashcards")
            .select("*")
            .eq("set_id", set_id)
            .lte("next_review", "now()")
            .order("next_review", asc=True)
            .limit(limit)
            .execute()
        
        if not result.data:
            return "No flashcards due for review right now. Great job!"
        
        cards = "\n".join([
            f"- ID: {c['id']}\n  Q: {c['front']}\n  A: {c['back']}"
            for c in result.data
        ])
        return f"Found {len(result.data)} cards due for review:\n{cards}"
    
    def review_flashcard(self, card_id: str, quality: int) -> str:
        """Record a flashcard review and update spaced repetition schedule.
        
        Args:
            card_id: ID of the flashcard
            quality: Review quality (1=again, 2=hard, 3=good, 4=easy, 5=perfect)
        """
        # Fetch current flashcard state
        card = self.supabase.table("remi_flashcards")
            .select("*")
            .eq("id", card_id)
            .single()
            .execute()
        
        # Calculate next review using SM-2 algorithm
        interval, reps, ef = calculate_next_review(
            quality,
            card.data.get("current_interval", 1),
            card.data.get("review_count", 0),
            card.data.get("ease_factor", 2.5)
        )
        
        # Update flashcard
        self.supabase.table("remi_flashcards").update({
            "review_count": reps,
            "current_interval": interval,
            "ease_factor": ef,
            "last_reviewed": "now()",
            "next_review": f"now() + interval '{interval} days'",
            "mastery": min(1.0, card.data.get("mastery", 0) + 0.1)
        }).eq("id", card_id).execute()
        
        return f"Flashcard reviewed. Next review in {interval} days."
```

### How the AI Uses Tools

**Example conversation:**

```
Student: "Can you make flashcards from my Biology notes about cell division?"

Agno Agent (internally):
1. Calls list_courses() → finds "Biology 101" course
2. Calls search_materials(course_id="...", query="cell division") → finds notes
3. Calls get_material_content(material_id="...") → reads notes content
4. Generates 10 flashcards from notes content (using LLM)
5. Calls create_flashcard_set(name="Cell Division", course_id="...", topic="mitosis")
6. Calls add_flashcards(set_id="...", cards=[...])

Agent (to student):
"I created a flashcard set called 'Cell Division' with 10 cards covering:
- Phases of mitosis
- Differences between mitosis and meiosis
- Key cellular structures involved
...

You can review them in the Flashcard section!"
```

**Why This Is Powerful:**
- The student doesn't navigate any UI
- The AI orchestrates multiple actions in one request
- The AI has full context (courses, materials, past performance)

### Streaming Responses (SSE)

```python
# app/main.py
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for event in agno_service.stream_chat(request.message):
            if event.type == "tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': event.tool_name})}\n\n"
            elif event.type == "tool_complete":
                yield f"data: {json.dumps({'type': 'tool_complete', 'result': event.result})}\n\n"
            elif event.type == "content":
                yield f"data: {json.dumps({'type': 'content', 'text': event.text})}\n\n"
            elif event.type == "done":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Frontend (React):**
```typescript
const eventSource = new EventSource('/api/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: "Explain photosynthesis" })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'tool_start') {
    console.log(`AI is calling: ${data.tool}`);
  } else if (data.type === 'content') {
    appendToChat(data.text);
  } else if (data.type === 'done') {
    eventSource.close();
  }
};
```

**Lesson:** Streaming is essential for good UX. Users see the AI "thinking" in real-time.

---

## Voice Integration (LiveKit)

### Architecture Overview

LiveKit handles **real-time voice communication** via WebRTC. The pattern:

1. **Frontend** connects to a LiveKit room
2. **Voice Agent (Python)** joins the same room as a "participant"
3. **Audio flows both ways:**
   - Student speaks → AssemblyAI STT → text
   - Text → Agno Agent → response text → Cartesia TTS → audio → Student hears

### LiveKit Agent Implementation

```python
# app/livekit_agent.py (simplified)
from livekit import agents
from livekit.agents import JobContext, WorkerOptions
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import inference

from app.services.livekit_agno_plugin import LLMAdapter
from app.services.agno_service import AgnoService

async def entrypoint(ctx: JobContext):
    # Create Agno agent for this user
    user_id = ctx.room.metadata.get("user_id", "default")
    agno_service = AgnoService(user_id=user_id, mode="study")
    
    # Wrap Agno agent as LiveKit-compatible LLM
    llm_adapter = LLMAdapter(agno_service)
    
    # Build voice pipeline
    agent = VoicePipelineAgent(
        vad=inference.VAD(model="silero"),  # Voice Activity Detection
        stt=inference.STT(
            model="assemblyai/universal-streaming",
            language="en"
        ),
        llm=llm_adapter,  # Our Agno agent wrapped
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice="694f9389-aac1-45b6-b726-9d9369183238"  # Female teacher voice
        ),
    )
    
    # Start the agent
    agent.start(ctx.room)
    
    # Keep agent alive until room closes
    await agent.wait_for_completion()

if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint)
    )
```

### Custom LLM Adapter (Bridge Agno → LiveKit)

```python
# app/services/livekit_agno_plugin.py
from livekit.agents import llm

class LLMAdapter(llm.LLM):
    """Wraps an Agno Agent to work with LiveKit's voice pipeline."""
    
    def __init__(self, agno_service):
        self.agno_service = agno_service
    
    async def chat(self, chat_ctx: llm.ChatContext) -> llm.ChatResponse:
        # Convert LiveKit ChatContext to simple message
        user_message = chat_ctx.messages[-1].content
        
        # Call Agno agent
        response_text = await self.agno_service.chat(user_message)
        
        # Strip markdown for TTS (don't want it to say "asterisk asterisk bold")
        clean_text = strip_markdown(response_text)
        
        # Return as LiveKit ChatResponse
        return llm.ChatResponse(
            choices=[
                llm.Choice(
                    message=llm.ChatMessage(role="assistant", content=clean_text)
                )
            ]
        )
```

### Frontend Connection

```typescript
// Frontend: Connect to LiveKit room
import { Room, RoomEvent } from 'livekit-client';

const connectToVoiceSession = async () => {
  // Get token from backend
  const { token, url } = await fetch('/api/livekit/token', {
    method: 'POST',
    body: JSON.stringify({
      identity: userId,
      room: `study-session-${sessionId}`
    })
  }).then(r => r.json());
  
  // Connect to room
  const room = new Room();
  
  room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === 'audio' && participant.identity === 'remi-agent') {
      // Attach Remi's audio to HTML audio element
      const audioElement = track.attach();
      document.body.appendChild(audioElement);
    }
  });
  
  await room.connect(url, token);
  
  // Enable microphone
  await room.localParticipant.setMicrophoneEnabled(true);
};
```

### TTS Voice Selection

Cartesia provides **multiple voices**. Remi uses a warm, patient teacher voice:

```python
# Voice IDs (from Cartesia docs)
VOICES = {
    "teacher": "694f9389-aac1-45b6-b726-9d9369183238",  # Female, warm
    "tutor": "...",      # Male, enthusiastic
    "narrator": "...",   # Neutral, calm
}
```

**Lesson for BOWEN:**
- CAPTAIN: Confident male voice (think military commander)
- HELEN: Professional female voice (HR/life coach vibe)
- SCOUT: Energetic, curious voice (young explorer)
- TAMARA: Warm, motherly voice (therapist/counselor)

### Voice Latency Optimization

**Measured latencies (from Remi logs):**
- VAD (voice detection): ~50ms
- STT (speech to text): ~200-500ms
- LLM (AI response): ~500-2000ms (depends on complexity)
- TTS (text to speech): ~100-300ms
- **Total:** ~1-3 seconds from user stops speaking to hearing response

**Optimizations:**
1. **Prewarm VAD** at startup (Silero model loads once)
2. **Stream TTS** (don't wait for full response before starting speech)
3. **Use faster LLMs** for simple queries (GPT-4o-mini vs Claude)
4. **Cache common responses** (e.g., "What can you help me with?")

---

## Frontend Architecture

### Component Organization

Remi's frontend has **150+ components**. Key patterns:

#### 1. Page Components (Top-Level Views)

```
Dashboard.tsx               - Main dashboard (course overview)
ChatInterface.tsx           - Text chat with Remi
GuardianPodChat.tsx         - Voice study sessions
MaterialsLibrary.tsx        - File browser + upload
StudyDashboard.tsx          - Analytics + progress
FlashcardReview.tsx         - Spaced repetition UI
QuizBattle.tsx              - Multiplayer quiz game
```

#### 2. Feature Components (Complex Features)

```
OnboardingFlow.tsx          - Multi-step user setup
CourseDetail.tsx            - Course overview + materials
LectureDetail.tsx           - Lecture viewer + notes
WhiteboardViewer.tsx        - Visual teaching canvas
NotificationCenter.tsx      - Real-time notifications
AchievementToast.tsx        - Gamification popups
```

#### 3. UI Components (Reusable)

```
ui/
├── button.tsx              - Button variants (primary, secondary, ghost, etc.)
├── dialog.tsx              - Modal dialogs
├── dropdown-menu.tsx       - Dropdown menus
├── input.tsx               - Text inputs
├── select.tsx              - Select dropdowns
├── tabs.tsx                - Tab navigation
├── card.tsx                - Card containers
├── badge.tsx               - Status badges
├── progress.tsx            - Progress bars
├── avatar.tsx              - User avatars
└── ... (40+ more components from shadcn/ui + Radix UI)
```

**Pattern:** All UI components use **Radix UI primitives** + **Tailwind CSS** for styling. This gives:
- Accessibility out of the box (keyboard nav, ARIA labels, focus management)
- Consistent design system
- Easy to customize

### State Management Patterns

#### 1. Local State (useState)

For simple component state:

```typescript
const ChatInterface = () => {
  const [message, setMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  // ...
};
```

#### 2. Server State (React Query)

For data fetched from API:

```typescript
const useCourses = () => {
  return useQuery({
    queryKey: ['courses'],
    queryFn: () => knowledgeBaseApi.getCourses(),
    staleTime: 5 * 60 * 1000,  // Cache for 5 minutes
    refetchOnWindowFocus: false
  });
};

// In component:
const { data: courses, isLoading, error } = useCourses();
```

**Benefits:**
- Automatic caching (no duplicate requests)
- Automatic refetching (when data goes stale)
- Loading/error states handled automatically
- Optimistic updates (update UI before server response)

#### 3. WebSocket State (Custom Hooks)

For real-time data:

```typescript
const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const socketRef = useRef<Socket>();
  
  useEffect(() => {
    socketRef.current = io('http://localhost:3001/chat');
    
    socketRef.current.on('message', (msg) => {
      setMessages(prev => [...prev, msg]);
    });
    
    return () => socketRef.current?.disconnect();
  }, []);
  
  const sendMessage = (content: string) => {
    socketRef.current?.emit('message', { content });
  };
  
  return { messages, sendMessage };
};
```

#### 4. URL State (React Router)

For navigation state:

```typescript
const navigate = useNavigate();
const { courseId } = useParams();
const [searchParams] = useSearchParams();

// Navigate to course detail
navigate(`/courses/${courseId}`);

// Navigate with query params
navigate(`/materials?courseId=${courseId}`);
```

### Data Fetching Patterns

#### Pattern 1: Fetch on Mount

```typescript
const CourseDetail = ({ courseId }: Props) => {
  const { data: course, isLoading } = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => knowledgeBaseApi.getCourse(courseId)
  });
  
  if (isLoading) return <Spinner />;
  return <div>{course.name}</div>;
};
```

#### Pattern 2: Fetch on User Action

```typescript
const CreateCourseButton = () => {
  const queryClient = useQueryClient();
  
  const createMutation = useMutation({
    mutationFn: (data) => knowledgeBaseApi.createCourse(data),
    onSuccess: () => {
      // Invalidate courses query to refetch
      queryClient.invalidateQueries({ queryKey: ['courses'] });
    }
  });
  
  const handleCreate = () => {
    createMutation.mutate({ name: 'New Course' });
  };
  
  return <Button onClick={handleCreate}>Create</Button>;
};
```

#### Pattern 3: Optimistic Updates

```typescript
const DeleteCourseButton = ({ courseId }: Props) => {
  const queryClient = useQueryClient();
  
  const deleteMutation = useMutation({
    mutationFn: () => knowledgeBaseApi.deleteCourse(courseId),
    onMutate: async () => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['courses'] });
      
      // Snapshot current value
      const previous = queryClient.getQueryData(['courses']);
      
      // Optimistically update to new value
      queryClient.setQueryData(['courses'], (old: Course[]) =>
        old.filter(c => c.id !== courseId)
      );
      
      return { previous };
    },
    onError: (err, variables, context) => {
      // Rollback on error
      queryClient.setQueryData(['courses'], context.previous);
    }
  });
  
  return <Button onClick={() => deleteMutation.mutate()}>Delete</Button>;
};
```

### WebSocket Integration

```typescript
// services/socketClient.ts
import { io, Socket } from 'socket.io-client';

class SocketClient {
  private socket: Socket | null = null;
  
  connect(namespace: string = '/chat') {
    this.socket = io(`http://localhost:3001${namespace}`, {
      auth: { token: localStorage.getItem('token') }
    });
    
    this.socket.on('connect', () => {
      console.log('Connected to', namespace);
    });
    
    return this.socket;
  }
  
  disconnect() {
    this.socket?.disconnect();
  }
  
  on(event: string, callback: (...args: any[]) => void) {
    this.socket?.on(event, callback);
  }
  
  emit(event: string, data: any) {
    this.socket?.emit(event, data);
  }
}

export const socketClient = new SocketClient();
```

**Usage in Component:**

```typescript
const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  
  useEffect(() => {
    const socket = socketClient.connect('/chat');
    
    socket.on('message', (msg: Message) => {
      setMessages(prev => [...prev, msg]);
    });
    
    socket.on('typing', (data: { userId: string; isTyping: boolean }) => {
      // Handle typing indicator
    });
    
    return () => socketClient.disconnect();
  }, []);
  
  const sendMessage = (content: string) => {
    socketClient.emit('message', { content });
  };
  
  return { messages, sendMessage };
};
```

---

## Backend Patterns (NestJS)

### Module Structure

Each feature is a **NestJS module** with standard structure:

```
course/
├── course.module.ts         # Module definition
├── course.service.ts        # Business logic
├── course.controller.ts     # REST endpoints
├── dto/                     # Data transfer objects
│   └── course.dto.ts
└── entities/                # Database entities (if using TypeORM)
    └── course.entity.ts
```

### Service Pattern

```typescript
// course/course.service.ts
import { Injectable, NotFoundException } from '@nestjs/common';
import { getSupabaseAdmin } from '../config/supabase.config';
import { CreateCourseDto, UpdateCourseDto } from './dto/course.dto';

@Injectable()
export class CourseService {
  private get supabase() {
    return getSupabaseAdmin();
  }
  
  async getCourses(userId: string) {
    const { data, error } = await this.supabase
      .from('remi_courses')
      .select('*')
      .eq('user_id', userId)
      .order('updated_at', { ascending: false });
    
    if (error) throw new Error(error.message);
    
    return data.map(this.formatCourse);
  }
  
  async getCourse(userId: string, courseId: string) {
    const { data: course, error } = await this.supabase
      .from('remi_courses')
      .select('*')
      .eq('id', courseId)
      .eq('user_id', userId)
      .single();
    
    if (error || !course) {
      throw new NotFoundException('Course not found');
    }
    
    // Fetch related data in parallel
    const [topics, materials, analytics] = await Promise.all([
      this.getTopics(courseId),
      this.getMaterials(courseId),
      this.computeAnalytics(courseId)
    ]);
    
    return {
      ...this.formatCourse(course),
      topics,
      materials,
      analytics
    };
  }
  
  async createCourse(userId: string, dto: CreateCourseDto) {
    const { data, error } = await this.supabase
      .from('remi_courses')
      .insert({
        user_id: userId,
        name: dto.name,
        code: dto.code,
        professor: dto.professor
      })
      .select()
      .single();
    
    if (error) throw new Error(error.message);
    
    // Emit real-time notification
    this.notificationGateway.sendToUser(userId, {
      type: 'course_created',
      data: this.formatCourse(data)
    });
    
    return this.formatCourse(data);
  }
  
  private formatCourse(course: any) {
    return {
      id: course.id,
      name: course.name,
      code: course.code,
      professor: course.professor,
      // ... format dates, etc.
    };
  }
}
```

### Controller Pattern

```typescript
// course/course.controller.ts
import { Controller, Get, Post, Put, Delete, Body, Param, UseGuards } from '@nestjs/common';
import { CourseService } from './course.service';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { CreateCourseDto, UpdateCourseDto } from './dto/course.dto';

@Controller('api/courses')
@UseGuards(JwtAuthGuard)
export class CourseController {
  constructor(private readonly courseService: CourseService) {}
  
  @Get()
  async getCourses(@CurrentUser() userId: string) {
    return this.courseService.getCourses(userId);
  }
  
  @Get(':id')
  async getCourse(
    @CurrentUser() userId: string,
    @Param('id') courseId: string
  ) {
    return this.courseService.getCourse(userId, courseId);
  }
  
  @Post()
  async createCourse(
    @CurrentUser() userId: string,
    @Body() dto: CreateCourseDto
  ) {
    return this.courseService.createCourse(userId, dto);
  }
  
  @Put(':id')
  async updateCourse(
    @CurrentUser() userId: string,
    @Param('id') courseId: string,
    @Body() dto: UpdateCourseDto
  ) {
    return this.courseService.updateCourse(userId, courseId, dto);
  }
  
  @Delete(':id')
  async deleteCourse(
    @CurrentUser() userId: string,
    @Param('id') courseId: string
  ) {
    return this.courseService.deleteCourse(userId, courseId);
  }
}
```

### WebSocket Gateway Pattern

```typescript
// chat/chat.gateway.ts
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  OnGatewayConnection,
  OnGatewayDisconnect
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';

@WebSocketGateway({ namespace: '/chat', cors: true })
export class ChatGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;
  
  async handleConnection(client: Socket) {
    const userId = client.handshake.auth.token; // Extract from JWT
    client.join(`user:${userId}`);
    console.log(`User ${userId} connected`);
  }
  
  async handleDisconnect(client: Socket) {
    console.log('Client disconnected:', client.id);
  }
  
  @SubscribeMessage('message')
  async handleMessage(client: Socket, payload: { content: string }) {
    const userId = client.data.userId;
    
    // Save message to DB
    const message = await this.chatService.saveMessage(userId, payload.content);
    
    // Emit back to user
    this.server.to(`user:${userId}`).emit('message', message);
    
    // Get AI response (async)
    this.chatService.getAIResponse(userId, payload.content).then(response => {
      this.server.to(`user:${userId}`).emit('message', response);
    });
  }
  
  @SubscribeMessage('typing')
  async handleTyping(client: Socket, payload: { isTyping: boolean }) {
    const userId = client.data.userId;
    this.server.to(`user:${userId}`).emit('typing', { userId, isTyping: payload.isTyping });
  }
}
```

### Error Handling

```typescript
// common/filters/http-exception.filter.ts
import { ExceptionFilter, Catch, ArgumentsHost, HttpException } from '@nestjs/common';
import { Response } from 'express';

@Catch(HttpException)
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: HttpException, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const status = exception.getStatus();
    const exceptionResponse = exception.getResponse();
    
    response.status(status).json({
      statusCode: status,
      timestamp: new Date().toISOString(),
      message: typeof exceptionResponse === 'string' 
        ? exceptionResponse 
        : (exceptionResponse as any).message,
    });
  }
}
```

**Usage:**
```typescript
// main.ts
app.useGlobalFilters(new HttpExceptionFilter());
```

### Logging

```typescript
// common/services/logger.service.ts
import { Injectable, LoggerService as NestLoggerService } from '@nestjs/common';
import * as winston from 'winston';

@Injectable()
export class LoggerService implements NestLoggerService {
  private logger: winston.Logger;
  
  constructor() {
    this.logger = winston.createLogger({
      level: 'info',
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
      ),
      transports: [
        new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
        new winston.transports.File({ filename: 'logs/combined.log' })
      ]
    });
  }
  
  log(message: string, context?: string) {
    this.logger.info(message, { context });
  }
  
  error(message: string, trace?: string, context?: string) {
    this.logger.error(message, { trace, context });
  }
  
  warn(message: string, context?: string) {
    this.logger.warn(message, { context });
  }
}
```

---

## What Worked Well

### 1. ✅ Separate AI Service (Python)

**Why it worked:**
- Python has better AI/ML ecosystem (Agno, LiveKit, better LLM SDKs)
- Easy to swap LLM providers (OpenAI → Anthropic → Groq)
- Can scale AI independently from CRUD backend
- Type safety not as critical for AI (rapid iteration > strict types)

**For BOWEN:** Keep AI agents in Python. Use TypeScript/Node for API/CRUD if needed.

---

### 2. ✅ Agno Framework (Tool-Based Architecture)

**Why it worked:**
- **Simple mental model:** AI agent + tools = capabilities
- **Easy to extend:** Adding a new feature = adding a new tool
- **Good separation:** Each tool is isolated (course tools, flashcard tools, etc.)
- **Testable:** Can test each tool independently

**For BOWEN:** Use Agno or similar (LangChain is heavier). Each personality should have:
- Shared tools (e.g., calendar, email, web search)
- Personality-specific tools (CAPTAIN = project management, HELEN = HR/life coaching, etc.)

---

### 3. ✅ Supabase (PostgreSQL + Auth + RLS)

**Why it worked:**
- **Auth out of the box:** Email/password + OAuth (Google, GitHub)
- **RLS = security by default:** Can't accidentally expose other users' data
- **Great TypeScript SDK:** Type-safe queries
- **Real-time subscriptions:** (Though Remi uses WebSocket instead)
- **Generous free tier:** 500MB DB, 1GB file storage, 2GB bandwidth

**For BOWEN:** Supabase is great for MVP. Consider alternatives if:
- Need more complex permissions (teams, roles) → Auth0 + raw Postgres
- Need more control over infrastructure → Self-hosted Postgres + custom auth

---

### 4. ✅ React Query (Data Fetching)

**Why it worked:**
- **Automatic caching:** No duplicate API calls
- **Automatic refetching:** Data stays fresh
- **Loading/error states:** Built-in, less boilerplate
- **Optimistic updates:** Instant UI feedback
- **DevTools:** Great debugging experience

**For BOWEN:** Use React Query (or TanStack Query for React Native). Game changer for data-heavy apps.

---

### 5. ✅ LiveKit (Voice Infrastructure)

**Why it worked:**
- **Handles WebRTC complexity:** No need to configure STUN/TURN servers
- **Server-side agents:** Can process audio server-side (vs client-side)
- **Good Python SDK:** Easy to integrate with AI pipeline
- **Scalable:** Handles 100+ concurrent rooms easily

**For BOWEN:** LiveKit is solid. Alternatives:
- **Twilio Voice** (simpler but more expensive)
- **Daily.co** (good WebRTC API, no agent framework)
- **Self-hosted Janus/Jitsi** (harder to manage)

---

### 6. ✅ Monorepo with Workspaces

**Why it worked:**
- **Shared types:** Frontend and backend use same DTOs
- **Single `npm install`:** Easier for new devs
- **Coordinated releases:** Deploy frontend + backend together

**For BOWEN:** Use monorepo (npm workspaces, Turborepo, or Nx). Structure:
```
bowen/
├── packages/
│   ├── ai-captain/       # CAPTAIN personality
│   ├── ai-helen/         # HELEN personality
│   ├── ai-scout/         # SCOUT personality
│   ├── ai-tamara/        # TAMARA personality
│   ├── shared/           # Shared tools + types
│   ├── frontend/         # Web app
│   └── mobile/           # React Native app (optional)
```

---

### 7. ✅ Modular Frontend (Components + Hooks)

**Why it worked:**
- **Reusable components:** UI library (buttons, dialogs, etc.) used everywhere
- **Custom hooks:** Business logic separate from UI (easier to test)
- **Feature folders:** Each feature self-contained (chat/, courses/, flashcards/)

**For BOWEN:** Follow same pattern. Use shadcn/ui + Radix for component library.

---

## What Didn't Work / Lessons Learned

### 1. ❌ No Caching Layer (Backend)

**Problem:**
- Analytics computed **on every request** (slow for users with lots of data)
- Example: Computing "total study time" requires scanning all study sessions
- No Redis/memcached layer

**Impact:**
- Dashboard loads slowly (~2-3 seconds for users with 100+ courses)
- Duplicate queries (frontend calls same endpoint multiple times)

**Fix for BOWEN:**
- Add **Redis** for caching computed analytics
- Use **materialized views** in Postgres for heavy aggregations
- Add `Cache-Control` headers to API responses

```typescript
// Example: Cache analytics for 5 minutes
@CacheKey('course-analytics')
@CacheTTL(300)
async getCourseAnalytics(courseId: string) {
  // ...
}
```

---

### 2. ❌ Overly Complex Frontend State

**Problem:**
- Multiple hooks managing similar state (courses, materials, quizzes)
- No centralized cache invalidation (each hook refetches independently)
- **Every component fetches its own data** → lots of duplicate API calls

**Example:**
```typescript
// Dashboard.tsx
const { data: courses } = useCourses();

// Sidebar.tsx (same page!)
const { data: courses } = useCourses();  // Duplicate fetch!

// Analytics.tsx (same page!)
const { data: courses } = useCourses();  // Another duplicate!
```

**Fix for BOWEN:**
- Use React Query's **shared cache** properly (same `queryKey` = same data)
- Centralize data fetching at **layout level** (fetch once, pass down)
- Use **Suspense + React Query** for better loading states

---

### 3. ❌ No Rate Limiting / Cost Controls

**Problem:**
- AI agent has **no per-user cost tracking**
- No rate limiting on API calls (user can spam AI)
- Voice sessions can run indefinitely (expensive!)

**Risk:**
- One user could rack up $100+ in LLM costs in a day
- DDoS-like behavior (accidental or malicious)

**Fix for BOWEN:**
- Add **Redis-based rate limiting** (express-rate-limit)
- Track **AI cost per user** (store in DB)
- Add **usage limits per tier** (free = 100 messages/day, pro = unlimited)
- Add **voice session time limits** (free = 10min/day, pro = unlimited)

```typescript
// Example: Rate limit AI chat
@UseGuards(RateLimitGuard)
@RateLimit({ points: 10, duration: 60 })  // 10 requests per minute
@Post('/chat')
async chat(@Body() dto: ChatDto) {
  // ...
}
```

---

### 4. ❌ Screen Capture Quality (OCR)

**Problem:**
- Uses **Tesseract.js** (JavaScript OCR library)
- Accuracy is **poor** (~60-70% for complex text)
- Slow (~2-5 seconds to process one screenshot)

**Impact:**
- Students try to ask about screen content → AI gets garbled text → bad responses

**Fix for BOWEN:**
- Use **cloud OCR** (Google Cloud Vision, AWS Textract) for better accuracy
- OR: Use **GPT-4 Vision** (send screenshot directly to AI, no OCR needed)
- OR: Use **macOS Accessibility API** (get text directly from apps without OCR)

```typescript
// Better approach: GPT-4 Vision
const analyzeScreen = async (screenshot: Buffer) => {
  const response = await openai.chat.completions.create({
    model: "gpt-4-vision-preview",
    messages: [{
      role: "user",
      content: [
        { type: "text", text: "What's on this screen?" },
        { type: "image_url", image_url: { url: `data:image/png;base64,${screenshot.toString('base64')}` } }
      ]
    }]
  });
  return response.choices[0].message.content;
};
```

---

### 5. ❌ Inconsistent Error Handling

**Problem:**
- Some errors thrown, some returned as `{ error: string }`
- Frontend has to check both `response.error` and `catch` blocks
- No standardized error format

**Example (inconsistent):**
```typescript
// Some endpoints do this:
return { error: "Course not found" };

// Others do this:
throw new NotFoundException("Course not found");
```

**Fix for BOWEN:**
- **Always throw exceptions** on server (NestJS handles them)
- **Standard error format:**

```typescript
{
  statusCode: 404,
  message: "Course not found",
  error: "Not Found",
  timestamp: "2026-03-07T12:00:00Z"
}
```

---

### 6. ❌ No Database Migrations Version Control

**Problem:**
- Migrations are **just SQL files** in a folder
- No migration runner (like Prisma Migrate, Drizzle, or Alembic)
- No rollback mechanism
- Hard to tell which migrations have been applied

**Fix for BOWEN:**
- Use **Prisma** (if TypeScript) or **Alembic** (if Python) for migrations
- Track migration state in DB (`_prisma_migrations` table)
- Support up/down migrations (rollback)

---

### 7. ❌ No End-to-End Tests

**Problem:**
- Only unit tests for backend services
- No E2E tests (Playwright, Cypress)
- No tests for critical flows (signup → onboarding → create course → chat)

**Risk:**
- Regressions go unnoticed
- Frontend-backend integration bugs

**Fix for BOWEN:**
- Add **Playwright** E2E tests for critical flows
- Run on every PR (CI/CD)

---

### 8. ❌ LiveKit Voice Latency

**Problem:**
- 1-3 second delay from user stops speaking to hearing response
- Feels sluggish compared to human conversation

**Why:**
- STT takes 200-500ms (can't optimize much)
- LLM takes 500-2000ms (depends on response complexity)
- TTS takes 100-300ms

**Partial Fix for BOWEN:**
- Use **faster LLMs** for simple queries (Groq's Llama 3 is 10x faster than GPT-4)
- Add **filler words** while AI thinks ("Hmm, let me think..." as audio)
- Stream TTS (start speaking before full response is generated)

---

### 9. ❌ No Telemetry / Analytics

**Problem:**
- No tracking of feature usage (which modes are popular?)
- No error tracking (Sentry, Rollbar)
- No performance monitoring (slow queries, API latency)

**Impact:**
- Can't make data-driven decisions
- Don't know where users struggle

**Fix for BOWEN:**
- Add **PostHog** or **Mixpanel** for product analytics
- Add **Sentry** for error tracking
- Add **Datadog** or **New Relic** for APM (optional, expensive)

---

### 10. ❌ Hardcoded Configuration

**Problem:**
- Many configs hardcoded in code (API URLs, timeouts, feature flags)
- No feature flags (can't A/B test or gradually roll out features)

**Fix for BOWEN:**
- Use **environment variables** for all config
- Add **feature flags** (LaunchDarkly, Flagsmith, or simple DB-based)

---

## BOWEN-Specific Recommendations

### Architecture: Multi-Personality System

**Core Concept:**
- 4 AI personalities: CAPTAIN, HELEN, SCOUT, TAMARA
- Each personality has its own:
  - System prompt (defines personality)
  - Voice (unique TTS voice)
  - Tools (shared + personality-specific)
  - Memory (long-term context about user)

### Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│                    React/Next.js                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ CAPTAIN  │  │  HELEN   │  │  SCOUT   │  │  TAMARA  │       │
│  │   Chat   │  │   Chat   │  │   Chat   │  │   Chat   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│         │              │              │              │          │
└─────────┼──────────────┼──────────────┼──────────────┼─────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
    ┌─────────────────────────────────────────────────────┐
    │           BOWEN Router (FastAPI)                    │
    │  Routes to appropriate personality based on user    │
    └─────────────────────────────────────────────────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ CAPTAIN │    │  HELEN  │    │  SCOUT  │    │ TAMARA  │
    │ Agent   │    │ Agent   │    │ Agent   │    │ Agent   │
    │         │    │         │    │         │    │         │
    │ Tools:  │    │ Tools:  │    │ Tools:  │    │ Tools:  │
    │ - Tasks │    │ - Career│    │ - Learn │    │ - Mental│
    │ - Goals │    │ - Resume│    │ - Books │    │   Health│
    │ - Team  │    │ - Inter-│    │ - Skills│    │ - Mood  │
    │         │    │   view  │    │ - Hobby │    │ - Habits│
    └─────────┘    └─────────┘    └─────────┘    └─────────┘
          │              │              │              │
          └──────────────┴──────────────┴──────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   PostgreSQL   │
                    │  (User data,   │
                    │   memories,    │
                    │  conversations)│
                    └────────────────┘
```

### Shared vs. Personality-Specific Code

#### Shared Components

```python
# shared/
├── tools/
│   ├── calendar_tools.py      # Google Calendar integration (all)
│   ├── email_tools.py          # Gmail integration (all)
│   ├── web_search_tools.py     # Web search (all)
│   ├── note_tools.py           # Note-taking (all)
│   └── memory_tools.py         # Long-term memory (all)
├── models/
│   └── user.py                 # User data models
├── db/
│   └── client.py               # Database client
└── config.py                   # Shared config
```

#### Personality-Specific Tools

```python
# personalities/captain/
├── tools/
│   ├── task_tools.py           # Task management (Todoist, Linear)
│   ├── project_tools.py        # Project tracking (Notion, Asana)
│   ├── goal_tools.py           # Goal setting + tracking
│   └── team_tools.py           # Team coordination (Slack)
├── prompts.py                  # System prompt for CAPTAIN
└── agent.py                    # Captain agent initialization

# personalities/helen/
├── tools/
│   ├── career_tools.py         # Resume builder, job search
│   ├── interview_tools.py      # Interview prep
│   ├── networking_tools.py     # LinkedIn integration
│   └── learning_tools.py       # Course recommendations
├── prompts.py
└── agent.py

# personalities/scout/
├── tools/
│   ├── learning_tools.py       # Educational resources
│   ├── book_tools.py           # Book recommendations
│   ├── skill_tools.py          # Skill assessments
│   └── hobby_tools.py          # Hobby suggestions
├── prompts.py
└── agent.py

# personalities/tamara/
├── tools/
│   ├── mental_health_tools.py  # Mood tracking, journaling
│   ├── habit_tools.py          # Habit formation
│   ├── mindfulness_tools.py    # Meditation, breathing
│   └── reflection_tools.py     # Daily reflection prompts
├── prompts.py
└── agent.py
```

### System Prompts (Examples)

#### CAPTAIN

```python
CAPTAIN_PROMPT = """
You are CAPTAIN, a disciplined and strategic AI assistant.

**Personality:**
- Military precision (but friendly, not robotic)
- Goal-oriented and action-driven
- Helps users plan, execute, and achieve
- Uses tactical language ("mission", "objective", "execute")
- Confident, direct, supportive

**Capabilities:**
- Task management (create, prioritize, track tasks)
- Goal setting (SMART goals, OKRs)
- Project planning (break down big goals)
- Team coordination (delegate, follow up)
- Productivity coaching (time blocking, focus)

**Tone:**
- Encouraging but firm
- "Let's get it done" energy
- Celebrates wins, pushes through obstacles
- Uses phrases like "Outstanding work", "Mission accomplished", "Let's regroup"

**Example Interactions:**
User: "I need to finish my thesis"
CAPTAIN: "Understood. Let's break this mission into tactical objectives. 
First, what's your deadline? Second, what sections are incomplete? 
We'll create a battle plan with daily targets."

User: "I'm feeling overwhelmed"
CAPTAIN: "I hear you. Overwhelm means we need to simplify and prioritize. 
Let's identify your top 3 objectives this week. Everything else can wait. 
Focus wins battles."
"""
```

#### HELEN

```python
HELEN_PROMPT = """
You are HELEN, a professional and empathetic career coach.

**Personality:**
- Warm but professional (HR/mentor vibe)
- Career-focused (job search, interviews, growth)
- Builds confidence, provides honest feedback
- Knowledgeable about workplace dynamics
- Encouraging without being patronizing

**Capabilities:**
- Resume review and improvement
- Interview preparation (mock interviews, feedback)
- Career path guidance (next steps, skill gaps)
- Networking advice (LinkedIn, cold outreach)
- Workplace navigation (conflict, negotiation, promotions)

**Tone:**
- Supportive and affirming
- Direct when giving feedback
- Uses professional language (not corporate jargon)
- Celebrates progress, normalizes setbacks

**Example Interactions:**
User: "I have an interview tomorrow and I'm nervous"
HELEN: "That's completely normal. Let's channel that energy into preparation. 
Tell me about the role. We'll do a mock interview and I'll give you feedback. 
You'll walk in confident."

User: "I don't know what I want to do career-wise"
HELEN: "Okay, let's explore. What energizes you? What drains you? 
We'll work backwards from there. You don't need a perfect plan—just the next step."
"""
```

#### SCOUT

```python
SCOUT_PROMPT = """
You are SCOUT, a curious and energetic learning companion.

**Personality:**
- Enthusiastic explorer (think friendly park ranger)
- Curious about everything (books, skills, hobbies)
- Makes learning fun and accessible
- Encourages experimentation ("let's try this!")
- Non-judgmental, celebrates curiosity

**Capabilities:**
- Learning resource recommendations (books, courses, videos)
- Skill assessments (identify what to learn next)
- Hobby exploration (find new interests)
- Study plans (structured learning paths)
- Progress tracking (celebrate milestones)

**Tone:**
- Upbeat and encouraging
- Uses exploratory language ("discover", "adventure", "journey")
- Asks lots of questions (Socratic method)
- Celebrates effort over perfection

**Example Interactions:**
User: "I want to learn guitar"
SCOUT: "Awesome! Let's start the adventure. Have you played any instruments before? 
I'll find beginner resources and we can set up a practice plan. 
First goal: learn 3 chords by next week. Ready?"

User: "I don't know what to learn"
SCOUT: "Perfect—that means we get to explore! What's something you've been 
curious about lately? Even just a tiny spark of interest. 
We'll follow the curiosity and see where it leads."
"""
```

#### TAMARA

```python
TAMARA_PROMPT = """
You are TAMARA, a compassionate and insightful mental wellness guide.

**Personality:**
- Warm, empathetic therapist/counselor vibe
- Non-judgmental and patient
- Helps with emotions, stress, habits, reflection
- Validates feelings, offers coping strategies
- Gentle but honest

**Capabilities:**
- Mood tracking (daily check-ins, patterns)
- Journaling prompts (reflection, gratitude)
- Habit formation (build healthy routines)
- Stress management (breathing, mindfulness)
- Mental health resources (when professional help is needed)

**Tone:**
- Calm and soothing
- Validating ("That makes sense", "It's okay to feel...")
- Asks reflective questions
- Never dismissive or toxic positivity

**Important:**
- You are NOT a therapist (remind users if they need professional help)
- Focus on wellness, not diagnosis
- If user expresses self-harm/crisis → provide crisis resources immediately

**Example Interactions:**
User: "I'm feeling really anxious today"
TAMARA: "I'm sorry you're feeling that way. Anxiety is tough. 
Let's take a breath together—4 counts in, hold for 4, 4 counts out. 
Once we're grounded, tell me what's on your mind."

User: "I can't stick to my morning routine"
TAMARA: "Building habits is hard. Let's start small. 
What's one tiny thing you could do tomorrow morning? 
Just one. We'll build from there. Progress over perfection."
"""
```

---

### Personality Switching UI

**Options:**

1. **Tab Interface:**
   ```
   [CAPTAIN] [HELEN] [SCOUT] [TAMARA]
     └─ Active chat
   ```

2. **Sidebar Icons:**
   ```
   ┌────────┐
   │   🎖️   │ CAPTAIN
   │   👩‍💼   │ HELEN
   │   🧭    │ SCOUT
   │   🌸    │ TAMARA
   └────────┘
       │
       └─ Chat interface
   ```

3. **Unified Chat with Personality Picker:**
   ```
   Type a message...
   [CAPTAIN v]  ← Dropdown to switch personality
   ```

**Recommendation:** Start with **sidebar icons** (easiest to understand, clearest separation).

---

### Memory Management (Critical for BOWEN)

Each personality needs **long-term memory** about the user. But memories should be:
- **Personality-specific** (CAPTAIN remembers goals, HELEN remembers career, etc.)
- **Shared when relevant** (all personalities know user's name, preferences)

**Schema:**

```sql
-- User profile (shared across personalities)
users (
  id, email, name, timezone, created_at
)

-- Personality-specific memory
personality_memories (
  id, user_id, personality, key, value,
  created_at, updated_at
)

-- Example rows:
{
  user_id: "user-123",
  personality: "captain",
  key: "current_goal",
  value: "Finish thesis by April 30"
}

{
  user_id: "user-123",
  personality: "helen",
  key: "job_search_status",
  value: "Applied to 5 companies, 2 interviews scheduled"
}

-- Conversations (personality-specific)
conversations (
  id, user_id, personality, created_at
)

messages (
  id, conversation_id, role, content, timestamp
)
```

**Memory Tools:**

```python
# shared/tools/memory_tools.py
class MemoryTools(Toolkit):
    def remember(self, key: str, value: str, personality: str) -> str:
        """Store a memory for later recall.
        
        Args:
            key: Memory key (e.g., "favorite_color", "current_goal")
            value: Memory value
            personality: Which personality this memory belongs to
        """
        supabase.table("personality_memories").upsert({
            "user_id": self.user_id,
            "personality": personality,
            "key": key,
            "value": value
        }).execute()
        return f"Remembered: {key} = {value}"
    
    def recall(self, key: str, personality: str) -> str:
        """Retrieve a stored memory.
        
        Args:
            key: Memory key to retrieve
            personality: Which personality's memory to retrieve
        """
        result = supabase.table("personality_memories")
            .select("value")
            .eq("user_id", self.user_id)
            .eq("personality", personality)
            .eq("key", key)
            .single()
            .execute()
        
        if result.data:
            return result.data["value"]
        return f"No memory found for key: {key}"
    
    def list_memories(self, personality: str) -> str:
        """List all stored memories for this personality."""
        result = supabase.table("personality_memories")
            .select("key, value")
            .eq("user_id", self.user_id)
            .eq("personality", personality)
            .execute()
        
        if not result.data:
            return "No memories stored yet."
        
        memories = "\n".join([f"- {m['key']}: {m['value']}" for m in result.data])
        return f"Stored memories:\n{memories}"
```

**Usage in Conversation:**

```
User (to CAPTAIN): "My goal is to finish my thesis by April 30"

CAPTAIN: "Understood. I'm locking that in as your primary mission. 
I'll remember this and check in on your progress."

[Internally calls: remember("current_goal", "Finish thesis by April 30", "captain")]

---

[Next day]

User (to CAPTAIN): "What should I work on today?"

CAPTAIN: "Your mission is to finish your thesis by April 30. 
Let's break today down. What's the next tactical step?"

[Internally called: recall("current_goal", "captain")]
```

---

### Voice Implementation for BOWEN

Each personality needs a **unique voice**. Recommendations:

| Personality | Voice Style | Cartesia Voice ID (Example) |
|-------------|-------------|------------------------------|
| CAPTAIN | Male, confident, clear | "masculine-confident" |
| HELEN | Female, professional, warm | "feminine-professional" |
| SCOUT | Gender-neutral, energetic | "neutral-enthusiastic" |
| TAMARA | Female, calm, soothing | "feminine-calm" |

**LiveKit Setup:**

```python
# personalities/captain/agent.py
from livekit.agents.pipeline import VoicePipelineAgent

captain_voice_agent = VoicePipelineAgent(
    vad=inference.VAD(model="silero"),
    stt=inference.STT(model="assemblyai/universal"),
    llm=LLMAdapter(captain_agent),
    tts=inference.TTS(
        model="cartesia/sonic-3",
        voice="masculine-confident"  # CAPTAIN voice
    )
)
```

---

### Subscription Pricing Model ($9/mo)

**Free Tier:**
- Text chat: 100 messages/month per personality (400 total)
- Voice: 30 minutes/month total
- 1 active goal/project per personality
- Basic memory (last 30 days)

**Pro Tier ($9/mo):**
- Text chat: Unlimited
- Voice: Unlimited
- Unlimited goals/projects
- Full long-term memory (forever)
- Priority voice latency (faster servers)
- Export conversations

**Implementation:**

```sql
-- Subscription table
subscriptions (
  id, user_id, tier, status,
  current_period_start, current_period_end,
  created_at
)

-- Usage tracking
usage_tracking (
  id, user_id, personality, type,
  count, month, created_at
)

-- type: 'text_message', 'voice_minute', 'goal_created', etc.
```

**Enforcement:**

```python
# Middleware to check usage limits
async def check_usage_limit(user_id: str, action: str):
    subscription = get_subscription(user_id)
    
    if subscription.tier == "pro":
        return True  # No limits
    
    # Check free tier limits
    usage_this_month = get_usage(user_id, action, current_month())
    
    limits = {
        "text_message": 400,
        "voice_minute": 30
    }
    
    if usage_this_month >= limits[action]:
        raise UsageLimitExceeded(
            f"You've reached your {action} limit for this month. "
            f"Upgrade to Pro for unlimited access."
        )
    
    return True
```

---

### Multi-Platform Strategy

**Phase 1 (MVP):** Web only
**Phase 2:** Desktop (Electron/Tauri)
**Phase 3:** Mobile (React Native)

**Shared Backend:**
- Same AI services for all platforms
- Same database
- Same subscription system

**Platform-Specific:**
- **Web:** Full-featured, best for desktop users
- **Desktop:** Global shortcut, system tray, screen capture
- **Mobile:** Push notifications, voice-first, simplified UI

---

## Prioritized Roadmap for BOWEN MVP

### Phase 0: Foundation (2 weeks)

**Goal:** Set up infrastructure

- [ ] Create monorepo structure (packages for each personality + shared)
- [ ] Set up PostgreSQL database (Supabase or self-hosted)
- [ ] Create user auth system (email/password + Google OAuth)
- [ ] Set up basic frontend (Next.js or Vite + React)
- [ ] Deploy infrastructure (Vercel for frontend, Railway for backend)

**Deliverables:**
- User can sign up, log in
- Empty dashboard (no AI yet)
- Database schema for users, conversations, messages, memories

---

### Phase 1: Single Personality (CAPTAIN) (3-4 weeks)

**Goal:** Prove the concept with one personality

- [ ] Implement CAPTAIN agent (Agno + OpenAI)
- [ ] Add basic tools (calendar, tasks, goals, notes)
- [ ] Build chat interface (text only, no voice yet)
- [ ] Implement memory system (remember goals, check-ins)
- [ ] Add streaming responses (SSE)

**Deliverables:**
- User can chat with CAPTAIN
- CAPTAIN can manage tasks, set goals
- CAPTAIN remembers context across sessions

---

### Phase 2: Multi-Personality (4-5 weeks)

**Goal:** Add remaining 3 personalities

- [ ] Implement HELEN agent (career tools)
- [ ] Implement SCOUT agent (learning tools)
- [ ] Implement TAMARA agent (wellness tools)
- [ ] Add personality switching UI (sidebar)
- [ ] Add personality-specific memory isolation
- [ ] Add shared tools (web search, notes) to all personalities

**Deliverables:**
- User can switch between 4 personalities
- Each personality has unique tools and memory
- Personality-specific system prompts working

---

### Phase 3: Voice Integration (3-4 weeks)

**Goal:** Add voice to all personalities

- [ ] Set up LiveKit server (cloud or self-hosted)
- [ ] Implement voice pipeline (VAD + STT + TTS)
- [ ] Add unique voice for each personality
- [ ] Build voice UI (audio player, mic button)
- [ ] Add voice session limits (free tier)

**Deliverables:**
- User can talk to any personality via voice
- Each personality has distinct voice
- Voice sessions tracked for billing

---

### Phase 4: Polish & Features (4-5 weeks)

**Goal:** Make it production-ready

- [ ] Add analytics dashboard (usage stats, goal progress)
- [ ] Add conversation history (search, export)
- [ ] Add integrations (Google Calendar, Todoist, Notion, etc.)
- [ ] Add onboarding flow (personality introduction)
- [ ] Add pricing page + Stripe integration
- [ ] Add mobile-responsive UI

**Deliverables:**
- User can view analytics
- User can export data
- User can upgrade to Pro ($9/mo)
- UI works on mobile browsers

---

### Phase 5: Testing & Launch (2-3 weeks)

**Goal:** Ship it

- [ ] Add E2E tests (Playwright)
- [ ] Load testing (100+ concurrent users)
- [ ] Security audit (pen testing, OWASP)
- [ ] Write documentation (user guide, API docs)
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Beta testing (invite 50-100 users)
- [ ] Public launch

**Deliverables:**
- Stable, tested product
- Ready for 1,000+ users
- Marketing site + documentation

---

### Total Timeline: ~18-23 weeks (4.5-6 months)

**Minimum viable launch:** 16 weeks (4 months) if aggressive

---

## Estimated Complexity & Timeline

### Complexity Breakdown

| Feature | Complexity | Time Estimate | Notes |
|---------|------------|---------------|-------|
| **Auth System** | Low | 1-2 weeks | Use Supabase or Auth0 (don't build from scratch) |
| **Database Schema** | Medium | 1-2 weeks | Design carefully (hard to change later) |
| **Single AI Personality** | Medium | 3-4 weeks | First one is hardest (establishes patterns) |
| **Additional Personalities** | Low-Medium | 1-2 weeks each | Copy pattern from first |
| **Memory System** | Medium | 2-3 weeks | Long-term context is tricky |
| **Voice Integration** | High | 3-4 weeks | LiveKit + TTS/STT integration complex |
| **Frontend (Chat UI)** | Low-Medium | 2-3 weeks | Use component library (shadcn/ui) |
| **Subscription System** | Medium | 2-3 weeks | Stripe integration + usage tracking |
| **Integrations** (Calendar, Todoist, etc.) | Medium | 1-2 weeks each | OAuth + API calls |
| **Mobile App** | High | 6-8 weeks | React Native (if needed) |
| **Testing & QA** | Medium | 2-3 weeks | E2E tests critical |
| **Deployment & DevOps** | Low-Medium | 1-2 weeks | Use managed services (Vercel, Railway) |

---

### Team Recommendations

**For 4-month timeline (aggressive):**

- 1 Full-Stack Engineer (backend + AI agents)
- 1 Frontend Engineer (React + UI/UX)
- 1 DevOps/Infrastructure (part-time)
- 1 Product Manager / Designer (part-time)

**For 6-month timeline (comfortable):**

- 2 Full-Stack Engineers
- 1 Frontend Engineer
- 1 DevOps Engineer (part-time)
- 1 Product Manager
- 1 Designer (UI/UX)

**For solo founder (12-18 months):**

- Start with CAPTAIN only (simplest personality)
- MVP = text chat only (no voice)
- Add personalities one at a time
- Add voice after launch (v2)

---

### Cost Estimates (Monthly, after launch)

**Infrastructure:**
- **Frontend Hosting** (Vercel): $20-50/mo
- **Backend Hosting** (Railway, Render): $50-100/mo
- **Database** (Supabase Pro): $25/mo
- **LiveKit** (Cloud): $100-500/mo (depends on usage)
- **Redis** (Upstash): $20-40/mo
- **Total Infrastructure:** ~$200-700/mo

**AI/ML Services (per user):**
- **OpenAI GPT-4o-mini:** ~$0.10-0.30 per user per month (text)
- **Voice (STT + TTS):** ~$1-2 per hour of voice usage
- **Total per user:** $0.50-2/mo (text), +$1-2 per voice hour

**At 1,000 users (50% free, 50% pro):**
- **AI costs:** $500-2,000/mo (depends heavily on usage)
- **Infrastructure:** $500-1,000/mo
- **Total:** ~$1,000-3,000/mo

**Revenue at 1,000 users:**
- 500 pro users × $9/mo = **$4,500/mo**
- **Profit margin:** ~50-70% (assuming $1,500-2,000 costs)

---

### Risk Factors

1. **Voice Costs Too High:**
   - **Mitigation:** Strict free tier limits, aggressive pro tier push
   - **Alternative:** Offer voice as add-on ($5/mo extra)

2. **LLM Costs Explode:**
   - **Mitigation:** Use cheaper models (Groq, OpenRouter) for non-critical tasks
   - **Alternative:** Rate limit free tier heavily

3. **User Retention Low:**
   - **Mitigation:** Strong onboarding, personality "bonding", push notifications
   - **Metrics:** Track DAU/MAU, conversation frequency

4. **Personality Confusion:**
   - **Mitigation:** Clear UI separation, unique voices, different icons/colors
   - **Alternative:** Start with 2 personalities (CAPTAIN + HELEN), expand later

5. **Privacy Concerns:**
   - **Mitigation:** Clear privacy policy, user data export, conversation deletion
   - **Compliance:** GDPR, CCPA compliance from day 1

---

## Key Takeaways for BOWEN

### Do This (High Value)

1. ✅ **Use Agno or similar framework** (tool-based AI architecture scales well)
2. ✅ **Keep AI agents in Python** (better ecosystem for LLMs/voice)
3. ✅ **Start with text chat only** (voice is expensive, add later)
4. ✅ **Implement memory system early** (critical for personality bonding)
5. ✅ **Use Supabase for MVP** (auth + DB + RLS out of the box)
6. ✅ **Add React Query** (data fetching game changer)
7. ✅ **Monorepo from day 1** (easier to share code between personalities)
8. ✅ **Rate limit aggressively** (protect against cost explosions)

### Avoid This (Pain Points from Remi)

1. ❌ **No caching layer** → Add Redis early
2. ❌ **No cost tracking** → Track AI usage per user from day 1
3. ❌ **Complex frontend state** → Centralize data fetching
4. ❌ **No E2E tests** → Add Playwright for critical flows
5. ❌ **Hardcoded config** → Environment variables + feature flags
6. ❌ **Poor OCR** → Use GPT-4 Vision instead of Tesseract

### Architecture Recommendations

**Backend:**
- **Python (FastAPI) for AI agents** (CAPTAIN, HELEN, SCOUT, TAMARA)
- **Node.js (NestJS) for CRUD API** (optional, if you need it)
- **PostgreSQL (Supabase) for database**
- **Redis for caching + rate limiting**

**Frontend:**
- **Next.js or Vite + React** (Next.js if you want SSR/SEO)
- **React Query for data fetching**
- **Radix UI + Tailwind for components**
- **Socket.io or SSE for real-time chat**

**Voice:**
- **LiveKit for infrastructure**
- **AssemblyAI or Deepgram for STT**
- **Cartesia or ElevenLabs for TTS**
- **Unique voice per personality**

**Deployment:**
- **Vercel for frontend**
- **Railway or Render for Python backend**
- **Supabase for database**
- **LiveKit Cloud for voice**

---

## Appendix: Code Examples

### Example: BOWEN Router (FastAPI)

```python
# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from personalities.captain.agent import create_captain_agent
from personalities.helen.agent import create_helen_agent
from personalities.scout.agent import create_scout_agent
from personalities.tamara.agent import create_tamara_agent

app = FastAPI()

# Agent registry
agents = {
    "captain": create_captain_agent,
    "helen": create_helen_agent,
    "scout": create_scout_agent,
    "tamara": create_tamara_agent
}

class ChatRequest(BaseModel):
    personality: str
    message: str
    user_id: str
    session_id: str | None = None

@app.post("/chat")
async def chat(request: ChatRequest):
    # Check usage limits
    await check_usage_limit(request.user_id, "text_message")
    
    # Get appropriate agent
    if request.personality not in agents:
        raise HTTPException(404, "Personality not found")
    
    agent = agents[request.personality](request.user_id)
    
    # Get response
    response = await agent.chat(request.message, request.session_id)
    
    # Track usage
    await track_usage(request.user_id, request.personality, "text_message")
    
    return {"response": response}

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint (Server-Sent Events)"""
    # Similar to above but yields events
    pass
```

---

### Example: Personality Agent Creation

```python
# personalities/captain/agent.py
from agno import Agent
from shared.tools import CalendarTools, EmailTools, NoteTools
from personalities.captain.tools import TaskTools, GoalTools, ProjectTools
from personalities.captain.prompts import CAPTAIN_PROMPT

def create_captain_agent(user_id: str):
    # Shared tools (all personalities have these)
    shared_tools = [
        CalendarTools(user_id),
        EmailTools(user_id),
        NoteTools(user_id)
    ]
    
    # CAPTAIN-specific tools
    captain_tools = [
        TaskTools(user_id),
        GoalTools(user_id),
        ProjectTools(user_id)
    ]
    
    # Create agent
    agent = Agent(
        name="CAPTAIN",
        model="openai:gpt-4o-mini",
        instructions=CAPTAIN_PROMPT,
        tools=shared_tools + captain_tools,
        storage=History(db_file=f"tmp/captain_{user_id}.db")
    )
    
    return agent
```

---

### Example: Task Tool Implementation

```python
# personalities/captain/tools/task_tools.py
from agno.tools.toolkit import Toolkit

class TaskTools(Toolkit):
    def __init__(self, user_id: str):
        super().__init__(name="task_tools")
        self.user_id = user_id
        
        self.register(self.create_task)
        self.register(self.list_tasks)
        self.register(self.complete_task)
        self.register(self.prioritize_tasks)
    
    def create_task(self, title: str, due_date: str | None = None, priority: str = "medium") -> str:
        """Create a new task.
        
        Args:
            title: Task title
            due_date: Optional due date (ISO format: YYYY-MM-DD)
            priority: high, medium, or low
        """
        # Insert into database
        task = supabase.table("tasks").insert({
            "user_id": self.user_id,
            "personality": "captain",
            "title": title,
            "due_date": due_date,
            "priority": priority,
            "status": "pending"
        }).execute()
        
        return f"Task created: {title} (Priority: {priority})"
    
    def list_tasks(self, status: str = "pending") -> str:
        """List tasks by status.
        
        Args:
            status: pending, in_progress, or completed
        """
        tasks = supabase.table("tasks")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("personality", "captain")
            .eq("status", status)
            .order("priority", desc=True)
            .execute()
        
        if not tasks.data:
            return f"No {status} tasks."
        
        task_list = "\n".join([
            f"- [{t['priority']}] {t['title']} (Due: {t['due_date'] or 'No deadline'})"
            for t in tasks.data
        ])
        
        return f"Your {status} tasks:\n{task_list}"
    
    def complete_task(self, task_id: str) -> str:
        """Mark a task as completed.
        
        Args:
            task_id: ID of the task to complete
        """
        supabase.table("tasks").update({
            "status": "completed",
            "completed_at": "now()"
        }).eq("id", task_id).execute()
        
        return f"Task completed! Outstanding work."
    
    def prioritize_tasks(self) -> str:
        """Get a prioritized list of tasks to work on today."""
        # Complex logic: sort by due date, priority, dependencies
        tasks = supabase.table("tasks")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("status", "pending")
            .execute()
        
        # Sort by urgency (due soon + high priority = top)
        sorted_tasks = sort_by_urgency(tasks.data)
        
        top_3 = sorted_tasks[:3]
        
        return f"Focus on these 3 tasks today:\n" + "\n".join([
            f"{i+1}. {t['title']}"
            for i, t in enumerate(top_3)
        ])
```

---

## Conclusion

Remi Guardian provides a **solid foundation** for understanding how to build a multi-modal AI assistant. Key lessons for BOWEN:

1. **Architecture:** Separate AI service (Python) + CRUD backend (Node/Python) + database (Postgres)
2. **AI Framework:** Use tool-based approach (Agno, LangChain) for extensibility
3. **Voice:** LiveKit + STT + TTS works well, but is expensive (tier voice carefully)
4. **Memory:** Long-term memory is critical for personality bonding
5. **Cost Management:** Track usage per user, rate limit aggressively, consider tiered pricing

**Timeline:** 4-6 months for MVP with 4 personalities (text + voice)  
**Team:** 2-3 engineers for comfortable timeline  
**Cost:** ~$1,000-3,000/mo at 1,000 users  
**Revenue:** ~$4,500/mo at 1,000 users (50% pro)

**Next Steps:**
1. Set up monorepo structure
2. Build CAPTAIN personality first (prove the concept)
3. Add remaining personalities (reuse patterns)
4. Add voice (after MVP validation)
5. Launch beta → iterate → scale

---

**Research compiled by:** Captain (BOWEN Subagent)  
**Date:** March 7, 2026  
**Contact:** Ready to build BOWEN 🚀
