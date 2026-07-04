import { Router, Request, Response } from 'express';
import multer from 'multer';
import { saveTrainingData, CATEGORIES } from '../scripts/train-vision';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('training');

const router = Router();
const upload = multer({ dest: 'uploads/' });

// Get available categories
router.get('/training/categories', (req: Request, res: Response) => {
  res.json({ categories: CATEGORIES });
});

// Submit training image
router.post('/training/submit', upload.single('image'), async (req: Request, res: Response) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Image file is required' });
    }
    
    const { category, description } = req.body;
    
    if (!category) {
      return res.status(400).json({ error: 'Category is required' });
    }
    
    // Read image as base64
    const fs = require('fs');
    const imageBuffer = fs.readFileSync(req.file.path);
    const base64Image = imageBuffer.toString('base64');
    
    // Save training data
    const result = await saveTrainingData(base64Image, category, description);
    
    // Clean up uploaded file
    fs.unlinkSync(req.file.path);
    
    res.json({
      success: true,
      id: result.id,
      message: `Training image saved: ${category}`,
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Training submission error:');
    res.status(500).json({ error: 'Failed to save training data' });
  }
});

// Get training stats
router.get('/training/stats', (req: Request, res: Response) => {
  try {
    const fs = require('fs');
    const path = require('path');
    
    const labelsPath = path.join(__dirname, '../../training-data/labels.json');
    
    if (!fs.existsSync(labelsPath)) {
      return res.json({ total: 0, byCategory: {} });
    }
    
    const labels = JSON.parse(fs.readFileSync(labelsPath, 'utf-8'));
    
    const byCategory: Record<string, number> = {};
    labels.forEach((label: any) => {
      byCategory[label.category] = (byCategory[label.category] || 0) + 1;
    });
    
    res.json({
      total: labels.length,
      byCategory,
    });
    
  } catch (error) {
    log.error({ err: error }, '❌ Training stats error:');
    res.status(500).json({ error: 'Failed to get training stats' });
  }
});

export default router;
