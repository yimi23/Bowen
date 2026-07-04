import { Router, Request, Response } from 'express';
import { generateDailyReport, sendDailyReportToCaregiver } from '../services/reporting';
import { sendWeeklySummaryToCaregiver } from '../services/proactive';
import { buildAlert, sendAlert, sendReassurance } from '../services/notifications';
import { testScheduler } from '../services/scheduler';
import { healthReportService } from '../services/health-report-sms';
import { adherenceReportService } from '../services/adherence-report-sms';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('reports');

const router = Router();

/**
 * GET /api/reports/daily - Preview daily report
 */
router.get('/reports/daily', (req: Request, res: Response) => {
  try {
    const report = generateDailyReport();
    res.json({
      success: true,
      report,
      note: 'This is a preview. Use POST to send via WhatsApp.'
    });
  } catch (error) {
    log.error({ err: error }, '❌ Daily report preview error:');
    res.status(500).json({ error: 'Failed to generate daily report' });
  }
});

/**
 * POST /api/reports/daily - Send daily report now
 */
router.post('/reports/daily', async (req: Request, res: Response) => {
  try {
    const success = await sendDailyReportToCaregiver();
    
    if (success) {
      res.json({
        success: true,
        message: 'Daily report sent to caregiver'
      });
    } else {
      res.status(500).json({
        success: false,
        error: 'Failed to send daily report'
      });
    }
  } catch (error) {
    log.error({ err: error }, '❌ Send daily report error:');
    res.status(500).json({ error: 'Failed to send daily report' });
  }
});

/**
 * POST /api/reports/weekly - Send weekly summary now
 */
router.post('/reports/weekly', async (req: Request, res: Response) => {
  try {
    await sendWeeklySummaryToCaregiver();
    res.json({
      success: true,
      message: 'Weekly summary sent to caregiver'
    });
  } catch (error) {
    log.error({ err: error }, '❌ Send weekly summary error:');
    res.status(500).json({ error: 'Failed to send weekly summary' });
  }
});

/**
 * POST /api/reports/test-alert - Test context-aware alert
 */
router.post('/reports/test-alert', async (req: Request, res: Response) => {
  try {
    const { event, medication, symptom, timeElapsed } = req.body;
    
    const alert = buildAlert({
      event: event || 'missed_medication',
      medication,
      symptom,
      timeElapsed
    });
    
    res.json({
      success: true,
      alert,
      note: 'This is a preview. Use /api/reports/send-alert to actually send.'
    });
  } catch (error) {
    log.error({ err: error }, '❌ Test alert error:');
    res.status(500).json({ error: 'Failed to generate test alert' });
  }
});

/**
 * POST /api/reports/send-alert - Send context-aware alert
 */
router.post('/reports/send-alert', async (req: Request, res: Response) => {
  try {
    const { event, medication, symptom, timeElapsed, additionalContext } = req.body;
    
    const success = await sendAlert({
      event: event || 'general_concern',
      medication,
      symptom,
      timeElapsed,
      additionalContext
    }, true);
    
    if (success) {
      res.json({
        success: true,
        message: 'Alert sent to caregiver'
      });
    } else {
      res.status(500).json({
        success: false,
        error: 'Failed to send alert'
      });
    }
  } catch (error) {
    log.error({ err: error }, '❌ Send alert error:');
    res.status(500).json({ error: 'Failed to send alert' });
  }
});

/**
 * POST /api/reports/reassurance - Send "all is well" message
 */
router.post('/reports/reassurance', async (req: Request, res: Response) => {
  try {
    const success = await sendReassurance(true);
    
    if (success) {
      res.json({
        success: true,
        message: 'Reassurance message sent to caregiver'
      });
    } else {
      res.status(500).json({
        success: false,
        error: 'Failed to send reassurance message'
      });
    }
  } catch (error) {
    log.error({ err: error }, '❌ Send reassurance error:');
    res.status(500).json({ error: 'Failed to send reassurance' });
  }
});

/**
 * POST /api/reports/test-scheduler - Run all scheduled tasks now (for testing)
 */
router.post('/reports/test-scheduler', async (req: Request, res: Response) => {
  try {
    await testScheduler();
    res.json({
      success: true,
      message: 'All scheduled tasks executed (check console for details)'
    });
  } catch (error) {
    log.error({ err: error }, '❌ Test scheduler error:');
    res.status(500).json({ error: 'Failed to test scheduler' });
  }
});

/**
 * GET /api/reports/status - Get health and adherence report status
 */
router.get('/status', (req: Request, res: Response) => {
  const healthStatus = healthReportService.getStatus();
  const adherenceStatus = adherenceReportService.getStatus();

  res.json({
    lastHealthReportAt: healthStatus.lastReportSentAt,
    lastAdherenceReportAt: adherenceStatus.lastReportSentAt,
    nextHealthReportAt: healthStatus.nextReportScheduledAt,
    nextAdherenceReportAt: adherenceStatus.nextReportScheduledAt,
    healthReportsSent: healthStatus.reportsSentCount,
    adherenceReportsSent: adherenceStatus.reportsSentCount,
    todayMetrics: healthStatus.metrics,
    weeklyAdherence: adherenceStatus.currentWeekAdherence,
  });
});

/**
 * POST /api/reports/health/send-now - Manually trigger health report
 */
router.post('/health/send-now', async (req: Request, res: Response) => {
  try {
    log.info('📊 Manual health report triggered');
    await healthReportService.sendDailyReport();
    res.json({ status: 'success', message: 'Health report sent' });
  } catch (error) {
    log.error({ err: error }, 'Error sending health report:');
    res.status(500).json({ error: 'Failed to send health report' });
  }
});

/**
 * POST /api/reports/adherence/send-now - Manually trigger adherence report
 */
router.post('/adherence/send-now', async (req: Request, res: Response) => {
  try {
    log.info('💊 Manual adherence report triggered');
    await adherenceReportService.sendWeeklyReport();
    res.json({ status: 'success', message: 'Adherence report sent' });
  } catch (error) {
    log.error({ err: error }, 'Error sending adherence report:');
    res.status(500).json({ error: 'Failed to send adherence report' });
  }
});

/**
 * GET /api/reports/adherence/history - Get adherence history
 */
router.get('/adherence/history', (req: Request, res: Response) => {
  const weeklyAdherence = adherenceReportService.calculateWeeklyAdherence();

  res.json({
    period: 'Last 7 days',
    summary: {
      overallAdherence: weeklyAdherence.overallAdherence,
      trend: weeklyAdherence.trend,
      bestDay: weeklyAdherence.bestDay,
      worstDay: weeklyAdherence.worstDay,
    },
    dailyBreakdown: weeklyAdherence.dailyBreakdown,
  });
});

/**
 * GET /api/reports/health/metrics - Get today's health metrics
 */
router.get('/health/metrics', (req: Request, res: Response) => {
  const metrics = healthReportService.calculateTodayMetrics();
  
  res.json({
    timestamp: new Date(),
    medications: {
      takenToday: metrics.medicationsTakenToday,
      scheduledToday: metrics.medicationsTotal,
      adherence: metrics.medicationAdherence,
    },
    activity: {
      count: metrics.activitiesCount,
      duration: metrics.activeDuration,
      lastActivity: metrics.lastActivity,
    },
    observations: metrics.observations,
    concerns: metrics.concerns,
  });
});

export default router;
