import { Router } from 'express';

import { assincrono, autenticar, validarBody, validarQuery } from '../../middleware/index.js';
import { prisma } from '../../shared/prisma.js';
import {
  analisarSchema,
  anotarSchema,
  atualizarStatusSchema,
  listarSinaisSchema,
} from './sinais.schemas.js';
import * as servico from './sinais.service.js';

export const sinaisRoutes = Router();

sinaisRoutes.use(autenticar);

sinaisRoutes.get(
  '/',
  validarQuery(listarSinaisSchema),
  assincrono(async (req, res) => {
    res.json(await servico.listar(req.query as never));
  }),
);

sinaisRoutes.get(
  '/abertos',
  assincrono(async (_req, res) => {
    res.json(await servico.abertos());
  }),
);

sinaisRoutes.get(
  '/resumo',
  assincrono(async (_req, res) => {
    res.json(await servico.resumo());
  }),
);

sinaisRoutes.get(
  '/desempenho',
  assincrono(async (req, res) => {
    const ativo = typeof req.query.ativo === 'string' ? req.query.ativo : undefined;
    res.json(await servico.desempenho(ativo));
  }),
);

sinaisRoutes.get(
  '/:id',
  assincrono(async (req, res) => {
    res.json(await servico.obter(req.params.id!));
  }),
);

sinaisRoutes.patch(
  '/:id/status',
  validarBody(atualizarStatusSchema),
  assincrono(async (req, res) => {
    res.json(await servico.atualizarStatus(req.params.id!, req.body));
  }),
);

sinaisRoutes.post(
  '/:id/anotacao',
  validarBody(anotarSchema),
  assincrono(async (req, res) => {
    res.status(201).json(await servico.anotar(req.params.id!, req.usuario!.sub, req.body));
  }),
);

/**
 * Dispara o motor sob demanda. Usa o capital do usuário logado — o mesmo padrão gera
 * número de contratos diferente para cada conta.
 */
sinaisRoutes.post(
  '/analisar',
  validarBody(analisarSchema),
  assincrono(async (req, res) => {
    const usuario = await prisma.usuario.findUnique({
      where: { id: req.usuario!.sub },
      select: { capital: true },
    });
    const capital = Number(usuario?.capital ?? 10_000);
    res.json(await servico.analisarAgora(req.body.ativo, req.body.timeframe, capital));
  }),
);
