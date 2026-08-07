import type { NextFunction, Request, Response } from 'express';
import { ZodError, type ZodSchema } from 'zod';

import { ErroHttp, NaoAutorizado, Proibido } from '../shared/erros.js';
import { logger } from '../shared/logger.js';
import { verificarAccessToken, type Claims } from '../shared/tokens.js';

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      usuario?: Claims;
    }
  }
}

/**
 * Envolve handler async para que rejeição vire `next(erro)`.
 *
 * Sem isto, um `await` que rejeita num handler Express 4 vira unhandled rejection e a
 * requisição fica pendurada até o timeout do cliente — sem log e sem resposta.
 */
export function assincrono<T extends Request>(
  handler: (req: T, res: Response, next: NextFunction) => Promise<unknown>,
) {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(handler(req as T, res, next)).catch(next);
  };
}

/** Valida `body` contra um schema Zod e substitui pelo resultado tipado. */
export function validarBody(schema: ZodSchema) {
  return (req: Request, _res: Response, next: NextFunction) => {
    const resultado = schema.safeParse(req.body);
    if (!resultado.success) return next(resultado.error);
    req.body = resultado.data;
    next();
  };
}

/** Idem para query string. */
export function validarQuery(schema: ZodSchema) {
  return (req: Request, _res: Response, next: NextFunction) => {
    const resultado = schema.safeParse(req.query);
    if (!resultado.success) return next(resultado.error);
    // `req.query` é getter-only no Express 5; guardamos à parte para funcionar nos dois.
    Object.defineProperty(req, 'query', { value: resultado.data, writable: true });
    next();
  };
}

export function autenticar(req: Request, _res: Response, next: NextFunction): void {
  const cabecalho = req.headers.authorization;
  if (!cabecalho?.startsWith('Bearer ')) {
    return next(new NaoAutorizado('Token ausente'));
  }
  try {
    req.usuario = verificarAccessToken(cabecalho.slice(7));
    next();
  } catch {
    next(new NaoAutorizado('Token inválido ou expirado'));
  }
}

export function exigirAdmin(req: Request, _res: Response, next: NextFunction): void {
  if (req.usuario?.papel !== 'ADMIN') return next(new Proibido());
  next();
}

/**
 * Tradutor final de erro para resposta.
 *
 * Erro desconhecido devolve mensagem genérica de propósito: stack trace numa resposta
 * HTTP entrega estrutura interna para quem estiver sondando. O detalhe vai para o log.
 */
export function tratarErro(
  erro: unknown,
  req: Request,
  res: Response,
  _next: NextFunction,
): void {
  if (erro instanceof ZodError) {
    res.status(400).json({
      erro: 'Dados inválidos',
      codigo: 'VALIDACAO',
      campos: erro.issues.map((i) => ({ campo: i.path.join('.'), mensagem: i.message })),
    });
    return;
  }

  if (erro instanceof ErroHttp) {
    res.status(erro.status).json({
      erro: erro.message,
      codigo: erro.codigo,
      ...(erro.detalhes ? { detalhes: erro.detalhes } : {}),
    });
    return;
  }

  logger.error({ err: erro, rota: `${req.method} ${req.path}` }, 'erro não tratado');
  res.status(500).json({ erro: 'Erro interno', codigo: 'ERRO_INTERNO' });
}

export function naoEncontrado(req: Request, res: Response): void {
  res.status(404).json({ erro: `Rota ${req.method} ${req.path} não existe`, codigo: 'ROTA_INEXISTENTE' });
}
