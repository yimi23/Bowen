"""
api/internal.py — Internal service surface for the GENI backend (and any
future supervised sidecar). Localhost traffic between BOWEN and its own
child processes.

POST /internal/llm/complete   GENI's brain + vision ride the LLMProvider
                              seam. Structured outputs (PILL_SCHEMA /
                              SCENE_SCHEMA) via output_schema.
POST /internal/tts            Elder speech. Kokoro by default; if the
                              tenant's elder_voice flag is on and the call
                              is elder-facing, the caller is told to use
                              its ElevenLabs path instead.
POST /internal/alerts         The alerts gate intake. GENI's notifyCaregiver
                              posts here — Twilio only ever fires inside
                              core/alert_delivery.py.

Auth: x-internal-key must match config.GENI_API_KEY when one is set.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel

from core.alerts import AlertEvent, get_gate
from core.tenants import load_tenant
from llm import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


def _check_key(request: Request, key: Optional[str]) -> None:
    expected = request.app.state.config.GENI_API_KEY
    if expected and key != expected:
        raise HTTPException(status_code=401, detail="bad internal key")


# ── LLM proxy (the seam, over HTTP) ────────────────────────────────────────────


class CompleteRequest(BaseModel):
    messages: list[dict]
    model: str = "haiku"                       # alias or explicit id
    max_tokens: int = 1024
    system: Optional[str] = None
    temperature: Optional[float] = None
    output_schema: Optional[dict] = None


@router.post("/llm/complete")
async def llm_complete(
    body: CompleteRequest,
    request: Request,
    x_internal_key: Optional[str] = Header(default=None),
) -> dict:
    _check_key(request, x_internal_key)
    config = request.app.state.config
    provider = get_provider("anthropic", config)
    model = {"haiku": config.HAIKU_MODEL, "sonnet": config.SONNET_MODEL}.get(body.model, body.model)

    response = await provider.complete(
        body.messages,
        model=model,
        max_tokens=body.max_tokens,
        system=body.system,
        temperature=body.temperature,
        output_schema=body.output_schema,
    )
    return {
        "text": response.text,
        "structured": response.structured,
        "stop_reason": response.stop_reason,
    }


# ── TTS (Kokoro default, elder_voice tenant flag) ─────────────────────────────


class TTSRequest(BaseModel):
    text: str
    tenant_id: str = "default"
    elder_facing: bool = False


@router.post("/tts")
async def tts(
    body: TTSRequest,
    request: Request,
    x_internal_key: Optional[str] = Header(default=None),
):
    _check_key(request, x_internal_key)
    config = request.app.state.config
    tenant = load_tenant(body.tenant_id, config.TENANTS_DIR)

    # The elder_voice flag is per-tenant CONFIG: only elder-facing replies
    # switch to ElevenLabs, and only when the tenant opted in.
    if body.elder_facing and tenant.elder_voice:
        return {"engine": "elevenlabs"}

    engine = getattr(request.app.state, "tts_engine", None)
    if engine is None or not engine.ready:
        raise HTTPException(status_code=503, detail="kokoro engine unavailable")

    wav = await asyncio.to_thread(engine.synthesize_wav, body.text)
    return Response(content=wav, media_type="audio/wav", headers={"x-tts-engine": "kokoro"})


# ── Alerts gate intake ─────────────────────────────────────────────────────────


class AlertIn(BaseModel):
    type: str
    priority: str = "medium"
    message: str
    tenant_id: str = "default"
    dedup_key: Optional[str] = None
    should_call: bool = False
    force: bool = False
    details: dict[str, Any] = {}


@router.post("/alerts")
async def alerts_intake(
    body: AlertIn,
    request: Request,
    x_internal_key: Optional[str] = Header(default=None),
) -> dict:
    _check_key(request, x_internal_key)
    decision = await get_gate().dispatch(AlertEvent(
        type=body.type,
        priority=body.priority,
        message=body.message,
        tenant_id=body.tenant_id,
        dedup_key=body.dedup_key,
        should_call=body.should_call,
        force=body.force,
        details=body.details,
    ))
    return {"decision": decision.decision.value, "reason": decision.reason}
