import { Router, Request, Response } from 'express';
import { textToSpeech } from '../services/elevenlabs';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('tts');

const router = Router();

const BOWEN_URL = process.env.BOWEN_INTERNAL_URL || 'http://localhost:8000';
const TENANT_ID = process.env.GENI_TENANT_ID || 'default';

/**
 * POST /api/tts — Generate elder-facing speech.
 *
 * GENI merge: Kokoro (local, free, runs inside BOWEN) is the default for ALL
 * GENI speech. The per-tenant elder_voice flag — config in BOWEN's tenant
 * YAML, never code — switches ONLY elder-facing replies to ElevenLabs.
 * BOWEN makes that call: it either returns Kokoro WAV bytes directly, or
 * {engine: "elevenlabs"} telling us to use the ElevenLabs path.
 * If BOWEN is unreachable, ElevenLabs is the graceful fallback (and the
 * frontend already falls back to browser TTS beyond that).
 */
router.post('/tts', async (req: Request, res: Response) => {
  try {
    const { text } = req.body;

    if (!text) {
      return res.status(400).json({ error: 'Text is required' });
    }

    log.info(`🔊 Generating TTS for: "${text.substring(0, 50)}..."`);

    try {
      const bowenRes = await fetch(`${BOWEN_URL}/internal/tts`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-internal-key': process.env.GENI_API_KEY || '',
        },
        body: JSON.stringify({ text, tenant_id: TENANT_ID, elder_facing: true }),
        signal: AbortSignal.timeout(20_000),
      });

      if (bowenRes.ok) {
        const contentType = bowenRes.headers.get('content-type') || '';
        if (contentType.includes('audio/wav')) {
          const audio = Buffer.from(await bowenRes.arrayBuffer());
          res.set({ 'Content-Type': 'audio/wav', 'Content-Length': audio.length, 'X-TTS-Engine': 'kokoro' });
          return res.send(audio);
        }
        const decision = await bowenRes.json() as { engine?: string };
        if (decision.engine !== 'elevenlabs') {
          log.warn({ decision }, 'unexpected TTS decision — falling through to ElevenLabs');
        }
        // elder_voice tenant flag is on → ElevenLabs for this elder-facing reply
      } else {
        log.warn({ status: bowenRes.status }, 'BOWEN TTS unavailable — ElevenLabs fallback');
      }
    } catch (error) {
      log.warn({ err: error }, 'BOWEN TTS unreachable — ElevenLabs fallback');
    }

    const audioBuffer = await textToSpeech(text);
    res.set({
      'Content-Type': 'audio/mpeg',
      'Content-Length': audioBuffer.length,
      'X-TTS-Engine': 'elevenlabs',
    });
    res.send(audioBuffer);

  } catch (error) {
    log.error({ err: error }, '❌ TTS generation failed:');
    res.status(500).json({ error: 'Failed to generate speech' });
  }
});

export default router;
