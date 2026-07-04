export interface Patient {
  name: string;
  age: number;
  conditions: string[];
  allergies: string[];
}

export interface Contact {
  name: string;
  relationship: string;
  phone: string;
  isPrimary: boolean;
}
