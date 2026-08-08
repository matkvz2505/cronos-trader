/**
 * Candles, catálogo de padrões e saúde do motor.
 *
 * Nota de convenção: `auth` tem controller separado porque há tradução HTTP de verdade
 * (status 201, user-agent, corpo do refresh). Aqui os handlers são de uma linha — um
 * arquivo a mais só acrescentaria indireção sem separar nada.
 */
import { Router } from 'express';
import { z } from 'zod';

import { assincrono, autenticar, validarQuery } from '../../middleware/index.js';
import { ia } from '../../shared/ia.js';
import { numero, prisma } from '../../shared/prisma.js';
import { ativoSchema, timeframeSchema } from '../sinais/sinais.schemas.js';

export const mercadoRoutes = Router();

const candlesQuery = z.object({
  ativo: ativoSchema.default('WIN'),
  timeframe: timeframeSchema.default('M5'),
  // 1500 é o teto porque o lightweight-charts fica pesado acima disso e ninguém lê
  // mais que isso numa tela.
  limite: z.coerce.number().int().min(10).max(1500).default(500),
  ate: z.coerce.date().optional(),
});

mercadoRoutes.get(
  '/candles',
  autenticar,
  validarQuery(candlesQuery),
  assincrono(async (req, res) => {
    const { ativo, timeframe, limite, ate } = req.query as unknown as z.infer<typeof candlesQuery>;

    const candles = await prisma.candle.findMany({
      where: { ativo, timeframe, ...(ate ? { ts: { lte: ate } } : {}) },
      orderBy: { ts: 'desc' },
      take: limite,
    });

    // O banco devolve do mais novo para o mais velho (índice desc); o gráfico precisa
    // do inverso.
    res.json({
      ativo,
      timeframe,
      candles: candles.reverse().map((c) => ({
        ts: c.ts.toISOString(),
        abertura: numero(c.abertura),
        maxima: numero(c.maxima),
        minima: numero(c.minima),
        fechamento: numero(c.fechamento),
        volume: numero(c.volume),
      })),
    });
  }),
);

/** Detecções para marcar no gráfico — inclui as que não viraram sinal. */
mercadoRoutes.get(
  '/deteccoes',
  autenticar,
  validarQuery(candlesQuery),
  assincrono(async (req, res) => {
    const { ativo, timeframe, limite } = req.query as unknown as z.infer<typeof candlesQuery>;
    const itens = await prisma.deteccao.findMany({
      where: { ativo, timeframe },
      orderBy: { ts: 'desc' },
      take: limite,
    });
    res.json(
      itens.reverse().map((d) => ({
        ts: d.ts.toISOString(),
        padraoId: d.padraoId,
        padraoNome: d.padraoNome,
        direcao: d.direcao,
        forca: numero(d.forca),
        scoreBruto: numero(d.scoreBruto),
      })),
    );
  }),
);

/** Catálogo dos padrões. Vem do motor — o backend não mantém cópia. */
mercadoRoutes.get(
  '/padroes',
  autenticar,
  assincrono(async (_req, res) => {
    res.json(await ia.catalogo());
  }),
);

/** Fechamento de dia, semana ou mês — e a preparação do próximo pregão. */
mercadoRoutes.get(
  '/diario',
  autenticar,
  validarQuery(
    z.object({
      ativo: ativoSchema,
      periodo: z.enum(['dia', 'semana', 'mes']).default('dia'),
    }),
  ),
  assincrono(async (req, res) => {
    const { ativo, periodo } = req.query as unknown as {
      ativo: string;
      periodo: 'dia' | 'semana' | 'mes';
    };
    res.json(await ia.diario(ativo, periodo));
  }),
);

/**
 * O raciocínio ao vivo do motor. Alimenta a Sala de Operações.
 *
 * Usa o capital do usuário logado — o mesmo setup gera número de contratos diferente
 * para cada conta, e mostrar o de outra pessoa seria pior que não mostrar.
 */
mercadoRoutes.get(
  '/raciocinio',
  autenticar,
  validarQuery(z.object({ ativo: ativoSchema })),
  assincrono(async (req, res) => {
    const usuario = await prisma.usuario.findUnique({
      where: { id: req.usuario!.sub },
      select: { capital: true },
    });
    const { ativo } = req.query as unknown as { ativo: string };
    res.json(await ia.raciocinio(ativo, Number(usuario?.capital ?? 20_000)));
  }),
);

const pregaoQuery = z.object({
  ativo: ativoSchema.default('WIN'),
  // `AAAA-MM-DD`. Não é `coerce.date()` de propósito: o `ts` do candle é relógio de parede
  // do pregão, e converter para Date aqui reintroduziria fuso numa data que não tem.
  dia: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'use AAAA-MM-DD')
    .optional(),
});

/**
 * O extrato do dia: cada entrada, na ordem, com o que aconteceu depois dela.
 *
 * Existe separado de `/diario` porque as duas perguntas são diferentes. O diário fecha o
 * período em placar; isto conta a sequência. Quem senta na mesa às 15h não quer saber a
 * expectância do dia — quer ver as duas entradas que apareceram às 10h e por quê.
 */
mercadoRoutes.get(
  '/pregao',
  autenticar,
  validarQuery(pregaoQuery),
  assincrono(async (req, res) => {
    const { ativo, dia } = req.query as unknown as z.infer<typeof pregaoQuery>;
    res.json(await ia.pregao(ativo, dia));
  }),
);

/** Estrutura gráfica para anotar o gráfico: canal, pivôs, rompimentos, zonas. */
mercadoRoutes.get(
  '/estrutura',
  autenticar,
  validarQuery(candlesQuery),
  assincrono(async (req, res) => {
    const { ativo, timeframe, limite } = req.query as unknown as z.infer<typeof candlesQuery>;
    res.json(await ia.estrutura(ativo, timeframe, Math.max(100, limite)));
  }),
);

/** As medições que sustentam os pesos do motor. */
mercadoRoutes.get(
  '/estudos',
  autenticar,
  assincrono(async (_req, res) => {
    res.json(await ia.estudos());
  }),
);

/** Confiabilidade medida pelo walk-forward, por padrão. */
mercadoRoutes.get(
  '/calibracoes',
  autenticar,
  assincrono(async (_req, res) => {
    const itens = await prisma.calibracaoPadrao.findMany({ orderBy: { expectanciaR: 'desc' } });
    res.json(
      itens.map((c) => ({
        ...c,
        taxaAcerto: numero(c.taxaAcerto),
        expectanciaR: numero(c.expectanciaR),
      })),
    );
  }),
);

/**
 * Saúde da stack inteira. Rota pública de propósito: é o que a tela de login consulta
 * para avisar "o motor está fora" antes de o usuário tentar operar.
 */
mercadoRoutes.get(
  '/saude',
  assincrono(async (_req, res) => {
    const [banco, motor] = await Promise.allSettled([
      prisma.$queryRaw`SELECT 1`,
      ia.saude(),
    ]);

    const bancoOk = banco.status === 'fulfilled';
    const motorOk = motor.status === 'fulfilled';

    res.status(bancoOk ? 200 : 503).json({
      ok: bancoOk && motorOk,
      banco: bancoOk,
      motor: motorOk ? motor.value : { ok: false, erro: 'motor de análise fora do ar' },
      candles: bancoOk ? await contarCandles() : null,
    });
  }),
);

async function contarCandles() {
  const grupos = await prisma.candle.groupBy({
    by: ['ativo', 'timeframe'],
    _count: { _all: true },
    _max: { ts: true },
  });
  return grupos.map((g) => ({
    ativo: g.ativo,
    timeframe: g.timeframe,
    total: g._count._all,
    ultimo: g._max.ts?.toISOString() ?? null,
  }));
}
