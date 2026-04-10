"""
api/topics.py — Topics (Notebooks) CRUD + conversations + messages.

Topics are the organizational layer — like Claude Projects.
Each topic contains conversations, which contain messages.

All endpoints require X-Api-Key header authentication and operate on the
authenticated user's memory store.

Routes:
  GET    /api/topics                           — list all topics
  POST   /api/topics                           — create topic
  GET    /api/topics/{topic_id}                — get topic details
  PATCH  /api/topics/{topic_id}/instructions   — update topic instructions
  GET    /api/topics/{topic_id}/conversations  — list conversations in topic
  POST   /api/topics/{topic_id}/conversations  — create conversation in topic
  GET    /api/conversations/{conv_id}/messages — paginated messages
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.deps import get_user_memory
from memory.store import MemoryStore

router = APIRouter(prefix="/api")


# ── Request bodies ────────────────────────────────────────────────────────────

class CreateTopicBody(BaseModel):
    name: str
    description: str = ""
    color: str = "#C4963A"
    instructions: str = ""


class UpdateInstructionsBody(BaseModel):
    instructions: str


class CreateConversationBody(BaseModel):
    title: str = "New conversation"


# ── Topic routes ──────────────────────────────────────────────────────────────

@router.get("/topics")
async def list_topics(
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    topics = await memory.get_topics()
    return {"topics": topics}


@router.post("/topics", status_code=201)
async def create_topic(
    body: CreateTopicBody,
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Topic name cannot be empty")
    topic_id = await memory.create_topic(
        name=body.name.strip(),
        description=body.description,
        color=body.color,
        instructions=body.instructions,
    )
    return {"topic_id": topic_id}


@router.get("/topics/{topic_id}")
async def get_topic(
    topic_id: str,
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    topic = await memory.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.patch("/topics/{topic_id}/instructions")
async def update_instructions(
    topic_id: str,
    body: UpdateInstructionsBody,
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    """Update per-topic instructions injected into every agent system prompt."""
    topic = await memory.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    await memory.update_topic_instructions(topic_id, body.instructions)
    return {"ok": True}


# ── Conversation routes ───────────────────────────────────────────────────────

@router.get("/topics/{topic_id}/conversations")
async def list_conversations(
    topic_id: str,
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    convs = await memory.get_conversations(topic_id)
    return {"conversations": convs}


@router.post("/topics/{topic_id}/conversations", status_code=201)
async def create_conversation(
    topic_id: str,
    body: CreateConversationBody,
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    topic = await memory.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    conv_id = await memory.create_conversation(topic_id=topic_id, title=body.title)
    return {"conversation_id": conv_id}


# ── Message routes ────────────────────────────────────────────────────────────

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    messages = await memory.get_messages(conversation_id, limit=limit, offset=offset)
    return {"messages": messages, "conversation_id": conversation_id}
