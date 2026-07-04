/**
 * Medication Adherence Analysis Service
 * Analyzes pill compartment states against current day/time to detect adherence issues
 * NO HARDCODED PATIENT NAMES - uses config.patient.name dynamically
 */

import { config } from '../config';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('medication-adherence');

export type CompartmentState = 'empty' | 'full' | 'unclear';

export interface CompartmentStates {
  monday?: CompartmentState;
  tuesday?: CompartmentState;
  wednesday?: CompartmentState;
  thursday?: CompartmentState;
  friday?: CompartmentState;
  saturday?: CompartmentState;
  sunday?: CompartmentState;
}

export type ConcernLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';

export interface AdherenceAnalysis {
  concernLevel: ConcernLevel;
  missedDays: number;
  expectedEmptyDays: string[]; // Days that SHOULD be empty by now
  actualEmptyDays: string[]; // Days that ARE empty
  actualFullDays: string[]; // Days that are still full
  issues: string[]; // Specific problems detected
  message: string; // Human-readable summary
  shouldAlertCaregiver: boolean;
  caregiverAlertMessage?: string;
}

/**
 * Get current day of week
 */
function getCurrentDay(): string {
  const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
  const now = new Date();
  return days[now.getDay()];
}

/**
 * Get all days up to and including a specific day
 */
function getDaysUpTo(targetDay: string): string[] {
  const allDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
  const targetIndex = allDays.indexOf(targetDay.toLowerCase());
  
  if (targetIndex === -1) return [];
  
  return allDays.slice(0, targetIndex + 1);
}

/**
 * Get days from Monday to target day (weekday perspective)
 */
function getWeekdaysUpTo(targetDay: string): string[] {
  const weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];
  const targetIndex = weekdays.indexOf(targetDay.toLowerCase());
  
  if (targetIndex === -1) {
    // If weekend or not found, return all weekdays
    return weekdays;
  }
  
  // Days BEFORE today. Today's compartment isn't 'missed' just because
  // the patient hasn't taken this morning's dose yet.
  return weekdays.slice(0, targetIndex);
}

/**
 * Analyze medication adherence based on compartment states and current day/time
 * 
 * Pattern Logic:
 * - Today: Monday AM, Monday empty → ✅ Perfect
 * - Today: Wednesday, Monday empty, Tue-Fri full → ⚠️ Missed 1 day  
 * - Today: Friday, Monday empty, Tue-Fri full → 🚨 Missed 3 days
 * - Today: Sunday, Mon-Fri all full → 🚨 CRITICAL - whole week missed
 */
export function analyzeMedicationAdherence(
  compartments: CompartmentStates,
  currentDay?: string,
  currentTime?: Date
): AdherenceAnalysis {
  const now = currentTime || new Date();
  const today = (currentDay || getCurrentDay()).toLowerCase();
  
  log.info('🔍 Analyzing medication adherence...');
  log.info({ detail: today }, '📅 Current day:');
  log.info({ detail: compartments }, '💊 Compartments:');
  
  // Determine which days SHOULD be empty by now
  // Logic: On Wednesday, Monday and Tuesday should be empty (assuming daily meds)
  const expectedEmptyDays = getWeekdaysUpTo(today);
  
  log.info({ detail: expectedEmptyDays }, '📊 Expected empty days:');
  
  // Get actual states
  const actualEmptyDays: string[] = [];
  const actualFullDays: string[] = [];
  const unclearDays: string[] = [];
  
  Object.entries(compartments).forEach(([day, state]) => {
    if (state === 'empty') {
      actualEmptyDays.push(day);
    } else if (state === 'full') {
      actualFullDays.push(day);
    } else if (state === 'unclear') {
      unclearDays.push(day);
    }
  });
  
  log.info({ detail: actualEmptyDays }, '✅ Actually empty:');
  log.info({ detail: actualFullDays }, '❌ Still full:');
  log.info({ detail: unclearDays }, '❓ Unclear:');
  
  // Calculate missed days
  // Missed = days that SHOULD be empty but are FULL
  const missedDays = expectedEmptyDays.filter(day => actualFullDays.includes(day));
  const missedCount = missedDays.length;
  
  log.info({ missedDays, missedCount }, 'missed days computed');
  
  // Determine concern level
  let concernLevel: ConcernLevel = 'none';
  let shouldAlertCaregiver = false;
  const issues: string[] = [];
  
  if (missedCount === 0 && actualEmptyDays.length > 0) {
    // Perfect adherence
    concernLevel = 'none';
    issues.push('All expected medications taken on time');
  } else if (missedCount === 1) {
    // 1 day missed
    concernLevel = 'low';
    shouldAlertCaregiver = false; // Informational only
    issues.push(`Missed 1 day: ${missedDays[0]}`);
  } else if (missedCount === 2) {
    // 2 days missed
    concernLevel = 'medium';
    shouldAlertCaregiver = true;
    issues.push(`Missed 2 days: ${missedDays.join(', ')}`);
  } else if (missedCount >= 3 && missedCount <= 4) {
    // 3-4 days missed
    concernLevel = 'high';
    shouldAlertCaregiver = true;
    issues.push(`Missed ${missedCount} days: ${missedDays.join(', ')}`);
  } else if (missedCount >= 5) {
    // 5+ days missed - CRITICAL
    concernLevel = 'critical';
    shouldAlertCaregiver = true;
    issues.push(`CRITICAL: Missed ${missedCount} days`);
  }
  
  // Special case: If it's weekend and whole week is full
  if ((today === 'saturday' || today === 'sunday') && actualFullDays.length >= 5) {
    concernLevel = 'critical';
    shouldAlertCaregiver = true;
    issues.push('CRITICAL: Entire week of medications not taken');
  }
  
  // Special case: All compartments unclear
  if (unclearDays.length > 0 && actualEmptyDays.length === 0 && actualFullDays.length === 0) {
    concernLevel = 'medium';
    shouldAlertCaregiver = false;
    issues.push('Cannot verify medication status - manual check needed');
  }
  
  // Generate summary message
  const message = generateSummaryMessage({
    concernLevel,
    missedCount,
    missedDays,
    actualEmptyDays,
    today,
    issues
  });
  
  // Generate caregiver alert if needed
  const caregiverAlertMessage = shouldAlertCaregiver 
    ? generateCaregiverAlertMessage({
        concernLevel,
        missedCount,
        missedDays,
        today,
        issues
      })
    : undefined;
  
  return {
    concernLevel,
    missedDays: missedCount,
    expectedEmptyDays,
    actualEmptyDays,
    actualFullDays,
    issues,
    message,
    shouldAlertCaregiver,
    caregiverAlertMessage
  };
}

/**
 * Generate patient-facing message (uses dynamic patient name)
 */
function generateSummaryMessage(params: {
  concernLevel: ConcernLevel;
  missedCount: number;
  missedDays: string[];
  actualEmptyDays: string[];
  today: string;
  issues: string[];
}): string {
  const { concernLevel, missedCount, missedDays, actualEmptyDays, today } = params;
  
  // Extract first name from config
  const patientFirstName = config.patient.name.split(' ')[0];
  
  if (concernLevel === 'none') {
    if (actualEmptyDays.length === 1 && actualEmptyDays[0] === today) {
      return `Great job, ${patientFirstName}! You took your ${today} medication.`;
    } else {
      return `Looking good, ${patientFirstName}! You're staying on track with your medications.`;
    }
  }
  
  if (concernLevel === 'low') {
    const missedDay = missedDays[0];
    const dayName = missedDay.charAt(0).toUpperCase() + missedDay.slice(1);
    return `Hey ${patientFirstName}, I noticed ${dayName}'s medication is still there. Did you take it already?`;
  }
  
  if (concernLevel === 'medium') {
    return `${patientFirstName}, I see you haven't taken your meds for the last ${missedCount} days. Everything okay?`;
  }
  
  if (concernLevel === 'high') {
    return `${patientFirstName}, you've missed ${missedCount} days of medication. This is important - let's get back on track.`;
  }
  
  if (concernLevel === 'critical') {
    if (missedCount >= 5) {
      return `${patientFirstName}, you haven't taken your medications all week. I'm really concerned. Let's talk about what's going on.`;
    } else {
      return `${patientFirstName}, this is serious - you've missed several days. I need to let your family know.`;
    }
  }
  
  return `Let me check on your medications, ${patientFirstName}.`;
}

/**
 * Generate caregiver alert message (uses dynamic patient name)
 */
function generateCaregiverAlertMessage(params: {
  concernLevel: ConcernLevel;
  missedCount: number;
  missedDays: string[];
  today: string;
  issues: string[];
}): string {
  const { concernLevel, missedCount, missedDays, today } = params;
  
  // Use full patient name from config
  const patientName = config.patient.name;
  const now = new Date();
  const timeStr = now.toLocaleString('en-US', { 
    weekday: 'short',
    month: 'short', 
    day: 'numeric',
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true 
  });
  
  let message = `🚨 Medication Alert - ${patientName}\n`;
  message += `${timeStr}\n\n`;
  
  if (concernLevel === 'medium') {
    message += `📊 Status: Missed ${missedCount} days\n`;
    message += `Days: ${missedDays.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')}\n\n`;
    message += `Action: Please check on ${patientName.split(' ')[0]}`;
  } else if (concernLevel === 'high') {
    message += `⚠️ URGENT: Missed ${missedCount} days\n`;
    message += `Days: ${missedDays.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')}\n\n`;
    message += `Action: Call ${patientName.split(' ')[0]} immediately`;
  } else if (concernLevel === 'critical') {
    message += `🚨 CRITICAL: ${missedCount >= 5 ? 'Entire week missed' : `Missed ${missedCount} days`}\n`;
    if (missedDays.length > 0) {
      message += `Days: ${missedDays.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')}\n`;
    }
    message += `\nAction: URGENT - Contact ${patientName.split(' ')[0]} NOW`;
  }
  
  return message;
}

/**
 * Determine if caregiver should be alerted (wrapper for backward compatibility)
 */
export function shouldAlertCaregiver(analysis: AdherenceAnalysis): boolean {
  return analysis.shouldAlertCaregiver;
}

/**
 * Get patient message from analysis (wrapper)
 */
export function getPatientMessage(analysis: AdherenceAnalysis): string {
  return analysis.message;
}

/**
 * Get caregiver alert message from analysis (wrapper)
 */
export function getCaregiverAlert(analysis: AdherenceAnalysis): string | undefined {
  return analysis.caregiverAlertMessage;
}
