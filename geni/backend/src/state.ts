import { Patient, Contact } from './models/Patient';
import { Medication, MedicationHistory } from './models/Medication';
import { Activity, createActivity } from './models/Activity';
import { Reminder } from './models/Reminder';
import { config } from './config';
import { loadProfile } from './lib/profile';
import { getDerivedMedicationHistory } from './database/pillCheckHistory';

interface PillCheckResult {
  timestamp: Date;
  status: 'taken' | 'present' | 'unclear';
  observations: string;
  compartments?: Record<string, string>;
  confidence: string;
}

interface FamilyMessage {
  id: string;
  senderName: string;
  message: string;
  timestamp: Date;
  read: boolean;
}

interface YOLOEmergency {
  type: 'fall' | 'desk_faint' | 'unresponsive';
  timestamp: Date;
  acknowledged: boolean;
}

interface AppState {
  patient: Patient;
  contacts: Contact[];
  todaysMedications: Medication[];
  medicationHistory: MedicationHistory[];
  activities: Activity[];
  reminders: Reminder[];
  pillCheckResults: PillCheckResult[];
  familyMessages: FamilyMessage[];
  lastEmergency?: YOLOEmergency;
  emergencyTriggeredAt?: Date;
  hardwareStatus: {
    online: boolean;
    leds: {
      red: boolean;
      yellow: boolean;
      green: boolean;
    };
    buzzer: boolean;
    button: 'idle' | 'pressed';
    lastSync: number;
  };
}

// ---------------------------------------------------------------------------
// State is built from data, never from literals:
//   - patient / contacts / medication schedule / reminders → data/profile.json
//   - medication history → derived from real pill-check records (SQLite)
// ---------------------------------------------------------------------------

const profile = loadProfile();

// Env can override the patient name (e.g. per-device deployment); the
// profile is the default source of truth.
config.patient.name = process.env.PATIENT_NAME || profile.patient.name;

function parseTimeToMinutes(time: string): number {
  const match = time.match(/(\d+):(\d+)\s*(AM|PM)?/i);
  if (!match) return 0;
  let hours = parseInt(match[1]);
  const minutes = parseInt(match[2]);
  const meridiem = match[3]?.toUpperCase();
  if (meridiem === 'PM' && hours !== 12) hours += 12;
  if (meridiem === 'AM' && hours === 12) hours = 0;
  return hours * 60 + minutes;
}

function buildTodaysMedications(): Medication[] {
  const nowMinutes = new Date().getHours() * 60 + new Date().getMinutes();
  return profile.medications.map(med => ({
    name: med.name,
    dosage: med.dosage,
    time: med.time,
    period: med.period,
    // Past-due doses start as 'pending' (awaiting confirmation); future
    // doses 'upcoming'. Runtime confirmations move them to 'taken'.
    status: parseTimeToMinutes(med.time) <= nowMinutes ? 'pending' : 'upcoming',
  }));
}

export const state: AppState = {
  patient: {
    name: config.patient.name,
    age: profile.patient.age,
    conditions: profile.patient.conditions,
    allergies: profile.patient.allergies,
  },

  contacts: profile.contacts,

  todaysMedications: buildTodaysMedications(),

  medicationHistory: getDerivedMedicationHistory(7),

  activities: [createActivity('GENI initialized and ready', 'system')],

  reminders: profile.reminders.map((r, i) => ({
    id: String(i + 1),
    time: r.time,
    message: r.message,
    completed: false,
    type: r.type,
  })),

  pillCheckResults: [],

  familyMessages: [],

  hardwareStatus: {
    online: true,
    leds: { red: false, yellow: false, green: true },
    buzzer: false,
    button: 'idle',
    lastSync: Date.now(),
  },
};

// Helper functions
export function addActivity(message: string, type: Activity['type']) {
  const activity = createActivity(message, type);
  state.activities.unshift(activity);
  
  // Keep only last 50 activities
  if (state.activities.length > 50) {
    state.activities = state.activities.slice(0, 50);
  }
  
  return activity;
}

export function updateMedicationStatus(medicationName: string, status: Medication['status']) {
  const med = state.todaysMedications.find(m => m.name === medicationName);
  if (med) {
    med.status = status;
    return true;
  }
  return false;
}

export function addPillCheckResult(result: Omit<PillCheckResult, 'timestamp'>) {
  state.pillCheckResults.push({
    ...result,
    timestamp: new Date(),
  });
  // Keep only last 50 results
  if (state.pillCheckResults.length > 50) {
    state.pillCheckResults.shift();
  }
}

export function addFamilyMessage(senderName: string, message: string) {
  state.familyMessages.push({
    id: `${Date.now()}-${Math.random()}`,
    senderName,
    message,
    timestamp: new Date(),
    read: false,
  });
}

export function markFamilyMessageAsRead(messageId: string) {
  const msg = state.familyMessages.find(m => m.id === messageId);
  if (msg) {
    msg.read = true;
  }
}

export function getPrimaryContact(): Contact | undefined {
  return state.contacts.find(c => c.isPrimary);
}
