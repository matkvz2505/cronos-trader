import { Router } from 'express';
import { z } from 'zod';

import { assincrono, autenticar, validarBody } from '../../middleware/index.js';
import { ia } from '../../shared/ia.js';
import { numero, prisma } from '../../shared/prisma.js';
import { ativoSchema, timeframeSchema } from '../sinais/sinais.schemas.js';

export const backtestRoutes = Router();

backtestRoutes.use(autenticar);

const rodarSchema = z
  .object({
    ativo: ativoSchema,
    timeframe: timeframeSchema.default('M5'),
    capital: z.coerce.number().positive().max(100_000_000).default(20_000),
    modo: z.enum(['backtest', 'walkforward']).default('walkforward'),
    janelas: z.coerce.number().int().min(2).max(12).default(4),
  })
  .strict();

/**
 * Roda a simulação no motor. Pode demorar — o timeout do cliente de IA é generoso
 * (`IA_TIMEOUT_MS`, 2min por padrão) porque uma série de 50 mil candles não termina em
 * segundos.
 *
 * `walkforward` é o default de propósito: `backtest` puro calibra e mede na mesma série,
 * o que é memorização e não evidência.
 */
backtestRoutes.post(
  '/',
  validarBody(rodarSchema),
  assincrono(async (req, res) => {
    res.json(await ia.backtest(req.body));
  }),
);

backtestRoutes.get(
  '/execucoes',
  assincrono(async (req, res) => {
    const ativo = typeof req.query.ativo === 'string' ? req.query.ativo : undefined;
    const itens = await prisma.execucaoBacktest.findMany({
      where: ativo ? { ativo } : {},
      orderBy: { criadoEm: 'desc' },
      take: 30,
    });
    res.json(
      itens.map((e) => ({
        ...e,
        capital: numero(e.capital),
        taxaAcerto: numero(e.taxaAcerto),
        expectanciaR: numero(e.expectanciaR),
        resultadoReais: numero(e.resultadoReais),
        rebaixamentoMax: numero(e.rebaixamentoMax),
      })),
    );
  }),
);

backtestRoutes.get(
  '/execucoes/:id',
  assincrono(async (req, res) => {
    const execucao = await prisma.execucaoBacktest.findUnique({ where: { id: req.params.id! } });
    if (!execucao) {
      res.status(404).json({ erro: 'Execução não encontrada', codigo: 'NAO_ENCONTRADO' });
      return;
    }
    res.json({
      ...execucao,
      capital: numero(execucao.capital),
      taxaAcerto: numero(execucao.taxaAcerto),
      expectanciaR: numero(execucao.expectanciaR),
      resultadoReais: numero(execucao.resultadoReais),
      rebaixamentoMax: numero(execucao.rebaixamentoMax),
    });
  }),
);
