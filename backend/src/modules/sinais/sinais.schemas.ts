import { z } from 'zod';

/** Escopo fechado do produto. Validado na borda para nunca chegar ao motor. */
export const ativoSchema = z.enum(['WIN', 'WDO']);
export const timeframeSchema = z.enum(['M5', 'M15', 'M30', 'H1', 'D1']);

export const listarSinaisSchema = z.object({
  ativo: ativoSchema.optional(),
  timeframe: timeframeSchema.optional(),
  status: z.enum(['ABERTO', 'ACIONADO', 'ALVO', 'STOP', 'EXPIRADO', 'CANCELADO']).optional(),
  direcao: z.enum(['ALTA', 'BAIXA']).optional(),
  /** Score mínimo — permite à tela filtrar o ruído sem refazer o cálculo. */
  scoreMinimo: z.coerce.number().min(0).max(1).optional(),
  desde: z.coerce.date().optional(),
  limite: z.coerce.number().int().min(1).max(200).default(50),
  pagina: z.coerce.number().int().min(1).default(1),
});

export const atualizarStatusSchema = z
  .object({
    status: z.enum(['ACIONADO', 'ALVO', 'STOP', 'EXPIRADO', 'CANCELADO']),
    precoSaida: z.coerce.number().optional(),
  })
  .strict();

export const anotarSchema = z
  .object({
    operou: z.boolean().default(false),
    texto: z.string().trim().max(2000).optional(),
  })
  .strict();

export const analisarSchema = z
  .object({
    ativo: ativoSchema,
    timeframe: timeframeSchema.default('M5'),
  })
  .strict();

export type ListarSinaisQuery = z.infer<typeof listarSinaisSchema>;
