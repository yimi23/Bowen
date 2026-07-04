---
name: mounting-skills
description: How Y picks situational skill packs from the library index and attaches them to dispatch briefs.
---

## Mechanics
Y's context carries the library INDEX (name + one-line description per skill).
Full bodies load only when mounted. To mount: list skill names in the dispatch
brief's mounted_skills; the worker loads the bodies at receipt.

## Selection rules
- Mount by task evidence, not habit: an Urhobo-speaking elder gets speaking-urhobo
  mounted on GENI; a bank integration gets that tenant's integration skill on CAPTAIN.
- Two mounted skills is normal, four is suspicious, six means the brief is unfocused.
- Standing skills never need mounting — they are already in the worker's prompt.
- Tenant-scoped skills mount ONLY onto work for that tenant. They never cross walls.
