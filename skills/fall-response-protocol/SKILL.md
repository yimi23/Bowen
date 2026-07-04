---
name: fall-response-protocol
description: GENI's fall sequence: confirmation window, the cancellable countdown, escalation, and what to say to the elder.
---

## The sequence
1. Pose model flags fall motion → 3-second confirmation window (filters stumbles).
2. Confirmed → 60-second CANCELLABLE countdown, announced calmly: "I saw you fall.
   I'm going to call Jamie in one minute unless you tell me you're okay."
3. Elder cancels → log the event, stay attentive, mention it in the daily report.
4. No cancel → fall_confirmed fires at CRITICAL priority: gate delivers 24/7,
   escalation breaks dedup, voice call flag set.
5. While alerts fire, GENI stays WITH the elder in voice: calm, present, no medical
   advice beyond "stay still, help is coming" if movement looks risky.
Repeated same-priority triggers inside 2 minutes merge — one page, not a storm.
