/**
 * Unified caregiver notification service.
 *
 * Every message to a caregiver flows through notifyCaregiver(), which applies
 * ONE decision gate: quiet hours by priority, then dedup with escalation
 * override. This replaces the three previous paths (alerts.ts,
 * caregiver-updates.ts, and direct twilio sends) that could each fire
 * independently for the same event.
 */

import { state, getPrimaryContact, addActivity } from '../state';
import { sendWhatsAppMessage } from './twilio';
import { buildGENIContext } from './geni-context';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('notifications');

export type NotificationPriority = 'low' | 'medium' | 'high' | 'critical';

export type NotificationType =
  | 'fall_detected'
  | 'unusual_activity'
  | 'medication_check'
  | 'medication_taken'
  | 'medication_missed'
  | 'symptom_reported'
  | 'inactivity'
  | 'daily_summary'
  | 'weekly_summary'
  | 'reassurance'
  | 'general_concern';

export interface CaregiverNotification {
  type: NotificationType;
  priority: NotificationPriority;
  message: string;
  /** Escalate to a voice call as well (wired later via twilio makeVoiceCall) */
  shouldCall?: boolean;
  details?: Record<string, any>;
  /** Bypass quiet hours and dedup — for manual/test sends from routes */
  force?: boolean;
  /** Override the dedup key, e.g. `medication_missed:${medName}` */
  dedupKey?: string;
}

const PRIORITY_RANK: Record<NotificationPriority, number> = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3,
};

/** Per-type dedup cooldowns. Repeated triggers inside the window are merged
 * unless the new notification has strictly higher priority (escalation). */
const COOLDOWN_MS: Record<NotificationType, number> = {
  fall_detected: 2 * 60_000,
  unusual_activity: 10 * 60_000,
  medication_check: 10 * 60_000,
  medication_taken: 5 * 60_000,
  medication_missed: 30 * 60_000,
  symptom_reported: 10 * 60_000,
  inactivity: 60 * 60_000,
  daily_summary: 60_000,
  weekly_summary: 60_000,
  reassurance: 60_000,
  general_concern: 60_000,
};

interface SentRecord {
  at: number;
  priority: NotificationPriority;
}

const recentlySent = new Map<string, SentRecord>();

export interface GateDecision {
  allowed: boolean;
  reason: 'ok' | 'forced' | 'quiet_hours' | 'duplicate';
}

/**
 * Pure decision function — exported for tests.
 * Quiet hours: critical always sends; high sends 7:00-23:00; medium/low 9:00-21:00.
 * Dedup: same key within cooldown is suppressed unless priority escalated.
 */
export function evaluateNotification(
  n: CaregiverNotification,
  now: Date = new Date(),
  sentLog: Map<string, SentRecord> = recentlySent
): GateDecision {
  if (n.force) return { allowed: true, reason: 'forced' };

  const hour = now.getHours();
  const inWindow =
    n.priority === 'critical' ||
    (n.priority === 'high' && hour >= 7 && hour < 23) ||
    ((n.priority === 'medium' || n.priority === 'low') && hour >= 9 && hour < 21);

  if (!inWindow) return { allowed: false, reason: 'quiet_hours' };

  const key = n.dedupKey || n.type;
  const last = sentLog.get(key);
  if (last) {
    const withinCooldown = now.getTime() - last.at < COOLDOWN_MS[n.type];
    const escalated = PRIORITY_RANK[n.priority] > PRIORITY_RANK[last.priority];
    if (withinCooldown && !escalated) {
      return { allowed: false, reason: 'duplicate' };
    }
  }

  return { allowed: true, reason: 'ok' };
}

/**
 * The single entry point for caregiver messaging.
 */
export async function notifyCaregiver(n: CaregiverNotification): Promise<boolean> {
  const contact = getPrimaryContact();
  if (!contact) {
    log.warn({ type: n.type }, 'no primary caregiver configured, skipping notification');
    return false;
  }

  const decision = evaluateNotification(n);
  if (!decision.allowed) {
    log.info(
      { type: n.type, priority: n.priority, reason: decision.reason },
      'notification suppressed'
    );
    return false;
  }

  const key = n.dedupKey || n.type;
  recentlySent.set(key, { at: Date.now(), priority: n.priority });

  try {
    const success = await sendWhatsAppMessage(contact.phone, n.message);
    if (success) {
      addActivity(`Notified ${contact.name}: ${n.type} (${n.priority})`, 'system');
      log.info({ type: n.type, priority: n.priority, to: contact.name }, 'notification sent');
    } else {
      log.error({ type: n.type }, 'notification send returned failure');
    }
    return success;
  } catch (error) {
    log.error({ err: error, type: n.type }, 'notification send threw');
    return false;
  }
}

/** Test hook — clears dedup memory between tests. */
export function resetNotificationState(): void {
  recentlySent.clear();
}

// ---------------------------------------------------------------------------
// Message builders (GENI's casual caregiver voice). Ported from alerts.ts and
// caregiver-updates.ts so every message keeps the same tone.
// ---------------------------------------------------------------------------

export interface AlertContext {
  event: 'missed_medication' | 'symptom_reported' | 'fall_detected' | 'no_activity' | 'general_concern';
  medication?: string;
  symptom?: string;
  timeElapsed?: number; // minutes
  additionalContext?: string;
}

export interface BuiltAlert {
  type: NotificationType;
  priority: NotificationPriority;
  message: string;
  shouldCall: boolean;
}

function firstName(): string {
  return state.patient.name.split(' ')[0];
}

function caregiverName(): string {
  return getPrimaryContact()?.name || 'there';
}

/** Build a context-aware alert without sending it (used for route previews). */
export function buildAlert(context: AlertContext): BuiltAlert {
  const patient = firstName();
  const caregiver = caregiverName();

  switch (context.event) {
    case 'missed_medication': {
      const elapsed = context.timeElapsed || 0;
      const med = context.medication || 'medication';
      if (elapsed < 30) {
        return {
          type: 'medication_missed',
          priority: 'low',
          shouldCall: false,
          message: `Hi ${caregiver}, ${patient} hasn't taken ${med} yet (due ${elapsed} min ago). I've reminded her. Just keeping you in the loop. - GENI`,
        };
      }
      if (elapsed < 120) {
        return {
          type: 'medication_missed',
          priority: 'medium',
          shouldCall: false,
          message: `Hi ${caregiver}, ${patient} missed ${med} (${Math.round(elapsed / 60)}h ago). I've followed up with her. Might be worth a quick check-in when you have a moment. - GENI`,
        };
      }
      return {
        type: 'medication_missed',
        priority: 'high',
        shouldCall: true,
        message: `${caregiver}, ${patient} hasn't taken ${med} yet (due ${Math.round(elapsed / 60)}h ago). I've reminded her multiple times. Please call when you can. - GENI`,
      };
    }

    case 'symptom_reported': {
      const symptom = context.symptom || 'not feeling well';
      if (context.medication) {
        return {
          type: 'symptom_reported',
          priority: 'high',
          shouldCall: true,
          message: `Hi ${caregiver}, ${patient} mentioned feeling ${symptom}. She also hasn't taken her ${context.medication} yet. I've reminded her to sit down and rest. Please check in when you can. - GENI`,
        };
      }
      return {
        type: 'symptom_reported',
        priority: 'medium',
        shouldCall: false,
        message: `Hi ${caregiver}, ${patient} mentioned feeling ${symptom}. She seems okay otherwise, but wanted you to know. Might be worth a call to check in. - GENI`,
      };
    }

    case 'fall_detected':
      return {
        type: 'fall_detected',
        priority: 'critical',
        shouldCall: true,
        message: `🚨 ${caregiver} - ${patient} has fallen. I've detected a fall and am checking on her now. Please call her IMMEDIATELY. - GENI`,
      };

    case 'no_activity': {
      const hours = Math.round((context.timeElapsed || 120) / 60);
      if (hours < 3) {
        return {
          type: 'inactivity',
          priority: 'low',
          shouldCall: false,
          message: `Hi ${caregiver}, I haven't heard from ${patient} in about ${hours} hours. She might be napping or relaxing. Just wanted you to know. - GENI`,
        };
      }
      return {
        type: 'inactivity',
        priority: 'medium',
        shouldCall: true,
        message: `Hi ${caregiver}, no activity from ${patient} in ${hours}+ hours. I've tried checking in but no response. Please call when you can. - GENI`,
      };
    }

    case 'general_concern':
    default:
      return {
        type: 'general_concern',
        priority: 'medium',
        shouldCall: false,
        message: `Hi ${caregiver}, ${patient} ${context.additionalContext || 'needs some assistance'}. Wanted to let you know. - GENI`,
      };
  }
}

/** Build + send a context-aware alert. */
export async function sendAlert(context: AlertContext, force = false): Promise<boolean> {
  const built = buildAlert(context);
  return notifyCaregiver({ ...built, force, details: { context } });
}

/** Quick "all is well" message. */
export async function sendReassurance(force = false): Promise<boolean> {
  return notifyCaregiver({
    type: 'reassurance',
    priority: 'low',
    force,
    message: `Hi! Just checking in - ${firstName()} is doing great today. All medications on track, active and engaged. 😊 - GENI`,
  });
}

/** Pill-check result update (vision or YOLO). */
export async function notifyPillCheck(result: {
  status: 'present' | 'taken' | 'unclear';
  observations: string;
  method: 'vision' | 'yolo';
}): Promise<boolean> {
  const context = buildGENIContext();
  const dateStr = new Date().toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  let message = '';
  if (result.status === 'taken') {
    message = `Pills taken 👍 (${dateStr})\n\n${result.observations}`;
  } else if (result.status === 'present') {
    message = `Pills not taken yet (${dateStr})\n\nSaw: ${result.observations}\n\n`;
    if (context.overdueMedications.length > 0) {
      message += `Overdue:\n`;
      context.overdueMedications.forEach(med => {
        message += `  • ${med.name} (was due at ${med.time})\n`;
      });
      message += `\nMight want to check in.`;
    } else if (context.pendingMedications.length > 0) {
      message += `Pending:\n`;
      context.pendingMedications.forEach(med => {
        message += `  • ${med.name} (${med.time})\n`;
      });
    }
  } else {
    message = `Pill check unclear (${dateStr})\n\nCouldn't tell for sure. ${result.observations}\n\nMight need to check manually.`;
  }

  let priority: NotificationPriority = 'low';
  if (result.status === 'unclear') priority = 'medium';
  if (context.overdueMedications.length > 0) priority = 'high';

  return notifyCaregiver({
    type: 'medication_check',
    priority,
    message,
    details: { result },
  });
}

/** Positive confirmation that a specific medication was taken. */
export async function notifyMedicationTaken(medicationName: string): Promise<boolean> {
  const context = buildGENIContext();
  const timeStr = new Date().toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  let message = `${medicationName} taken 👍 (${timeStr})\n\n`;
  const remaining = context.pendingMedications.filter(m => m.name !== medicationName);
  if (remaining.length > 0) {
    message += `Still pending:\n`;
    remaining.forEach(med => {
      message += `  • ${med.name} (${med.time})\n`;
    });
  } else {
    message += `All meds for today done 🎉`;
  }

  return notifyCaregiver({
    type: 'medication_taken',
    priority: 'low',
    message,
    dedupKey: `medication_taken:${medicationName}`,
  });
}

/** Alert that a specific medication is overdue. */
export async function notifyMedicationMissed(medication: {
  name: string;
  time: string;
}): Promise<boolean> {
  const timeStr = new Date().toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  const message =
    `⚠️ ${medication.name} not taken yet (${timeStr})\n\n` +
    `Was due at ${medication.time}\n\nMight want to check in.`;

  return notifyCaregiver({
    type: 'medication_missed',
    priority: 'high',
    message,
    dedupKey: `medication_missed:${medication.name}`,
  });
}

/** End-of-day summary for the caregiver. */
export async function sendDailySummary(force = false): Promise<boolean> {
  const context = buildGENIContext();
  const dateStr = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });

  let message = `Daily update - ${dateStr}\n\n`;
  const totalMeds = context.todaysMedications.length;
  const takenMeds = context.todaysMedications.filter(m => m.status === 'taken').length;
  message += `Meds: ${takenMeds}/${totalMeds} taken`;

  if (context.overdueMedications.length > 0) {
    message += `\n\nMissed:\n`;
    context.overdueMedications.forEach(med => {
      message += `  • ${med.name}\n`;
    });
  }

  if (context.activityLevel === 'concerning' || context.activityLevel === 'quiet') {
    message += `\n\nBeen pretty quiet today.`;
  }
  if (context.hoursSinceLastInteraction > 6) {
    message += ` Last chat was ${Math.floor(context.hoursSinceLastInteraction)} hours ago.`;
  }

  if (takenMeds === totalMeds) {
    message += `\n\nAll meds taken 👍`;
  } else if (takenMeds >= totalMeds * 0.75) {
    message += `\n\nDoing okay overall.`;
  } else {
    message += `\n\nMight want to check in.`;
  }

  return notifyCaregiver({ type: 'daily_summary', priority: 'low', message, force });
}
