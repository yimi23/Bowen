import OpenAI from 'openai';
import { config } from '../config';
import fs from 'fs';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('whisper');

const openai = new OpenAI({
  apiKey: config.openai.apiKey,
});

export async function transcribeAudio(audioFilePath: string): Promise<string> {
  try {
    const transcription = await openai.audio.transcriptions.create({
      file: fs.createReadStream(audioFilePath),
      model: 'whisper-1',
      language: 'en',
    });
    
    log.info({ detail: transcription.text }, '🎤 Transcribed:');
    return transcription.text;
    
  } catch (error) {
    log.error({ err: error }, '❌ Transcription failed:');
    throw error;
  }
}
