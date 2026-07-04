/**
 * GENI Context Engine
 * Aggregates all context GENI needs to respond intelligently
 */

import { state } from '../state';
import type { Activity } from '../models/Activity';
import type { Medication } from '../models/Medication';

interface FamilyMessage {
  id: string;
  senderName: string;
  message: string;
  timestamp: Date;
  read: boolean;
}

export interface GENIContext {
  // Time awareness
  timestamp: Date;
  timeOfDay: 'early-morning' | 'morning' | 'afternoon' | 'evening' | 'late-evening' | 'night';
  dayOfWeek: string;
  fullDate: string;
  
  // Patient info (from state)
  patientName: string;
  patientAge: number;
  
  // Medication state
  todaysMedications: Medication[];
  medicationStatus: 'all-taken' | 'some-pending' | 'overdue' | 'none-scheduled';
  pendingMedications: Medication[];
  overdueMedications: Medication[];
  
  // Last pill check
  lastPillCheckTime: Date | null;
  lastPillCheckResult: {
    status: 'taken' | 'present' | 'unclear';
    observations: string;
  } | null;
  
  // Activity tracking
  recentActivities: Activity[];
  lastActivityTime: Date | null;
  activityLevel: 'active' | 'normal' | 'quiet' | 'concerning';
  
  // Family/messages
  pendingFamilyMessages: FamilyMessage[];
  hasPendingMessages: boolean;
  
  // Conversation context
  lastInteractionTime: Date | null;
  hoursSinceLastInteraction: number;
}

/**
 * Get time of day category
 */
function getTimeOfDay(hour: number): GENIContext['timeOfDay'] {
  if (hour >= 4 && hour < 7) return 'early-morning';
  if (hour >= 7 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 20) return 'evening';
  if (hour >= 20 && hour < 23) return 'late-evening';
  return 'night';
}

/**
 * Determine medication status
 */
function getMedicationStatus(medications: Medication[]): {
  status: GENIContext['medicationStatus'];
  pending: Medication[];
  overdue: Medication[];
} {
  if (medications.length === 0) {
    return { status: 'none-scheduled', pending: [], overdue: [] };
  }
  
  const now = new Date();
  const currentHour = now.getHours();
  const currentMinutes = now.getMinutes();
  const currentTime = currentHour * 60 + currentMinutes;
  
  const pending = medications.filter(m => m.status === 'pending');
  const overdue = pending.filter(med => {
    const [medHour, medMinutes] = med.time.split(':').map(Number);
    const medTime = medHour * 60 + medMinutes;
    const minutesLate = currentTime - medTime;
    return minutesLate > 30; // Overdue if >30 min late
  });
  
  if (pending.length === 0) {
    return { status: 'all-taken', pending, overdue };
  }
  
  if (overdue.length > 0) {
    return { status: 'overdue', pending, overdue };
  }
  
  return { status: 'some-pending', pending, overdue };
}

/**
 * Determine activity level
 */
function getActivityLevel(activities: Activity[]): GENIContext['activityLevel'] {
  const now = new Date();
  const recentActivities = activities.filter(a => {
    const activityTime = new Date(a.timestamp);
    const hoursSince = (now.getTime() - activityTime.getTime()) / (1000 * 60 * 60);
    return hoursSince < 4; // Last 4 hours
  });
  
  if (recentActivities.length === 0) return 'concerning';
  if (recentActivities.length < 3) return 'quiet';
  if (recentActivities.length < 8) return 'normal';
  return 'active';
}

/**
 * Build complete GENI context
 */
export function buildGENIContext(): GENIContext {
  const now = new Date();
  const hour = now.getHours();
  
  // Time context
  const dayOfWeek = now.toLocaleDateString('en-US', { weekday: 'long' });
  const fullDate = now.toLocaleDateString('en-US', { 
    weekday: 'long', 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  });
  
  // Medication context
  const { status: medicationStatus, pending, overdue } = getMedicationStatus(state.todaysMedications);
  
  // Activity context
  const recentActivities = state.activities.slice(-20);
  const lastActivity = state.activities[state.activities.length - 1];
  const lastActivityTime = lastActivity ? new Date(lastActivity.timestamp) : null;
  const activityLevel = getActivityLevel(state.activities);
  
  // Family messages
  const pendingFamilyMessages = state.familyMessages.filter(m => !m.read);
  
  // Last interaction
  const lastInteractionTime = lastActivityTime; // For now, using last activity
  const hoursSinceLastInteraction = lastInteractionTime 
    ? (now.getTime() - lastInteractionTime.getTime()) / (1000 * 60 * 60)
    : 999;
  
  // Last pill check (from activities)
  const pillCheckActivities = state.activities
    .filter(a => a.message.toLowerCase().includes('pill check'))
    .slice(-1);
  const lastPillCheckActivity = pillCheckActivities[0];
  const lastPillCheckTime = lastPillCheckActivity ? new Date(lastPillCheckActivity.timestamp) : null;
  
  // Last pill check (from state)
  const lastPillCheckResult = state.pillCheckResults.length > 0 
    ? state.pillCheckResults[state.pillCheckResults.length - 1]
    : null;
  
  // Extract first name only (e.g., "Margaret Johnson" → "Margaret")
  const firstName = state.patient.name.split(' ')[0];
  
  return {
    timestamp: now,
    timeOfDay: getTimeOfDay(hour),
    dayOfWeek,
    fullDate,
    
    patientName: firstName,
    patientAge: state.patient.age,
    
    todaysMedications: state.todaysMedications,
    medicationStatus,
    pendingMedications: pending,
    overdueMedications: overdue,
    
    lastPillCheckTime,
    lastPillCheckResult,
    
    recentActivities,
    lastActivityTime,
    activityLevel,
    
    pendingFamilyMessages,
    hasPendingMessages: pendingFamilyMessages.length > 0,
    
    lastInteractionTime,
    hoursSinceLastInteraction
  };
}

/**
 * Format context for debugging/logging
 */
export function formatContextSummary(context: GENIContext): string {
  return `
📅 ${context.fullDate}
⏰ ${context.timeOfDay} (${context.timestamp.toLocaleTimeString()})
👤 Patient: ${context.patientName}, ${context.patientAge}
💊 Medications: ${context.medicationStatus}
   - Pending: ${context.pendingMedications.length}
   - Overdue: ${context.overdueMedications.length}
🏃 Activity: ${context.activityLevel}
📬 Messages: ${context.hasPendingMessages ? 'Yes' : 'No'}
🕐 Last interaction: ${context.hoursSinceLastInteraction.toFixed(1)}h ago
  `.trim();
}
