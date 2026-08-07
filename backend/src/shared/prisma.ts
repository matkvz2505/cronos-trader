import { PrismaClient } from '@prisma/client';

import { emProducao } from '../config/env.js';
import { logger } from './logger.js';

/**
 * Cliente Prisma único do processo.
 *
 * Em dev, `tsx watch` recarrega o módulo a cada save. Sem guardar a instância no
 * `globalThis`, cada reload abriria um novo pool e o Postgres esgotaria as conexões
 * depois de algumas dezenas de edições.
 */
const global = globalThis as unknown as { prisma?: PrismaClient };

export const prisma =
  global.prisma ??
  new PrismaClient({
    log: emProducao ? ['error'] : ['warn', 'error'],
  });

if (!emProducao) global.prisma = prisma;

export async function encerrarPrisma(): Promise<void> {
  await prisma.$disconnect();
  logger.info('prisma desconectado');
}

/** Prisma devolve `Decimal`; a API devolve `number`. Converte na borda de saída. */
export function numero(valor: unknown): number {
  if (valor === null || valor === undefined) return 0;
  if (typeof valor === 'number') return valor;
  return Number(valor.toString());
}
