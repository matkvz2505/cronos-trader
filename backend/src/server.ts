import { createServer } from 'node:http';

import { criarApp } from './app.js';
import { env } from './config/env.js';
import { montarWebSocket } from './realtime/ws.js';
import { encerrarPrisma } from './shared/prisma.js';
import { logger } from './shared/logger.js';

const servidor = createServer(criarApp());
const encerrarWs = montarWebSocket(servidor);

servidor.listen(env.PORT, () => {
  logger.info(
    { porta: env.PORT, ia: env.IA_URL, ambiente: env.NODE_ENV },
    `cronos-trader-backend no ar em http://localhost:${env.PORT}/api/v1`,
  );
});

/**
 * Encerramento gracioso: para de aceitar conexão nova, fecha WebSocket e devolve o pool
 * do Prisma. Sem isto, um restart em dev deixa conexões penduradas no Postgres até o
 * timeout do servidor.
 */
async function encerrar(sinal: string): Promise<void> {
  logger.info({ sinal }, 'encerrando');
  encerrarWs();
  servidor.close();
  await encerrarPrisma();
  process.exit(0);
}

process.on('SIGINT', () => void encerrar('SIGINT'));
process.on('SIGTERM', () => void encerrar('SIGTERM'));

process.on('unhandledRejection', (motivo) => {
  logger.error({ err: motivo }, 'promise rejeitada sem tratamento');
});
