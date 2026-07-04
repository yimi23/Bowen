import { Request, Response, NextFunction } from 'express';
import { config } from '../config';
import { logger } from '../lib/logger';

let warnedNoKey = false;

/**
 * Shared-secret API auth. When GENI_API_KEY is set, every /api request must
 * carry it via the x-api-key header (or Authorization: Bearer). When unset
 * in development the API stays open for local work, with a startup warning.
 * Production refuses to start without a key (enforced in config.ts).
 *
 * Inbound webhook paths (Twilio calls us — it can't know our key) are
 * exempted at mount time in index.ts, not here.
 */
export function requireApiKey(req: Request, res: Response, next: NextFunction) {
  if (!config.security.apiKey) {
    if (!warnedNoKey) {
      warnedNoKey = true;
      logger.warn('GENI_API_KEY not set — API is OPEN. Fine for local dev, never for deployment.');
    }
    return next();
  }

  const provided =
    req.header('x-api-key') ||
    (req.header('authorization')?.startsWith('Bearer ')
      ? req.header('authorization')!.slice(7)
      : undefined);

  if (provided === config.security.apiKey) {
    return next();
  }

  (req.log ?? logger).warn({ path: req.path, ip: req.ip }, 'rejected unauthenticated request');
  res.status(401).json({ error: 'Unauthorized' });
}
