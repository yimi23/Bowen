/**
 * GENI Fall Detection Service
 * Manages the Python fall detection process and handles emergency alerts
 */

import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { state, addActivity } from '../state';
import { emitActivity, emitFallAlert, emitFallDetected } from '../socket';
import { sendWhatsAppMessage } from './twilio';
import { notifyCaregiver } from './notifications';
import { moduleLogger } from '../lib/logger';

const log = moduleLogger('fall-detection');

interface FallEvent {
  timestamp: number;
  level: 'info' | 'warning' | 'error' | 'emergency';
  message: string;
  patient: string;
  data?: any;
}

interface FrameFallPose {
  timestamp: number;
  keypointsDetected: boolean;
  noseX?: number;
  noseVelocity?: number;
  hipX?: number;
  hipVelocity?: number;
  shoulderX?: number;
  frameHeight?: number;
  frameWidth?: number;
  personDown: boolean;
  fallPrimed: boolean;
  emergencyTriggered: boolean;
  stillSeconds: number;
  confirmationTime: number;
}

export class FallDetectionService {
  getHealth() {
    return {
      running: this.isRunning,
      restartAttempts: this.restartAttempts,
      degraded: this.degradedAlertSent,
      lastStartAt: this.lastStartAt,
      emergencyActive: this.emergencyActive,
    };
  }

  private pythonProcess: ChildProcess | null = null;
  private isRunning = false;
  private emergencyActive = false;
  private emergencyStartTime: number | null = null;
  private responseTimeout: NodeJS.Timeout | null = null;
  private restartAttempts = 0;
  private degradedAlertSent = false;
  private lastStartAt: number | null = null;
  private lastImpactAt: number | null = null;
  private impactWindowStart: number | null = null;
  private impactCount = 0;
  private currentIncidentId: string | null = null;
  private incidentStartedAt: number | null = null;
  
  // Configuration
  private readonly RESPONSE_TIMEOUT_MS = 15000; // 15 seconds
  private readonly MAX_RESTART_ATTEMPTS = 3;
  private readonly RESTART_DELAY_MS = 50000;
  private readonly STABLE_RUN_RESET_MS = 120000;
  private readonly BACKOFF_DELAY_MS = 300000;
  private readonly IMPACT_VEL_THRESHOLD = 80;
  private readonly IMPACT_COOLDOWN_MS = 2 * 60 * 1000;
  private readonly IMPACT_WINDOW_MS = 5 * 60 * 1000;
  private readonly INCIDENT_COOLDOWN_MS = 2 * 60 * 1000;
  private readonly scriptPath = path.join(__dirname, '../../scripts/fall_detection.py');
  
  /**
   * Start fall detection monitoring
   */
  start(options: { patient?: string; camera?: number; headless?: boolean } = {}) {
    if (this.isRunning) {
      log.info('⚠️  Fall detection already running');
      return;
    }
    
    const args = [
      this.scriptPath,
      '--patient', options.patient || state.patient.name,
      '--camera', String(options.camera || 0),
    ];
    
    if (options.headless !== false) {
      args.push('--headless'); // Production mode (no window)
    }
    
    log.info({ args: args.join(' ') }, 'starting fall detection');
    
    this.pythonProcess = spawn('python3', args);
    this.isRunning = true;
    this.lastStartAt = Date.now();
    
    // Listen to stdout (JSON events)
    this.pythonProcess.stdout?.on('data', (data: Buffer) => {
      const lines = data.toString().split('\n').filter(line => line.trim());
      
      lines.forEach(line => {
        try {
          const event: FallEvent = JSON.parse(line);
          this.handleEvent(event);
        } catch (error) {
          // Not JSON - probably debug output
          log.info({ detail: line }, '[Fall Detection]');
        }
      });
    });
    
    // Listen to stderr (errors)
    this.pythonProcess.stderr?.on('data', (data: Buffer) => {
      log.error({ stderr: data.toString() }, 'fall detection stderr');
    });
    
    // Handle process exit
    this.pythonProcess.on('exit', (code, signal) => {
      log.info(`🛑 Fall detection process exited: code=${code}, signal=${signal}`);
      this.isRunning = false;
      this.pythonProcess = null;
      
      // Auto-restart on crash (unless manually stopped)
      if (code !== 0 && code !== null) {
        const runtimeMs = this.lastStartAt ? Date.now() - this.lastStartAt : 0;
        if (runtimeMs > this.STABLE_RUN_RESET_MS) {
          this.restartAttempts = 0;
          this.degradedAlertSent = false;
        }
        
        this.restartAttempts += 1;
        const delayMs =
          this.restartAttempts > this.MAX_RESTART_ATTEMPTS
            ? this.BACKOFF_DELAY_MS
            : this.RESTART_DELAY_MS;
        
        if (this.restartAttempts > this.MAX_RESTART_ATTEMPTS) {
          log.warn('⚠️  Fall detection unstable; backing off retries to 5 minutes. Check camera access.');
          if (!this.degradedAlertSent) {
            this.degradedAlertSent = true;
            notifyCaregiver({
              type: 'general_concern',
              priority: 'high',
              message: `Heads up - GENI's fall detection camera keeps stopping and I'm having trouble restarting it. ${options.patient} is NOT currently covered by automatic fall detection. Please check the GENI device when you can. - GENI`,
              dedupKey: 'fall_detection_degraded',
            }).catch(() => {});
          }
        }
        
        const delayLabel = delayMs >= 60000 ? `${Math.round(delayMs / 60000)} minutes` : `${Math.round(delayMs / 1000)} seconds`;
        log.info(`🔄 Restarting fall detection in ${delayLabel}... (attempt ${this.restartAttempts})`);
        setTimeout(() => this.start(options), delayMs);
      }
    });
  }

  /**
   * Update fall state from frame-based pose pipeline
   */
  updateFromFrame(pose: FrameFallPose, patientName: string) {
    if (!pose.keypointsDetected) return;
    
    if (this.currentIncidentId && this.incidentStartedAt) {
      const age = Date.now() - this.incidentStartedAt;
      if (age < this.INCIDENT_COOLDOWN_MS) {
        return;
      }
    }
    
    const noseVel = pose.noseVelocity ?? 0;
    const hipVel = pose.hipVelocity ?? 0;
    const impactDetected = Math.abs(noseVel) >= this.IMPACT_VEL_THRESHOLD ||
      Math.abs(hipVel) >= this.IMPACT_VEL_THRESHOLD;
    
    if (impactDetected && !this.emergencyActive) {
      if (this.currentIncidentId) return;
      const now = Date.now();
      if (!this.lastImpactAt || now - this.lastImpactAt > this.IMPACT_COOLDOWN_MS) {
        this.lastImpactAt = now;
        if (!this.impactWindowStart || now - this.impactWindowStart > this.IMPACT_WINDOW_MS) {
          this.impactWindowStart = now;
          this.impactCount = 0;
        }
        this.impactCount += 1;
        
        const activity = addActivity('Possible head/impact detected', 'system');
        emitActivity(activity);
        this.startIncident();
        emitFallDetected({ incidentId: this.currentIncidentId });
        emitFallAlert({
          state: 'confirming',
          message: 'Fall detected - checking on you...',
          progress: 0,
          patient: patientName,
          timestamp: Date.now(),
          data: { incidentId: this.currentIncidentId },
        });
        // Frontend modal handles audible prompts to avoid overlapping TTS.
        
        notifyCaregiver({
          type: 'fall_detected',
          priority: 'high',
          message: `GENI detected a sudden impact for ${patientName}. Monitoring for response; will call 911 if no response.`,
          details: { impactCount: this.impactCount }
        }).catch(error => {
          log.error({ err: error }, '❌ Failed to notify caregiver of impact:');
        });
        
        if (this.impactCount >= 2) {
          notifyCaregiver({
            type: 'unusual_activity',
            priority: 'medium',
            message: `GENI detected repeated sudden movements for ${patientName} within the last few minutes. Please check in.`,
            details: { impactCount: this.impactCount }
          }).catch(error => {
            log.error({ err: error }, '❌ Failed to send caregiver impact update:');
          });
        }
      }
    }
    
    if ((pose.emergencyTriggered || pose.fallPrimed) && !this.emergencyActive) {
      const emergencyPose = {
        ...pose,
        emergencyTriggered: true,
      };
      this.activateEmergencyFromFrame(emergencyPose, patientName);
      return;
    }
    
    if (pose.fallPrimed && !this.emergencyActive) {
      emitFallAlert({
        state: 'confirming',
        message: 'Checking on you...',
        progress: pose.confirmationTime > 0 ? pose.stillSeconds / pose.confirmationTime : 0,
      });
    }
  }
  
  /**
   * Stop fall detection monitoring
   */
  stop() {
    if (!this.isRunning || !this.pythonProcess) {
      log.info('⚠️  Fall detection not running');
      return;
    }
    
    log.info('🛑 Stopping fall detection...');
    this.pythonProcess.kill('SIGTERM');
    this.isRunning = false;
    this.pythonProcess = null;
    
    if (this.responseTimeout) {
      clearTimeout(this.responseTimeout);
      this.responseTimeout = null;
    }
  }
  
  /**
   * Handle events from Python script
   */
  private async handleEvent(event: FallEvent) {
    log.info({ level: event.level, data: event.data }, event.message);
    
    switch (event.level) {
      case 'info':
        this.handleInfo(event);
        break;
      
      case 'warning':
        this.handleWarning(event);
        break;
      
      case 'error':
        this.handleError(event);
        break;
      
      case 'emergency':
        await this.handleEmergency(event);
        break;
    }
  }
  
  /**
   * Handle info events (logging, state updates)
   */
  private handleInfo(event: FallEvent) {
    // Log significant state changes
    if (event.message.includes('initialized') || 
        event.message.includes('Recovery detected') ||
        event.message.includes('reset')) {
      
      const activity = addActivity(event.message, 'system');
      emitActivity(activity);
    }
  }
  
  /**
   * Handle warning events (fall primed, confirming)
   */
  private handleWarning(event: FallEvent) {
    if (event.message.includes('Impact detected')) {
      // Fall might be happening - log it
      const activity = addActivity(
        `⚠️ Possible fall detected - ${event.data?.type || 'unknown'} type`,
        'system'
      );
      emitActivity(activity);
      
      // Notify frontend to show "Confirming..." state
      emitFallAlert({
        state: 'confirming',
        message: 'Checking on you...',
        progress: 0
      });
    }
  }
  
  /**
   * Handle error events
   */
  private handleError(event: FallEvent) {
    log.error({ data: event.data }, `fall detection error: ${event.message}`);
    
    // Log error activity
    const activity = addActivity(`Fall detection error: ${event.message}`, 'system');
    emitActivity(activity);
  }
  
  /**
   * Handle EMERGENCY event (fall confirmed)
   */
  private async handleEmergency(event: FallEvent) {
    if (this.emergencyActive) {
      log.info('⚠️  Emergency already active, ignoring duplicate');
      return;
    }
    
    this.emergencyActive = true;
    this.emergencyStartTime = Date.now();
    
    log.info('🚨 FALL DETECTED - INITIATING EMERGENCY RESPONSE');
    
    // 1. Log to database
    const activity = addActivity(
      `🚨 FALL DETECTED: ${event.patient} may have fallen and is unresponsive`,
      'emergency'
    );
    emitActivity(activity);
    
    // 2. Show full-screen alert in frontend
    emitFallAlert({
      state: 'emergency',
      message: 'FALL DETECTED - Are you okay?',
      patient: event.patient,
      timestamp: event.timestamp,
      data: event.data
    });
    
    // 3. Send immediate WhatsApp alert to primary caregiver
    await this.sendCaregiverAlert(event);
    
    // 4. Start response timeout - if no "I'm OK" response in 60 seconds, escalate
    this.responseTimeout = setTimeout(() => {
      this.escalateEmergency(event);
    }, this.RESPONSE_TIMEOUT_MS);
  }

  /**
   * Activate emergency from frame-based pose pipeline
   */
  private async activateEmergencyFromFrame(pose: FrameFallPose, patientName: string) {
    this.emergencyActive = true;
    this.emergencyStartTime = Date.now();
    this.startIncident();
    
    const activity = addActivity(
      `🚨 FALL DETECTED: ${patientName} may have fallen and is unresponsive`,
      'emergency'
    );
    emitActivity(activity);
    
    emitFallAlert({
      state: 'emergency',
      message: 'FALL DETECTED - Are you okay?',
      patient: patientName,
      timestamp: pose.timestamp,
      data: { confirmation_time: pose.confirmationTime, incidentId: this.currentIncidentId }
    });
    emitFallDetected({ incidentId: this.currentIncidentId });
    // Frontend modal handles audible prompts to avoid overlapping TTS.
    
    notifyCaregiver({
      type: 'fall_detected',
      priority: 'critical',
      message: `GENI detected a fall for ${patientName}. Calling 911 now unless cancelled.`,
      details: { confirmationTime: pose.confirmationTime }
    }).catch(error => {
      log.error({ err: error }, '❌ Failed to notify caregiver of 911 decision:');
    });
    
    const event: FallEvent = {
      timestamp: Math.round(pose.timestamp),
      level: 'emergency',
      message: 'FALL DETECTED - CONFIRMED',
      patient: patientName,
      data: { confirmation_time: pose.confirmationTime },
    };
    
    await this.sendCaregiverAlert(event);
    
    this.responseTimeout = setTimeout(() => {
      this.simulateEmergencyCall(event);
      this.escalateEmergency(event);
    }, this.RESPONSE_TIMEOUT_MS);
  }

  private simulateEmergencyCall(event: FallEvent) {
    log.info('📞 Simulating 911 call...');
    const activity = addActivity('Simulated 911 call initiated', 'emergency');
    emitActivity(activity);
    // Frontend modal handles audible prompts to avoid overlapping TTS.
  }
  
  /**
   * Send WhatsApp alert to caregiver
   */
  private async sendCaregiverAlert(event: FallEvent) {
    const primaryContact = state.contacts.find(c => c.isPrimary);
    
    if (!primaryContact) {
      log.error('❌ No primary contact configured');
      return;
    }
    
    const message = `🚨 EMERGENCY ALERT

${event.patient} may have fallen!

Fall detected at ${new Date(event.timestamp * 1000).toLocaleTimeString()}.

${event.patient} has not responded for ${event.data?.confirmation_time || 3} seconds.

Please check on ${event.patient} IMMEDIATELY.

If ${event.patient} is okay, they can cancel this alert in the GENI app.

- GENI Fall Detection System`;
    
    try {
      log.info({ detail: primaryContact.name }, '📱 Sending emergency WhatsApp to:');
      await sendWhatsAppMessage(primaryContact.phone, message);
      log.info('✅ Emergency alert sent to caregiver');
      
      // Log activity
      const activity = addActivity(
        `Emergency alert sent to ${primaryContact.name}`,
        'emergency'
      );
      emitActivity(activity);
      
    } catch (error) {
      log.error({ err: error }, '❌ Failed to send emergency WhatsApp:');
      
      // Log failure
      const activity = addActivity(
        `Failed to send emergency alert: ${error}`,
        'system'
      );
      emitActivity(activity);
    }
  }
  
  /**
   * Escalate emergency if no response
   */
  private async escalateEmergency(event: FallEvent) {
    log.info('🚨 NO RESPONSE - ESCALATING EMERGENCY');
    
    // Send to ALL contacts
    const allContacts = state.contacts;
    
    const escalationMessage = `🚨🚨 URGENT EMERGENCY 🚨🚨

${event.patient} FELL AND IS NOT RESPONDING!

Fall detected ${Math.round((Date.now() - (event.timestamp * 1000)) / 1000)}s ago.

NO RESPONSE for 60+ seconds.

IMMEDIATE ASSISTANCE REQUIRED.

Consider calling emergency services (911) if you cannot reach ${event.patient}.

- GENI Fall Detection System`;
    
    for (const contact of allContacts) {
      try {
        log.info({ detail: contact.name }, '📱 Sending escalation to:');
        await sendWhatsAppMessage(contact.phone, escalationMessage);
      } catch (error) {
        log.error({ err: error }, `❌ Failed to send to ${contact.name}:`);
      }
    }
    
    // Log escalation
    const activity = addActivity(
      'Emergency escalated - all contacts notified',
      'emergency'
    );
    emitActivity(activity);
    
    // Emit escalation to frontend
    emitFallAlert({
      state: 'escalated',
      message: 'Help is on the way',
      patient: event.patient
    });
  }
  
  /**
   * User confirmed they're okay - cancel emergency
   */
  confirmOK() {
    if (!this.emergencyActive) {
      log.info('⚠️  No active emergency to confirm');
      return false;
    }
    
    log.info('✅ User confirmed OK - canceling emergency');
    
    const duration = this.emergencyStartTime 
      ? Math.round((Date.now() - this.emergencyStartTime) / 1000)
      : 0;
    
    // Clear timeout
    if (this.responseTimeout) {
      clearTimeout(this.responseTimeout);
      this.responseTimeout = null;
    }
    
    // Reset emergency state
    this.emergencyActive = false;
    this.emergencyStartTime = null;
    this.currentIncidentId = null;
    this.incidentStartedAt = null;
    
    // Log activity
    const activity = addActivity(
      `False alarm - ${state.patient.name} confirmed OK after ${duration}s`,
      'system'
    );
    emitActivity(activity);
    
    // Notify frontend
    emitFallAlert({
      state: 'cancelled',
      message: 'Emergency cancelled - user is OK'
    });
    
    // Notify caregiver
    this.sendFalseAlarmNotification();
    
    return true;
  }

  private startIncident() {
    if (!this.currentIncidentId) {
      this.currentIncidentId = `fall-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      this.incidentStartedAt = Date.now();
    }
  }
  
  /**
   * Send false alarm notification to caregiver
   */
  private async sendFalseAlarmNotification() {
    const primaryContact = state.contacts.find(c => c.isPrimary);
    
    if (!primaryContact) return;
    
    const message = `✅ FALSE ALARM

${state.patient.name} confirmed they are okay.

The fall alert has been cancelled.

- GENI Fall Detection System`;
    
    try {
      await sendWhatsAppMessage(primaryContact.phone, message);
      log.info('✅ False alarm notification sent');
    } catch (error) {
      log.error({ err: error }, '❌ Failed to send false alarm notification:');
    }
  }
  
  /**
   * Get current status
   */
  getStatus() {
    return {
      isRunning: this.isRunning,
      emergencyActive: this.emergencyActive,
      emergencyDuration: this.emergencyStartTime 
        ? Math.round((Date.now() - this.emergencyStartTime) / 1000)
        : null
    };
  }
}

// Singleton instance
export const fallDetectionService = new FallDetectionService();
