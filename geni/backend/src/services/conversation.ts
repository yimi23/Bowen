/**
 * GENI Conversation System
 * Makes GENI proactive and conversational, not just reactive
 */

import { buildGENIContext } from './geni-context';
import { config } from '../config';

import { anthropic } from '../lib/anthropic';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('conversation');

/**
 * Determine if GENI should initiate a conversation
 */
export function shouldInitiateConversation(): { shouldStart: boolean; reason: string } {
  const context = buildGENIContext();
  const now = new Date();
  const hour = now.getHours();
  
  // Morning greeting (8-9 AM)
  if (hour === 8 && context.hoursSinceLastInteraction > 8) {
    return { shouldStart: true, reason: 'morning-greeting' };
  }
  
  // Long silence (>4 hours during waking hours)
  if (hour >= 9 && hour <= 21 && context.hoursSinceLastInteraction > 4) {
    return { shouldStart: true, reason: 'check-in' };
  }
  
  // Medication reminder (30 min after due time)
  if (context.overdueMedications.length > 0) {
    return { shouldStart: true, reason: 'medication-reminder' };
  }
  
  // Unusual inactivity
  if (context.activityLevel === 'concerning' && hour >= 10 && hour <= 20) {
    return { shouldStart: true, reason: 'wellness-check' };
  }
  
  return { shouldStart: false, reason: 'none' };
}

/**
 * Generate proactive conversation starter
 */
export async function generateConversationStarter(reason: string): Promise<string> {
  const context = buildGENIContext();
  
  const prompt = `You are GENI, a warm and caring AI companion for ${context.patientName}.

CURRENT CONTEXT:
Time: ${context.timestamp.toLocaleTimeString()} (${context.timeOfDay})
Day: ${context.dayOfWeek}
Patient: ${context.patientName}, age ${context.patientAge}
Activity: ${context.activityLevel}
Last interaction: ${context.hoursSinceLastInteraction.toFixed(1)} hours ago

${context.overdueMedications.length > 0 ? `
OVERDUE MEDICATIONS:
${context.overdueMedications.map(m => `- ${m.name} (${m.time})`).join('\n')}
` : ''}

REASON FOR REACHING OUT: ${reason}

TASK: Generate a warm, natural conversation starter. Be conversational, not transactional.

VOICE RULES:
- Sound like a helpful neighbor, not a system
- Use contractions (haven't, it's, you're)
- Natural flow over perfect grammar
- No corporate speak, no "AI assistant" energy

EXAMPLES (these are VIBE, not scripts):
- Morning greeting: "Hey, good morning! Sleep okay? Got your morning pills coming up soon."
- Check-in: "Haven't heard from you in a bit. You doing alright?"
- Medication reminder: "Looks like you haven't taken your pills yet. Everything okay?"
- Wellness check: "Been pretty quiet today. Want to chat for a bit?"

Generate ONE natural message. Short, clear, warm. Sound like texting someone you care about.

GENI:`;

  try {
    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 256,
      messages: [
        {
          role: 'user',
          content: prompt,
        },
      ],
    });
    
    const response = message.content[0].type === 'text' ? message.content[0].text : '';
    log.info({ detail: response }, '💬 Generated conversation starter:');
    return response;
    
  } catch (error) {
    log.error({ err: error }, '❌ Failed to generate conversation starter:');
    // Fallback
    return `Hey ${context.patientName}, how are you doing?`;
  }
}

/**
 * Generate follow-up question based on patient's response
 */
export async function generateFollowUp(
  patientMessage: string,
  conversationHistory: { role: 'user' | 'assistant'; text: string }[]
): Promise<{ response: string; shouldAskFollowUp: boolean }> {
  const context = buildGENIContext();
  
  const historyText = conversationHistory.slice(-3).map(msg => {
    const role = msg.role === 'user' ? context.patientName : 'GENI';
    return `${role}: ${msg.text}`;
  }).join('\n');
  
  const prompt = `You are GENI, having a natural conversation with ${context.patientName}.

RECENT CONVERSATION:
${historyText}
${context.patientName}: ${patientMessage}

TASK: 
1. Respond naturally and warmly
2. Determine if you should ask a follow-up question to keep the conversation going

WHEN TO ASK FOLLOW-UPS:
- They shared something interesting (ask for more details)
- They mentioned feeling unwell (check if they need help)
- They seem chatty (engage naturally)
- Topic is incomplete (natural curiosity)

WHEN NOT TO ASK FOLLOW-UPS:
- They gave a short/closed answer (respect their space)
- They seem busy or distracted
- Conversation feels natural to end
- You just asked multiple questions

Respond with JSON:
{
  "response": "Your natural response here",
  "shouldAskFollowUp": true/false,
  "reasoning": "Why you did/didn't ask a follow-up"
}

GENI:`;

  try {
    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 512,
      messages: [
        {
          role: 'user',
          content: prompt,
        },
      ],
      output_config: {
        format: {
          type: 'json_schema',
          schema: {
            type: 'object',
            properties: {
              response: { type: 'string' },
              shouldAskFollowUp: { type: 'boolean' },
              reasoning: { type: 'string' },
            },
            required: ['response', 'shouldAskFollowUp', 'reasoning'],
            additionalProperties: false,
          },
        },
      },
    });
    
    const responseText = message.content[0].type === 'text' ? message.content[0].text : '';
    const result = JSON.parse(responseText);
    
    log.info({ shouldAskFollowUp: result.shouldAskFollowUp, reasoning: result.reasoning }, 'follow-up decision');
    
    return {
      response: result.response,
      shouldAskFollowUp: result.shouldAskFollowUp,
    };
    
  } catch (error) {
    log.error({ err: error }, '❌ Failed to generate follow-up:');
    return {
      response: patientMessage,
      shouldAskFollowUp: false,
    };
  }
}
