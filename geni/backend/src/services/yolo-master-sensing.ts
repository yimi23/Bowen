/**
 * GENI Master Sensing Core
 * Integrates YOLOv8-pose with emergency detection and alert dispatch
 * 
 * Detection Logic:
 * - Desk Faint: Head drops below shoulder line (nose_y > shoulder_y + 40)
 * - Floor Fall: Hips drop rapidly (hip_vel > 45 pixels/frame)
 * - Head/Hip proximity: abs(nose_y - hip_y) < 65 (collapsed state)
 * 
 * Confirmation: 3.0 seconds of unresponsiveness required before alert
 */

import { buildGENIContext } from './geni-context';
import { notifyCaregiver } from './notifications';
import { textToSpeech } from './elevenlabs';
import { state, addActivity } from '../state';
import { emitActivity } from '../socket';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('yolo-master-sensing');

interface YOLOEmergencyAlert {
  type: 'fall' | 'desk_faint' | 'unresponsive';
  timestamp: string;
  confidence: number;
  detected_at_frame: number;
  person_detected: boolean;
}

export const yoloMasterSensing = {
  isMonitoring: false,
  lastEmergency: null as YOLOEmergencyAlert | null,
  emergencyInProgress: false,

  /**
   * Handle emergency alert from YOLO service
   * Called when detection confirms 3 seconds of unresponsiveness
   */
  async handleEmergencyDetected(alert: YOLOEmergencyAlert) {
    log.info({ detail: alert.type }, '🚨 YOLO EMERGENCY DETECTED:');

    // Prevent duplicate alerts within 30 seconds
    if (this.emergencyInProgress) {
      log.info('⚠️ Emergency already in progress, ignoring duplicate');
      return;
    }

    this.emergencyInProgress = true;
    this.lastEmergency = alert;

    try {
      // Log activity
      const activity = addActivity(
        `EMERGENCY: ${alert.type.toUpperCase()} detected at ${alert.timestamp}`,
        'emergency'
      );
      emitActivity(activity);

      // 1. IMMEDIATE AUDIO ALERT
      log.info('📢 Triggering audio alert...');
      const audioMessage = 'Are you okay? I am notifying the authorities and your caretaker now.';
      await textToSpeech(audioMessage);

      // 2. SEND SMS TO CAREGIVER
      log.info('📱 Sending SMS alert to caregiver...');
      const context = buildGENIContext();
      const updateMessage = alert.type === 'fall' 
        ? `EMERGENCY: FALL DETECTED - ${context.patientName} may need immediate assistance`
        : `EMERGENCY: UNRESPONSIVE STATE - ${context.patientName} is not responding`;

      await notifyCaregiver({
        type: 'unusual_activity',
        priority: 'critical',
        message: updateMessage,
        details: { alertType: alert.type, timestamp: alert.timestamp },
      });

      // 3. UPDATE STATE
      if (!state.lastEmergency) {
        state.lastEmergency = {
          type: alert.type,
          timestamp: new Date(alert.timestamp),
          acknowledged: false,
        };
      }
      state.emergencyTriggeredAt = new Date(alert.timestamp);

      // 4. Auto-clear after 60 seconds if no manual confirmation
      setTimeout(() => {
        this.emergencyInProgress = false;
        log.info('✅ Emergency timeout reset');
      }, 60000);
    } catch (error) {
      log.error({ err: error }, '❌ Error handling emergency:');
      this.emergencyInProgress = false;
    }
  },

  /**
   * Clear/acknowledge emergency
   */
  clearEmergency() {
    log.info('✅ Emergency cleared by user');
    this.emergencyInProgress = false;
    this.lastEmergency = null;
    if (state.lastEmergency) {
      state.lastEmergency.acknowledged = true;
    }
  },

  /**
   * Get current emergency status
   */
  getStatus() {
    return {
      isMonitoring: this.isMonitoring,
      emergencyInProgress: this.emergencyInProgress,
      lastEmergency: this.lastEmergency,
    };
  },
};
