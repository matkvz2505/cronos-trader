import { env } from '../../config/env.js';
import { Conflito, NaoAutorizado, NaoEncontrado } from '../../shared/erros.js';
import { numero, prisma } from '../../shared/prisma.js';
import {
  assinarAccessToken,
  conferirSenha,
  gerarHashSenha,
  gerarRefreshToken,
  hashRefresh,
} from '../../shared/tokens.js';
import type { AtualizarPerfilEntrada, LoginEntrada, RegistroEntrada } from './auth.schemas.js';

/**
 * Campos públicos do usuário.
 *
 * Sempre `select` explícito, nunca desestruturar o resultado do Prisma para "remover" a
 * senha: um `select` novo no futuro traria `senhaHash` de volta sem ninguém notar.
 */
const CAMPOS_PUBLICOS = {
  id: true,
  nome: true,
  email: true,
  papel: true,
  capital: true,
  criadoEm: true,
  ultimoLogin: true,
} as const;

function serializar(usuario: {
  id: string;
  nome: string;
  email: string;
  papel: string;
  capital: unknown;
  criadoEm: Date;
  ultimoLogin: Date | null;
}) {
  return { ...usuario, capital: numero(usuario.capital) };
}

async function emitirSessao(usuario: { id: string; email: string; papel: string }, userAgent?: string) {
  const { token, hash } = gerarRefreshToken();
  const expiraEm = new Date(Date.now() + env.REFRESH_EXPIRA_DIAS * 86_400_000);

  await prisma.sessao.create({
    data: { usuarioId: usuario.id, tokenHash: hash, expiraEm, userAgent: userAgent ?? null },
  });

  return {
    accessToken: assinarAccessToken({ sub: usuario.id, email: usuario.email, papel: usuario.papel }),
    refreshToken: token,
    expiraEm: expiraEm.toISOString(),
  };
}

export async function registrar(dados: RegistroEntrada, userAgent?: string) {
  const existente = await prisma.usuario.findUnique({ where: { email: dados.email } });
  if (existente) throw new Conflito('Já existe uma conta com este e-mail');

  const usuario = await prisma.usuario.create({
    data: {
      nome: dados.nome,
      email: dados.email,
      senhaHash: await gerarHashSenha(dados.senha),
      capital: dados.capital,
    },
    select: CAMPOS_PUBLICOS,
  });

  return { usuario: serializar(usuario), ...(await emitirSessao(usuario, userAgent)) };
}

export async function login(dados: LoginEntrada, userAgent?: string) {
  const usuario = await prisma.usuario.findUnique({
    where: { email: dados.email },
    select: { ...CAMPOS_PUBLICOS, senhaHash: true, ativo: true },
  });

  // Mensagem idêntica para e-mail inexistente e senha errada: diferenciar as duas
  // transforma o login num verificador de quais e-mails têm conta.
  if (!usuario || !usuario.ativo) throw new NaoAutorizado();
  if (!(await conferirSenha(dados.senha, usuario.senhaHash))) throw new NaoAutorizado();

  await prisma.usuario.update({
    where: { id: usuario.id },
    data: { ultimoLogin: new Date() },
  });

  const { senhaHash: _ignorado, ativo: _ativo, ...publico } = usuario;
  return { usuario: serializar(publico), ...(await emitirSessao(usuario, userAgent)) };
}

/**
 * Troca refresh por um par novo, **rotacionando**: a sessão antiga é revogada no mesmo
 * ato. Assim um refresh token roubado só serve até o dono legítimo renovar — e a partir
 * daí o ladrão recebe 401.
 */
export async function renovar(refreshToken: string, userAgent?: string) {
  const sessao = await prisma.sessao.findUnique({
    where: { tokenHash: hashRefresh(refreshToken) },
    include: { usuario: { select: { ...CAMPOS_PUBLICOS, ativo: true } } },
  });

  if (!sessao || sessao.revogadaEm || sessao.expiraEm < new Date()) {
    throw new NaoAutorizado('Sessão expirada. Faça login novamente.');
  }
  if (!sessao.usuario.ativo) throw new NaoAutorizado();

  await prisma.sessao.update({
    where: { id: sessao.id },
    data: { revogadaEm: new Date() },
  });

  const { ativo: _ativo, ...publico } = sessao.usuario;
  return { usuario: serializar(publico), ...(await emitirSessao(sessao.usuario, userAgent)) };
}

export async function sair(refreshToken: string): Promise<void> {
  await prisma.sessao.updateMany({
    where: { tokenHash: hashRefresh(refreshToken), revogadaEm: null },
    data: { revogadaEm: new Date() },
  });
}

export async function perfil(usuarioId: string) {
  const usuario = await prisma.usuario.findUnique({
    where: { id: usuarioId },
    select: CAMPOS_PUBLICOS,
  });
  if (!usuario) throw new NaoEncontrado('Usuário');
  return serializar(usuario);
}

export async function atualizarPerfil(usuarioId: string, dados: AtualizarPerfilEntrada) {
  const usuario = await prisma.usuario.update({
    where: { id: usuarioId },
    data: dados,
    select: CAMPOS_PUBLICOS,
  });
  return serializar(usuario);
}
