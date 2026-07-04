import { Router, Request, Response } from 'express';
import multer from 'multer';
import { state, addActivity, updateMedicationStatus } from '../state';
import { emitActivity, emitMedicationUpdate } from '../socket';
import { getPillCheckHistory, getLastPillCheck } from '../database/pillCheckHistory';
import { monitoring } from '../services/monitoring/core';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('medication');

const router = Router();
const upload = multer({ dest: 'uploads/' });

// Get medication history
router.get('/medication/history', (req: Request, res: Response) => {
  res.json({
    history: state.medicationHistory,
    today: state.todaysMedications,
  });
});

// Get pill check history
router.get('/medication/pill-check-history', (req: Request, res: Response) => {
  try {
    const limit = parseInt(req.query.limit as string) || 20;
    const history = getPillCheckHistory(limit);
    const lastCheck = getLastPillCheck();
    
    res.json({
      history,
      lastCheck,
      count: history.length,
    });
  } catch (error) {
    log.error({ err: error }, '❌ Get pill check history error:');
    res.status(500).json({ error: 'Failed to get pill check history' });
  }
});

// Manual medication confirmation
router.post('/medication/confirm', (req: Request, res: Response) => {
  try {
    const { medicationName } = req.body;
    
    if (!medicationName) {
      return res.status(400).json({ error: 'Medication name is required' });
    }
    
    const success = updateMedicationStatus(medicationName, 'taken');
    
    if (success) {
      const activity = addActivity(`Medication confirmed: ${medicationName}`, 'medication');
      emitActivity(activity);
      emitMedicationUpdate(state.todaysMedications);
      
      res.json({ success: true, medications: state.todaysMedications });
    } else {
      res.status(404).json({ error: 'Medication not found' });
    }
    
  } catch (error) {
    log.error({ err: error }, '❌ Medication confirm error:');
    res.status(500).json({ error: 'Failed to confirm medication' });
  }
});

// Pill check via camera (YOLOv8 + Claude Vision fallback)
router.post('/pill-check', upload.single('image'), async (req: Request, res: Response) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Image file is required' });
    }
    
    // Read image as base64
    const fs = require('fs');
    const imageBuffer = fs.readFileSync(req.file.path);
    const base64Image = imageBuffer.toString('base64');
    
    const pipeline = await monitoring.processFrame(base64Image, { source: 'manual' });
    
    // Clean up uploaded file
    fs.unlinkSync(req.file.path);
    
    res.json({
      ...pipeline.pillCheck.result,
      method: pipeline.pillCheck.method,
      recordId: pipeline.pillCheck.recordId,
      responseText: pipeline.pillCheck.responseText,
      adherenceAnalysis: pipeline.pillCheck.adherenceAnalysis,
      vision: pipeline.vision,
      visionMessage: pipeline.visionMessage,
      fallPose: pipeline.fallPose,
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Pill check error:');
    res.status(500).json({ error: 'Failed to analyze pill image' });
  }
});

export default router;
