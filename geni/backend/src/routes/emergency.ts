import { Router, Request, Response } from 'express';
import { sendEmergencyAlert } from '../services/twilio';
import { state, addActivity } from '../state';
import { emitActivity, emitFallDetected } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('emergency');

const router = Router();

router.post('/emergency', async (req: Request, res: Response) => {
  try {
    const { type = 'sos' } = req.body;
    
    // Log emergency
    const activity = addActivity(`🚨 EMERGENCY: ${type} detected`, 'emergency');
    emitActivity(activity);
    
    // Trigger fall detection modal on frontend
    emitFallDetected();
    
    // Send alerts to all contacts
    await sendEmergencyAlert(state.contacts, state.patient.name, type as 'fall' | 'sos' | 'medical');
    
    // Log alerts sent
    const alertActivity = addActivity(
      `Emergency alerts sent to ${state.contacts.length} contact(s)`,
      'emergency'
    );
    emitActivity(alertActivity);
    
    res.json({
      success: true,
      contactsAlerted: state.contacts.length,
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Emergency error:');
    res.status(500).json({ error: 'Failed to process emergency' });
  }
});

// Hardware button press (from FREE-WiLi)
router.post('/button-pressed', async (req: Request, res: Response) => {
  try {
    const activity = addActivity('Emergency button pressed (hardware)', 'emergency');
    emitActivity(activity);
    
    // Trigger fall detection modal
    emitFallDetected();
    
    res.json({ success: true });
    
  } catch (error) {
    log.error({ err: error }, '❌ Button press error:');
    res.status(500).json({ error: 'Failed to process button press' });
  }
});

export default router;
