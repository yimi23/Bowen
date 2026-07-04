/**
 * Patient profile loader.
 *
 * Everything about WHO GENI cares for — name, age, conditions, contacts,
 * medication schedule, reminders — lives in data/profile.json (gitignored,
 * user-editable), never in code. First boot seeds it from
 * profile.example.json with placeholder data and warns loudly.
 */

import fs from 'fs';
import path from 'path';
import { moduleLogger } from './logger';

const log = moduleLogger('profile');

export interface ProfileContact {
  name: string;
  relationship: string;
  phone: string;
  isPrimary: boolean;
}

export interface ProfileMedication {
  name: string;
  dosage: string;
  time: string; // e.g. "8:00 AM"
  period: 'morning' | 'afternoon' | 'evening';
}

export interface ProfileReminder {
  time: string;
  message: string;
  type: 'medication' | 'appointment' | 'general';
}

export interface PatientProfile {
  patient: {
    name: string;
    age: number;
    conditions: string[];
    allergies: string[];
  };
  contacts: ProfileContact[];
  medications: ProfileMedication[];
  reminders: ProfileReminder[];
}

const PROFILE_PATH = path.join(__dirname, '../../data/profile.json');
const EXAMPLE_PATH = path.join(__dirname, '../../profile.example.json');

export function loadProfile(): PatientProfile {
  const dataDir = path.dirname(PROFILE_PATH);
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  if (!fs.existsSync(PROFILE_PATH)) {
    fs.copyFileSync(EXAMPLE_PATH, PROFILE_PATH);
    log.warn(
      { path: PROFILE_PATH },
      'No patient profile found — seeded a PLACEHOLDER profile. Edit data/profile.json with the real patient before relying on GENI.'
    );
  }

  const profile = JSON.parse(fs.readFileSync(PROFILE_PATH, 'utf-8')) as PatientProfile;

  // Minimal validation: fail fast on a malformed profile rather than running
  // an elder-care system against garbage data.
  if (!profile.patient?.name) throw new Error('profile.json: patient.name is required');
  if (!Array.isArray(profile.contacts)) throw new Error('profile.json: contacts must be an array');
  if (!profile.contacts.some(c => c.isPrimary)) {
    log.warn('profile.json has no primary contact — caregiver notifications will be skipped');
  }
  if (!Array.isArray(profile.medications)) throw new Error('profile.json: medications must be an array');

  log.info(
    {
      patient: profile.patient.name,
      contacts: profile.contacts.length,
      medications: profile.medications.length,
    },
    'patient profile loaded'
  );
  return profile;
}
