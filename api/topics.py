"""
api/topics.py — Topics (Notebooks) CRUD + conversations + messages.

Topics are the organizational layer — like Claude Projects.
Each topic contains conversations, which contain messages.

Routes:
  GET    /api/topics                          — list all topics
  POST   /api/topics                          — create topic
  GET    /api/topics/{topic_id}               — get topic details
  PATCH  /api/topics/{topic_id}/instructions  — update topic instructions
  GET    /api/topics/{topic_id}/conversations — list conversations in topic
  POST   /api/topics/{topic_id}/conversations — create conversation in topic
  GET    /api/conversations/{conv_id}/messages — paginated messages
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

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
async def list_topics(request: Request) -> dict:
    memory = request.app.state.memory
    topics = await memory.get_topics()
    return {"topics": topics}


@router.post("/topics", status_code=201)
async def create_topic(request: Request, body: CreateTopicBody) -> dict:
    memory = request.app.state.memory
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
async def get_topic(request: Request, topic_id: str) -> dict:
    memory = request.app.state.memory
    topic = await memory.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.patch("/topics/{topic_id}/instructions")
async def update_instructions(
    request: Request,
    topic_id: str,
    body: UpdateInstructionsBody,
) -> dict:
    """Update per-topic instructions injected into every agent system prompt."""
    memory = request.app.state.memory
    topic = await memory.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    await memory.update_topic_instructions(topic_id, body.instructions)
    return {"ok": True}


# ── Conversation routes ───────────────────────────────────────────────────────

@router.get("/topics/{topic_id}/conversations")
async def list_conversations(request: Request, topic_id: str) -> dict:
    memory = request.app.state.memory
    convs = await memory.get_conversations(topic_id)
    return {"conversations": convs}


@router.post("/topics/{topic_id}/conversations", status_code=201)
async def create_conversation(
    request: Request,
    topic_id: str,
    body: CreateConversationBody,
) -> dict:
    memory = request.app.state.memory
    topic = await memory.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    conv_id = await memory.create_conversation(topic_id=topic_id, title=body.title)
    return {"conversation_id": conv_id}


# ── Message routes ────────────────────────────────────────────────────────────

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    request: Request,
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    memory = request.app.state.memory
    messages = await memory.get_messages(conversation_id, limit=limit, offset=offset)
    return {"messages": messages, "conversation_id": conversation_id}
