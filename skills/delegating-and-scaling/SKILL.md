---
name: delegating-and-scaling
description: How Y dispatches work: the four-part contract every brief must carry, and the effort rubric that decides one worker vs parallel. This is the cost governor.
---

## The four-part contract (law — miss one and the worker drifts)
Every dispatch carries ALL FOUR:
1. **Objective** — what done looks like, in one paragraph. Not the topic; the finish line.
2. **Output format** — the exact shape of the return (fields, length cap, citations or not).
3. **Tools and sources** — which tools are permitted, which sources to prefer or avoid.
4. **Boundaries** — what is OUT of scope, when to stop, what not to touch.

## The effort rubric (rule, not vibes)
- One agent, one dispatch: the default. Simple fact-finding, single builds, single reviews.
- 2 to 4 parallel workers: comparisons and genuinely independent questions only.
- 10+: reserved for research programs that divide into independent strands. Rare.
- CAPTAIN is ALWAYS sequential. Tightly-coupled work (one codebase) underperforms
  under parallelism. One CAPTAIN, one rich brief, never two CAPTAINs on one repo.

## Failure modes to avoid (learned, not theoretical)
- Spawning many workers for a simple question. Ask: would one Haiku worker answer this?
- Loops: re-dispatching the same objective after a failed return. Change the brief or stop.
- Status-update chatter between workers. Workers return results, not progress reports.
- Vague objectives ("look into X"). If you cannot state what done looks like, do not dispatch.

## Cost discipline
Parallel bursts cost roughly fifteen times a chat turn. Default to a single dispatch,
prefer Haiku-tier workers where reading dominates, and parallelize only independence.
