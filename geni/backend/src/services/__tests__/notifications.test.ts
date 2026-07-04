import { describe, it, expect } from 'vitest';
import { evaluateNotification, buildAlert, type CaregiverNotification } from '../notifications';

// Helper: a Date pinned to a specific hour today
function at(hour: number): Date {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d;
}

function n(partial: Partial<CaregiverNotification>): CaregiverNotification {
  return {
    type: 'general_concern',
    priority: 'medium',
    message: 'test',
    ...partial,
  };
}

describe('evaluateNotification — quiet hours', () => {
  it('critical always sends, even at 3am', () => {
    const result = evaluateNotification(
      n({ type: 'fall_detected', priority: 'critical' }),
      at(3),
      new Map()
    );
    expect(result.allowed).toBe(true);
  });

  it('high is blocked at 6am and allowed at 8am', () => {
    const blocked = evaluateNotification(n({ priority: 'high' }), at(6), new Map());
    expect(blocked).toEqual({ allowed: false, reason: 'quiet_hours' });

    const allowed = evaluateNotification(n({ priority: 'high' }), at(8), new Map());
    expect(allowed.allowed).toBe(true);
  });

  it('low/medium are blocked at 8am and allowed at 10am', () => {
    expect(evaluateNotification(n({ priority: 'low' }), at(8), new Map()).allowed).toBe(false);
    expect(evaluateNotification(n({ priority: 'medium' }), at(8), new Map()).allowed).toBe(false);
    expect(evaluateNotification(n({ priority: 'low' }), at(10), new Map()).allowed).toBe(true);
  });

  it('force bypasses quiet hours', () => {
    const result = evaluateNotification(n({ priority: 'low', force: true }), at(3), new Map());
    expect(result).toEqual({ allowed: true, reason: 'forced' });
  });
});

describe('evaluateNotification — dedup and escalation', () => {
  it('suppresses a duplicate within the cooldown window', () => {
    const now = at(12);
    const sentLog = new Map([
      ['medication_check', { at: now.getTime() - 60_000, priority: 'low' as const }],
    ]);
    const result = evaluateNotification(
      n({ type: 'medication_check', priority: 'low' }),
      now,
      sentLog
    );
    expect(result).toEqual({ allowed: false, reason: 'duplicate' });
  });

  it('allows the same type again after the cooldown expires', () => {
    const now = at(12);
    const sentLog = new Map([
      ['medication_check', { at: now.getTime() - 11 * 60_000, priority: 'low' as const }],
    ]);
    const result = evaluateNotification(
      n({ type: 'medication_check', priority: 'low' }),
      now,
      sentLog
    );
    expect(result.allowed).toBe(true);
  });

  it('CRITICAL: a fall escalation passes the dedup gate', () => {
    // An impact warning (high) went out 30s ago; the confirmed fall (critical)
    // must NOT be suppressed as a duplicate.
    const now = at(12);
    const sentLog = new Map([
      ['fall_detected', { at: now.getTime() - 30_000, priority: 'high' as const }],
    ]);
    const result = evaluateNotification(
      n({ type: 'fall_detected', priority: 'critical' }),
      now,
      sentLog
    );
    expect(result.allowed).toBe(true);
  });

  it('repeated same-priority fall triggers within 2 minutes are merged', () => {
    const now = at(12);
    const sentLog = new Map([
      ['fall_detected', { at: now.getTime() - 30_000, priority: 'critical' as const }],
    ]);
    const result = evaluateNotification(
      n({ type: 'fall_detected', priority: 'critical' }),
      now,
      sentLog
    );
    expect(result).toEqual({ allowed: false, reason: 'duplicate' });
  });

  it('separate dedupKeys do not collide (per-medication)', () => {
    const now = at(12);
    const sentLog = new Map([
      ['medication_missed:Lisinopril', { at: now.getTime() - 60_000, priority: 'high' as const }],
    ]);
    const result = evaluateNotification(
      n({ type: 'medication_missed', priority: 'high', dedupKey: 'medication_missed:Metformin' }),
      now,
      sentLog
    );
    expect(result.allowed).toBe(true);
  });
});

describe('buildAlert — priority tiers', () => {
  it('fall is always critical with a call escalation', () => {
    const alert = buildAlert({ event: 'fall_detected' });
    expect(alert.priority).toBe('critical');
    expect(alert.shouldCall).toBe(true);
  });

  it('missed medication escalates with elapsed time', () => {
    expect(buildAlert({ event: 'missed_medication', timeElapsed: 10 }).priority).toBe('low');
    expect(buildAlert({ event: 'missed_medication', timeElapsed: 60 }).priority).toBe('medium');
    const late = buildAlert({ event: 'missed_medication', timeElapsed: 180 });
    expect(late.priority).toBe('high');
    expect(late.shouldCall).toBe(true);
  });

  it('symptom plus missed medication is high priority with call', () => {
    const alert = buildAlert({ event: 'symptom_reported', symptom: 'dizzy', medication: 'Lisinopril' });
    expect(alert.priority).toBe('high');
    expect(alert.shouldCall).toBe(true);
  });

  it('symptom alone is medium without call', () => {
    const alert = buildAlert({ event: 'symptom_reported', symptom: 'dizzy' });
    expect(alert.priority).toBe('medium');
    expect(alert.shouldCall).toBe(false);
  });
});
