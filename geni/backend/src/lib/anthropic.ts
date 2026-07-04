/**
 * lib/anthropic.ts — GENI's brain/vision calls ride BOWEN's LLMProvider seam.
 *
 * This used to be a direct @anthropic-ai/sdk client. It is now a thin fetch
 * client to BOWEN's internal endpoint (/internal/llm/complete), which routes
 * through the same adapter every BOWEN agent thinks with. The exported shape
 * is unchanged — anthropic.messages.create(...) returning content[0].text —
 * so vision.ts, geni-brain.ts, and conversation.ts did not change at all.
 *
 * Structured outputs: output_config json_schema maps to the seam's
 * output_schema; the guaranteed-valid JSON comes back as content[0].text,
 * exactly what the callers already parse.
 *
 * Timeout stays 30s so a hung request can never stall a monitoring loop.
 */

import { config } from '../config';

const BOWEN_URL = process.env.BOWEN_INTERNAL_URL || 'http://localhost:8000';
const TIMEOUT_MS = 30_000;

interface CreateParams {
  model: string;
  max_tokens: number;
  messages: any[];
  system?: string;
  temperature?: number;
  output_config?: { format?: { type: string; schema?: any } };
  [key: string]: any;
}

async function create(params: CreateParams): Promise<any> {
  const body = {
    messages: params.messages,
    model: params.model,
    max_tokens: params.max_tokens,
    system: typeof params.system === 'string' ? params.system : undefined,
    temperature: params.temperature,
    output_schema: params.output_config?.format?.schema ?? undefined,
  };

  const res = await fetch(`${BOWEN_URL}/internal/llm/complete`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-internal-key': process.env.GENI_API_KEY || '',
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });

  if (!res.ok) {
    throw new Error(`BOWEN LLM seam error ${res.status}: ${await res.text()}`);
  }

  const data = await res.json() as { text?: string; structured?: any; stop_reason?: string };
  const text = data.structured != null ? JSON.stringify(data.structured) : (data.text ?? '');
  return {
    content: [{ type: 'text', text }],
    stop_reason: data.stop_reason ?? 'end_turn',
  };
}

export const anthropic = { messages: { create } };

export const CHAT_MODEL = 'claude-haiku-4-5';
export const VISION_MODEL = config.anthropic.visionModel;
