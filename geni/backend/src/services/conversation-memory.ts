/**
 * GENI Conversation Memory — SQLite-backed.
 * Same public API as the old JSON-file implementation. Every message is a
 * single indexed insert instead of rewriting a whole session file.
 */

import { db } from '../lib/db';
import { moduleLogger } from '../lib/logger';
import { state } from '../state';

const log = moduleLogger('conversation-memory');

export interface ConversationMessage {
  id: string;
  sessionId: string;
  timestamp: Date;
  role: 'user' | 'geni';
  type: 'text' | 'voice' | 'system';
  content: string;
  metadata?: {
    voiceNotePath?: string;
    voiceDuration?: number;
    transcription?: string;
    sentiment?: 'positive' | 'neutral' | 'concerned' | 'distressed';
    timeOfDay?: string;
    medicationsPending?: string[];
    visionSnapshot?: string;
    isFollowUp?: boolean;
    respondingTo?: string;
  };
}

export interface ConversationSession {
  id: string;
  patientName: string;
  startedAt: Date;
  lastMessageAt: Date;
  messageCount: number;
  voiceNoteCount: number;
  topics: string[];
  medicationsDiscussed: string[];
  concernLevel: 'none' | 'low' | 'medium' | 'high';
}

interface SessionRow {
  id: string;
  patient_name: string;
  started_at: number;
  last_message_at: number;
  message_count: number;
  voice_note_count: number;
  topics: string;
  medications_discussed: string;
  concern_level: string;
}

interface MessageRow {
  id: string;
  session_id: string;
  timestamp: number;
  role: string;
  type: string;
  content: string;
  metadata: string | null;
}

function rowToSession(row: SessionRow): ConversationSession {
  return {
    id: row.id,
    patientName: row.patient_name,
    startedAt: new Date(row.started_at),
    lastMessageAt: new Date(row.last_message_at),
    messageCount: row.message_count,
    voiceNoteCount: row.voice_note_count,
    topics: JSON.parse(row.topics),
    medicationsDiscussed: JSON.parse(row.medications_discussed),
    concernLevel: row.concern_level as ConversationSession['concernLevel'],
  };
}

function rowToMessage(row: MessageRow): ConversationMessage {
  return {
    id: row.id,
    sessionId: row.session_id,
    timestamp: new Date(row.timestamp),
    role: row.role as ConversationMessage['role'],
    type: row.type as ConversationMessage['type'],
    content: row.content,
    metadata: row.metadata ? JSON.parse(row.metadata) : undefined,
  };
}

const getSessionStmt = db.prepare('SELECT * FROM conversation_sessions WHERE id = ?');
const insertSessionStmt = db.prepare(`
  INSERT INTO conversation_sessions
    (id, patient_name, started_at, last_message_at, message_count, voice_note_count, topics, medications_discussed, concern_level)
  VALUES (?, ?, ?, ?, 0, 0, '[]', '[]', 'none')
`);
const insertMessageStmt = db.prepare(`
  INSERT INTO conversation_messages (id, session_id, timestamp, role, type, content, metadata)
  VALUES (?, ?, ?, ?, ?, ?, ?)
`);
const recentMessagesStmt = db.prepare(`
  SELECT * FROM (
    SELECT * FROM conversation_messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?
  ) ORDER BY timestamp ASC
`);
const updateSessionOnMessageStmt = db.prepare(`
  UPDATE conversation_sessions
  SET last_message_at = ?,
      message_count = message_count + 1,
      voice_note_count = voice_note_count + ?
  WHERE id = ?
`);
const updateTopicsStmt = db.prepare('UPDATE conversation_sessions SET topics = ? WHERE id = ?');
const updateMedsStmt = db.prepare('UPDATE conversation_sessions SET medications_discussed = ? WHERE id = ?');
const updateConcernStmt = db.prepare('UPDATE conversation_sessions SET concern_level = ? WHERE id = ?');
const activeSessionsStmt = db.prepare(`
  SELECT * FROM conversation_sessions WHERE last_message_at > ? ORDER BY last_message_at DESC
`);

class ConversationMemory {
  getOrCreateSession(patientName: string, sessionId?: string): ConversationSession {
    const id = sessionId || `session-${patientName.toLowerCase().replace(/\s+/g, '-')}-${Date.now()}`;

    const existing = getSessionStmt.get(id) as SessionRow | undefined;
    if (existing) return rowToSession(existing);

    const now = Date.now();
    insertSessionStmt.run(id, patientName, now, now);
    return rowToSession(getSessionStmt.get(id) as SessionRow);
  }

  addMessage(
    sessionId: string,
    role: 'user' | 'geni',
    content: string,
    metadata?: ConversationMessage['metadata']
  ): ConversationMessage {
    const sessionRow = getSessionStmt.get(sessionId) as SessionRow | undefined;
    if (!sessionRow) {
      throw new Error(`Session ${sessionId} not found`);
    }

    const message: ConversationMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      sessionId,
      timestamp: new Date(),
      role,
      type: metadata?.voiceNotePath ? 'voice' : 'text',
      content,
      metadata,
    };

    insertMessageStmt.run(
      message.id,
      sessionId,
      message.timestamp.getTime(),
      role,
      message.type,
      content,
      metadata ? JSON.stringify(metadata) : null
    );
    updateSessionOnMessageStmt.run(message.timestamp.getTime(), message.type === 'voice' ? 1 : 0, sessionId);

    // Track medications mentioned by name (from today's actual schedule,
    // not a hardcoded list)
    const knownMeds = (state.todaysMedications || []).map((m: any) => m.name);
    const discussed: string[] = JSON.parse(sessionRow.medications_discussed);
    let medsChanged = false;
    for (const med of knownMeds) {
      if (content.toLowerCase().includes(med.toLowerCase()) && !discussed.includes(med)) {
        discussed.push(med);
        medsChanged = true;
      }
    }
    if (medsChanged) {
      updateMedsStmt.run(JSON.stringify(discussed), sessionId);
    }

    log.debug({ role, type: message.type, sessionId }, content.substring(0, 60));
    return message;
  }

  getRecentContext(sessionId: string, limit: number = 10): string {
    const rows = recentMessagesStmt.all(sessionId, limit) as MessageRow[];
    return rows
      .map(row => {
        const role = row.role === 'user' ? 'Patient' : 'GENI';
        const type = row.type === 'voice' ? ' (voice)' : '';
        return `${role}${type}: ${row.content}`;
      })
      .join('\n');
  }

  getHistory(sessionId: string, limit: number = 10): { role: 'user' | 'assistant'; text: string }[] {
    const rows = recentMessagesStmt.all(sessionId, limit) as MessageRow[];
    return rows.map(row => ({
      role: row.role === 'user' ? ('user' as const) : ('assistant' as const),
      text: row.content,
    }));
  }

  getSessionSummary(sessionId: string): string {
    const row = getSessionStmt.get(sessionId) as SessionRow | undefined;
    if (!row) return 'No session found';
    const session = rowToSession(row);

    const duration = Date.now() - session.startedAt.getTime();
    const hours = Math.floor(duration / (1000 * 60 * 60));
    const minutes = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60));

    return `
Session ${sessionId}
Started: ${session.startedAt.toLocaleString()}
Messages: ${session.messageCount} (${session.voiceNoteCount} voice notes)
Duration: ${hours}h ${minutes}m
Topics: ${session.topics.join(', ') || 'General conversation'}
Medications discussed: ${session.medicationsDiscussed.join(', ') || 'None'}
Last activity: ${session.lastMessageAt.toLocaleString()}
`.trim();
  }

  trackTopic(sessionId: string, topic: string): void {
    const row = getSessionStmt.get(sessionId) as SessionRow | undefined;
    if (!row) return;
    const topics: string[] = JSON.parse(row.topics);
    if (!topics.includes(topic)) {
      topics.push(topic);
      updateTopicsStmt.run(JSON.stringify(topics), sessionId);
    }
  }

  trackMedicationDiscussion(sessionId: string, medication: string): void {
    const row = getSessionStmt.get(sessionId) as SessionRow | undefined;
    if (!row) return;
    const meds: string[] = JSON.parse(row.medications_discussed);
    if (!meds.includes(medication)) {
      meds.push(medication);
      updateMedsStmt.run(JSON.stringify(meds), sessionId);
    }
  }

  updateConcernLevel(sessionId: string, level: ConversationSession['concernLevel']): void {
    updateConcernStmt.run(level, sessionId);
  }

  getActiveSessions(): ConversationSession[] {
    const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
    const rows = activeSessionsStmt.all(oneDayAgo) as SessionRow[];
    return rows.map(rowToSession);
  }

  buildConversationState(sessionId: string) {
    const row = getSessionStmt.get(sessionId) as SessionRow | undefined;
    const session = row ? rowToSession(row) : undefined;
    const recentMessages = (recentMessagesStmt.all(sessionId, 10) as MessageRow[]).map(rowToMessage);

    return {
      session,
      recentMessages,
      context: this.getRecentContext(sessionId, 10),
      medicationsDiscussed: session?.medicationsDiscussed || [],
      topics: session?.topics || [],
      hasVoiceNotes: (session?.voiceNoteCount || 0) > 0,
    };
  }
}

export const conversationMemory = new ConversationMemory();
