import { Router, Request, Response } from 'express';
import multer from 'multer';
import path from 'path';
import { transcribeAudio } from '../services/whisper';
import { parseIntent, generateResponse } from '../services/intent';
import { state, addActivity } from '../state';
import { emitActivity, emitSpeak } from '../socket';
import { conversationMemory } from '../services/conversation-memory';
import { generateFollowUp } from '../services/conversation';
import { buildGENIContext } from '../services/geni-context';
import { config } from '../config';

const router = Router();

// Configure multer to preserve file extension
const storage = multer.diskStorage({
  destination: 'uploads/',
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    // Force .webm extension for audio files
    cb(null, 'voice-' + uniqueSuffix + '.webm');
  }
});

const upload = multer({ storage });

import { anthropic } from '../lib/anthropic';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('voice');

/**
 * Analyze sentiment from transcribed voice note
 */
async function analyzeSentiment(transcription: string): Promise<'positive' | 'neutral' | 'concerned' | 'distressed'> {
  try {
    const prompt = `Analyze the sentiment of this voice message from an elderly patient:

"${transcription}"

Categorize as one of:
- positive: Happy, grateful, energetic
- neutral: Matter-of-fact, calm
- concerned: Worried, uncertain, mild distress
- distressed: In pain, scared, urgent help needed

Output ONLY the category (one word).`;

    const message = await anthropic.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 16,
      messages: [{ role: 'user', content: prompt }],
    });

    const sentiment = (message.content[0].type === 'text' ? message.content[0].text.trim().toLowerCase() : 'neutral') as any;
    return ['positive', 'neutral', 'concerned', 'distressed'].includes(sentiment) ? sentiment : 'neutral';
  } catch (error) {
    log.error({ err: error }, '❌ Sentiment analysis failed:');
    return 'neutral';
  }
}

router.post('/voice', upload.single('audio'), async (req: Request, res: Response) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Audio file is required' });
    }
    
    log.info({ file: req.file.filename, size: req.file.size }, 'received audio file');
    
    const { sessionId } = req.body;
    
    // Get or create session
    const session = conversationMemory.getOrCreateSession(
      state.patient.name,
      sessionId
    );
    
    // Transcribe audio
    const transcription = await transcribeAudio(req.file.path);
    log.info(`📝 Transcription: "${transcription}"`);
    
    // Analyze sentiment
    const sentiment = await analyzeSentiment(transcription);
    log.info(`🎭 Sentiment: ${sentiment}`);
    
    // Log transcription
    const transcriptionActivity = addActivity(`Voice: ${transcription}`, 'voice');
    emitActivity(transcriptionActivity);
    
    // Add to persistent conversation memory with voice metadata
    const context = buildGENIContext();
    conversationMemory.addMessage(session.id, 'user', transcription, {
      voiceNotePath: req.file.path,
      voiceDuration: 0, // TODO: Calculate from audio file
      transcription,
      sentiment,
      timeOfDay: context.timeOfDay,
      medicationsPending: context.pendingMedications.map(m => m.name),
    });
    
    // Get conversation history for follow-up logic
    const history = conversationMemory.getHistory(session.id, 10);
    
    // Parse intent and generate contextual response with follow-up logic
    const intent = await parseIntent(transcription);
    let response: string;
    let shouldAskFollowUp = false;
    
    // Use conversational AI for follow-ups (with voice context)
    try {
      const followUpResult = await generateFollowUp(transcription, history);
      response = followUpResult.response;
      shouldAskFollowUp = followUpResult.shouldAskFollowUp;
    } catch (error) {
      log.error({ err: error }, '❌ Follow-up generation failed, using standard response:');
      response = intent.response || await generateResponse(transcription, history);
    }
    
    // Add GENI response to persistent memory
    conversationMemory.addMessage(session.id, 'geni', response, {
      isFollowUp: shouldAskFollowUp,
      respondingTo: 'voice note',
      timeOfDay: context.timeOfDay,
    });
    
    // Log GENI response
    const geniActivity = addActivity(`GENI: ${response}`, 'voice');
    emitActivity(geniActivity);
    
    // Trigger TTS on client
    emitSpeak(response);
    
    log.info(`\n🎤 Voice Conversation Flow:`);
    log.info('');
    
    // Clean up uploaded file
    const fs = require('fs');
    fs.unlinkSync(req.file.path);
    log.info('🗑️  Cleaned up audio file');
    
    res.json({
      transcription,
      response,
      intent: intent.intent,
      entities: intent.entities,
      sentiment,
      conversational: shouldAskFollowUp,
      sessionId: session.id,
      sessionSummary: conversationMemory.getSessionSummary(session.id),
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Voice error:');
    // Clean up file on error too
    if (req.file) {
      try {
        const fs = require('fs');
        fs.unlinkSync(req.file.path);
      } catch {}
    }
    res.status(500).json({ error: 'Failed to process voice' });
  }
});

export default router;
