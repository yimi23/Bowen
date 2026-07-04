import { state, getPrimaryContact } from '../state';
import { sendWhatsAppMessage } from './twilio';
import { addActivity } from '../state';
import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('reporting');

/**
 * Generate end-of-day summary for caregiver
 */
export function generateDailyReport(): string {
  const patient = state.patient;
  const today = new Date();
  const dayName = today.toLocaleDateString('en-US', { weekday: 'long' });
  const dateStr = today.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  
  // Calculate medication status
  const totalMeds = state.todaysMedications.length;
  const takenMeds = state.todaysMedications.filter(m => m.status === 'taken').length;
  const pendingMeds = state.todaysMedications.filter(m => m.status === 'pending' || m.status === 'upcoming');
  const missedMeds = state.todaysMedications.filter(m => m.status === 'missed');
  
  // Get conversation activity (how many times patient talked to GENI)
  const todayStart = new Date(today).setHours(0, 0, 0, 0);
  const conversationCount = state.activities.filter(a => 
    (a.type === 'voice' || a.type === 'message') && a.timestamp > todayStart
  ).length;
  
  // Get patient name dynamically
  const patientFirstName = config.patient.name.split(' ')[0];
  
  // Build medication summary
  let medSummary = '';
  state.todaysMedications.forEach(med => {
    const icon = med.status === 'taken' ? '✅' : 
                 med.status === 'pending' ? '⏳' : 
                 med.status === 'upcoming' ? '📅' : '❌';
    const timeInfo = med.status === 'taken' ? 'On time' : med.time;
    medSummary += `   ${icon} ${med.period.charAt(0).toUpperCase() + med.period.slice(1)}: ${med.name} (${timeInfo})\n`;
  });
  
  // Determine overall tone
  let overallMessage = '';
  if (missedMeds.length > 0) {
    overallMessage = `${patientFirstName} had a good day overall, though ${patientFirstName.toLowerCase() === 'margaret' ? 'she' : 'they'} missed ${missedMeds.length} medication${missedMeds.length > 1 ? 's' : ''}. I'll keep monitoring.`;
  } else if (pendingMeds.length > 0) {
    overallMessage = `${patientFirstName}'s doing well! ${patientFirstName.toLowerCase() === 'margaret' ? 'She' : 'They'} has ${pendingMeds.length} medication${pendingMeds.length > 1 ? 's' : ''} left for tonight.`;
  } else {
    overallMessage = `${patientFirstName} had a great day! All medications taken on time. 🎉`;
  }
  
  // Build the report
  const report = `Hi! Here's ${patientFirstName}'s daily update:

📅 ${dayName}, ${dateStr}

💊 Medications (${takenMeds}/${totalMeds} taken):
${medSummary}
💬 Activity:
   • Spoke with GENI ${conversationCount} time${conversationCount !== 1 ? 's' : ''}
   • ${state.activities.length > 0 ? state.activities[0].message : 'Active and engaged'}

😊 Overall: ${overallMessage}

- GENI`;

  return report;
}

/**
 * Send daily report to primary caregiver
 */
export async function sendDailyReportToCaregiver(): Promise<boolean> {
  const primaryContact = getPrimaryContact();
  if (!primaryContact) {
    log.info('⚠️  No primary contact found for daily report');
    return false;
  }
  
  const report = generateDailyReport();
  
  const success = await sendWhatsAppMessage(primaryContact.phone, report);
  
  if (success) {
    addActivity(`Daily report sent to ${primaryContact.name}`, 'system');
    log.info(`✅ Daily report sent to ${primaryContact.name}`);
  } else {
    log.error('❌ Failed to send daily report');
  }
  
  return success;
}

/**
 * Generate quick status update (for mid-day check-ins)
 */
export function generateQuickUpdate(): string {
  const takenMeds = state.todaysMedications.filter(m => m.status === 'taken').length;
  const totalMeds = state.todaysMedications.length;
  const patientFirstName = config.patient.name.split(' ')[0];
  
  return `Quick update: ${patientFirstName}'s doing well! ${takenMeds}/${totalMeds} medications taken so far today. 👍`;
}
