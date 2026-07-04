import twilio from 'twilio';
import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('twilio');

const client = twilio(config.twilio.accountSid, config.twilio.authToken);
const isMessagingEnabled = () => config.messaging.enabled;

/**
 * Send WhatsApp message to caregiver
 */
export async function sendWhatsAppMessage(to: string, message: string): Promise<boolean> {
  if (!isMessagingEnabled()) {
    log.info('ℹ️ Messaging disabled; skipping WhatsApp send.');
    return false;
  }
  try {
    const result = await client.messages.create({
      from: `whatsapp:${config.twilio.whatsappNumber}`,
      to: `whatsapp:${to}`,
      body: message,
    });
    
    log.info(`✅ WhatsApp sent to ${to}: ${result.sid}`);
    return true;
  } catch (error) {
    log.error({ err: error }, '❌ WhatsApp send failed:');
    return false;
  }
}

/**
 * Send SMS message
 */
export async function sendSMS(to: string, message: string): Promise<boolean> {
  if (!isMessagingEnabled()) {
    log.info('ℹ️ Messaging disabled; skipping SMS send.');
    return false;
  }
  try {
    const result = await client.messages.create({
      from: config.twilio.phoneNumber,
      to: to,
      body: message,
    });
    
    log.info(`✅ SMS sent to ${to}: ${result.sid}`);
    return true;
  } catch (error) {
    log.error({ err: error }, '❌ SMS send failed:');
    return false;
  }
}

/**
 * Make voice call to caregiver or doctor
 * @param to - Phone number to call
 * @param message - TwiML message to speak
 * @param callerName - Name of caller (GENI or the patient)
 */
export async function makeVoiceCall(
  to: string, 
  message: string, 
  callerName: string = 'GENI'
): Promise<boolean> {
  if (!isMessagingEnabled()) {
    log.info('ℹ️ Messaging disabled; skipping voice call.');
    return false;
  }
  try {
    // Generate TwiML for the call
    const twiml = `
      <Response>
        <Say voice="Polly.Joanna">
          Hello, this is ${callerName} calling on behalf of ${config.patient.name}.
          ${message}
        </Say>
        <Pause length="2"/>
        <Say voice="Polly.Joanna">
          If this is an emergency, please check on ${config.patient.name.split(' ')[0]} immediately.
          You can also reply to this number via text message.
        </Say>
      </Response>
    `;
    
    const call = await client.calls.create({
      from: config.twilio.phoneNumber,
      to: to,
      twiml: twiml,
    });
    
    log.info(`📞 Voice call initiated to ${to}: ${call.sid}`);
    return true;
  } catch (error) {
    log.error({ err: error }, '❌ Voice call failed:');
    return false;
  }
}

/**
 * Send emergency alert to all contacts
 */
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
  
  // Send to all contacts
  for (const contact of contacts) {
    // Send WhatsApp
    await sendWhatsAppMessage(contact.phone, message);
    
    // Also make voice call for emergencies
    if (emergencyType === 'fall' || emergencyType === 'sos') {
      await makeVoiceCall(
        contact.phone,
        `This is an emergency alert for ${patientName}. ${message}`,
        'GENI Emergency System'
      );
    }
  }
}

/**
 * Send informational update to caregiver
 */
export async function sendCaregiverUpdate(
  to: string,
  patientName: string,
  action: string,
  context?: string
): Promise<boolean> {
  const message = `📋 GENI Update for ${patientName}:\n\n${action}${context ? '\n\nContext: ' + context : ''}\n\nThis is an informational message. No action required.`;
  
  return await sendWhatsAppMessage(to, message);
}

/**
 * Send medication reminder to caregiver
 */
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

/**
 * Call doctor's office
 */
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
