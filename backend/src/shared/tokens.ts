import { createHash, randomBytes } from 'node:crypto';

import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

import { env } from '../config/env.js';

const ROUNDS = 12;

export async function gerarHashSenha(senha: string): Promise<string> {
  return bcrypt.hash(senha, ROUNDS);
}

export async function conferirSenha(senha: string, hash: string): Promise<boolean> {
  return bcrypt.compare(senha, hash);
}

export interface Claims {
  sub: string;
  email: string;
  papel: string;
}

export function assinarAccessToken(claims: Claims): string {
  return jwt.sign(claims, env.JWT_SECRET, {
    // Os tipos do jsonwebtoken exigem um literal de duração (`'15m'`, `'7d'`) ou um
    // número de segundos. Como o valor vem do ambiente, o TypeScript só enxerga
    // `string` — a validação de formato acontece em runtime, no boot: um
    // `JWT_EXPIRA_EM` inválido faz o `jwt.sign` lançar na primeira assinatura.
    expiresIn: env.JWT_EXPIRA_EM as jwt.SignOptions['expiresIn'],
    issuer: 'cronos-trader',
    audience: 'cronos-trader-web',
  });
}

export function verificarAccessToken(token: string): Claims {
  return jwt.verify(token, env.JWT_SECRET, {
    issuer: 'cronos-trader',
    audience: 'cronos-trader-web',
  }) as Claims;
}

/**
 * Refresh token opaco.
 *
 * Devolve o par `{ token, hash }`: o token vai para o cliente **uma única vez**, e só o
 * hash é persistido. Vazamento do banco não pode virar sessão válida — é a mesma
 * política do cronos-auth.
 */
export function gerarRefreshToken(): { token: string; hash: string } {
  const token = randomBytes(48).toString('base64url');
  return { token, hash: hashRefresh(token) };
}

export function hashRefresh(token: string): string {
  return createHash('sha256').update(token).digest('hex');
}
