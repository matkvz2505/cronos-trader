import { z } from 'zod';

/**
 * Política de senha deliberadamente simples: comprimento mínimo real (10) em vez do
 * teatro de "1 maiúscula, 1 símbolo". Comprimento é o que de fato resiste a força bruta;
 * regras de composição só empurram o usuário para `Senha@123`.
 */
const senha = z
  .string()
  .min(10, 'A senha precisa de pelo menos 10 caracteres')
  .max(200, 'Senha longa demais');

export const registroSchema = z.object({
  nome: z.string().trim().min(2, 'Informe seu nome').max(120),
  email: z.string().trim().toLowerCase().email('E-mail inválido'),
  senha,
  /** Capital usado no dimensionamento de posição. */
  capital: z.coerce.number().positive().max(100_000_000).default(10_000),
});

export const loginSchema = z.object({
  email: z.string().trim().toLowerCase().email('E-mail inválido'),
  senha: z.string().min(1, 'Informe a senha'),
});

export const refreshSchema = z.object({
  refreshToken: z.string().min(20, 'Refresh token inválido'),
});

export const atualizarPerfilSchema = z
  .object({
    nome: z.string().trim().min(2).max(120).optional(),
    capital: z.coerce.number().positive().max(100_000_000).optional(),
  })
  .strict();

export type RegistroEntrada = z.infer<typeof registroSchema>;
export type LoginEntrada = z.infer<typeof loginSchema>;
export type AtualizarPerfilEntrada = z.infer<typeof atualizarPerfilSchema>;
