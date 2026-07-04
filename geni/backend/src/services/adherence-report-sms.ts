/**
 * Medication Adherence Report SMS Service
 * Generates and sends weekly medication adherence summaries
 * Schedule: Weekly on Sundays at 6:00 PM
 */

import { state } from '../state';
import { notifyCaregiver } from './notifications';
import { buildGENIContext } from './geni-context';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('adherence-report-sms');

interface DailyAdherence {
  date: string;
  day: string;
  medicationsTaken: number;
  medicationsScheduled: number;
  adherencePercent: number;
}

interface WeeklyAdherenceSummary {
  weekOf: string;
  totalDaysTracked: number;
  overallAdherence: number;
  bestDay: { day: string; adherence: number };
  worstDay: { day: string; adherence: number };
  dailyBreakdown: DailyAdherence[];
  trend: 'improving' | 'stable' | 'declining';
}

export const adherenceReportService = {
  lastReportSentAt: null as Date | null,
  reportsSentCount: 0,

  /**
   * Calculate adherence for a specific date
   */
  getAdherenceForDate(date: Date): DailyAdherence {
    const dateOnly = new Date(date);
    dateOnly.setHours(0, 0, 0, 0);

    const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
    const dateStr = date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });

    // Find medication history entry for this date
    const medHistory = state.medicationHistory.find(med => {
      const medDate = new Date(med.date);
      medDate.setHours(0, 0, 0, 0);
      return medDate.getTime() === dateOnly.getTime();
    });

    let adherencePercent = 0;
    let takenCount = 0;
    const totalCount = state.todaysMedications.length;

    if (medHistory) {
      if (medHistory.status === 'all-taken') {
        adherencePercent = 100;
        takenCount = totalCount;
      } else if (medHistory.status === 'partial') {
        adherencePercent = 50;
        takenCount = Math.floor(totalCount / 2);
      }
    }

    return {
      date: dateStr,
      day: dayName,
      medicationsTaken: takenCount,
      medicationsScheduled: totalCount,
      adherencePercent,
    };
  },

  /**
   * Calculate weekly adherence summary (last 7 days)
   */
  calculateWeeklyAdherence(): WeeklyAdherenceSummary {
    const today = new Date();
    const dailyAdherence: DailyAdherence[] = [];

    // Get last 7 days
    for (let i = 6; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      dailyAdherence.push(this.getAdherenceForDate(date));
    }

    // Calculate metrics
    const validDays = dailyAdherence.filter(d => d.medicationsScheduled > 0);
    const overallAdherence = validDays.length > 0
      ? Math.round(
          validDays.reduce((sum, d) => sum + d.adherencePercent, 0) /
            validDays.length
        )
      : 0;

    const bestDay = validDays.length > 0
      ? validDays.reduce((best, current) =>
          current.adherencePercent > best.adherencePercent ? current : best
        )
      : { day: 'N/A', adherencePercent: 0 };

    const worstDay = validDays.length > 0
      ? validDays.reduce((worst, current) =>
          current.adherencePercent < worst.adherencePercent ? current : worst
        )
      : { day: 'N/A', adherencePercent: 0 };

    // Determine trend (compare last 3 days vs previous 3 days)
    const recentDays = dailyAdherence.slice(-3);
    const previousDays = dailyAdherence.slice(0, 3);
    const recentAvg =
      recentDays.reduce((sum, d) => sum + d.adherencePercent, 0) / 3;
    const previousAvg =
      previousDays.reduce((sum, d) => sum + d.adherencePercent, 0) / 3;

    let trend: 'improving' | 'stable' | 'declining' = 'stable';
    if (recentAvg > previousAvg + 5) trend = 'improving';
    if (recentAvg < previousAvg - 5) trend = 'declining';

    // Format week of
    const weekStart = new Date(today);
    weekStart.setDate(weekStart.getDate() - 6);
    const weekOf = `${weekStart.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })} - ${today.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;

    return {
      weekOf,
      totalDaysTracked: validDays.length,
      overallAdherence,
      bestDay: { day: bestDay.day, adherence: bestDay.adherencePercent },
      worstDay: { day: worstDay.day, adherence: worstDay.adherencePercent },
      dailyBreakdown: dailyAdherence,
      trend,
    };
  },

  /**
   * Generate adherence report message
   */
  generateReportMessage(): string {
    const summary = this.calculateWeeklyAdherence();
    const context = buildGENIContext();

    let message = `💊 GENI Weekly Medication Adherence Report\n`;
    message += `Patient: ${context.patientName}\n`;
    message += `Week: ${summary.weekOf}\n\n`;

    message += `📈 Summary:\n`;
    message += `   Overall Adherence: ${summary.overallAdherence}%\n`;
    message += `   Days Tracked: ${summary.totalDaysTracked}\n`;
    message += `   Trend: ${summary.trend === 'improving' ? '📈 Improving' : summary.trend === 'declining' ? '📉 Declining' : '➡️ Stable'}\n\n`;

    message += `⭐ Best Day: ${summary.bestDay.day} (${summary.bestDay.adherence}%)\n`;
    message += `⚠️ Lowest Day: ${summary.worstDay.day} (${summary.worstDay.adherence}%)\n\n`;

    message += `📅 Daily Breakdown:\n`;
    summary.dailyBreakdown.forEach(day => {
      const bar = '█'.repeat(Math.round(day.adherencePercent / 10));
      const empty = '░'.repeat(10 - Math.round(day.adherencePercent / 10));
      message += `   ${day.day} ${day.date}: ${bar}${empty} ${day.adherencePercent}% (${day.medicationsTaken}/${day.medicationsScheduled})\n`;
    });

    if (summary.overallAdherence >= 90) {
      message += `\n✨ Excellent adherence! Keep up the great work!`;
    } else if (summary.overallAdherence >= 70) {
      message += `\n👍 Good adherence. Small improvements possible.`;
    } else {
      message += `\n📋 Adherence needs attention. Follow up recommended.`;
    }

    return message;
  },

  /**
   * Send weekly adherence report via SMS
   */
  async sendWeeklyReport(): Promise<void> {
    try {
      log.info('💊 Generating weekly adherence report...');

      const message = this.generateReportMessage();
      log.info('📱 Sending adherence report to caregiver via SMS...');

      await notifyCaregiver({
        type: 'weekly_summary',
        priority: 'medium',
        message: message,
        details: this.calculateWeeklyAdherence(),
      });

      this.lastReportSentAt = new Date();
      this.reportsSentCount++;

      log.info(`✅ Weekly adherence report sent (Total: ${this.reportsSentCount})`);
    } catch (error) {
      log.error({ err: error }, '❌ Failed to send adherence report:');
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
      currentWeekAdherence: this.calculateWeeklyAdherence(),
    };
  },

  /**
   * Calculate next report time (Sunday 6 PM)
   */
  getNextReportTime(): Date {
    const now = new Date();
    const nextSunday = new Date(now);
    
    // Calculate days until Sunday (0 = Sunday)
    const daysUntilSunday = (7 - nextSunday.getDay()) % 7;
    nextSunday.setDate(nextSunday.getDate() + (daysUntilSunday === 0 ? 7 : daysUntilSunday));
    
    nextSunday.setHours(18, 0, 0, 0); // 6 PM
    return nextSunday;
  },
};
