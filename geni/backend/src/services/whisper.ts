/**
 * services/whisper.ts — GENI merge: STT moved from OpenAI to Groq.
 *
 * Same Whisper model family (whisper-large-v3-turbo), one fewer vendor
 * dependency: the OpenAI client is gone entirely. Groq exposes an
 * OpenAI-compatible transcription endpoint, so this is a plain multipart
 * fetch — no SDK needed. This matches BOWEN's own voice pipeline, which
 * already does STT through Groq.
 */

import fs from 'fs';
import path from 'path';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('whisper');

const GROQ_TRANSCRIPTION_URL = 'https://api.groq.com/openai/v1/audio/transcriptions';
const STT_MODEL = 'whisper-large-v3-turbo';

export async function transcribeAudio(audioFilePath: string): Promise<string> {
  const apiKey = process.env.GROQ_API_KEY || '';
  if (!apiKey) {
    throw new Error('GROQ_API_KEY not configured — STT unavailable');
  }

  try {
    const buffer = fs.readFileSync(audioFilePath);
    const form = new FormData();
    form.append('file', new Blob([buffer]), path.basename(audioFilePath) || 'audio.wav');
    form.append('model', STT_MODEL);
    form.append('language', 'en');

    const res = await fetch(GROQ_TRANSCRIPTION_URL, {
      method: 'POST',
      headers: { authorization: `Bearer ${apiKey}` },
      body: form,
      signal: AbortSignal.timeout(30_000),
    });

    if (!res.ok) {
      throw new Error(`Groq transcription error ${res.status}: ${await res.text()}`);
    }

    const data = await res.json() as { text: string };
    log.info({ detail: data.text }, '🎤 Transcribed:');
    return data.text;

  } catch (error) {
    log.error({ err: error }, '❌ Transcription failed:');
    throw error;
  }
}
