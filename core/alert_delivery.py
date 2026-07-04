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
        if not (self._sid and self._token and self._from and tenant.caregiver_phone):
            raise RuntimeError("twilio_whatsapp not configured for this tenant")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TWILIO_API}/Accounts/{self._sid}/Messages.json",
                auth=(self._sid, self._token),
                data={
                    "From": f"whatsapp:{self._from}",
                    "To": f"whatsapp:{tenant.caregiver_phone}",
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
        if not (self._sid and self._token and self._from and tenant.caregiver_phone):
            raise RuntimeError("twilio_sms not configured for this tenant")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TWILIO_API}/Accounts/{self._sid}/Messages.json",
                auth=(self._sid, self._token),
                data={
                    "From": self._from,
                    "To": tenant.caregiver_phone,
                    "Body": event.message,
                },
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
        "log": LogChannel(),
    }
