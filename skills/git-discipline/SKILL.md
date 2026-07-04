---
name: git-discipline
description: CAPTAIN's commit law: conventional commits in logical groups, clean tree, never push unasked.
---

## Rules
- Conventional commits: feat:, fix:, chore:, test:, refactor:, docs:. Scope in parens.
- Group logically: one concern per commit. Sixteen files of mixed work is never one commit.
- The tree ends clean. Uncommitted work at session end is a decision, not an accident.
- NEVER push without being asked. NEVER rewrite history without explicit instruction.
- Never commit secrets, .env files, or generated artifacts. Check .gitignore first.
- Read the diff before committing. The message describes what the diff does, not what
  you intended.
