import { Router, Request, Response } from 'express';
import { parseIntent, generateResponse } from '../services/intent';
import { state, addActivity } from '../state';
import { emitActivity, emitSpeak } from '../socket';
import { generateFollowUp } from '../services/conversation';
import { conversationMemory } from '../services/conversation-memory';
import { buildGENIContext } from '../services/geni-context';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('chat');

const router = Router();

router.post('/chat', async (req: Request, res: Response) => {
  try {
    const { message, sessionId } = req.body;
    
    if (!message) {
      return res.status(400).json({ error: 'Message is required' });
    }
    
    // Get or create session
    const session = conversationMemory.getOrCreateSession(
      state.patient.name,
      sessionId
    );
    
    // Log user message
    const userActivity = addActivity(`User: ${message}`, 'message');
    emitActivity(userActivity);
    
    // Add to persistent conversation memory
    const context = buildGENIContext();
    conversationMemory.addMessage(session.id, 'user', message, {
      timeOfDay: context.timeOfDay,
      medicationsPending: context.pendingMedications.map(m => m.name),
    });
    
    // Get conversation history for follow-up logic
    const history = conversationMemory.getHistory(session.id, 10);
    
    // Parse intent and generate contextual response with follow-up logic
    const intent = await parseIntent(message);
    let response: string;
    let shouldAskFollowUp = false;
    
    // Use conversational AI for follow-ups
    try {
      const followUpResult = await generateFollowUp(message, history);
      response = followUpResult.response;
      shouldAskFollowUp = followUpResult.shouldAskFollowUp;
    } catch (error) {
      log.error({ err: error }, '❌ Follow-up generation failed, using standard response:');
      response = intent.response || await generateResponse(message, history);
    }
    
    // Add GENI response to persistent memory
    conversationMemory.addMessage(session.id, 'geni', response, {
      isFollowUp: shouldAskFollowUp,
      timeOfDay: context.timeOfDay,
    });
    
    // Log GENI response
    const geniActivity = addActivity(`GENI: ${response}`, 'message');
    emitActivity(geniActivity);
    
    // Trigger TTS on client
    emitSpeak(response);
    
    log.info(`\n💬 Conversation Flow:`);
    log.info('');
    
    res.json({
      response,
      intent: intent.intent,
      entities: intent.entities,
      conversational: shouldAskFollowUp, // Let client know this is a conversation, not just an answer
      sessionId: session.id,
      sessionSummary: conversationMemory.getSessionSummary(session.id),
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Chat error:');
    res.status(500).json({ error: 'Failed to process message' });
  }
});

export default router;
