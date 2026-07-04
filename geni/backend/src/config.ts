import dotenv from 'dotenv';
import path from 'path';

// Load from root .env file
dotenv.config({ path: path.join(__dirname, '../../.env') });

const nodeEnv = process.env.NODE_ENV || 'development';

export const config = {
  // 5001 default: macOS AirPlay occupies 5000 on every Mac
  port: parseInt(process.env.PORT || '5001'),
  nodeEnv,
  
  patient: {
    // Resolved from data/profile.json at boot (state.ts); env overrides.
    name: process.env.PATIENT_NAME || '',
  },

  // IANA timezone for schedules/reports; defaults to the system timezone
  timezone: process.env.GENI_TIMEZONE || Intl.DateTimeFormat().resolvedOptions().timeZone,
  
  messaging: {
    enabled: process.env.GENI_ENABLE_MESSAGING === 'true' || nodeEnv === 'production',
  },
  
  fallDetection: {
    enabled: process.env.GENI_ENABLE_FALL_DETECTION === 'true' || nodeEnv === 'production',
    mode: (process.env.GENI_FALL_DETECTION_MODE || 'frame') as 'frame' | 'camera',
    cameraIndex: parseInt(process.env.GENI_CAMERA_INDEX || '0'),
  },
  
  twilio: {
    accountSid: process.env.TWILIO_ACCOUNT_SID || '',
    authToken: process.env.TWILIO_AUTH_TOKEN || '',
    whatsappNumber: process.env.TWILIO_WHATSAPP_NUMBER || '',
    phoneNumber: process.env.TWILIO_PHONE_NUMBER || '',
  },
  
  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY || '',
    visionModel: process.env.ANTHROPIC_VISION_MODEL || 'claude-haiku-4-5',
  },
  
  elevenlabs: {
    apiKey: process.env.ELEVENLABS_API_KEY || '',
    voiceId: process.env.ELEVENLABS_VOICE_ID || '',
  },

  security: {
    // Shared secret for device + dashboard. Open API in dev when unset;
    // production refuses to start without it (see validation below).
    apiKey: process.env.GENI_API_KEY || '',
    corsOrigins: (process.env.CORS_ORIGINS || 'http://localhost:3000,http://localhost:5173')
      .split(',')
      .map(origin => origin.trim())
      .filter(Boolean),
  },
};

// Validate required env vars
const requiredVars = [
  'TWILIO_ACCOUNT_SID',
  'TWILIO_AUTH_TOKEN',
  'GROQ_API_KEY',
  'GENI_API_KEY',
];

if (config.nodeEnv === 'production') {
  for (const varName of requiredVars) {
    if (!process.env[varName]) {
      console.error(`❌ Missing required environment variable: ${varName}`);
      process.exit(1);
    }
  }
}
