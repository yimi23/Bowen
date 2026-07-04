import { randomUUID } from 'crypto';
import { Request, Response, NextFunction } from 'express';
import { logger } from '../lib/logger';

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      id: string;
      log: ReturnType<typeof logger.child>;
    }
  }
}

export function requestContext(req: Request, res: Response, next: NextFunction) {
  req.id = randomUUID();
  req.log = logger.child({ requestId: req.id, method: req.method, path: req.path });
  res.setHeader('x-request-id', req.id);

  const start = Date.now();
  res.on('finish', () => {
    const level = res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'debug';
    req.log[level]({ status: res.statusCode, durationMs: Date.now() - start }, 'request completed');
  });

  next();
}
