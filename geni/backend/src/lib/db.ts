/**
 * SQLite storage for GENI (better-sqlite3, WAL mode).
 *
 * Replaces the JSON-file persistence that capped pill history at 100 records
 * and rewrote whole files on every message. On first run, existing JSON data
 * (data/pill_check_history.json and data/conversations/*) is imported so
 * nothing is lost.
 */

import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { moduleLogger } from './logger';

const log = moduleLogger('db');

const dataDir = path.join(__dirname, '../../data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

export const db = new Database(path.join(dataDir, 'geni.db'));
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS pill_checks (
    id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'taken', 'unclear')),
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    observations TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('vision', 'yolo'))
  );
  CREATE INDEX IF NOT EXISTS idx_pill_checks_timestamp ON pill_checks(timestamp DESC);

  CREATE TABLE IF NOT EXISTS conversation_sessions (
    id TEXT PRIMARY KEY,
    patient_name TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    last_message_at INTEGER NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    voice_note_count INTEGER NOT NULL DEFAULT 0,
    topics TEXT NOT NULL DEFAULT '[]',
    medications_discussed TEXT NOT NULL DEFAULT '[]',
    concern_level TEXT NOT NULL DEFAULT 'none'
  );
  CREATE INDEX IF NOT EXISTS idx_sessions_last_message
    ON conversation_sessions(last_message_at DESC);

  CREATE TABLE IF NOT EXISTS conversation_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES conversation_sessions(id),
    timestamp INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'geni')),
    type TEXT NOT NULL CHECK (type IN ('text', 'voice', 'system')),
    content TEXT NOT NULL,
    metadata TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_messages_session
    ON conversation_messages(session_id, timestamp);
`);

// ---------------------------------------------------------------------------
// One-time import of legacy JSON data
// ---------------------------------------------------------------------------

function importLegacyJson(): void {
  // Pill checks
  const pillJson = path.join(dataDir, 'pill_check_history.json');
  const pillCount = (db.prepare('SELECT COUNT(*) AS n FROM pill_checks').get() as { n: number }).n;
  if (pillCount === 0 && fs.existsSync(pillJson)) {
    try {
      const legacy = JSON.parse(fs.readFileSync(pillJson, 'utf-8'));
      const insert = db.prepare(`
        INSERT OR IGNORE INTO pill_checks (id, timestamp, date, time, status, confidence, observations, method)
        VALUES (@id, @timestamp, @date, @time, @status, @confidence, @observations, @method)
      `);
      const rows = Array.isArray(legacy.records) ? legacy.records : [];
      db.transaction(() => {
        for (const r of rows) insert.run({ method: 'vision', ...r });
      })();
      log.info({ imported: rows.length }, 'imported legacy pill check history');
    } catch (error) {
      log.error({ err: error }, 'failed to import legacy pill checks');
    }
  }

  // Conversations
  const convDir = path.join(dataDir, 'conversations');
  const sessionsJson = path.join(convDir, 'sessions.json');
  const sessionCount = (db.prepare('SELECT COUNT(*) AS n FROM conversation_sessions').get() as { n: number }).n;
  if (sessionCount === 0 && fs.existsSync(sessionsJson)) {
    try {
      const sessions = JSON.parse(fs.readFileSync(sessionsJson, 'utf-8'));
      const insertSession = db.prepare(`
        INSERT OR IGNORE INTO conversation_sessions
          (id, patient_name, started_at, last_message_at, message_count, voice_note_count, topics, medications_discussed, concern_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      const insertMessage = db.prepare(`
        INSERT OR IGNORE INTO conversation_messages (id, session_id, timestamp, role, type, content, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      let messageTotal = 0;
      db.transaction(() => {
        for (const s of sessions) {
          insertSession.run(
            s.id,
            s.patientName,
            new Date(s.startedAt).getTime(),
            new Date(s.lastMessageAt).getTime(),
            s.messageCount || 0,
            s.voiceNoteCount || 0,
            JSON.stringify(s.topics || []),
            JSON.stringify(s.medicationsDiscussed || []),
            s.concernLevel || 'none'
          );

          const messagesFile = path.join(convDir, `${s.id}.json`);
          if (fs.existsSync(messagesFile)) {
            try {
              const messages = JSON.parse(fs.readFileSync(messagesFile, 'utf-8'));
              for (const m of messages) {
                insertMessage.run(
                  m.id,
                  s.id,
                  new Date(m.timestamp).getTime(),
                  m.role,
                  m.type || 'text',
                  m.content,
                  m.metadata ? JSON.stringify(m.metadata) : null
                );
                messageTotal++;
              }
            } catch {
              // Skip unparseable message file; session header is still imported
            }
          }
        }
      })();
      log.info({ sessions: sessions.length, messages: messageTotal }, 'imported legacy conversations');
    } catch (error) {
      log.error({ err: error }, 'failed to import legacy conversations');
    }
  }
}

importLegacyJson();
