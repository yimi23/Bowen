import 'express-async-errors';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import http from 'http';
import { config } from './config';
import { logger } from './lib/logger';
import { requestContext } from './middleware/request-context';
import { errorHandler } from './middleware/error-handler';
import { requireApiKey } from './middleware/auth';
import { initializeSocket } from './socket';
import { initializeScheduler } from './services/scheduler';
import { fallDetectionService } from './services/fall-detection';

// Routes
import statusRouter from './routes/status';
import chatRouter from './routes/chat';
import voiceRouter from './routes/voice';
import medicationRouter from './routes/medication';
import messagesRouter from './routes/messages';
import emergencyRouter from './routes/emergency';
import webhooksRouter from './routes/webhooks';
import proactiveRouter from './routes/proactive';
import twilioRouter from './routes/twilio';
import callsRouter from './routes/calls';
import fallRouter from './routes/fall';
import reportsRouter from './routes/reports';
import ttsRouter from './routes/tts';
import trainingRouter from './routes/training';
import monitoringRouter from './routes/monitoring';
import fallDetectionRouter from './routes/fall-detection';
import visionStreamRouter from './routes/vision-stream';
import yoloEmergencyRouter from './routes/yolo-emergency';
import { moduleLogger } from './lib/logger';

const log = moduleLogger('index');

const app = express();
const server = http.createServer(app);

// Initialize Socket.IO
initializeSocket(server);

// Initialize Scheduler (daily/weekly reports, health checks)
initializeScheduler();

// Initialize Fall Detection (continuous monitoring)
if (config.fallDetection.enabled && config.fallDetection.mode === 'camera') {
  fallDetectionService.start({
    patient: config.patient.name,
    camera: config.fallDetection.cameraIndex,
    headless: true, // No window in production
  });
  log.info('🚨 Fall detection started (YOLO pose estimation)');
} else {
  log.info('⚠️  Fall detection camera process disabled (using frame pipeline or disabled)');
}

// Middleware
app.use(helmet());
app.use(
  cors({
    origin: config.security.corsOrigins,
    credentials: true,
  })
);
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));
app.use(requestContext);
app.use(
  rateLimit({
    windowMs: 60_000,
    limit: 300, // generous: continuous vision posts every 30s per device
    standardHeaders: true,
    legacyHeaders: false,
  })
);

// Auth on everything under /api EXCEPT inbound webhooks (Twilio calls us
// and signs its own requests; it cannot present our key)
app.use('/api', (req, res, next) => {
  if (req.path.startsWith('/webhook') || req.path.startsWith('/twilio')) {
    return next();
  }
  return requireApiKey(req, res, next);
});

// Routes
app.use('/api', statusRouter);
app.use('/api', chatRouter);
app.use('/api', voiceRouter);
app.use('/api', medicationRouter);
app.use('/api', messagesRouter);
app.use('/api', emergencyRouter);
app.use('/api', webhooksRouter);
app.use('/api', proactiveRouter);
app.use('/api/twilio', twilioRouter);
app.use('/api', callsRouter);
app.use('/api', fallRouter);
app.use('/api', fallDetectionRouter);
app.use('/api', reportsRouter);
app.use('/api', ttsRouter);
app.use('/api', trainingRouter);
app.use('/api', monitoringRouter);
app.use('/api', visionStreamRouter);
app.use('/api/yolo', yoloEmergencyRouter);

// Health check — reports whether GENI's eyes and voice are actually working,
// not just that Express is up.
app.get('/health', (req, res) => {
  const fallDetection = fallDetectionService.getHealth();
  const degraded =
    (config.fallDetection.enabled && config.fallDetection.mode === 'camera' && !fallDetection.running) ||
    fallDetection.degraded;

  res.status(degraded ? 503 : 200).json({
    status: degraded ? 'degraded' : 'ok',
    uptimeSeconds: Math.floor(process.uptime()),
    fallDetection: {
      enabled: config.fallDetection.enabled,
      mode: config.fallDetection.mode,
      ...fallDetection,
    },
    ai: {
      anthropicConfigured: !!config.anthropic.apiKey,
      openaiConfigured: !!config.openai.apiKey,
      elevenlabsConfigured: !!config.elevenlabs.apiKey,
    },
    messagingEnabled: config.messaging.enabled,
    timestamp: Date.now(),
  });
});

// Global error safety net (must be registered after all routes)
app.use(errorHandler);

// Start server
server.listen(config.port, () => {
  log.info(
    {
      port: config.port,
      env: config.nodeEnv,
      patient: config.patient.name,
      authEnabled: !!config.security.apiKey,
      fallDetection: config.fallDetection.enabled ? config.fallDetection.mode : 'disabled',
    },
    '🐾 GENI backend running'
  );
});

export default app;
