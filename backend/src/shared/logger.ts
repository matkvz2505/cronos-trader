import pino from 'pino';

import { emProducao, env } from '../config/env.js';

/**
 * Logger com redaction obrigatória.
 *
 * Os campos abaixo nunca podem chegar ao log, nem em `debug`: senha em claro num log de
 * requisição é vazamento de credencial com aparência de detalhe de implementação.
 */
export const logger = pino({
  level: env.LOG_NIVEL,
  redact: {
    paths: [
      'req.headers.authorization',
      'req.headers.cookie',
      '*.senha',
      '*.senhaHash',
      '*.token',
      '*.refreshToken',
      'body.senha',
      'body.token',
    ],
    censor: '[redigido]',
  },
  transport: emProducao
    ? undefined
    : {
        target: 'pino-pretty',
        options: { colorize: true, translateTime: 'HH:MM:ss', ignore: 'pid,hostname' },
      },
});
