import cron from 'node-cron';
import { sendDailyReportToCaregiver } from './reporting';
import { sendWeeklySummaryToCaregiver } from './proactive';
import { addActivity } from '../state';
import { generateConversationStarter } from './conversation';
import { emitSpeak } from '../socket';
import { healthReportService } from './health-report-sms';
import { adherenceReportService } from './adherence-report-sms';
import { moduleLogger } from '../lib/logger';
import { config } from '../config';
import { monitoring } from './monitoring/core';

const log = moduleLogger('scheduler');

/**
 * Initialize all scheduled tasks
 */
export function initializeScheduler() {
  log.info('⏰ Initializing scheduler...');
  
  // Daily health report SMS: 8:00 AM every day
  cron.schedule('0 8 * * *', async () => {
    log.info('📊 Running daily health report SMS...');
    try {
      await healthReportService.sendDailyReport();
    } catch (error) {
      log.error({ err: error }, 'Error sending daily health report:');
    }
  }, {
    timezone: config.timezone
  });

  // Weekly medication adherence report SMS: Sunday at 6:00 PM
  cron.schedule('0 18 * * 0', async () => {
    log.info('💊 Running weekly adherence report SMS...');
    try {
      await adherenceReportService.sendWeeklyReport();
    } catch (error) {
      log.error({ err: error }, 'Error sending adherence report:');
    }
  }, {
    timezone: config.timezone
  });
  
  // Daily report: 9:00 PM every day
  cron.schedule('0 21 * * *', async () => {
    log.info('📊 Running daily report...');
    await sendDailyReportToCaregiver();
  }, {
    timezone: config.timezone
  });
  
  // Weekly summary: Sunday at 8:00 PM
  cron.schedule('0 20 * * 0', async () => {
    log.info('📊 Running weekly summary...');
    await sendWeeklySummaryToCaregiver();
  }, {
    timezone: config.timezone
  });
  
  // Unified monitoring cycle: every 15 min (8 AM - 10 PM). The core throttles
  // internally (conversation 30 min, meds 30 min, wellness 2 h), so this one
  // cron replaces the three separate med/health/conversation crons that each
  // duplicated part of the cycle.
  cron.schedule('*/15 8-22 * * *', async () => {
    try {
      await monitoring.runCycle();
    } catch (error) {
      log.error({ err: error }, 'monitoring cycle failed');
    }
  }, {
    timezone: config.timezone
  });
  
  // Morning greeting: 8:00 AM every day
  cron.schedule('0 8 * * *', async () => {
    log.info('☀️ Good morning check triggered');
    const starter = await generateConversationStarter('morning-greeting');
    addActivity(`GENI: ${starter}`, 'system');
    emitSpeak(starter);
  }, {
    timezone: config.timezone
  });
  
  log.info('scheduler initialized: monitoring cycle */15 8-22, reports daily 9pm + weekly Sun, morning greeting 8am');
}

/**
 * Test scheduler (trigger reports immediately for testing)
 */
export async function testScheduler() {
  log.info('🧪 Testing scheduler functions...');
  
  log.info('1. Testing daily report...');
  await sendDailyReportToCaregiver();
  
  log.info('2. Testing weekly summary...');
  await sendWeeklySummaryToCaregiver();
  
  log.info('3. Testing monitoring cycle...');
  await monitoring.runCycle();
  
  log.info('✅ Scheduler tests complete');
}
