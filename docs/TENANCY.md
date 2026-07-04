# Tenancy: How Isolation Works

BOWEN is supply-ready: one running instance serves multiple tenants, and
every tenant lives behind walls that are tested by attempted crossings
(`tests/test_tenancy.py`). This page is the delivery-kit seed — what a
per-contract deployment looks like and why the isolation claims hold.

## The walls

Each tenant gets a physically separate universe under `memory/users/<id>/`:

| Asset | Location | Isolation mechanism |
|---|---|---|
| Structured data (conversations, tasks, memories) | `bowen.db` | Separate SQLite file per tenant |
| Semantic memory (vectors) | `chroma/` | Separate Chroma store per tenant directory |
| Identity | `profile.md` | Loaded only into that tenant's agent prompts |
| Alert history (cooldowns, dedup) | in the gate, keyed by tenant | `AlertGate` history is a per-tenant map; one household's suppressed duplicate can never eat another's first alert |
| Quiet hours, channels, elder_voice | `memory/tenants/<id>.yaml` | Config per tenant, defaults to GENI's proven semantics |

Shared in exactly one direction: `memory/shared_knowledge.md` (git-tracked)
is injected read-only into every tenant's prompts. The only writer is the
admin endpoint behind `X-Admin-Key` (constant-time compared). No tenant
code path can touch it — a test inspects the store's source to prove it.

## Keys and sessions

- API keys are `bwn_`-prefixed, 40 chars of `secrets` randomness, shown
  exactly once at provisioning. Only the SHA-256 hash is stored; a test
  scans the raw database bytes (including the WAL journal) for plaintext.
- Verification is constant-time (`hmac.compare_digest`) after the indexed
  hash lookup.
- Every authenticated request passes a per-tenant sliding-window rate
  limit (default 120/min). One tenant burning their budget cannot throttle
  another — tested.
- The WebSocket door authenticates via `?key=`. Keyless connections are
  allowed only when no admin key is configured (single-tenant local dev).
  Bad key → close 4401; rate-limited → close 4429.

## Provisioning a tenant

```bash
.venv/bin/python scripts/create_tenant.py <username> "Display Name"
```

Creates the account (hash at rest), scaffolds the isolated stores and the
tenant YAML, and prints the key once. Lost keys are regenerated
(`POST /api/admin/users/<id>/regen`), never recovered.

## What a per-contract deployment looks like

A contract gets its own BOWEN instance — tenancy hardening is defense in
depth, not a reason to co-locate strangers:

1. **Private endpoint.** One host (or VM) per contract, `ADMIN_API_KEY`
   set, WebSocket + REST bound behind the customer's network boundary.
   Nothing multi-contract shares a process.
2. **Own tenant set.** The customer's households/users are tenants on
   THEIR instance, provisioned with `create_tenant.py`. Their tenant YAMLs
   (quiet hours, caregiver numbers, elder_voice) are theirs to edit.
3. **LocalProvider slot.** For inside-the-walls contracts, implement
   `llm/local_provider.py` against the customer's on-prem runtime and
   point `agents.yaml` at it. No agent code changes — that seam exists so
   local deployment is an adapter, not a rewrite.
4. **The gate is law.** All human interruptions pass `core/alerts.py`;
   Twilio (or the customer's channel) lives only in the delivery layer.
   Swapping channels per contract = one class in `core/alert_delivery.py`
   plus tenant YAML.

## Verifying the walls

```bash
.venv/bin/python -m pytest tests/test_tenancy.py -v
```

Every test is an attack: read another tenant's memory (comes back empty),
poach their profile into your prompt (absent), ride their alert cooldown
(delivers anyway), loosen your quiet hours to loosen theirs (doesn't),
scan the database for plaintext keys (nothing), exhaust your rate budget
to starve them (they're unaffected).
