"""
core/alert_delivery.py — The gate's delivery layer.

THE ONLY FILE in the OS allowed to call Twilio or any push channel.
Everything upstream goes through core/alerts.AlertGate, which owns the
deliver/defer/suppress decision. If you are adding a new way to buzz a
human's phone, it goes here and nowhere else.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TWILIO_API = "https://api.twilio.com/2010-04-01"


class TwilioWhatsAppChannel:
    """Caregiver WhatsApp via Twilio REST (GENI's proven channel)."""

    name = "twilio_whatsapp"

    def __init__(self, account_sid: str = "", auth_token: str = "", from_number: str = "") -> None:
        self._sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self._token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from = from_number or os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    async def send(self, event, tenant) -> None:
        to = event.details.get("to_phone") or tenant.caregiver_phone
        if not (self._sid and self._token and self._from and to):
            raise RuntimeError("twilio_whatsapp not configured for this tenant")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TWILIO_API}/Accounts/{self._sid}/Messages.json",
                auth=(self._sid, self._token),
                data={
                    "From": f"whatsapp:{self._from}",
                    "To": f"whatsapp:{to}",
                    "Body": event.message,
                },
            )
            resp.raise_for_status()


class TwilioSMSChannel:
    name = "twilio_sms"

    def __init__(self, account_sid: str = "", auth_token: str = "", from_number: str = "") -> None:
        self._sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self._token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from = from_number or os.getenv("TWILIO_PHONE_NUMBER", "")

    async def send(self, event, tenant) -> None:
        to = event.details.get("to_phone") or tenant.caregiver_phone
        if not (self._sid and self._token and self._from and to):
            raise RuntimeError("twilio_sms not configured for this tenant")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TWILIO_API}/Accounts/{self._sid}/Messages.json",
                auth=(self._sid, self._token),
                data={
                    "From": self._from,
                    "To": to,
                    "Body": event.message,
                },
            )
            resp.raise_for_status()


class TwilioVoiceChannel:
    """Escalation voice call (GENI's TwiML preserved verbatim)."""

    name = "twilio_voice"

    def __init__(self, account_sid: str = "", auth_token: str = "", from_number: str = "") -> None:
        self._sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self._token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from = from_number or os.getenv("TWILIO_PHONE_NUMBER", "")

    async def send(self, event, tenant) -> None:
        to = event.details.get("to_phone") or tenant.caregiver_phone
        if not (self._sid and self._token and self._from and to):
            raise RuntimeError("twilio_voice not configured for this tenant")
        caller = event.details.get("caller_name", "GENI")
        patient = event.details.get("patient_name", "the patient")
        twiml = (
            "<Response>"
            f'<Say voice="Polly.Joanna">Hello, this is {caller} calling on behalf of {patient}. '
            f"{event.message}</Say>"
            '<Pause length="2"/>'
            f'<Say voice="Polly.Joanna">If this is an emergency, please check on {patient.split(" ")[0]} '
            "immediately. You can also reply to this number via text message.</Say>"
            "</Response>"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TWILIO_API}/Accounts/{self._sid}/Calls.json",
                auth=(self._sid, self._token),
                data={"From": self._from, "To": to, "Twiml": twiml},
            )
            resp.raise_for_status()


class LogChannel:
    """Dev/default channel: the alert lands in the log, nowhere else."""

    name = "log"

    async def send(self, event, tenant) -> None:
        logger.info(
            "[ALERT:%s] tenant=%s priority=%s | %s",
            event.type, tenant.tenant_id, event.priority, event.message,
        )


def default_channels() -> dict:
    return {
        "twilio_whatsapp": TwilioWhatsAppChannel(),
        "twilio_sms": TwilioSMSChannel(),
        "twilio_voice": TwilioVoiceChannel(),
        "log": LogChannel(),
    }
