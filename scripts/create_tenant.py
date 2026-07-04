#!/usr/bin/env python3
"""
scripts/create_tenant.py — Provision a new tenant end to end.

    .venv/bin/python scripts/create_tenant.py <username> [display name]

Creates:
  1. The user account in memory/users.db (API key printed ONCE, hash at rest)
  2. The isolated stores:  memory/users/<id>/{bowen.db, chroma/, profile.md}
  3. The tenant config scaffold:  memory/tenants/<id>.yaml
     (quiet hours, alert channels, caregiver phone, elder_voice — config,
      never code)

The API key is shown exactly once. It is not recoverable — only its SHA-256
hash is stored. Regenerate via POST /api/admin/users/<id>/regen if lost.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from memory.multi_store import MultiUserStore
from memory.users import UserManager

TENANT_YAML_TEMPLATE = """\
# Tenant config for {username} — edit freely; config, not code.
# Missing keys fall back to defaults (critical 24/7, high 7-23, med/low 9-21).

quiet_hours:
  high:   {{start: 7, end: 23}}
  medium: {{start: 9, end: 21}}
  low:    {{start: 9, end: 21}}

# Alert delivery order of preference. Options: twilio_whatsapp, twilio_sms,
# twilio_voice, log. Twilio channels need caregiver_phone below.
channels: [log]

caregiver_name: ""
caregiver_phone: ""

# true = elder-facing GENI replies use ElevenLabs instead of local Kokoro
elder_voice: false
"""


async def create_tenant(username: str, display_name: str = "") -> None:
    config = Config()
    display_name = display_name or username

    user_manager = UserManager(config.USERS_DB_PATH)
    await user_manager.initialize()

    try:
        user = await user_manager.create_user(username, display_name)
    except ValueError as e:
        print(f"✗ {e}")
        await user_manager.close()
        sys.exit(1)

    user_id = user["user_id"]

    # Isolated stores (SQLite + Chroma dir + starter profile)
    multi_store = MultiUserStore(config.USERS_BASE_DIR, config)
    store = await multi_store.get_or_create(user_id, username, display_name)
    await store.close()

    # Tenant alert/voice config scaffold
    config.TENANTS_DIR.mkdir(parents=True, exist_ok=True)
    tenant_yaml = config.TENANTS_DIR / f"{user_id}.yaml"
    if not tenant_yaml.exists():
        tenant_yaml.write_text(TENANT_YAML_TEMPLATE.format(username=username))

    await user_manager.close()

    user_dir = config.USERS_BASE_DIR / user_id
    print(f"""
✓ Tenant provisioned: {display_name} ({user_id})

  Isolated stores:  {user_dir}/
                      bowen.db   (SQLite — conversations, tasks, memories)
                      chroma/    (vector memory)
                      profile.md (identity, injected into every prompt)
  Tenant config:    {tenant_yaml}
  Shared knowledge: memory/shared_knowledge.md (read-only inheritance)

  API KEY (shown once, hash-only at rest — copy it NOW):

      {user['api_key']}

  Connect:  ws://<host>:8000/ws/chat?key=<API_KEY>
  REST:     X-Api-Key: <API_KEY>
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: create_tenant.py <username> [display name]")
        sys.exit(1)
    asyncio.run(create_tenant(sys.argv[1], " ".join(sys.argv[2:])))
