/**
 * services/twilio.ts — GENI merge: this is no longer a Twilio client.
 *
 * Every function keeps its original signature, but delivery now rides
 * BOWEN's alert gate (/internal/alerts). The ONLY code that talks to
 * Twilio lives in BOWEN's core/alert_delivery.py — the gate's delivery
 * layer. GENI's callers (notifications.ts gate, fall-detection escalation,
 * routes) did not change.
 *
 * force=true on the primitives: by the time GENI calls these, its own
 * tested gate (notifications.ts) or its emergency logic has already made
 * the deliver decision — BOWEN's gate is the audited doorway and the
 * delivery engine, not a second opinion.
 */

import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('twilio');

const BOWEN_URL = process.env.BOWEN_INTERNAL_URL || 'http://localhost:8000';
const isMessagingEnabled = () => config.messaging.enabled;

async function dispatchViaGate(alert: {
  type: string;
  priority: string;
  message: string;
  details: Record<string, any>;
}): Promise<boolean> {
  try {
    const res = await fetch(`${BOWEN_URL}/internal/alerts`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-internal-key': process.env.GENI_API_KEY || '',
      },
      body: JSON.stringify({ ...alert, force: true, tenant_id: process.env.GENI_TENANT_ID || 'default' }),
      signal: AbortSignal.timeout(20_000),
    });
    if (!res.ok) {
      log.error({ status: res.status }, '❌ gate dispatch failed');
      return false;
    }
    const data = await res.json() as { decision: string };
    log.info({ decision: data.decision, type: alert.type }, '✅ dispatched via BOWEN gate');
    return data.decision === 'deliver';
  } catch (error) {
    log.error({ err: error }, '❌ gate dispatch threw');
    return false;
  }
}

/** Send WhatsApp message to caregiver (via the gate's delivery layer). */
export async function sendWhatsAppMessage(to: string, message: string): Promise<boolean> {
  if (!isMessagingEnabled()) {
    log.info('ℹ️ Messaging disabled; skipping WhatsApp send.');
    return false;
  }
  return dispatchViaGate({
    type: 'geni_send',
    priority: 'high',
    message,
    details: { to_phone: to, channel: 'twilio_whatsapp' },
  });
}

/** Send SMS message (via the gate's delivery layer). */
export async function sendSMS(to: string, message: string): Promise<boolean> {
  if (!isMessagingEnabled()) {
    log.info('ℹ️ Messaging disabled; skipping SMS send.');
    return false;
  }
  return dispatchViaGate({
    type: 'geni_send',
    priority: 'high',
    message,
    details: { to_phone: to, channel: 'twilio_sms' },
  });
}

/** Make voice call to caregiver or doctor (via the gate's delivery layer). */
export async function makeVoiceCall(
  to: string,
  message: string,
  callerName: string = 'GENI'
): Promise<boolean> {
  if (!isMessagingEnabled()) {
    log.info('ℹ️ Messaging disabled; skipping voice call.');
    return false;
  }
  return dispatchViaGate({
    type: 'geni_call',
    priority: 'critical',
    message,
    details: {
      to_phone: to,
      channel: 'twilio_voice',
      caller_name: callerName,
      patient_name: config.patient.name || 'the patient',
    },
  });
}

/** Send emergency alert to all contacts. */
export async function sendEmergencyAlert(
  contacts: { name: string; phone: string; relationship?: string }[],
  patientName: string,
  emergencyType: 'fall' | 'sos' | 'medical'
): Promise<void> {
  let message = '';

  switch (emergencyType) {
    case 'fall':
      message = `🚨 FALL DETECTED: ${patientName} has fallen and may need assistance. GENI detected a fall at ${new Date().toLocaleTimeString()}. Please check immediately.`;
      break;
    case 'sos':
      message = `🆘 EMERGENCY: ${patientName} pressed the emergency button. Immediate assistance needed.`;
      break;
    case 'medical':
      message = `⚕️ MEDICAL ALERT: ${patientName} reported a medical concern. Please contact them as soon as possible.`;
      break;
  }

  for (const contact of contacts) {
    await sendWhatsAppMessage(contact.phone, message);
    if (emergencyType === 'fall' || emergencyType === 'sos') {
      await makeVoiceCall(
        contact.phone,
        `This is an emergency alert for ${patientName}. ${message}`,
        'GENI Emergency System'
      );
    }
  }
}

/** Send informational update to caregiver. */
export async function sendCaregiverUpdate(
  to: string,
  patientName: string,
  action: string,
  context?: string
): Promise<boolean> {
  const message = `📋 GENI Update for ${patientName}:\n\n${action}${context ? '\n\nContext: ' + context : ''}\n\nThis is an informational message. No action required.`;
  return await sendWhatsAppMessage(to, message);
}

/** Send medication reminder to caregiver. */
export async function sendMedicationAlert(
  to: string,
  patientName: string,
  medication: string,
  issue: 'missed' | 'late' | 'refill_needed'
): Promise<boolean> {
  let message = '';

  switch (issue) {
    case 'missed':
      message = `💊 Medication Alert: ${patientName} has not taken ${medication} yet. GENI has reminded them.`;
      break;
    case 'late':
      message = `⏰ ${patientName} is late taking ${medication}. GENI is following up.`;
      break;
    case 'refill_needed':
      message = `🔄 Refill Needed: ${patientName}'s pill box is empty. Please refill medications for the week.`;
      break;
  }

  return await sendWhatsAppMessage(to, message);
}

/** Call doctor's office. */
export async function callDoctor(
  doctorPhone: string,
  patientName: string,
  reason: string
): Promise<boolean> {
  const message = `
    I am calling on behalf of ${patientName}.
    ${reason}
    Please call back at your earliest convenience.
  `;
  return await makeVoiceCall(doctorPhone, message, 'GENI Care System');
}
