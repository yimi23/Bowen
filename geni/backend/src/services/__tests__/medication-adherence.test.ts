import { describe, it, expect } from 'vitest';
import { analyzeMedicationAdherence, type CompartmentStates } from '../medication-adherence';

function week(overrides: Partial<CompartmentStates>): CompartmentStates {
  return {
    monday: 'full',
    tuesday: 'full',
    wednesday: 'full',
    thursday: 'full',
    friday: 'full',
    saturday: 'full',
    sunday: 'full',
    ...overrides,
  };
}

describe('analyzeMedicationAdherence', () => {
  it('perfect adherence: no concern, no caregiver alert', () => {
    const result = analyzeMedicationAdherence(
      week({ monday: 'empty', tuesday: 'empty' }),
      'wednesday'
    );
    expect(result.concernLevel).toBe('none');
    expect(result.shouldAlertCaregiver).toBe(false);
  });

  it('one missed day: low concern, informational only', () => {
    const result = analyzeMedicationAdherence(
      week({ monday: 'full', tuesday: 'empty' }),
      'wednesday'
    );
    expect(result.concernLevel).toBe('low');
    expect(result.shouldAlertCaregiver).toBe(false);
  });

  it('two missed days: medium concern, caregiver alerted', () => {
    const result = analyzeMedicationAdherence(
      week({ monday: 'full', tuesday: 'full', wednesday: 'empty' }),
      'thursday'
    );
    expect(result.concernLevel).toBe('medium');
    expect(result.shouldAlertCaregiver).toBe(true);
  });

  it('three to four missed days: high concern', () => {
    const result = analyzeMedicationAdherence(
      week({ monday: 'full', tuesday: 'full', wednesday: 'full', thursday: 'empty' }),
      'friday'
    );
    expect(result.concernLevel).toBe('high');
    expect(result.shouldAlertCaregiver).toBe(true);
  });

  it('entire week untouched on Sunday: critical', () => {
    const result = analyzeMedicationAdherence(week({}), 'sunday');
    expect(result.concernLevel).toBe('critical');
    expect(result.shouldAlertCaregiver).toBe(true);
  });

  it('all compartments unclear: medium concern, manual check, no alert', () => {
    const result = analyzeMedicationAdherence(
      {
        monday: 'unclear',
        tuesday: 'unclear',
        wednesday: 'unclear',
        thursday: 'unclear',
        friday: 'unclear',
        saturday: 'unclear',
        sunday: 'unclear',
      },
      'wednesday'
    );
    expect(result.concernLevel).toBe('medium');
    expect(result.shouldAlertCaregiver).toBe(false);
  });
});
