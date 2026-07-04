---
name: repo-conventions
description: House conventions for the BOWEN repo: where things live and the seams that must not be violated.
---

## The seams (grep-enforced law)
- No anthropic/groq imports outside llm/. All model calls ride the LLMProvider seam.
- No Twilio or push-channel calls outside core/alert_delivery.py. The gate is the doorway.
- Model choice lives in agents.yaml only. Never hardcode a model in an agent.
- No os.getenv outside config.py.
- Foundry corpus data never shares a store with tenant memory.

## Layout
agents/ (one file per agent) · llm/ (the seam) · core/ (gate, tenants, skills, logging)
bus/ (typed payloads only — never raw strings) · memory/ (three-layer, per tenant)
tools/ (registry-gated) · geni/backend (supervised Node, wrap not rewrite)
corpus/ (Foundry) · skills/ (this library) · tests/ (offline, blocked-socket)
