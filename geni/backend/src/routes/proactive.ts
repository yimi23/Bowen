import { Router, Request, Response } from 'express';
import {
  shouldTriggerProactiveAction,
  generateMorningBriefing,
  generateSmartMedicationReminder,
  proactiveHealthCheck,
  sendWeeklySummaryToCaregiver
} from '../services/proactive';
import { addActivity } from '../state';
import { emitActivity, emitSpeak } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('proactive');

const router = Router();

// Trigger proactive intelligence check
router.post('/proactive/check', async (req: Request, res: Response) => {
  try {
    const action = shouldTriggerProactiveAction();
    
    if (action) {
      // Log and emit the proactive message
      const activity = addActivity(action.message, 'system');
      emitActivity(activity);
      emitSpeak(action.message);
      
      res.json({
        triggered: true,
        action: action.action,
        message: action.message
      });
    } else {
      res.json({
        triggered: false,
        message: 'No proactive actions needed right now'
      });
    }
  } catch (error) {
    log.error({ err: error }, '❌ Proactive check error:');
    res.status(500).json({ error: 'Failed to check proactive actions' });
  }
});

// Manual trigger for morning briefing
router.post('/proactive/morning-briefing', (req: Request, res: Response) => {
  try {
    const briefing = generateMorningBriefing();
    const activity = addActivity(briefing, 'system');
    emitActivity(activity);
    emitSpeak(briefing);
    
    res.json({
      success: true,
      briefing
    });
  } catch (error) {
    log.error({ err: error }, '❌ Morning briefing error:');
    res.status(500).json({ error: 'Failed to generate briefing' });
  }
});

// Manual trigger for health check
router.post('/proactive/health-check', async (req: Request, res: Response) => {
  try {
    await proactiveHealthCheck();
    res.json({
      success: true,
      message: 'Health check initiated'
    });
  } catch (error) {
    log.error({ err: error }, '❌ Health check error:');
    res.status(500).json({ error: 'Failed to perform health check' });
  }
});

// Send weekly summary to caregiver
router.post('/proactive/weekly-summary', async (req: Request, res: Response) => {
  try {
    await sendWeeklySummaryToCaregiver();
    res.json({
      success: true,
      message: 'Weekly summary sent'
    });
  } catch (error) {
    log.error({ err: error }, '❌ Weekly summary error:');
    res.status(500).json({ error: 'Failed to send weekly summary' });
  }
});

export default router;
