import type { Prisma } from '@prisma/client';

import { NaoEncontrado } from '../../shared/erros.js';
import { ia } from '../../shared/ia.js';
import { numero, prisma } from '../../shared/prisma.js';
import type { ListarSinaisQuery } from './sinais.schemas.js';

/** Prisma devolve Decimal; a API sempre devolve number. Conversão num lugar só. */
function serializar(sinal: Record<string, unknown>) {
  const campos = [
    'entrada',
    'stop',
    'alvo',
    'riscoPontos',
    'retornoPontos',
    'rr',
    'score',
    'confiabilidade',
    'precoSaida',
    'resultadoPontos',
  ] as const;
  const saida: Record<string, unknown> = { ...sinal };
  for (const campo of campos) {
    if (saida[campo] !== null && saida[campo] !== undefined) saida[campo] = numero(saida[campo]);
  }
  return saida;
}

export async function listar(filtros: ListarSinaisQuery) {
  const where: Prisma.SinalWhereInput = {
    ...(filtros.ativo ? { ativo: filtros.ativo } : {}),
    ...(filtros.timeframe ? { timeframe: filtros.timeframe } : {}),
    ...(filtros.status ? { status: filtros.status } : {}),
    ...(filtros.direcao ? { direcao: filtros.direcao } : {}),
    ...(filtros.scoreMinimo !== undefined ? { score: { gte: filtros.scoreMinimo } } : {}),
    ...(filtros.desde ? { ts: { gte: filtros.desde } } : {}),
  };

  const [total, itens] = await Promise.all([
    prisma.sinal.count({ where }),
    prisma.sinal.findMany({
      where,
      orderBy: { ts: 'desc' },
      take: filtros.limite,
      skip: (filtros.pagina - 1) * filtros.limite,
    }),
  ]);

  return {
    total,
    pagina: filtros.pagina,
    limite: filtros.limite,
    itens: itens.map(serializar),
  };
}

export async function obter(id: string) {
  const sinal = await prisma.sinal.findUnique({
    where: { id },
    include: { anotacoes: { select: { id: true, operou: true, texto: true, criadoEm: true } } },
  });
  if (!sinal) throw new NaoEncontrado('Sinal');
  return serializar(sinal);
}

/** Sinais ainda vivos — é o que o dashboard e o WebSocket empurram. */
export async function abertos(limite = 20) {
  const itens = await prisma.sinal.findMany({
    where: { status: { in: ['ABERTO', 'ACIONADO'] } },
    orderBy: { ts: 'desc' },
    take: limite,
  });
  return itens.map(serializar);
}

export async function atualizarStatus(
  id: string,
  dados: { status: string; precoSaida?: number },
) {
  const sinal = await prisma.sinal.findUnique({ where: { id } });
  if (!sinal) throw new NaoEncontrado('Sinal');

  const encerrado = ['ALVO', 'STOP', 'EXPIRADO', 'CANCELADO'].includes(dados.status);
  const precoSaida = dados.precoSaida ?? null;

  // Resultado em pontos só faz sentido com preço de saída e com a direção certa:
  // numa venda, lucro é entrada MENOS saída.
  let resultadoPontos: number | null = null;
  if (precoSaida !== null) {
    const entrada = numero(sinal.entrada);
    resultadoPontos = sinal.direcao === 'ALTA' ? precoSaida - entrada : entrada - precoSaida;
  }

  const atualizado = await prisma.sinal.update({
    where: { id },
    data: {
      status: dados.status as never,
      precoSaida,
      resultadoPontos,
      fechadoEm: encerrado ? new Date() : null,
    },
  });
  return serializar(atualizado);
}

export async function anotar(
  sinalId: string,
  usuarioId: string,
  dados: { operou: boolean; texto?: string },
) {
  const sinal = await prisma.sinal.findUnique({ where: { id: sinalId }, select: { id: true } });
  if (!sinal) throw new NaoEncontrado('Sinal');

  return prisma.anotacaoSinal.upsert({
    where: { sinalId_usuarioId: { sinalId, usuarioId } },
    create: { sinalId, usuarioId, operou: dados.operou, texto: dados.texto ?? null },
    update: { operou: dados.operou, texto: dados.texto ?? null },
  });
}

/**
 * Dispara uma análise no motor e devolve o que ele encontrou.
 *
 * O motor persiste os sinais do lado Python (upsert idempotente pela chave
 * `ativo+timeframe+ts+padraoId`), então chamar duas vezes não duplica nada.
 */
export async function analisarAgora(ativo: string, timeframe: string, capital: number) {
  return ia.analisar(ativo, timeframe, capital, true);
}

/** Placar por padrão, com o resultado que o usuário de fato viveu. */
export async function desempenho(ativo?: string) {
  const encerrados = await prisma.sinal.findMany({
    where: {
      status: { in: ['ALVO', 'STOP'] },
      ...(ativo ? { ativo } : {}),
    },
    select: { padraoId: true, padraoNome: true, status: true, rr: true },
  });

  const mapa = new Map<string, { nome: string; n: number; acertos: number; somaR: number }>();
  for (const s of encerrados) {
    const atual = mapa.get(s.padraoId) ?? { nome: s.padraoNome, n: 0, acertos: 0, somaR: 0 };
    atual.n += 1;
    if (s.status === 'ALVO') {
      atual.acertos += 1;
      atual.somaR += numero(s.rr);
    } else {
      atual.somaR -= 1; // stop = perde exatamente 1R por construção
    }
    mapa.set(s.padraoId, atual);
  }

  return [...mapa.entries()]
    .map(([padraoId, v]) => ({
      padraoId,
      nome: v.nome,
      ocorrencias: v.n,
      acertos: v.acertos,
      taxaAcerto: v.n ? v.acertos / v.n : 0,
      expectanciaR: v.n ? v.somaR / v.n : 0,
      // Abaixo de 30 ocorrências não há evidência — a tela precisa dizer isso.
      suficiente: v.n >= 30,
    }))
    .sort((a, b) => b.expectanciaR - a.expectanciaR);
}

export async function resumo() {
  const [abertosCount, hoje, encerrados] = await Promise.all([
    prisma.sinal.count({ where: { status: { in: ['ABERTO', 'ACIONADO'] } } }),
    prisma.sinal.count({
      where: { ts: { gte: new Date(new Date().setHours(0, 0, 0, 0)) } },
    }),
    prisma.sinal.findMany({
      where: { status: { in: ['ALVO', 'STOP'] } },
      select: { status: true, rr: true },
      take: 500,
      orderBy: { ts: 'desc' },
    }),
  ]);

  const acertos = encerrados.filter((s) => s.status === 'ALVO').length;
  const somaR = encerrados.reduce(
    (acc, s) => acc + (s.status === 'ALVO' ? numero(s.rr) : -1),
    0,
  );

  return {
    abertos: abertosCount,
    emitidosHoje: hoje,
    encerrados: encerrados.length,
    taxaAcerto: encerrados.length ? acertos / encerrados.length : 0,
    expectanciaR: encerrados.length ? somaR / encerrados.length : 0,
    amostraSuficiente: encerrados.length >= 30,
  };
}
