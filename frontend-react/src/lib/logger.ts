/**
 * Structured logging for NoobBook frontend using pino.
 *
 * Usage:
 *   import { createLogger } from '@/lib/logger';
 *   const log = createLogger('my-module');
 *   log.info('hello');
 *   log.error({ err }, 'something failed');
 */
import pino from 'pino';

const rootLogger = pino({
  level: import.meta.env.DEV ? 'debug' : 'warn',
  browser: { asObject: false },
});

/** Create a child logger tagged with a module name. */
export function createLogger(module: string) {
  return rootLogger.child({ module });
}
