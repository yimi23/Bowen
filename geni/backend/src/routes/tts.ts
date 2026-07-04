import { Router, Request, Response } from 'express';
import { textToSpeech } from '../services/elevenlabs';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('tts');

const router = Router();

/**
 * POST /api/tts - Generate speech from text using ElevenLabs
 */
router.post('/tts', async (req: Request, res: Response) => {
  try {
    const { text } = req.body;
    
    if (!text) {
      return res.status(400).json({ error: 'Text is required' });
    }
    
    log.info(`🔊 Generating TTS for: "${text.substring(0, 50)}..."`);
    
    const audioBuffer = await textToSpeech(text);
    
    res.set({
      'Content-Type': 'audio/mpeg',
      'Content-Length': audioBuffer.length,
    });
    
    res.send(audioBuffer);
    
  } catch (error) {
    log.error({ err: error }, '❌ TTS generation failed:');
    res.status(500).json({ error: 'Failed to generate speech' });
  }
});

export default router;
