"""
tests/test_tenancy.py — True tenancy, proven by trying to break it.

Every test here is an attempted crossing of a tenant wall:
  SQLite, Chroma, profile, prompt, alert-gate history, quiet hours,
  shared knowledge, API keys, rate limits.
The walls must hold. This file is the evidence a per-contract deployment
("supply-ready", never a shared free-for-all) stands on.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

import memory.store as store_mod
from core.alerts import AlertEvent, AlertGate, Decision, evaluate_alert
from memory.multi_store import MultiUserStore
from memory.users import RateLimited, UserManager, _hash_key
from tests.conftest import FakeCollection, make_config


# ── Fixtures: two live tenants with separate everything ───────────────────────


@pytest.fixture
async def two_tenants(tmp_path, monkeypatch):
    """MultiUserStore with per-path fake Chroma collections (one per tenant)."""
    collections: dict[str, FakeCollection] = {}

    def fake_client(path):
        collections.setdefault(path, FakeCollection())
        return SimpleNamespace(
            get_or_create_collection=lambda **kw: collections[path]
        )

    monkeypatch.setattr(store_mod.chromadb, "PersistentClient", fake_client)
    monkeypatch.setattr(
        store_mod.embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        lambda model_name: None,
    )

    config = make_config(
        DB_PATH=tmp_path / "legacy" / "bowen.db",       # no legacy data
        CHROMA_PATH=tmp_path / "legacy" / "chroma",
        PROFILE_PATH=tmp_path / "legacy" / "profile.md",
    )
    multi = MultiUserStore(tmp_path / "users", config)
    alpha = await multi.get_or_create("usr_alpha", "alpha", "Tenant Alpha")
    beta = await multi.get_or_create("usr_beta", "beta", "Tenant Beta")

    yield SimpleNamespace(
        multi=multi, alpha=alpha, beta=beta,
        collections=collections, base=tmp_path / "users",
    )
    await multi.close_all()


# ── 1. Store isolation: SQLite, Chroma, profile ────────────────────────────────


class TestStoreIsolation:
    async def test_stores_are_physically_separate(self, two_tenants):
        t = two_tenants
        assert t.alpha is not t.beta
        assert t.alpha._db_path != t.beta._db_path
        assert "usr_alpha" in t.alpha._db_path and "usr_beta" in t.beta._db_path
        # Two distinct Chroma collections were created (one per tenant path)
        assert len(t.collections) == 2
        assert t.alpha._collection is not t.beta._collection

    async def test_cross_wall_memory_read_comes_back_empty(self, two_tenants):
        t = two_tenants
        secret = "ALPHA-SECRET-medical-history-9Q4Z"
        await t.alpha.write_memory(
            agent_id="all", memory_type="fact", content=secret, importance=0.9,
        )

        # The attack: search Beta's store for Alpha's secret
        leaked = t.beta.search(secret, top_k=8, min_relevance=0.0)
        assert secret not in leaked
        assert leaked == ""   # Beta's collection is empty — nothing to leak

        # And Beta's SQLite has no trace of it either
        rows = await t.beta._query("SELECT content FROM memories")
        assert all(secret not in r["content"] for r in rows)

    async def test_cross_wall_conversation_read_comes_back_empty(self, two_tenants):
        t = two_tenants
        await t.alpha.log_message("conv-a", 1, "user", "BOWEN", "alpha's private note")
        history = await t.beta.get_recent_history("conv-a", n=10)
        assert history == []   # same conversation id, different universe

    async def test_profile_wall_holds_in_composed_prompts(self, two_tenants):
        from agents.bowen import BOWENAgent
        from bus.message_bus import MessageBus

        t = two_tenants
        alpha_profile = t.base / "usr_alpha" / "profile.md"
        alpha_profile.write_text("# Tenant Alpha\nALPHA-PROFILE-MARK-77\n")

        config = make_config()
        beta_agent = BOWENAgent(config, t.beta, MessageBus())
        prompt = await beta_agent.build_system_prompt("who am I")
        assert "ALPHA-PROFILE-MARK-77" not in prompt
        assert "Tenant Beta" in prompt   # Beta sees only Beta


# ── 2. Alert gate: history, cooldowns, quiet hours are per-tenant ──────────────


class RecordingChannel:
    name = "recording"

    def __init__(self):
        self.sent: list = []

    async def send(self, event, tenant) -> None:
        self.sent.append(event.tenant_id)


class TestGateIsolation:
    """The gate is OS law now — its walls get the same adversarial treatment."""

    @pytest.fixture
    def gate(self, tmp_path):
        self.channel = RecordingChannel()
        for name in ("alpha", "beta"):
            (tmp_path / f"{name}.yaml").write_text("channels: [recording]\n")
        # Alpha runs a night-shift household: medium allowed around the clock
        (tmp_path / "alpha.yaml").write_text(
            "channels: [recording]\nquiet_hours:\n  medium: {start: 0, end: 24}\n"
        )
        return AlertGate(tmp_path, channels={"recording": self.channel})

    def noon(self):
        return datetime(2026, 7, 4, 12, 0, 0)

    async def test_alpha_suppressed_duplicate_cannot_eat_betas_first_alert(self, gate):
        # Alpha sends twice: deliver, then suppress (cooldown).
        e = dict(type="medication_check", priority="low", message="check")
        assert (await gate.dispatch(AlertEvent(tenant_id="alpha", **e), now=self.noon())).decision is Decision.DELIVER
        assert (await gate.dispatch(AlertEvent(tenant_id="alpha", **e), now=self.noon())).decision is Decision.SUPPRESS

        # The attack scenario: Beta's FIRST alert of the same type+key must
        # deliver — Alpha's cooldown history must be invisible to Beta.
        result = await gate.dispatch(AlertEvent(tenant_id="beta", **e), now=self.noon())
        assert result.decision is Decision.DELIVER
        assert self.channel.sent == ["alpha", "beta"]

    async def test_tenant_quiet_hours_do_not_bleed(self, gate):
        # 2am, medium priority. Alpha's night-shift config allows it...
        two_am = datetime(2026, 7, 4, 2, 0, 0)
        a = await gate.dispatch(
            AlertEvent(tenant_id="alpha", type="reminder", priority="medium", message="m"),
            now=two_am,
        )
        assert a.decision is Decision.DELIVER
        # ...and must NOT loosen Beta's default sleeping hours.
        b = await gate.dispatch(
            AlertEvent(tenant_id="beta", type="reminder", priority="medium", message="m"),
            now=two_am,
        )
        assert b.decision is Decision.DEFER

    def test_pure_gate_takes_history_by_reference_not_global(self):
        # Belt and braces: the pure function itself has no shared state.
        e = AlertEvent(type="reminder", priority="medium", message="m")
        now = datetime(2026, 7, 4, 12, 0, 0)
        assert evaluate_alert(e, now, {}).decision is Decision.DELIVER
        assert evaluate_alert(e, now, {}).decision is Decision.DELIVER  # no memory between calls


# ── 3. Shared knowledge: inherited by all, writable by none ───────────────────


class TestSharedKnowledge:
    async def test_all_tenants_inherit_shared_knowledge_read_only(self, two_tenants, monkeypatch):
        from agents import base as base_mod
        from agents.bowen import BOWENAgent
        from bus.message_bus import MessageBus

        monkeypatch.setattr(
            base_mod, "_load_shared_knowledge", lambda: "SHARED-HOUSE-RULE-42"
        )
        config = make_config()
        for store in (two_tenants.alpha, two_tenants.beta):
            prompt = await BOWENAgent(config, store, MessageBus()).build_system_prompt("hi")
            assert "SHARED-HOUSE-RULE-42" in prompt

    def test_no_tenant_code_path_writes_shared_knowledge(self):
        # The ONLY writer is the admin endpoint (X-Admin-Key gated).
        # MemoryStore has no method that touches shared_knowledge.md:
        import inspect

        from memory.store import MemoryStore

        source = inspect.getsource(MemoryStore)
        assert "shared_knowledge" not in source

        # And the admin writer really does demand the admin key:
        import inspect as _i

        from api.admin import _require_admin

        assert "compare_digest" in _i.getsource(_require_admin)

    def test_admin_knowledge_endpoint_rejects_tenants(self, tmp_path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.admin import router

        app = FastAPI()
        app.include_router(router)
        app.state.config = make_config(ADMIN_API_KEY="admin-secret")

        client = TestClient(app)
        # A tenant with a valid TENANT key but no admin key: rejected.
        r = client.post(
            "/api/admin/knowledge",
            json={"entry": "tenant vandalism attempt"},
            headers={"X-Admin-Key": "bwn_someTenantKey"},
        )
        assert r.status_code == 403


# ── 4. Keys: hashed at rest, constant-time, rate-limited ──────────────────────


class TestKeys:
    @pytest.fixture
    async def users(self, tmp_path):
        um = UserManager(tmp_path / "users.db", rate_limit_per_min=5)
        await um.initialize()
        yield um
        await um.close()

    async def test_plaintext_key_never_touches_disk(self, users, tmp_path):
        created = await users.create_user("praise2", "Praise Two")
        key = created["api_key"]

        # WAL mode: scan the db AND its journal — plaintext must be nowhere
        raw = (tmp_path / "users.db").read_bytes()
        for suffix in ("-wal", "-shm"):
            side = tmp_path / f"users.db{suffix}"
            if side.exists():
                raw += side.read_bytes()
        assert key.encode() not in raw                      # plaintext absent
        assert _hash_key(key).encode() in raw               # hash present

    async def test_authenticate_uses_constant_time_confirm(self, users):
        import inspect

        source = inspect.getsource(users.authenticate)
        assert "compare_digest" in source

        created = await users.create_user("c", "C")
        assert (await users.authenticate(created["api_key"]))["id"] == created["user_id"]
        assert await users.authenticate("bwn_wrongwrongwrongwrongwrongwrongwrong") is None

    async def test_per_tenant_rate_limit_trips_and_isolates(self, users):
        a = await users.create_user("heavy", "Heavy User")
        b = await users.create_user("light", "Light User")

        for _ in range(5):
            assert await users.authenticate(a["api_key"]) is not None
        with pytest.raises(RateLimited):
            await users.authenticate(a["api_key"])

        # The wall: Alpha burning their budget must not throttle Beta.
        assert await users.authenticate(b["api_key"]) is not None
