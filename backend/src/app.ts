import cors from 'cors';
import express, { type Express } from 'express';
import helmet from 'helmet';

import { env } from './config/env.js';
import { naoEncontrado, tratarErro } from './middleware/index.js';
import { authRoutes } from './modules/auth/auth.routes.js';
import { backtestRoutes } from './modules/backtest/backtest.routes.js';
import { mercadoRoutes } from './modules/mercado/mercado.routes.js';
import { sinaisRoutes } from './modules/sinais/sinais.routes.js';
import { logger } from './shared/logger.js';

export function criarApp(): Express {
  const app = express();

  app.disable('x-powered-by');
  app.use(helmet());
  app.use(
    cors({
      origin: env.CORS_ORIGENS,
      credentials: true,
    }),
  );
  app.use(express.json({ limit: '1mb' }));

  app.use((req, _res, next) => {
    logger.debug({ metodo: req.method, rota: req.path }, 'requisição');
    next();
  });

  // Tudo sob /api/v1 — mesma convenção dos outros cronos do workspace.
  app.use('/api/v1/auth', authRoutes);
  app.use('/api/v1/sinais', sinaisRoutes);
  app.use('/api/v1/mercado', mercadoRoutes);
  app.use('/api/v1/backtest', backtestRoutes);

  app.get('/api/v1', (_req, res) => {
    res.json({
      servico: 'cronos-trader-backend',
      versao: '0.1.0',
      escopo: 'WIN e WDO — apenas sinal, sem envio de ordem',
      rotas: ['/api/v1/auth', '/api/v1/sinais', '/api/v1/mercado', '/api/v1/backtest'],
    });
  });

  app.use(naoEncontrado);
  app.use(tratarErro);

  return app;
}
