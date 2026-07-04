/**
 * GENI Unified Monitoring Route
 * Exposes monitoring endpoints for manual triggers and status checks
 */

import { Router, Request, Response } from 'express';
import { monitoring } from '../services/monitoring/core';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('monitoring');

const router = Router();

/**
 * Trigger manual monitoring cycle
 */
router.post('/monitor/cycle', async (req: Request, res: Response) => {
  try {
    log.info('🔄 Manual monitoring cycle triggered');
    
    const result = await monitoring.runCycle();
    
    res.json({
      success: true,
      result,
      timestamp: new Date(),
    });
  } catch (error) {
    log.error({ err: error }, '❌ Monitoring cycle error:');
    res.status(500).json({ error: 'Failed to run monitoring cycle' });
  }
});

/**
 * Get monitoring status
 */
router.get('/monitor/status', (req: Request, res: Response) => {
  try {
    const status = monitoring.getStatus();
    const events = monitoring.getRecentEvents(20);
    
    res.json({
      status,
      events,
      timestamp: new Date(),
    });
  } catch (error) {
    log.error({ err: error }, '❌ Status error:');
    res.status(500).json({ error: 'Failed to get status' });
  }
});

/**
 * Get recent monitoring events
 */
router.get('/monitor/events', (req: Request, res: Response) => {
  try {
    const limit = parseInt(req.query.limit as string) || 10;
    const events = monitoring.getRecentEvents(limit);
    
    res.json({
      events,
      count: events.length,
      timestamp: new Date(),
    });
  } catch (error) {
    log.error({ err: error }, '❌ Events error:');
    res.status(500).json({ error: 'Failed to get events' });
  }
});

export default router;
