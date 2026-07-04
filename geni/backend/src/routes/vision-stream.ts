/**
 * Continuous Vision Stream Route
 * Receives frames from frontend and processes them continuously
 */

import { Router, Request, Response } from 'express';
import { monitoring } from '../services/monitoring/core';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('vision-stream');

const router = Router();

/**
 * POST /api/vision/analyze
 * Analyze a single camera frame
 */
router.post('/vision/analyze', async (req: Request, res: Response) => {
  try {
    const { image } = req.body;
    
    if (!image) {
      return res.status(400).json({ error: 'No image provided' });
    }
    
    // Extract base64 data (remove data:image/jpeg;base64, prefix if present)
    const base64Data = image.replace(/^data:image\/\w+;base64,/, '');
    
    const source = req.body.source === 'manual' ? 'manual' : 'continuous';
    
    // Check if paused (only for continuous monitoring)
    if (source === 'continuous' && monitoring.isPaused()) {
      return res.json({
        status: 'paused',
        message: 'Vision monitoring is paused (voice interaction active)',
      });
    }

    // A previous frame is still being analyzed — skip instead of stacking
    // AI calls (manual checks still wait their turn)
    if (source === 'continuous' && monitoring.isBusy()) {
      return res.json({
        status: 'busy',
        message: 'Previous frame still processing',
      });
    }
    
    // Analyze frame with unified pipeline
    const pipeline = await monitoring.processFrame(base64Data, { source });
    
    // Return analysis
    res.json({
      status: 'success',
      timestamp: pipeline.vision.timestamp,
      observations: pipeline.vision.observations,
      activity: pipeline.vision.activity,
      pillStatus: pipeline.vision.pillStatus,
      concerns: pipeline.vision.concerns,
      message: pipeline.visionMessage,
      pillCheck: pipeline.pillCheck,
      fallPose: pipeline.fallPose,
    });
    
  } catch (error: any) {
    log.error({ err: error }, '❌ Vision analysis error:');
    res.status(500).json({
      error: 'Vision analysis failed',
      details: error.message,
    });
  }
});

/**
 * GET /api/vision/status
 * Get current vision monitoring status
 */
router.get('/vision/status', (req: Request, res: Response) => {
  const state = monitoring.getVisionState();
  
  res.json({
    isPaused: monitoring.isPaused(),
    lastAnalysis: state.lastAnalysis,
    pillsPresentSince: state.pillsPresentSince,
    consecutiveConcerns: state.consecutiveConcerns,
  });
});

export default router;
