import type { Request, Response } from 'express';

import * as servico from './auth.service.js';

/** Controllers não têm lógica de negócio — só traduzem HTTP para chamada de service. */

export async function registrar(req: Request, res: Response): Promise<void> {
  const resultado = await servico.registrar(req.body, req.get('user-agent'));
  res.status(201).json(resultado);
}

export async function login(req: Request, res: Response): Promise<void> {
  res.json(await servico.login(req.body, req.get('user-agent')));
}

export async function renovar(req: Request, res: Response): Promise<void> {
  res.json(await servico.renovar(req.body.refreshToken, req.get('user-agent')));
}

export async function sair(req: Request, res: Response): Promise<void> {
  await servico.sair(req.body.refreshToken);
  res.status(204).send();
}

export async function eu(req: Request, res: Response): Promise<void> {
  res.json(await servico.perfil(req.usuario!.sub));
}

export async function atualizar(req: Request, res: Response): Promise<void> {
  res.json(await servico.atualizarPerfil(req.usuario!.sub, req.body));
}
