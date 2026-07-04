"""
core/tenants.py — Per-tenant configuration. Config, not code.

Each tenant (a household, a resident, a user) gets one YAML file at
memory/tenants/<tenant_id>.yaml controlling how the OS is allowed to
interrupt its humans:

    quiet_hours:
      high:   {start: 7, end: 23}     # hour ranges when this priority may send
      medium: {start: 9, end: 21}
      low:    {start: 9, end: 21}
    channels: [twilio_whatsapp]        # delivery order of preference
    caregiver_phone: "+15551234567"
    elder_voice: false                 # true → elder-facing TTS uses ElevenLabs

Missing file or missing keys fall back to DEFAULTS — which reproduce GENI's
proven gate semantics exactly (critical 24/7, high 7-23, medium/low 9-21).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULT_QUIET_HOURS = {
    "high": {"start": 7, "end": 23},
    "medium": {"start": 9, "end": 21},
    "low": {"start": 9, "end": 21},
}


@dataclass
class TenantConfig:
    tenant_id: str = "default"
    quiet_hours: dict = field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_QUIET_HOURS.items()})
    channels: list[str] = field(default_factory=lambda: ["log"])
    caregiver_phone: str = ""
    caregiver_name: str = ""
    elder_voice: bool = False

    def window(self, priority: str) -> tuple[int, int]:
        hours = self.quiet_hours.get(priority, DEFAULT_QUIET_HOURS.get(priority, {"start": 9, "end": 21}))
        return int(hours["start"]), int(hours["end"])


def load_tenant(tenant_id: str, tenants_dir: Path) -> TenantConfig:
    """Load a tenant's config; absent file → defaults (GENI semantics)."""
    path = tenants_dir / f"{tenant_id}.yaml"
    if not path.exists():
        return TenantConfig(tenant_id=tenant_id)
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:
        logger.error("Tenant config %s unreadable (%s) — using defaults", path, exc)
        return TenantConfig(tenant_id=tenant_id)

    cfg = TenantConfig(tenant_id=tenant_id)
    if isinstance(raw.get("quiet_hours"), dict):
        for prio, hours in raw["quiet_hours"].items():
            if prio in cfg.quiet_hours and isinstance(hours, dict):
                cfg.quiet_hours[prio].update(hours)
    if isinstance(raw.get("channels"), list):
        cfg.channels = [str(c) for c in raw["channels"]]
    cfg.caregiver_phone = str(raw.get("caregiver_phone", "") or "")
    cfg.caregiver_name = str(raw.get("caregiver_name", "") or "")
    cfg.elder_voice = bool(raw.get("elder_voice", False))
    return cfg
