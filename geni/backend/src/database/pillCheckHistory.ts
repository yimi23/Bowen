/**
 * Pill check history — SQLite-backed.
 * Same public API as the old JSON implementation; storage is now durable,
 * indexed, and no longer capped at 100 records.
 */

import { db } from '../lib/db';
import { moduleLogger } from '../lib/logger';
import type { MedicationHistory } from '../models/Medication';

const log = moduleLogger('pill-history');

export interface PillCheckRecord {
  id: string;
  timestamp: number;
  date: string;
  time: string;
  status: 'present' | 'taken' | 'unclear';
  confidence: 'high' | 'medium' | 'low';
  observations: string;
  method: 'vision' | 'yolo';
}

const insertStmt = db.prepare(`
  INSERT INTO pill_checks (id, timestamp, date, time, status, confidence, observations, method)
  VALUES (@id, @timestamp, @date, @time, @status, @confidence, @observations, @method)
`);

const recentStmt = db.prepare(`
  SELECT * FROM pill_checks ORDER BY timestamp DESC LIMIT ?
`);

const lastStmt = db.prepare(`
  SELECT * FROM pill_checks ORDER BY timestamp DESC LIMIT 1
`);

const todayStmt = db.prepare(`
  SELECT * FROM pill_checks WHERE date = ? ORDER BY timestamp DESC
`);

const clearOldStmt = db.prepare(`
  DELETE FROM pill_checks WHERE timestamp <= ?
`);

export function savePillCheck(
  status: 'present' | 'taken' | 'unclear',
  confidence: 'high' | 'medium' | 'low',
  observations: string,
  method: 'vision' | 'yolo' = 'vision'
): PillCheckRecord {
  const now = new Date();
  const record: PillCheckRecord = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: Date.now(),
    date: now.toLocaleDateString('en-US'),
    time: now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }),
    status,
    confidence,
    observations,
    method,
  };

  insertStmt.run(record);
  log.debug({ id: record.id, status }, 'pill check saved');
  return record;
}

export function getPillCheckHistory(limit: number = 20): PillCheckRecord[] {
  return recentStmt.all(limit) as PillCheckRecord[];
}

export function getLastPillCheck(): PillCheckRecord | null {
  return (lastStmt.get() as PillCheckRecord | undefined) || null;
}

export function getTodaysPillChecks(): PillCheckRecord[] {
  const today = new Date().toLocaleDateString('en-US');
  return todayStmt.all(today) as PillCheckRecord[];
}

/** Clear records older than 30 days. */
export function clearOldRecords(): number {
  const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
  const result = clearOldStmt.run(thirtyDaysAgo);
  log.info({ cleared: result.changes }, 'cleared old pill check records');
  return result.changes;
}

const dayRangeStmt = db.prepare(`
  SELECT * FROM pill_checks WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC
`);

/**
 * Medication history derived from REAL pill-check records (last `days` days)
 * — replaces the hardcoded demo history that previously lived in state.ts.
 */
export function getDerivedMedicationHistory(days: number = 7): MedicationHistory[] {
  const history: MedicationHistory[] = [];
  const now = new Date();

  for (let i = days - 1; i >= 0; i--) {
    const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    const dayEnd = new Date(dayStart.getTime() + 24 * 60 * 60 * 1000);
    const records = dayRangeStmt.all(dayStart.getTime(), dayEnd.getTime()) as PillCheckRecord[];

    const takenCount = records.filter(r => r.status === 'taken').length;
    const presentCount = records.filter(r => r.status === 'present').length;

    let status: MedicationHistory['status'];
    if (i === 0) {
      status = 'today';
    } else if (records.length === 0) {
      status = 'none';
    } else if (takenCount > 0 && presentCount === 0) {
      status = 'all-taken';
    } else if (takenCount > 0) {
      status = 'partial';
    } else {
      status = 'none';
    }

    history.push({
      date: dayStart.toISOString().slice(0, 10),
      day: dayStart.toLocaleDateString('en-US', { weekday: 'short' }),
      dayNumber: dayStart.getDate(),
      status,
      details: records.map(r => ({
        time: r.time,
        medication: `Pill check (${r.method})`,
        status: r.status === 'taken' ? ('taken' as const) : ('missed' as const),
      })),
    });
  }

  return history;
}
