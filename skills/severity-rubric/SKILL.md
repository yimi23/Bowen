---
name: severity-rubric
description: DEVOPS's severity ladder: what counts as CRITICAL vs HIGH vs MEDIUM vs LOW, with house examples.
---

## The ladder
- CRITICAL: exploitable now, or data crosses a tenant wall. (Hardcoded live key;
  cross-tenant read; unauthenticated write endpoint.) Ship is blocked.
- HIGH: real vulnerability needing one precondition. (Missing rate limit on auth;
  non-constant-time key compare; injection with authenticated access.)
- MEDIUM: weakness that compounds. (Broad permissions; secrets in logs at debug;
  missing dedup on a paging path.)
- LOW: hygiene. (Unused dependency; TODO in a security path; verbose errors.)
Severity is assigned by exploit path, not by how embarrassing the fix is.
