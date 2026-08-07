/**
 * Configuração validada na borda.
 *
 * Regra do repositório: nunca use `process.env` fora deste arquivo. O motivo é
 * operacional — uma variável faltando tem que derrubar o processo no boot, com mensagem
 * clara, e não virar `undefined` que só explode três horas depois numa rota específica.
 */
import 'dotenv/config';
import { z } from 'zod';

const esquema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().default(1840),

  DATABASE_URL: z.string().url('DATABASE_URL precisa ser uma URL postgres válida'),

  /** Segredo de assinatura do access token. Em produção, obrigatoriamente longo. */
  JWT_SECRET: z.string().min(32, 'JWT_SECRET precisa de ao menos 32 caracteres'),
  JWT_EXPIRA_EM: z.string().default('15m'),
  REFRESH_EXPIRA_DIAS: z.coerce.number().int().positive().default(30),

  /** Serviço de IA em Python — onde o motor de padrões roda de fato. */
  IA_URL: z.string().url().default('http://localhost:1841'),
  IA_TIMEOUT_MS: z.coerce.number().int().positive().default(120_000),

  CORS_ORIGENS: z
    .string()
    .default('http://localhost:5180')
    .transform((valor) => valor.split(',').map((o) => o.trim()).filter(Boolean)),

  LOG_NIVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),

  /** Intervalo do polling que empurra sinais novos pelo WebSocket. */
  WS_INTERVALO_MS: z.coerce.number().int().positive().default(5_000),
});

const resultado = esquema.safeParse(process.env);

if (!resultado.success) {
  const problemas = resultado.error.issues
    .map((i) => `  - ${i.path.join('.')}: ${i.message}`)
    .join('\n');
  console.error(`\nConfiguração inválida. Corrija o .env:\n${problemas}\n`);
  process.exit(1);
}

export const env = resultado.data;

export const emProducao = env.NODE_ENV === 'production';

if (emProducao && env.JWT_SECRET.includes('desenvolvimento')) {
  console.error('JWT_SECRET ainda é o valor de exemplo. Troque antes de subir em produção.');
  process.exit(1);
}
