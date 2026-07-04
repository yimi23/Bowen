/**
 * Health Report SMS Service
 * Generates and sends daily health summaries to caregiver
 * Schedule: Daily at 8:00 AM
 */

import { state } from '../state';
import { notifyCaregiver } from './notifications';
import { buildGENIContext } from './geni-context';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('health-report-sms');

interface HealthMetrics {
  medicationsTakenToday: number;
  medicationsTotal: number;
  medicationAdherence: string;
  activitiesCount: number;
  lastActivity: string | null;
  activeDuration: number; // minutes
  observations: string[];
  concerns: string[];
}

export const healthReportService = {
  lastReportSentAt: null as Date | null,
  reportsSentCount: 0,

  /**
   * Calculate today's health metrics
   */
  calculateTodayMetrics(): HealthMetrics {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Count medications taken today (using status field)
    const todayMeds = state.medicationHistory.filter(med => {
      const medDate = new Date(med.date);
      medDate.setHours(0, 0, 0, 0);
      return medDate.getTime() === today.getTime();
    });

    const todayStatus = todayMeds[0]?.status || 'none';
    let medicationsTaken = 0;
    if (todayStatus === 'all-taken') medicationsTaken = state.todaysMedications.length;
    else if (todayStatus === 'partial') medicationsTaken = Math.floor(state.todaysMedications.length / 2);
    
    const medsScheduledToday = state.todaysMedications.length;
    const medicationAdherence = medsScheduledToday > 0
      ? Math.round((medicationsTaken / medsScheduledToday) * 100)
      : 0;

    // Count activities today
    const todaysActivities = state.activities.filter(activity => {
      const actTime = new Date(activity.timestamp);
      actTime.setHours(0, 0, 0, 0);
      return actTime.getTime() === today.getTime();
    });

    // Calculate active duration (rough estimate)
    let activeDuration = 0;
    if (todaysActivities.length > 0) {
      activeDuration = Math.min(todaysActivities.length * 5, 120); // Max 2 hours
    }

    // Extract observations from activities
    const observations = todaysActivities
      .filter(a => !a.type.includes('medication'))
      .slice(0, 3)
      .map(a => a.type);

    const concerns = state.activities
      .filter(a => a.type === 'emergency')
      .slice(0, 2)
      .map(a => a.type);

    return {
      medicationsTakenToday: medicationsTaken,
      medicationsTotal: medsScheduledToday,
      medicationAdherence: `${medicationAdherence}%`,
      activitiesCount: todaysActivities.length,
      lastActivity: todaysActivities[todaysActivities.length - 1]?.type || null,
      activeDuration,
      observations,
      concerns,
    };
  },

  /**
   * Generate health report message
   */
  generateReportMessage(): string {
    const metrics = this.calculateTodayMetrics();
    const context = buildGENIContext();
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });

    let message = `📊 GENI Daily Health Report - ${context.patientName}\n`;
    message += `Time: ${now.toLocaleDateString()} ${timeStr}\n\n`;

    message += `💊 Medications:\n`;
    message += `   Taken: ${metrics.medicationsTakenToday}/${metrics.medicationsTotal}\n`;
    message += `   Adherence: ${metrics.medicationAdherence}\n\n`;

    message += `🏃 Activity:\n`;
    message += `   Activities: ${metrics.activitiesCount}\n`;
    message += `   Duration: ~${metrics.activeDuration} min\n`;
    if (metrics.lastActivity) {
      message += `   Last: ${metrics.lastActivity}\n`;
    }
    message += '\n';

    if (metrics.observations.length > 0) {
      message += `📝 Observations:\n`;
      metrics.observations.forEach(obs => {
        message += `   • ${obs}\n`;
      });
      message += '\n';
    }

    if (metrics.concerns.length > 0) {
      message += `⚠️ Concerns:\n`;
      metrics.concerns.forEach(concern => {
        message += `   • ${concern}\n`;
      });
    }

    return message;
  },

  /**
   * Send daily health report via SMS
   */
  async sendDailyReport(): Promise<void> {
    try {
      log.info('📊 Generating daily health report...');

      const message = this.generateReportMessage();
      log.info('📱 Sending report to caregiver via SMS...');

      await notifyCaregiver({
        type: 'daily_summary',
        priority: 'medium',
        message: message,
        details: this.calculateTodayMetrics(),
      });

      this.lastReportSentAt = new Date();
      this.reportsSentCount++;

      log.info(`✅ Daily report sent (Total: ${this.reportsSentCount})`);
    } catch (error) {
      log.error({ err: error }, '❌ Failed to send daily report:');
      throw error;
    }
  },

  /**
   * Get status for frontend
   */
  getStatus() {
    return {
      lastReportSentAt: this.lastReportSentAt,
      reportsSentCount: this.reportsSentCount,
      nextReportScheduledAt: this.getNextReportTime(),
      metrics: this.calculateTodayMetrics(),
    };
  },

  /**
   * Calculate next report time (8 AM)
   */
  getNextReportTime(): Date {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(8, 0, 0, 0);
    return tomorrow;
  },
};
