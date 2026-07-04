export interface Medication {
  name: string;
  dosage: string;
  time: string;
  status: 'taken' | 'pending' | 'missed' | 'upcoming';
  period: 'morning' | 'afternoon' | 'evening';
}

export interface MedicationSchedule {
  date: string;
  medications: Medication[];
}

export interface MedicationHistory {
  date: string;
  day: string;
  dayNumber: number;
  status: 'all-taken' | 'partial' | 'none' | 'today';
  details: {
    time: string;
    medication: string;
    status: 'taken' | 'missed';
  }[];
}
