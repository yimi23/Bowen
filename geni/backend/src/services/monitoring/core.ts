/**
 * GENI Monitoring Core
 *
 * The single home for everything that used to live in vision-pipeline.ts,
 * continuous-vision.ts and unified-monitoring.ts:
 *
 *   processFrame()  — the one frame path: fall pose → scene analysis →
 *                     contextual messaging → pill check → notifications
 *   runCycle()      — the time-based checks: proactive conversation,
 *                     overdue medications, wellness
 *
 * The core extends EventEmitter and emits typed events ('fall-pose',
 * 'pill-check', 'concern', 'cycle') so new consumers (dashboards, recorders)
 * can attach without adding another pipeline.
 */

import { EventEmitter } from 'events';
import { config } from '../../config';
import { moduleLogger } from '../../lib/logger';
import { state, addActivity, addPillCheckResult } from '../../state';
import { emitActivity, emitSpeak, emitVisionUpdate } from '../../socket';
import { analyzeFrame, type SceneAnalysis } from '../vision';
import { analyzeMedicationAdherence, type CompartmentStates } from '../medication-adherence';
import { generatePillCheckResponse } from '../geni-brain';
import { notifyPillCheck, notifyCaregiver, notifyMedicationMissed, type NotificationPriority } from '../notifications';
import { savePillCheck } from '../../database/pillCheckHistory';
import { conversationMemory } from '../conversation-memory';
import { buildGENIContext } from '../geni-context';
import { shouldInitiateConversation, generateConversationStarter } from '../conversation';
import { fallPoseStream } from '../fall-pose-stream';
import { fallDetectionService } from '../fall-detection';

const log = moduleLogger('monitoring');

export type FrameSource = 'manual' | 'continuous';

export interface FrameResult {
  vision: SceneAnalysis;
  visionMessage: string | null;
  fallPose: any | null;
  pillCheck: {
    result: any;
    method: 'vision' | 'yolo';
    recordId: string;
    responseText: string;
    adherenceAnalysis: any | null;
    suppressed: boolean;
  };
}

export interface MonitoringEvent {
  timestamp: Date;
  type: 'pill-check' | 'conversation-initiated' | 'wellness-check' | 'medication-alert' | 'vision-analysis';
  summary: string;
  details: any;
  concernLevel: 'none' | 'low' | 'medium' | 'high' | 'critical';
  actionTaken?: string;
  notifiedCaregiver: boolean;
}

interface VisionState {
  lastAnalysis: SceneAnalysis | null;
  pillsPresentSince: Date | null;
  lastActivityChange: Date | null;
  consecutiveConcerns: number;
}

function getTimeOfDay(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'morning';
  if (hour < 17) return 'afternoon';
  if (hour < 21) return 'evening';
  return 'night';
}

class MonitoringCore extends EventEmitter {
  private paused = false;
  private frameInFlight = false;

  private vision: VisionState = {
    lastAnalysis: null,
    pillsPresentSince: null,
    lastActivityChange: null,
    consecutiveConcerns: 0,
  };

  private eventLog: MonitoringEvent[] = [];
  private lastPillCheck: Date | null = null;
  private lastConversationCheck: Date | null = null;
  private lastWellnessCheck: Date | null = null;

  // -------------------------------------------------------------------------
  // Frame path
  // -------------------------------------------------------------------------

  /** True while a frame is being analyzed — continuous frames arriving
   * during analysis are skipped at the route to avoid double AI spend. */
  isBusy(): boolean {
    return this.frameInFlight;
  }

  async processFrame(imageBase64: string, options: { source: FrameSource }): Promise<FrameResult> {
    this.frameInFlight = true;
    try {
      return await this.processFrameInner(imageBase64, options);
    } finally {
      this.frameInFlight = false;
    }
  }

  private async processFrameInner(imageBase64: string, options: { source: FrameSource }): Promise<FrameResult> {
    // 1. Fall pose first — a fall in progress suppresses all chatter below
    const fallPose =
      config.fallDetection.enabled && config.fallDetection.mode === 'frame'
        ? await fallPoseStream.analyzeFrame(imageBase64)
        : null;

    const suppress = !!(fallPose?.emergencyTriggered || fallPose?.fallPrimed);

    if (fallPose?.keypointsDetected) {
      log.debug(
        { personDown: fallPose.personDown, fallPrimed: fallPose.fallPrimed, emergency: fallPose.emergencyTriggered },
        'fall pose'
      );
      this.emit('fall-pose', fallPose);
      fallDetectionService.updateFromFrame(fallPose, config.patient.name);
    }

    // 2. ONE combined vision call: scene + pill organizer together
    const frame = await analyzeFrame(imageBase64, config.patient.name, this.getMedicationScheduleContext());
    const sceneAnalysis = frame.scene;
    const pillResult = frame.pills;

    const visionMessage = this.processSceneAnalysis(sceneAnalysis, {
      emitUpdates: options.source === 'continuous' && !suppress,
      speak: options.source === 'continuous' && !suppress,
      recordMemory: !suppress,
    });

    const method: 'vision' | 'yolo' = 'vision';
    const confidence = pillResult.confidence as 'high' | 'medium' | 'low';
    const observations = pillResult.observations;

    const savedRecord = savePillCheck(pillResult.status, confidence, observations, method);
    addPillCheckResult({ status: pillResult.status, observations, confidence });

    const activityMessage =
      pillResult.status === 'taken'
        ? `Pills confirmed taken (${method} verification)`
        : pillResult.status === 'present'
          ? `Pills still present (${method} check)`
          : `Pill check unclear (${method} review needed)`;
    emitActivity(addActivity(activityMessage, 'medication'));
    this.emit('pill-check', { result: pillResult, method });

    // 4. Adherence analysis or conversational pill response + caregiver update
    let adherenceAnalysis: any | null = null;
    let responseText = '';

    const compartments = 'compartments' in pillResult ? (pillResult as any).compartments : null;
    const hasCompartments = compartments && Object.keys(compartments).length > 0;

    if (hasCompartments) {
      adherenceAnalysis = analyzeMedicationAdherence(compartments as CompartmentStates);

      if (!suppress) {
        responseText = adherenceAnalysis.message;
      }

      if (adherenceAnalysis.shouldAlertCaregiver && adherenceAnalysis.caregiverAlertMessage && !suppress) {
        const priorityMap: Record<string, NotificationPriority> = {
          none: 'low',
          low: 'low',
          medium: 'medium',
          high: 'high',
          critical: 'critical',
        };
        notifyCaregiver({
          type: 'medication_check',
          priority: priorityMap[adherenceAnalysis.concernLevel] || 'low',
          message: adherenceAnalysis.caregiverAlertMessage,
          details: { adherenceAnalysis, visionResult: pillResult, method },
        }).catch(error => log.error({ err: error }, 'adherence caregiver alert failed'));
      }
    } else if (!suppress) {
      responseText = await generatePillCheckResponse({
        status: pillResult.status as 'taken' | 'present' | 'unclear',
        observations,
      });

      notifyPillCheck({
        status: pillResult.status as 'taken' | 'present' | 'unclear',
        observations,
        method,
      }).catch(error => log.error({ err: error }, 'pill check caregiver update failed'));
    }

    if (options.source === 'manual' && responseText) {
      const session = conversationMemory.getOrCreateSession(config.patient.name);
      conversationMemory.addMessage(session.id, 'geni', responseText, {
        timeOfDay: getTimeOfDay(),
        visionSnapshot: `${sceneAnalysis.observations} | activity: ${sceneAnalysis.activity} | pillStatus: ${sceneAnalysis.pillStatus}`,
      });
    }

    return {
      vision: sceneAnalysis,
      visionMessage,
      fallPose,
      pillCheck: {
        result: pillResult,
        method,
        recordId: savedRecord.id,
        responseText,
        adherenceAnalysis,
        suppressed: suppress,
      },
    };
  }

  /**
   * Stateful scene processing: delta tracking, change detection, and the
   * contextual-message rules (ported from continuous-vision.ts).
   */
  private processSceneAnalysis(
    analysis: SceneAnalysis,
    options: { emitUpdates?: boolean; speak?: boolean; recordMemory?: boolean } = {}
  ): string | null {
    const { emitUpdates = true, speak = true, recordMemory = true } = options;
    const now = new Date();

    // Delta tracking
    if (analysis.pillStatus === 'present') {
      if (!this.vision.pillsPresentSince) this.vision.pillsPresentSince = now;
    } else if (analysis.pillStatus === 'taken' && this.vision.pillsPresentSince) {
      const duration = Math.round((now.getTime() - this.vision.pillsPresentSince.getTime()) / 60000);
      log.debug({ minutes: duration }, 'pills taken after timer');
      this.vision.pillsPresentSince = null;
    }

    if (this.vision.lastAnalysis && this.vision.lastAnalysis.activity !== analysis.activity) {
      this.vision.lastActivityChange = now;
      log.debug({ from: this.vision.lastAnalysis.activity, to: analysis.activity }, 'activity changed');
    }

    this.vision.consecutiveConcerns = analysis.concerns.length > 0 ? this.vision.consecutiveConcerns + 1 : 0;

    // Change detection
    const prev = this.vision.lastAnalysis;
    const changes = {
      pillStatusChanged: prev ? prev.pillStatus !== analysis.pillStatus : false,
      newConcerns: analysis.concerns.length > 0 && this.vision.consecutiveConcerns === 1,
      pillsOverdue: this.isPillsOverdue(),
    };

    // Contextual message rules
    let message: string | null = null;
    const time = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

    if (changes.pillsOverdue && analysis.pillStatus === 'present') {
      const minutesOverdue = Math.round((now.getTime() - this.vision.pillsPresentSince!.getTime()) / 60000);
      const nextMed = this.getRecentMedication();
      if (nextMed) {
        message = `${config.patient.name}, it's ${time}. I can see your ${nextMed.time} medications are still in the organizer. It's been about ${minutesOverdue} minutes. Everything okay?`;
      }
    } else if (changes.pillStatusChanged && analysis.pillStatus === 'taken') {
      message = `Great! I see you took your medications. Thank you for staying on track, ${config.patient.name}.`;
    } else if (changes.newConcerns && analysis.concerns.length > 0) {
      message = `${config.patient.name}, I noticed ${analysis.concerns[0]}. Are you okay?`;
      this.emit('concern', { concerns: analysis.concerns, analysis });
    } else if (analysis.activity === 'not visible' && this.vision.lastActivityChange) {
      const minutesNotVisible = Math.round((now.getTime() - this.vision.lastActivityChange.getTime()) / 60000);
      if (minutesNotVisible > 60) {
        message = `${config.patient.name}, I haven't seen you in a while. Just checking in - everything alright?`;
      }
    }

    if (message) {
      if (recordMemory) {
        const session = conversationMemory.getOrCreateSession(config.patient.name);
        conversationMemory.addMessage(session.id, 'geni', message, { timeOfDay: getTimeOfDay() });
      }

      addActivity(`GENI vision: ${message}`, 'message');

      if (emitUpdates) {
        emitVisionUpdate({
          timestamp: analysis.timestamp,
          observation: analysis.observations,
          message,
          concerns: analysis.concerns,
        });
      }

      if (speak) emitSpeak(message);
    }

    this.vision.lastAnalysis = analysis;
    return message;
  }

  // -------------------------------------------------------------------------
  // Time-based cycle (ported from unified-monitoring.ts)
  // -------------------------------------------------------------------------

  async runCycle(): Promise<string> {
    const context = buildGENIContext();
    log.info('monitoring cycle started');

    const outputs: string[] = [];

    const conversation = await this.checkConversation(context);
    if (conversation) outputs.push(conversation);

    const medication = await this.checkMedication(context);
    if (medication) outputs.push(medication);

    const wellness = this.checkWellness(context);
    if (wellness) outputs.push(wellness);

    this.emit('cycle', { actions: outputs.length });
    log.info({ actions: outputs.length }, 'monitoring cycle complete');
    return outputs.length > 0 ? outputs.join('\n\n') : 'MONITORING_OK';
  }

  private async checkConversation(context: any): Promise<string | null> {
    const now = Date.now();
    if (this.lastConversationCheck && now - this.lastConversationCheck.getTime() < 30 * 60 * 1000) {
      return null;
    }
    this.lastConversationCheck = new Date();

    const { shouldStart, reason } = shouldInitiateConversation();
    if (!shouldStart) return null;

    const message = await generateConversationStarter(reason);
    const session = conversationMemory.getOrCreateSession(state.patient.name);
    conversationMemory.addMessage(session.id, 'geni', message, {
      timeOfDay: context.timeOfDay,
      isFollowUp: false,
    });
    conversationMemory.trackTopic(session.id, reason);

    emitActivity(addActivity(`GENI initiated: ${message}`, 'message'));
    emitSpeak(message);

    this.logEvent({
      timestamp: new Date(),
      type: 'conversation-initiated',
      summary: `Proactive conversation: ${reason}`,
      details: { message, reason },
      concernLevel: 'none',
      actionTaken: 'Initiated conversation',
      notifiedCaregiver: false,
    });

    return `💬 CONVERSATION INITIATED (${reason}):\n"${message}"`;
  }

  private async checkMedication(context: any): Promise<string | null> {
    const now = Date.now();
    if (this.lastPillCheck && now - this.lastPillCheck.getTime() < 30 * 60 * 1000) return null;

    const hour = context.timestamp.getHours();
    if (hour < 8 || hour > 22) return null;

    this.lastPillCheck = new Date();

    if (context.overdueMedications.length === 0) return null;

    const overdueMeds = context.overdueMedications.map((m: any) => `${m.name} (${m.time})`).join(', ');
    const medName = context.overdueMedications[0].name;
    const medTime = context.overdueMedications[0].time;
    const message = `${context.patientName}, I noticed you haven't taken your ${medName} yet. It was scheduled for ${medTime}. Everything okay?`;

    const session = conversationMemory.getOrCreateSession(state.patient.name);
    conversationMemory.addMessage(session.id, 'geni', message, {
      timeOfDay: context.timeOfDay,
      medicationsPending: context.overdueMedications.map((m: any) => m.name),
    });
    conversationMemory.trackMedicationDiscussion(session.id, medName);

    emitActivity(addActivity(`GENI reminder: ${message}`, 'medication'));
    emitSpeak(message);

    const minutesOverdue = context.overdueMedications.reduce((max: number, m: any) => {
      const [h, min] = m.time.split(':').map(Number);
      const medMinutes = h * 60 + min;
      const currentMinutes = context.timestamp.getHours() * 60 + context.timestamp.getMinutes();
      return Math.max(max, currentMinutes - medMinutes);
    }, 0);

    const concernLevel = minutesOverdue > 120 ? 'high' : minutesOverdue > 60 ? 'medium' : 'low';

    let notifiedCaregiver = false;
    if (concernLevel === 'high') {
      await notifyMedicationMissed({ name: medName, time: medTime });
      notifiedCaregiver = true;
    }

    this.logEvent({
      timestamp: new Date(),
      type: 'medication-alert',
      summary: `Overdue: ${overdueMeds}`,
      details: { medications: context.overdueMedications, minutesOverdue },
      concernLevel,
      actionTaken: 'Sent reminder to patient',
      notifiedCaregiver,
    });

    return `💊 MEDICATION ALERT (${concernLevel}):\n${overdueMeds}\n→ Reminded patient${notifiedCaregiver ? ' + notified caregiver' : ''}`;
  }

  private checkWellness(context: any): string | null {
    const now = Date.now();
    if (this.lastWellnessCheck && now - this.lastWellnessCheck.getTime() < 2 * 60 * 60 * 1000) return null;

    const hour = context.timestamp.getHours();
    if (hour < 9 || hour > 21) return null;

    this.lastWellnessCheck = new Date();

    if (context.activityLevel !== 'concerning') return null;

    const message = `${context.patientName}, I haven't heard from you in a while. How are you doing? Everything okay?`;
    const session = conversationMemory.getOrCreateSession(state.patient.name);
    conversationMemory.addMessage(session.id, 'geni', message, { timeOfDay: context.timeOfDay });
    conversationMemory.trackTopic(session.id, 'wellness-check');

    emitActivity(addActivity(`GENI wellness check: ${message}`, 'message'));
    emitSpeak(message);

    this.logEvent({
      timestamp: new Date(),
      type: 'wellness-check',
      summary: 'Low activity detected',
      details: {
        activityLevel: context.activityLevel,
        hoursSinceLastInteraction: context.hoursSinceLastInteraction,
      },
      concernLevel: 'medium',
      actionTaken: 'Initiated wellness check',
      notifiedCaregiver: false,
    });

    return `⚠️  WELLNESS CHECK (medium):\nLow activity detected\n→ Checked in with patient`;
  }

  // -------------------------------------------------------------------------
  // Shared state and introspection
  // -------------------------------------------------------------------------

  pause(): void {
    this.paused = true;
    log.info('monitoring paused (voice active)');
  }

  resume(): void {
    this.paused = false;
    log.info('monitoring resumed');
  }

  isPaused(): boolean {
    return this.paused;
  }

  getVisionState(): VisionState {
    return this.vision;
  }

  getRecentEvents(limit = 10): MonitoringEvent[] {
    return this.eventLog.slice(-limit);
  }

  getStatus(): string {
    const recentEvents = this.eventLog.slice(-5);
    return [
      'GENI MONITORING STATUS',
      '',
      'Last checks:',
      `  Medication: ${this.lastPillCheck?.toLocaleTimeString() || 'Never'}`,
      `  Conversation: ${this.lastConversationCheck?.toLocaleTimeString() || 'Never'}`,
      `  Wellness: ${this.lastWellnessCheck?.toLocaleTimeString() || 'Never'}`,
      '',
      'Recent events:',
      ...(recentEvents.length === 0
        ? ['  No events yet']
        : recentEvents.map(
            e => `  [${e.timestamp.toLocaleTimeString()}] ${e.type} (${e.concernLevel}): ${e.summary}`
          )),
    ].join('\n');
  }

  private logEvent(event: MonitoringEvent): void {
    this.eventLog.push(event);
    if (this.eventLog.length > 100) {
      this.eventLog = this.eventLog.slice(-100);
    }
  }

  private isPillsOverdue(): boolean {
    if (!this.vision.pillsPresentSince) return false;
    return (Date.now() - this.vision.pillsPresentSince.getTime()) / 60000 >= 30;
  }

  private getMedicationScheduleContext(): string {
    const hour = new Date().getHours();
    const schedule = state.todaysMedications || [];
    const upcoming = schedule.filter((med: any) => {
      const [medHour] = med.time.split(':').map(Number);
      return medHour >= hour;
    });
    return upcoming.length > 0
      ? upcoming.map((m: any) => `${m.name} at ${m.time}`).join(', ')
      : 'No upcoming medications today';
  }

  private getRecentMedication() {
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    const schedule = state.todaysMedications || [];

    return schedule
      .map((med: any) => {
        const [medHour, medMinute] = med.time.split(':').map(Number);
        const medMinutes = medHour * 60 + medMinute;
        return { ...med, diff: currentMinutes - medMinutes };
      })
      .filter((m: any) => m.diff >= 0 && m.diff <= 120)
      .sort((a: any, b: any) => a.diff - b.diff)[0];
  }
}

export const monitoring = new MonitoringCore();
