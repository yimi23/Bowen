import { Request, Response, NextFunction } from 'express';
import { logger } from '../lib/logger';

// Global safety net. Routes still handle their own expected failures; this
// catches everything that escapes so no error dies silently with a bare 500.
export function errorHandler(err: Error, req: Request, res: Response, _next: NextFunction) {
  const log = req.log ?? logger;
  log.error({ err, requestId: req.id }, 'unhandled route error');

  if (res.headersSent) return;
  res.status(500).json({
    error: 'Internal server error',
    requestId: req.id,
  });
}
