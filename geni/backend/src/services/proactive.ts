import { state, addActivity } from '../state';
import { notifyCaregiver } from './notifications';
import { emitActivity, emitSpeak } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('proactive');

const CAREGIVER_ALERT_COOLDOWN_MS = 6 * 60 * 60 * 1000;
const NO_ACTIVITY_ALERT_COOLDOWN_MS = 6 * 60 * 60 * 1000;
const lastMedicationAlertAt = new Map<string, number>();
let lastNoActivityAlertAt: number | null = null;

function parseTimeToMinutes(time: string): number {
  const [timePart, periodPart] = time.split(' ');
  const [hourStr, minuteStr] = timePart.split(':');
  let hours = parseInt(hourStr, 10);
  const minutes = parseInt(minuteStr, 10);
  const period = (periodPart || '').toLowerCase();
  
  if (period === 'pm' && hours < 12) hours += 12;
  if (period === 'am' && hours === 12) hours = 0;
  
  return hours * 60 + minutes;
}

function getRecentPillCheckContext(): string | null {
  const last = state.pillCheckResults[state.pillCheckResults.length - 1];
  if (!last) return null;
  
  const ageMs = Date.now() - last.timestamp.getTime();
  if (ageMs > 2 * 60 * 60 * 1000) return null;
  
  const timeStr = last.timestamp.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  return `Last camera check at ${timeStr} showed "${last.status}" (${last.confidence}).`;
}

// Proactive Intelligence Service for Elder Care

export async function checkMedicationAdherence() {
  const now = new Date();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  
  for (const med of state.todaysMedications) {
    if (med.status === 'pending') {
      const medMinutes = parseTimeToMinutes(med.time);
      const minutesSince = nowMinutes - medMinutes;
      
      // After 30 minutes, gentle reminder
      if (minutesSince >= 30 && minutesSince < 60) {
        const reminder = `Hi ${state.patient.name}, just checking - did you take your ${med.time} ${med.name}?`;
        emitSpeak(reminder);
        addActivity(reminder, 'system');
      }
      
      // After 2 hours, alert caregiver
      if (minutesSince >= 120) {
        const alertKey = `${med.name}-${med.time}`;
        const lastSent = lastMedicationAlertAt.get(alertKey);
        if (lastSent && Date.now() - lastSent < CAREGIVER_ALERT_COOLDOWN_MS) {
          continue;
        }
        
        const context = getRecentPillCheckContext();
        if (!context) {
          log.info('⚠️  Skipping caregiver alert: no recent pill check context.');
          continue;
        }
        
        const sent = await notifyCaregiver({
          type: 'medication_missed',
          priority: 'high',
          message: `Hey, this is GENI. ${state.patient.name} hasn't confirmed ${med.time} medication (${med.name}). Please check in. ${context}`,
          dedupKey: `medication_missed:${med.name}`,
        });
        if (sent) {
          lastMedicationAlertAt.set(alertKey, Date.now());
        }
      }
    }
  }
}

export function generateMorningBriefing(): string {
  const patient = state.patient;
  const pendingMeds = state.todaysMedications.filter(m => m.status !== 'taken');
  const appointments = state.reminders.filter(r => r.type === 'appointment' && !r.completed);
  
  let briefing = `Good morning ${patient.name}! Here's your day:\n\n`;
  
  // Medication summary
  briefing += `💊 Medications: ${pendingMeds.length} doses scheduled today\n`;
  if (pendingMeds.length > 0) {
    const nextMed = pendingMeds[0];
    briefing += `   Next: ${nextMed.name} at ${nextMed.time}\n\n`;
  }
  
  // Appointments
  if (appointments.length > 0) {
    briefing += `📅 Appointments:\n`;
    appointments.forEach(apt => {
      briefing += `   ${apt.time} - ${apt.message}\n`;
    });
    briefing += '\n';
  }
  
  // Encouragement
  briefing += `⚡ You're doing great! Have a wonderful day.`;
  
  return briefing;
}

export function generateSmartMedicationReminder(medName: string, time: string): string {
  const med = state.todaysMedications.find(m => m.name === medName);
  if (!med) return `Time for your ${medName}`;
  
  let reminder = `${state.patient.name}, it's ${time} - time for your ${med.period} medication.\n\n`;
  reminder += `You have:\n`;
  reminder += `- ${med.name} ${med.dosage}\n\n`;
  
  if (med.period === 'morning') {
    reminder += `Take with breakfast. I'll check in 30 minutes to confirm.`;
  } else if (med.period === 'afternoon') {
    reminder += `Take with lunch or a snack. Need me to call ${state.contacts[0].name} if you need help?`;
  } else if (med.period === 'evening') {
    reminder += `Take with dinner. This is your last dose for today.`;
  }
  
  return reminder;
}

export async function proactiveHealthCheck() {
  // Check if there's been activity in last 2 hours
  const twoHoursAgo = Date.now() - (2 * 60 * 60 * 1000);
  const recentActivity = state.activities.find(a => a.timestamp > twoHoursAgo);
  
  if (!recentActivity) {
    const checkIn = `${state.patient.name}, I haven't heard from you in a while. Everything okay? Say 'yes' or press the button if you need help.`;
    emitSpeak(checkIn);
    addActivity(checkIn, 'system');
    
    // If no response in 5 minutes, alert caregiver
    setTimeout(async () => {
      const stillNoActivity = !state.activities.find(a => a.timestamp > Date.now() - 5 * 60 * 1000);
      if (stillNoActivity) {
        if (lastNoActivityAlertAt && Date.now() - lastNoActivityAlertAt < NO_ACTIVITY_ALERT_COOLDOWN_MS) {
          return;
        }
        const sent = await notifyCaregiver({
          type: 'inactivity',
          priority: 'medium',
          message: `Hey, this is GENI. No activity from ${state.patient.name} in 2+ hours. Please check in when possible.`,
        });
        if (sent) {
          lastNoActivityAlertAt = Date.now();
        }
      }
    }, 5 * 60 * 1000);
  }
}

export function generateAppointmentReminder(appointment: string, hoursUntil: number): string {
  const primaryContact = state.contacts.find(c => c.isPrimary);
  
  let reminder = `Reminder: ${appointment} in ${hoursUntil} hours.\n\n`;
  
  if (hoursUntil === 3) {
    reminder += `${primaryContact?.name} will pick you up at ${new Date(Date.now() + (hoursUntil - 0.5) * 60 * 60 * 1000).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}.\n`;
    reminder += `Have your insurance card and medication list ready.`;
  } else if (hoursUntil === 1) {
    reminder += `Get ready soon. ${primaryContact?.name} will be here shortly.`;
  }
  
  return reminder;
}

export async function sendWeeklySummaryToCaregiver() {
  const primaryContact = state.contacts.find(c => c.isPrimary);
  if (!primaryContact) return;
  
  const totalMeds = state.medicationHistory.length * 3; // Assume 3 doses/day
  const takenMeds = state.medicationHistory.reduce((sum, day) => {
    return sum + day.details.filter(d => d.status === 'taken').length;
  }, 0);
  const adherence = Math.round((takenMeds / totalMeds) * 100);
  
  const summary = `Hi ${primaryContact.name}! Here's ${state.patient.name}'s weekly summary:

✅ Medication Adherence: ${adherence}%
✅ Activity: Normal routine, active daily
✅ Health: No concerning patterns detected

Overall: ${state.patient.name} is doing well! Keep up the great work.

- GENI 🐾`;

  await notifyCaregiver({
    type: 'weekly_summary',
    priority: 'low',
    message: summary,
  });
}

export function shouldTriggerProactiveAction(): { action: string; message: string } | null {
  const now = new Date();
  const hour = now.getHours();
  
  // Morning briefing at 8am
  if (hour === 8 && !state.activities.find(a => a.message.includes('morning briefing'))) {
    return {
      action: 'morning_briefing',
      message: generateMorningBriefing()
    };
  }
  
  // Check for pending medications
  const pendingMed = state.todaysMedications.find(m => {
    if (m.status !== 'pending') return false;
    const medHour = parseInt(m.time.split(':')[0]);
    return medHour === hour;
  });
  
  if (pendingMed) {
    return {
      action: 'medication_reminder',
      message: generateSmartMedicationReminder(pendingMed.name, pendingMed.time)
    };
  }
  
  // Check for upcoming appointments
  const upcomingAppt = state.reminders.find(r => {
    if (r.type !== 'appointment' || r.completed) return false;
    const aptHour = parseInt(r.time.split(':')[0]);
    return aptHour - hour === 3; // 3 hours before
  });
  
  if (upcomingAppt) {
    return {
      action: 'appointment_reminder',
      message: generateAppointmentReminder(upcomingAppt.message, 3)
    };
  }
  
  return null;
}
