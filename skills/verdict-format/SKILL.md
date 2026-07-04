---
name: verdict-format
description: DEVOPS's return schema: findings as [SEVERITY] file:line — issue — fix, closed with SHIP / NEEDS WORK / DO NOT SHIP.
---

## The schema (a verdict is a schema, not a vibe)
Each finding, one line:
[SEVERITY] file:line — what is wrong — the specific fix

Then the verdict, exactly one of:
- SHIP — no CRITICAL or HIGH findings. MEDIUMs listed as follow-ups.
- NEEDS WORK — HIGH findings present, or MEDIUMs that compound. Fixes named.
- DO NOT SHIP — any CRITICAL. The blocking findings listed first.

No verdict without findings shown. No finding without a fix named.
