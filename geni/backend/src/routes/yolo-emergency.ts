/**
 * YOLO Emergency Alert Endpoint
 * Receives alerts from Python YOLOv8 service
 * Triggers SMS, audio, and frontend notifications
 */

import { Router, Request, Response } from 'express';
import { yoloMasterSensing } from '../services/yolo-master-sensing';
import { getIO } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('yolo-emergency');

const router = Router();

/**
 * POST /api/yolo/emergency
 * Receive emergency alert from Python YOLO service
 */
router.post('/emergency', async (req: Request, res: Response) => {
  try {
    const { type, timestamp, confidence, detected_at_frame, person_detected } = req.body;

    log.info(`[YOLO API] Emergency alert received: ${type}`);

    if (!type || !timestamp) {
      return res.status(400).json({ error: 'Missing required fields: type, timestamp' });
    }

    // Handle the emergency
    await yoloMasterSensing.handleEmergencyDetected({
      type: type as 'fall' | 'desk_faint' | 'unresponsive',
      timestamp,
      confidence: confidence || 0.95,
      detected_at_frame: detected_at_frame || 0,
      person_detected: person_detected !== false,
    });

    // Broadcast to all connected frontend clients
    const io = getIO();
    io.emit('emergency_alert', {
      type,
      timestamp,
      message: type === 'fall' 
        ? '⚠️ FALL DETECTED - Emergency services notified' 
        : '⚠️ UNRESPONSIVE - Caregiver notified',
    });

    res.json({ 
      status: 'success', 
      message: 'Emergency alert processed',
      emergency_in_progress: yoloMasterSensing.emergencyInProgress 
    });
  } catch (error) {
    log.error({ err: error }, '[YOLO API] Error:');
    res.status(500).json({ error: 'Failed to process emergency alert' });
  }
});

/**
 * GET /api/yolo/status
 * Get current YOLO monitoring status
 */
router.get('/status', (req: Request, res: Response) => {
  const status = yoloMasterSensing.getStatus();
  res.json(status);
});

/**
 * POST /api/yolo/clear
 * Clear/acknowledge emergency
 */
router.post('/clear', (req: Request, res: Response) => {
  yoloMasterSensing.clearEmergency();
  
  // Broadcast to frontend
  const io = getIO();
  io.emit('emergency_cleared', { timestamp: new Date() });

  res.json({ status: 'success', message: 'Emergency cleared' });
});

export default router;
