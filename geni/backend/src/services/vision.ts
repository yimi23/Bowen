import { config } from '../config';
import { PILL_DETECTION_PROMPT } from '../prompts/pillDetection';
import { buildFrameAnalysisPrompt } from '../prompts/frameAnalysis';

import { anthropic, VISION_MODEL } from '../lib/anthropic';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('vision');


const DAY_STATE = { type: 'string', enum: ['empty', 'full', 'unclear'] } as const;
const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];

// JSON schemas enforced via structured outputs — the API guarantees the
// response parses, so no regex extraction or "got conversational text"
// failure mode exists anymore.
const PILL_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['present', 'taken', 'unclear'] },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    compartments: {
      type: 'object',
      properties: Object.fromEntries(DAYS.map(d => [d, DAY_STATE])),
      additionalProperties: false,
    },
    pillCounts: {
      type: 'object',
      properties: Object.fromEntries(DAYS.map(d => [d, { type: 'integer' }])),
      additionalProperties: false,
    },
    overallStatus: {
      type: 'string',
      enum: ['all-taken', 'partial-adherence', 'no-adherence', 'unclear', 'no-organizer-detected'],
    },
    observations: { type: 'string' },
  },
  required: ['status', 'confidence', 'observations'],
  additionalProperties: false,
};

const SCENE_SCHEMA = {
  type: 'object',
  properties: {
    observations: { type: 'string' },
    activity: {
      type: 'string',
      enum: ['at desk', 'walking', 'sitting', 'lying down', 'not visible', 'unclear'],
    },
    pillStatus: { type: 'string', enum: ['present', 'taken', 'unclear'] },
    concerns: { type: 'array', items: { type: 'string' } },
  },
  required: ['observations', 'activity', 'pillStatus', 'concerns'],
  additionalProperties: false,
};

interface PillDetectionResult {
  status: 'present' | 'taken' | 'unclear';
  confidence: 'high' | 'medium' | 'low';
  compartments?: {
    monday?: 'empty' | 'full' | 'unclear';
    tuesday?: 'empty' | 'full' | 'unclear';
    wednesday?: 'empty' | 'full' | 'unclear';
    thursday?: 'empty' | 'full' | 'unclear';
    friday?: 'empty' | 'full' | 'unclear';
    saturday?: 'empty' | 'full' | 'unclear';
    sunday?: 'empty' | 'full' | 'unclear';
  };
  pillCounts?: {
    monday?: number;
    tuesday?: number;
    wednesday?: number;
    thursday?: number;
    friday?: number;
    saturday?: number;
    sunday?: number;
  };
  overallStatus?: 'all-taken' | 'partial-adherence' | 'no-adherence' | 'unclear' | 'no-organizer-detected';
  observations: string;
}

export async function analyzePillImage(imageBase64: string): Promise<PillDetectionResult> {
  try {
    // Remove data URL prefix if present
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, '');
    
    const message = await anthropic.messages.create({
      model: VISION_MODEL,
      max_tokens: 1024,
      system: "You are a computer vision API. You MUST respond with ONLY a valid JSON object, no other text whatsoever. No explanations, no apologies, no markdown. Start with { and end with }.",
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: 'image/jpeg',
                data: base64Data,
              },
            },
            {
              type: 'text',
              text: PILL_DETECTION_PROMPT,
            },
          ],
        },
      ],
      output_config: { format: { type: 'json_schema', schema: PILL_SCHEMA } },
    });
    
    const responseText = message.content[0].type === 'text' ? message.content[0].text : '';
    const result: PillDetectionResult = JSON.parse(responseText);
    return result;
    
  } catch (error: any) {
    log.error('❌ Pill vision analysis failed:');
    log.error({ err: error.name }, 'Error name:');
    log.error({ err: error.message }, 'Error message:');
    return {
      status: 'unclear',
      confidence: 'low',
      observations: `Error: ${error.message || 'Unknown error'}`,
    };
  }
}

export interface SceneAnalysis {
  timestamp: Date;
  observations: string;
  activity: string; // 'at desk' | 'walking' | 'sitting' | 'lying down' | 'not visible' | 'unclear'
  pillStatus: 'present' | 'taken' | 'unclear';
  concerns: string[];
}

/**
 * General scene understanding for the continuous monitoring loop:
 * what is the patient doing, is the pill organizer visible, any concerns.
 */
export async function analyzeScene(
  imageBase64: string,
  scheduleContext: string
): Promise<SceneAnalysis> {
  const fallback: SceneAnalysis = {
    timestamp: new Date(),
    observations: 'Analysis unavailable',
    activity: 'unclear',
    pillStatus: 'unclear',
    concerns: [],
  };

  try {
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, '');

    const response = await anthropic.messages.create({
      model: VISION_MODEL,
      max_tokens: 300,
      system:
        'You are a computer vision API. You MUST respond with ONLY a valid JSON object. No extra text, no markdown. Start with { and end with }.',
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: { type: 'base64', media_type: 'image/jpeg', data: base64Data },
            },
            {
              type: 'text',
              text: `You are GENI, an AI elder care companion monitoring ${config.patient.name}.

Analyze this camera frame and respond in JSON format:

{
  "observations": "Brief description of what you see",
  "activity": "at desk" | "walking" | "sitting" | "lying down" | "not visible",
  "pillStatus": "present" | "taken" | "unclear",
  "concerns": ["list any concerns"]
}

Current time: ${new Date().toLocaleTimeString()}
Current medications schedule: ${scheduleContext}

Focus on:
1. Is ${config.patient.name} visible and what are they doing?
2. Can you see the pill organizer? Are pills present or taken?
3. Any safety concerns (unusual position, fall risk)?
4. Any changes from typical behavior?

Be concise and factual. Only list real concerns.`,
            },
          ],
        },
      ],
      output_config: { format: { type: 'json_schema', schema: SCENE_SCHEMA } },
    });

    const content = response.content[0];
    if (content.type !== 'text') return fallback;

    const analysis = JSON.parse(content.text);
    return { timestamp: new Date(), ...analysis };
  } catch (error) {
    return fallback;
  }
}

export interface FrameAnalysis {
  scene: SceneAnalysis;
  pills: PillDetectionResult;
}

const FRAME_SCHEMA = {
  type: 'object',
  properties: {
    scene: {
      type: 'object',
      properties: {
        observations: SCENE_SCHEMA.properties.observations,
        activity: SCENE_SCHEMA.properties.activity,
        concerns: SCENE_SCHEMA.properties.concerns,
      },
      required: ['observations', 'activity', 'concerns'],
      additionalProperties: false,
    },
    pills: PILL_SCHEMA,
  },
  required: ['scene', 'pills'],
  additionalProperties: false,
};

/**
 * ONE vision call for the whole monitoring frame path: scene understanding
 * and pill-organizer reading together. Halves image tokens and round trips
 * versus the previous analyzeScene + analyzePillImage pair.
 */
export async function analyzeFrame(
  imageBase64: string,
  patientName: string,
  scheduleContext: string
): Promise<FrameAnalysis> {
  const fallback: FrameAnalysis = {
    scene: {
      timestamp: new Date(),
      observations: 'Analysis unavailable',
      activity: 'unclear',
      pillStatus: 'unclear',
      concerns: [],
    },
    pills: { status: 'unclear', confidence: 'low', observations: 'Analysis unavailable' },
  };

  try {
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, '');

    const message = await anthropic.messages.create({
      model: VISION_MODEL,
      max_tokens: 1024,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: { type: 'base64', media_type: 'image/jpeg', data: base64Data },
            },
            { type: 'text', text: buildFrameAnalysisPrompt(patientName, scheduleContext) },
          ],
        },
      ],
      output_config: { format: { type: 'json_schema', schema: FRAME_SCHEMA } },
    });

    const content = message.content[0];
    if (content.type !== 'text') return fallback;

    const parsed = JSON.parse(content.text);
    return {
      scene: {
        timestamp: new Date(),
        ...parsed.scene,
        // pillStatus on the scene mirrors the dedicated pills reading
        pillStatus: parsed.pills.status,
      },
      pills: parsed.pills,
    };
  } catch (error) {
    log.error({ err: error }, 'combined frame analysis failed');
    return fallback;
  }
}
