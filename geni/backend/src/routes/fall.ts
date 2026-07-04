import { Router, Request, Response } from 'express';
import { state, addActivity } from '../state';
import { emitActivity, emitFallDetected } from '../socket';
import { sendEmergencyAlert } from '../services/twilio';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('fall');

const router = Router();

// Fall detection state
interface FallState {
  detected: boolean;
  timestamp: number | null;
  responseReceived: boolean;
  emergencyCountdown: NodeJS.Timeout | null;
}

const fallState: FallState = {
  detected: false,
  timestamp: null,
  responseReceived: false,
  emergencyCountdown: null,
};

/**
 * Camera detected a fall
 * Triggers the confirmation workflow
 */
router.post('/fall/detected', async (req: Request, res: Response) => {
  try {
    log.info('🚨 FALL DETECTED by camera');
    
    // Update state
    fallState.detected = true;
    fallState.timestamp = Date.now();
    fallState.responseReceived = false;
    
    // Log activity
    const activity = addActivity(
      'Fall detected by camera - Checking on patient',
      'emergency'
    );
    emitActivity(activity);
    
    // Emit to frontend to show confirmation dialog
    emitFallDetected();
    
    // Start 60-second countdown
    if (fallState.emergencyCountdown) {
      clearTimeout(fallState.emergencyCountdown);
    }
    
    fallState.emergencyCountdown = setTimeout(async () => {
      if (!fallState.responseReceived) {
        log.info('⏰ No response to fall detection - Calling for help');
        
        // Send emergency alerts
        await sendEmergencyAlert(
          state.contacts.filter(c => c.isPrimary),
          state.patient.name,
          'fall'
        );
        
        const emergencyActivity = addActivity(
          'No response after fall - Emergency services notified',
          'emergency'
        );
        emitActivity(emergencyActivity);
      }
    }, 60000); // 60 seconds
    
    res.json({ 
      success: true, 
      message: 'Fall detection triggered - awaiting response',
      countdown: 60
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Fall detection error:');
    res.status(500).json({ error: 'Failed to process fall detection' });
  }
});

/**
 * User responded: "I'm Okay"
 */
router.post('/fall/okay', (req: Request, res: Response) => {
  try {
    log.info('✅ User reported they are okay');
    
    // Cancel emergency countdown
    if (fallState.emergencyCountdown) {
      clearTimeout(fallState.emergencyCountdown);
      fallState.emergencyCountdown = null;
    }
    
    fallState.responseReceived = true;
    fallState.detected = false;
    
    // Log activity
    const activity = addActivity(
      'Fall detected but patient confirmed they are okay',
      'system'
    );
    emitActivity(activity);
    
    res.json({ success: true, message: 'Glad you\'re okay!' });
    
  } catch (error) {
    log.error({ err: error }, '❌ Fall okay error:');
    res.status(500).json({ error: 'Failed to process response' });
  }
});

/**
 * User responded: "I Need Help"
 */
router.post('/fall/help', async (req: Request, res: Response) => {
  try {
    log.info('🆘 User needs help after fall');
    
    // Cancel countdown (we're calling immediately)
    if (fallState.emergencyCountdown) {
      clearTimeout(fallState.emergencyCountdown);
      fallState.emergencyCountdown = null;
    }
    
    fallState.responseReceived = true;
    
    // Immediately call for help
    await sendEmergencyAlert(
      state.contacts.filter(c => c.isPrimary),
      state.patient.name,
      'fall'
    );
    
    const activity = addActivity(
      'Patient requested help after fall - Emergency contacts notified',
      'emergency'
    );
    emitActivity(activity);
    
    res.json({ 
      success: true, 
      message: 'Help is on the way. Emergency contacts have been notified.' 
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Fall help error:');
    res.status(500).json({ error: 'Failed to call for help' });
  }
});

/**
 * User cancelled the countdown
 */
router.post('/fall/cancel', (req: Request, res: Response) => {
  try {
    log.info('⏸️  Fall alert cancelled by user');
    
    if (fallState.emergencyCountdown) {
      clearTimeout(fallState.emergencyCountdown);
      fallState.emergencyCountdown = null;
    }
    
    fallState.responseReceived = true;
    fallState.detected = false;
    
    const activity = addActivity(
      'Fall alert cancelled by patient',
      'system'
    );
    emitActivity(activity);
    
    res.json({ success: true, message: 'Alert cancelled' });
    
  } catch (error) {
    log.error({ err: error }, '❌ Fall cancel error:');
    res.status(500).json({ error: 'Failed to cancel alert' });
  }
});

/**
 * Get current fall detection status
 */
router.get('/fall/status', (req: Request, res: Response) => {
  res.json({
    detected: fallState.detected,
    timestamp: fallState.timestamp,
    awaitingResponse: fallState.detected && !fallState.responseReceived,
  });
});

export default router;
