"""
tests/test_geni_integration.py — The merge, proven end to end.

1. A simulated fall_confirmed event travels GENI → bus → TAMARA → alert
   gate → (mocked) Twilio pathway.
2. The elder_voice toggle flips GENI speech between Kokoro and ElevenLabs
   from tenant CONFIG, not code.
3. The /internal/alerts intake gates events exactly like the library gate.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.alerts as alerts_mod
from agents.geni import GENIAgent
from agents.tamara import TamaraAgent
from bus.message_bus import MessageBus
from bus.schema import FallConfirmedPayload
from core.alerts import AlertGate
from tests.conftest import make_config


class MockTwilioChannel:
    """Stands in for the real TwilioWhatsAppChannel — records, never dials."""

    name = "twilio_whatsapp"

    def __init__(self):
        self.sent: list = []

    async def send(self, event, tenant) -> None:
        self.sent.append((event, tenant))


@pytest.fixture
def twilio(tmp_path):
    """Process-wide gate wired to a mocked Twilio channel for one tenant."""
    channel = MockTwilioChannel()
    (tmp_path / "casa-oyimi.yaml").write_text(
        "channels: [twilio_whatsapp]\ncaregiver_phone: '+15550001111'\n"
    )
    gate = AlertGate(tmp_path, channels={"twilio_whatsapp": channel})
    alerts_mod.set_gate(gate)
    yield channel
    alerts_mod.set_gate(None)


class TestFallEventEndToEnd:
    async def test_fall_confirmed_travels_geni_bus_tamara_twilio(self, store, twilio):
        config = make_config()
        bus = MessageBus()
        geni = GENIAgent(config, store, bus)
        tamara = TamaraAgent(config, store, bus)

        # 1. GENI's monitoring core confirms a fall → typed payload onto the bus
        fall = FallConfirmedPayload(
            tenant_id="casa-oyimi",
            patient_name="Margaret Hale",
            message="🚨 Margaret has fallen. I've detected a fall and am checking on her now. Please call her IMMEDIATELY. - GENI",
            confidence=0.94,
            detected_at="2026-07-03T03:12:00",
        )
        await geni.forward_event(fall)

        # 2. The bus carries it to TAMARA at urgent priority
        msg = await bus.receive("TAMARA", timeout=0.1)
        assert msg is not None
        assert msg.sender == "GENI"
        assert msg.priority == 5
        assert isinstance(msg.payload, FallConfirmedPayload)

        # 3. TAMARA routes it through the alert gate to the Twilio pathway
        result = await tamara.handle(msg)
        assert "deliver" in result

        # 4. The mocked Twilio channel received it — critical passes at any hour
        assert len(twilio.sent) == 1
        event, tenant = twilio.sent[0]
        assert event.type == "fall_detected"
        assert event.priority == "critical"
        assert "Margaret has fallen" in event.message
        assert tenant.caregiver_phone == "+15550001111"

    async def test_duplicate_fall_within_cooldown_does_not_double_page(self, store, twilio):
        config = make_config()
        bus = MessageBus()
        geni = GENIAgent(config, store, bus)
        tamara = TamaraAgent(config, store, bus)

        fall = FallConfirmedPayload(
            tenant_id="casa-oyimi", patient_name="Margaret Hale",
            message="fall!", detected_at="2026-07-03T03:12:00",
        )
        for _ in range(2):
            await geni.forward_event(fall)
            msg = await bus.receive("TAMARA", timeout=0.1)
            await tamara.handle(msg)

        # Gate dedup: one page, not two, for the same confirmed fall
        assert len(twilio.sent) == 1


# ── /internal API: elder_voice toggle + alerts intake ─────────────────────────


class FakeKokoro:
    ready = True

    def synthesize_wav(self, text: str) -> bytes:
        return b"RIFFfakewav" + text.encode()[:8]


def make_internal_app(tmp_path, tenants: dict[str, str]) -> TestClient:
    from api.internal import router

    for name, yaml_text in tenants.items():
        (tmp_path / f"{name}.yaml").write_text(yaml_text)

    app = FastAPI()
    app.include_router(router)
    app.state.config = make_config(TENANTS_DIR=tmp_path, GENI_API_KEY="")
    app.state.tts_engine = FakeKokoro()
    return TestClient(app)


class TestElderVoiceToggle:
    def test_default_tenant_speech_is_kokoro(self, tmp_path):
        client = make_internal_app(tmp_path, {"default": "elder_voice: false\n"})
        resp = client.post("/internal/tts", json={
            "text": "Good morning, Margaret", "tenant_id": "default", "elder_facing": True,
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("audio/wav")
        assert resp.headers["x-tts-engine"] == "kokoro"
        assert resp.content.startswith(b"RIFF")

    def test_elder_voice_flag_switches_elder_facing_to_elevenlabs(self, tmp_path):
        client = make_internal_app(tmp_path, {"casa": "elder_voice: true\n"})
        resp = client.post("/internal/tts", json={
            "text": "Good morning, Margaret", "tenant_id": "casa", "elder_facing": True,
        })
        assert resp.status_code == 200
        assert resp.json() == {"engine": "elevenlabs"}

    def test_non_elder_facing_speech_stays_kokoro_even_with_flag(self, tmp_path):
        # elder_voice switches ONLY elder-facing replies; system speech stays local
        client = make_internal_app(tmp_path, {"casa": "elder_voice: true\n"})
        resp = client.post("/internal/tts", json={
            "text": "Caregiver report ready", "tenant_id": "casa", "elder_facing": False,
        })
        assert resp.status_code == 200
        assert resp.headers["x-tts-engine"] == "kokoro"


class TestAlertsIntake:
    def test_geni_backend_alert_flows_through_gate(self, tmp_path, twilio):
        client = make_internal_app(tmp_path, {})
        resp = client.post("/internal/alerts", json={
            "type": "geni_send",
            "priority": "high",
            "message": "Pills taken 👍",
            "tenant_id": "casa-oyimi",
            "force": True,
            "details": {"to_phone": "+15550001111", "channel": "twilio_whatsapp"},
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "deliver"
        assert len(twilio.sent) == 1
