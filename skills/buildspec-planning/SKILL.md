---
name: buildspec-planning
description: CAPTAIN's dual-ledger planning: write the BuildSpec before the first tool call, check it before declaring done.
---

## The pattern
Before building anything non-trivial, write a BuildSpec: the files to create,
modify, or delete, each with a one-line reason. Two ledgers:
1. The plan (BuildSpec) — written BEFORE the first file operation.
2. The reality (files actually touched) — tracked as you work.

Before declaring done, diff the ledgers. Every divergence is either justified
in one sentence or fixed. Silent scope drift is how builds rot.
