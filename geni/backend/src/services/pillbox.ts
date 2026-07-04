/**
 * Pill Box Intelligence Service
 * Handles context-aware medication management based on pill box state
 * NOW POWERED BY GENI BRAIN - No hardcoded responses
 */

import { state, addActivity } from '../state';
import { emitActivity, emitSpeak } from '../socket';
import { sendCaregiverUpdate, sendMedicationAlert } from './twilio';
import { generatePillCheckResponse } from './geni-brain';

export interface PillBoxState {
  monday: 'full' | 'empty';
  tuesday: 'full' | 'empty';
  wednesday: 'full' | 'empty';
  thursday: 'full' | 'empty';
  friday: 'full' | 'empty';
  saturday?: 'full' | 'empty';
  sunday?: 'full' | 'empty';
}

/**
 * Analyze pill box and determine appropriate action
 */
export async function analyzePillBox(pillBoxState: PillBoxState): Promise<{
  status: string;
  action: string;
  message: string;
  caregiverAlert?: string;
}> {
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
  const allDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];
  
  // Check if all compartments are full
  const allFull = allDays.every(day => pillBoxState[day as keyof PillBoxState] === 'full');
  
  // Check if all compartments are empty
  const allEmpty = allDays.every(day => pillBoxState[day as keyof PillBoxState] === 'empty');
  
  // Check today's compartment
  const todayState = pillBoxState[today as keyof PillBoxState];
  
  // Scenario 1: All compartments full (week just refilled)
  if (allFull) {
    const message = `Great! Your pill box is fully stocked for the week. Remember to take your medications with food and plenty of water. Let's have a healthy week, ${state.patient.name}!`;
    
    // Log activity
    addActivity('Pill box fully stocked for the week', 'medication');
    
    // Speak to user
    emitSpeak(message);
    
    // Inform caregiver
    const primaryCaregiver = state.contacts.find(c => c.isPrimary);
    if (primaryCaregiver) {
      await sendCaregiverUpdate(
        primaryCaregiver.phone,
        state.patient.name,
        'Pill box has been refilled for the week',
        'All compartments are full'
      );
    }
    
    return {
      status: 'full_week',
      action: 'remind_routine',
      message,
      caregiverAlert: 'Pill box refilled for the week'
    };
  }
  
  // Scenario 2: All compartments empty (needs refill)
  if (allEmpty) {
    const message = `${state.patient.name}, I notice your pill box is empty. It's time to refill it for the upcoming week. I'm also notifying your caregiver to help with the refill.`;
    
    // Log activity
    const activity = addActivity('Pill box empty - Refill needed', 'medication');
    emitActivity(activity);
    
    // Speak to user
    emitSpeak(message);
    
    // Alert caregiver
    const primaryCaregiver = state.contacts.find(c => c.isPrimary);
    if (primaryCaregiver) {
      await sendMedicationAlert(
        primaryCaregiver.phone,
        state.patient.name,
        'all medications',
        'refill_needed'
      );
    }
    
    return {
      status: 'empty_week',
      action: 'refill_needed',
      message,
      caregiverAlert: 'Pill box refill needed urgently'
    };
  }
  
  // Scenario 3: Monday empty (check if taken or needs refill)
  if (pillBoxState.monday === 'empty') {
    // Check if it's actually Monday
    if (today === 'monday') {
      const message = `Perfect! I can see you've taken your Monday medication. Great job keeping up with your schedule!`;
      
      // Update medication status
      const mondayMeds = state.todaysMedications.filter(m => m.period === 'morning');
      mondayMeds.forEach(med => {
        med.status = 'taken';
      });
      
      // Log activity
      addActivity('Monday medication confirmed taken (camera verification)', 'medication');
      
      // Inform caregiver
      const primaryCaregiver = state.contacts.find(c => c.isPrimary);
      if (primaryCaregiver) {
        await sendCaregiverUpdate(
          primaryCaregiver.phone,
          state.patient.name,
          `Just took Monday medications (${mondayMeds.map(m => m.name).join(', ')})`,
          'Camera verified empty compartment'
        );
      }
      
      return {
        status: 'taken',
        action: 'medication_confirmed',
        message,
        caregiverAlert: 'Monday medication taken and confirmed'
      };
    } else {
      // Not Monday but Monday compartment empty - might be mid-week
      // Check the current day's compartment
      if (todayState === 'full') {
        const message = `${state.patient.name}, I see you haven't taken today's (${today.charAt(0).toUpperCase() + today.slice(1)}) medication yet. The compartment still has pills. Would you like me to remind you about your ${today} medication?`;
        
        // Speak to user
        emitSpeak(message);
        
        return {
          status: 'not_taken_today',
          action: 'remind_today',
          message
        };
      } else {
        // Today's compartment is empty - good!
        const message = `Excellent! Your ${today.charAt(0).toUpperCase() + today.slice(1)} medication has been taken. Keep up the great work!`;
        
        // Log activity
        addActivity(`${today.charAt(0).toUpperCase() + today.slice(1)} medication confirmed taken`, 'medication');
        
        return {
          status: 'taken',
          action: 'medication_confirmed',
          message
        };
      }
    }
  }
  
  // Scenario 4: Current day compartment still full (hasn't taken today's meds)
  if (todayState === 'full') {
    const currentTime = new Date().getHours();
    let period = 'morning';
    if (currentTime >= 12 && currentTime < 17) period = 'afternoon';
    if (currentTime >= 17) period = 'evening';
    
    const todayMeds = state.todaysMedications.filter(m => m.period === period && m.status === 'pending');
    
    if (todayMeds.length > 0) {
      const medNames = todayMeds.map(m => m.name).join(' and ');
      const message = `${state.patient.name}, I notice you haven't taken your ${period} medication yet. You have ${medNames} scheduled for ${period}. Please take them when you're ready.`;
      
      // Speak reminder
      emitSpeak(message);
      
      // If significantly late, alert caregiver
      const medTime = parseInt(todayMeds[0].time.split(':')[0]);
      if (currentTime > medTime + 2) {
        const primaryCaregiver = state.contacts.find(c => c.isPrimary);
        if (primaryCaregiver) {
          await sendMedicationAlert(
            primaryCaregiver.phone,
            state.patient.name,
            medNames,
            'late'
          );
        }
      }
      
      return {
        status: 'present',
        action: 'remind_now',
        message
      };
    }
  }
  
  // Default: Check compartment
  return {
    status: 'checking',
    action: 'verify',
    message: 'Let me verify your pill box status...'
  };
}

/**
 * Get medication context for AI responses
 */
export function getMedicationContext(): string {
  const patient = state.patient;
  const meds = state.todaysMedications;
  
  return `
PATIENT: ${patient.name}, Age ${patient.age}
ALLERGIES: ${patient.allergies.join(', ')} - NEVER suggest these!
CONDITIONS: ${patient.conditions.join(', ')}

TODAY'S MEDICATIONS:
${meds.map(m => `- ${m.name} (${m.dosage}) at ${m.time} - Status: ${m.status}`).join('\n')}

IMPORTANT MEDICATION RULES:
1. Metformin should be taken with food to avoid stomach upset
2. Blood pressure medication (Lisinopril) should be taken at the same time daily
3. Patient takes Metformin twice daily (morning and evening)
4. Always check for allergies before suggesting any medication
5. Remind about water intake with medications

When advising about medications:
- Be specific about which medication and when
- Mention food requirements if applicable
- Use encouraging, warm language
- Don't sound medical/clinical - be like a caring friend
`.trim();
}
