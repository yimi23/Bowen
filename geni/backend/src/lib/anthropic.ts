import Anthropic from '@anthropic-ai/sdk';
import { config } from '../config';

// Single shared client: 30s timeout so a hung request can never stall a
// monitoring loop, 2 retries for transient 429/5xx.
export const anthropic = new Anthropic({
  apiKey: config.anthropic.apiKey,
  timeout: 30_000,
  maxRetries: 2,
});

export const CHAT_MODEL = 'claude-haiku-4-5';
export const VISION_MODEL = config.anthropic.visionModel;
