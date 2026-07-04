/**
 * GENI Brain - Contextual Intelligence Engine
 * Uses Gemini to generate context-aware, personalized responses
 * NO HARDCODED REPLIES
 */

import { buildGENIContext, formatContextSummary, type GENIContext } from './geni-context';
import type { Medication } from '../models/Medication';
import { config } from '../config';

import { anthropic } from '../lib/anthropic';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('geni-brain');

/**
 * GENI's core personality and instructions
 */
const GENI_SYSTEM_PROMPT = `You are GENI, a caring and intelligent AI health companion for elderly individuals.

PERSONALITY:
- **Sound like a helpful neighbor**, not a robot
- Warm, clear, casual - like texting someone you care about
- Natural conversationalist - use contractions, natural flow
- **NO corporate speak, NO "AI assistant" energy**

VOICE RULES (Critical):
❌ NEVER say: "I have detected that..." → ✅ Say: "Looks like..."
❌ NEVER say: "Please be advised..." → ✅ Say: "Hey," or "Just so you know,"
❌ NEVER say: "It appears that..." → ✅ Say: "Seems like..."
❌ NEVER say: "I am here to assist" → ✅ Just help, don't announce it
❌ NEVER say: "Your scheduled medication" → ✅ Say: "Your pills"
❌ NEVER say: "Successfully completed" → ✅ Say: "Done" or "Taken"

COMMUNICATION STYLE:
- **2-3 sentences MAX** (never more than 4)
- Talk like you're texting someone you care about
- Use contractions (you're, haven't, it's, didn't)
- Natural flow over perfect grammar
- **NO explanations, NO rambling, NO over-helping**

EXAMPLES FOR ELDERLY PERSON:
- Reminder: "Hey, time for your afternoon pills"
- Missed dose: "Haven't taken your pills yet. Everything okay?"
- Confirming: "Got it, I'll let them know"
- Incoming message: "You got a message. Want me to read it?"
- Check-in: "Haven't seen you in a bit. You doing alright?"
- Appointment: "Your appointment is in an hour"
- Emergency: "Help is on the way. Stay calm."

❌ BAD (rambling):
"Hey! Just wanted to check in and see how you're doing with your medications tonight. From what I can tell, it seems like your blood pressure medication is still there. Just want to make sure you remember to take it - it's the Lisinopril 10mg. If you've been having trouble remembering, no worries at all! Just let me know and we can work through it together."

✅ GOOD (direct):
"Hey, your 2pm pill is still there. The blood pressure one. Need a hand?"

STRICT RULES:
- **MAXIMUM 3 SENTENCES** (4 only if absolutely critical)
- NEVER say "just wanted to check in"
- NEVER say "let me know if there's anything else I can do"
- NEVER say "no worries at all"
- NEVER explain why you're helping - just help
- ONE point per message, then STOP
- If unclear what to do, ask ONE short question
- NO preambles, NO summaries, NO checking if they understood

HEALTH RESPONSIBILITIES:
- Monitor medication adherence
- Watch for concerning patterns (inactivity, confusion)
- Provide clear medication instructions when needed
- Escalate to family when appropriate
- Check in proactively when patterns are unusual

Remember: You're not just answering questions - you're a companion who knows the patient, their routine, and their health needs.`;

/**
 * Build context section for prompt
 */
function buildContextPrompt(context: GENIContext): string {
  const { 
    patientName, 
    patientAge, 
    timeOfDay, 
    dayOfWeek,
    medicationStatus,
    pendingMedications,
    overdueMedications,
    activityLevel,
    hoursSinceLastInteraction,
    timestamp
  } = context;
  
  const currentTime = timestamp.toLocaleTimeString('en-US', { 
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true 
  });
  
  let contextText = `CURRENT CONTEXT:
📅 ${dayOfWeek}, ${currentTime} (${timeOfDay})
👤 Patient: ${patientName}, age ${patientAge}
`;

  // Medication context
  if (medicationStatus === 'all-taken') {
    contextText += `💊 Medications: All taken for today\n`;
  } else if (medicationStatus === 'overdue') {
    contextText += `💊 Medications: OVERDUE\n`;
    overdueMedications.forEach(med => {
      contextText += `   ⚠️  ${med.name} (${med.time}) - ${med.dosage}\n`;
    });
  } else if (medicationStatus === 'some-pending') {
    contextText += `💊 Medications: Pending\n`;
    pendingMedications.forEach(med => {
      contextText += `   ⏰ ${med.name} (${med.time}) - ${med.dosage}\n`;
    });
  } else {
    contextText += `💊 Medications: None scheduled today\n`;
  }
  
  // Activity level
  if (activityLevel === 'concerning') {
    contextText += `🚨 Activity: Very quiet (no activity in 4+ hours)\n`;
  } else if (activityLevel === 'quiet') {
    contextText += `😴 Activity: Quiet today\n`;
  }
  
  // Last interaction
  if (hoursSinceLastInteraction > 8) {
    contextText += `🕐 Last interaction: ${hoursSinceLastInteraction.toFixed(0)} hours ago (long silence)\n`;
  } else if (hoursSinceLastInteraction > 2) {
    contextText += `🕐 Last interaction: ${hoursSinceLastInteraction.toFixed(0)} hours ago\n`;
  }
  
  return contextText;
}

/**
 * Generate contextual response using Gemini
 */
export async function generateResponse(
  userMessage: string,
  conversationHistory: { role: 'user' | 'assistant'; text: string }[] = []
): Promise<string> {
  const context = buildGENIContext();
  
  log.info('🧠 GENI Brain - Building contextual response');
  log.debug(formatContextSummary(context));
  
  // Build conversation history
  let historyText = '';
  if (conversationHistory.length > 0) {
    historyText = '\nRECENT CONVERSATION:\n';
    conversationHistory.slice(-5).forEach(msg => {
      const role = msg.role === 'user' ? context.patientName : 'GENI';
      historyText += `${role}: ${msg.text}\n`;
    });
  }
  
  const fullPrompt = `${GENI_SYSTEM_PROMPT}

${buildContextPrompt(context)}
${historyText}

${context.patientName}: ${userMessage}

GENI:`;

  log.info('🔮 Sending to Claude via GENI brain...');
  
  try {
    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 1024,
      messages: [
        {
          role: 'user',
          content: fullPrompt,
        },
      ],
    });
    
    const response = message.content[0].type === 'text' ? message.content[0].text : '';
    log.info({ detail: response }, '✅ GENI response:');
    return response;
  } catch (error) {
    log.error({ err: error }, '❌ Claude error:');
    // Fallback (but still contextual)
    return `I'm having a bit of trouble thinking right now, ${context.patientName}. Can you try again?`;
  }
}

/**
 * Generate pill check response based on vision result
 */
export async function generatePillCheckResponse(
  visionResult: {
    status: 'taken' | 'present' | 'unclear';
    observations: string;
  }
): Promise<string> {
  const context = buildGENIContext();
  
  log.info('🧠 GENI Brain - Generating pill check response');
  log.info({ detail: visionResult }, 'Vision result:');
  log.debug(formatContextSummary(context));
  
  const pillCheckPrompt = `${GENI_SYSTEM_PROMPT}

${buildContextPrompt(context)}

SITUATION:
You just used the camera to check ${context.patientName}'s medication at ${context.timestamp.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', hour12: true})}.

WHAT THE CAMERA SAW:
Status: ${visionResult.status}
Visual details: ${visionResult.observations}

MEDICATION CONTEXT:
${context.overdueMedications.length > 0 ? `⚠️ OVERDUE: ${context.overdueMedications.map(m => `${m.name} (${m.time})`).join(', ')}` : ''}
${context.pendingMedications.length > 0 ? `⏳ Pending today: ${context.pendingMedications.map(m => `${m.name} at ${m.time}`).join(', ')}` : ''}
${context.pendingMedications.length === 0 && context.overdueMedications.length === 0 ? '✅ All medications taken today' : ''}

TASK:
Respond naturally based on what you ACTUALLY SEE and the time/medication context.

**BE CONTEXTUALLY AWARE:**
- If you see the patient (human-face detected) but no pill organizer → Acknowledge you see THEM, then ask about meds
- If you see just background (wall/other) → Say you can't see them or the pills, ask about meds
- If you see the pill organizer → Report on pill status directly

**USE TIME CONTEXT:**
- Morning (before 12pm) → Mention morning meds
- Afternoon (12pm-5pm) → Mention afternoon meds  
- Evening (5pm-9pm) → Mention evening meds
- Night (after 9pm) → Be casual, check on day's meds

EXAMPLES BY SCENARIO:

✅ Patient visible, no pill organizer, afternoon:
"Hey [name], I see you there but can't spot your pill box. It's 2pm - did you take your blood pressure med yet?"

✅ Just background, morning meds pending:
"Can't see you or the pill box right now. Did you take your morning meds?"

✅ Pill organizer with pills visible:
"Your afternoon pill is still in the box. The Lisinopril. Time to take it."

✅ Empty pill compartment:
"Nice! Looks like you took your afternoon med."

✅ Patient visible, evening, no overdue meds:
"Hey there! I see you're around. You already took your evening meds?"

**STRICT RULES:**
- Maximum 2-3 sentences
- Acknowledge what you SEE (person, background, pills)
- Use specific time of day context
- Name the actual medication when relevant
- Be natural and conversational
- NO generic responses
- **NEVER use asterisks or status messages** (*processing*, *scanning*, etc.)
- **NO bracketed text** - speak directly and naturally
- Direct response ONLY - no meta-commentary

GENI:`;

  try {
    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 512,
      messages: [
        {
          role: 'user',
          content: pillCheckPrompt,
        },
      ],
    });
    
    const response = message.content[0].type === 'text' ? message.content[0].text : '';
    log.info({ detail: response }, '✅ Pill check response:');
    return response;
  } catch (error) {
    log.error({ err: error }, '❌ Claude error:');
    // Contextual fallback - SHORT responses
    if (visionResult.status === 'present') {
      return `Your medication is ready. Time to take it.`;
    } else if (visionResult.status === 'taken') {
      return `Nice! Looks like you took your meds.`;
    } else {
      return `Can't see your pill box. Did you take your meds?`;
    }
  }
}

/**
 * Generate proactive check-in message
 */
export async function generateProactiveCheckIn(
  reason: 'overdue-medication' | 'long-silence' | 'low-activity' | 'morning-greeting'
): Promise<string> {
  const context = buildGENIContext();
  
  log.info('🧠 GENI Brain - Generating proactive check-in');
  log.info({ detail: reason }, 'Reason:');
  log.debug(formatContextSummary(context));
  
  let situationText = '';
  
  switch (reason) {
    case 'overdue-medication':
      situationText = `${context.patientName} has overdue medication. You need to check in and remind them gently but persistently.`;
      break;
    case 'long-silence':
      situationText = `It's been ${context.hoursSinceLastInteraction.toFixed(0)} hours since you last heard from ${context.patientName}. Check in to make sure everything is okay.`;
      break;
    case 'low-activity':
      situationText = `${context.patientName} has been very quiet today (low activity). Check in warmly to see if they need anything.`;
      break;
    case 'morning-greeting':
      situationText = `It's morning. Greet ${context.patientName} warmly and let them know what's on the schedule for today.`;
      break;
  }
  
  const checkInPrompt = `${GENI_SYSTEM_PROMPT}

${buildContextPrompt(context)}

SITUATION:
${situationText}

Generate a warm, natural proactive message. Don't ask generic questions - be specific to their context.

GENI:`;

  try {
    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 512,
      messages: [
        {
          role: 'user',
          content: checkInPrompt,
        },
      ],
    });
    
    const response = message.content[0].type === 'text' ? message.content[0].text : '';
    log.info({ detail: response }, '✅ Proactive check-in:');
    return response;
  } catch (error) {
    log.error({ err: error }, '❌ Claude error:');
    // Basic fallback
    return `Hey ${context.patientName}, just checking in. How are you doing?`;
  }
}

/**
 * Quick context check without generating response
 */
export function getContext(): GENIContext {
  return buildGENIContext();
}
