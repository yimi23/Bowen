---
name: medication-adherence-grading
description: GENI's adherence ladder: how compartment history maps to concern level and when the caregiver hears about it.
---

## The ladder (proven in code and tests — this skill mirrors it)
- All compartments on schedule: no concern. Positive note in the daily report only.
- 1 day missed this week: LOW concern. Gentle elder reminder. No caregiver alert.
- 2 days missed: MEDIUM. Caregiver notified through the gate.
- 3 to 4 days: HIGH. Caregiver alert with call escalation flag.
- Entire week untouched: CRITICAL. Immediate alert, call escalation.
- All compartments unclear (vision uncertain): MEDIUM, no alert — say so honestly
  and ask for a manual check rather than inventing a reading.
Time-of-day escalation for a single missed dose: under 30min LOW, under 2h MEDIUM,
beyond HIGH with call. All caregiver messaging rides the gate — no side channels.
