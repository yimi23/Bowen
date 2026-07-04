---
name: security-audit-checklist
description: DEVOPS's audit sweep: secrets, injection, authz, dependency risk, the house seams.
---

## The sweep (every audit, in order)
1. Secrets: hardcoded keys, tokens in code or history, .env hygiene, key rotation debt.
2. Injection: SQL (parameterized?), shell (quoted? blocklisted?), prompt injection
   surfaces on anything user-supplied that reaches a model.
3. AuthZ: every endpoint authenticated? Tenant walls hold? Constant-time compares?
   Rate limits present?
4. Dependencies: unused deps (attack surface), known-vulnerable pins, vendored code.
5. House seams: SDK imports outside llm/, channel calls outside the gate's delivery
   layer, os.getenv outside config. The seams ARE the security model.
6. Data: what leaves the machine, to whom, logged where. PII in logs is a finding.
