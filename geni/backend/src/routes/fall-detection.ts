/**
 * Fall Detection API Routes
 * Control fall detection monitoring and handle emergency responses
 */

import { Router, Request, Response } from 'express';
import { fallDetectionService } from '../services/fall-detection';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('fall-detection');

const router = Router();

/**
 * Start fall detection monitoring
 */
router.post('/fall-detection/start', (req: Request, res: Response) => {
  try {
    const { patient, camera, headless } = req.body;
    
    fallDetectionService.start({
      patient,
      camera: camera !== undefined ? parseInt(camera) : undefined,
      headless: headless !== false, // Default true for production
    });
    
    res.json({
      success: true,
      message: 'Fall detection started',
      status: fallDetectionService.getStatus()
    });
  } catch (error) {
    log.error({ err: error }, '❌ Start fall detection error:');
    res.status(500).json({ error: 'Failed to start fall detection' });
  }
});

/**
 * Stop fall detection monitoring
 */
router.post('/fall-detection/stop', (req: Request, res: Response) => {
  try {
    fallDetectionService.stop();
    
    res.json({
      success: true,
      message: 'Fall detection stopped',
      status: fallDetectionService.getStatus()
    });
  } catch (error) {
    log.error({ err: error }, '❌ Stop fall detection error:');
    res.status(500).json({ error: 'Failed to stop fall detection' });
  }
});

/**
 * Get fall detection status
 */
router.get('/fall-detection/status', (req: Request, res: Response) => {
  try {
    const status = fallDetectionService.getStatus();
    
    res.json({
      success: true,
      status
    });
  } catch (error) {
    log.error({ err: error }, '❌ Get status error:');
    res.status(500).json({ error: 'Failed to get status' });
  }
});

/**
 * User confirms they're okay (cancel emergency)
 */
router.post('/fall-detection/confirm-ok', (req: Request, res: Response) => {
  try {
    const cancelled = fallDetectionService.confirmOK();
    
    if (cancelled) {
      res.json({
        success: true,
        message: 'Emergency cancelled - user confirmed OK'
      });
    } else {
      res.json({
        success: false,
        message: 'No active emergency to cancel'
      });
    }
  } catch (error) {
    log.error({ err: error }, '❌ Confirm OK error:');
    res.status(500).json({ error: 'Failed to process confirmation' });
  }
});

export default router;
