/** Formatação em pt-BR. Um lugar só, para a tela inteira falar a mesma língua. */

import type { Ativo } from './tipos';

/**
 * Casas decimais por ativo.
 *
 * WIN anda em passos de 5 pontos inteiros; WDO tem meio ponto. Mostrar `130000,00` no
 * WIN é ruído visual, e mostrar `5432` no WDO esconde o tick.
 */
const CASAS: Record<Ativo, number> = { WIN: 0, WDO: 1 };

export function preco(valor: number | null | undefined, ativo: Ativo = 'WIN'): string {
  if (valor === null || valor === undefined) return '—';
  return valor.toLocaleString('pt-BR', {
    minimumFractionDigits: CASAS[ativo],
    maximumFractionDigits: CASAS[ativo],
  });
}

export function reais(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return valor.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

export function percentual(valor: number | null | undefined, casas = 1): string {
  if (valor === null || valor === undefined) return '—';
  return `${(valor * 100).toFixed(casas)}%`;
}

/** Expectância sempre com sinal explícito: `+0,42R` lê diferente de `0,42R`. */
export function emR(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return `${valor >= 0 ? '+' : ''}${valor.toFixed(2)}R`;
}

export function pontos(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—';
  return valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
}

/**
 * Fuso em que os instantes vindos da API devem ser LIDOS.
 *
 * O `ts` de um candle é relógio de parede do pregão, guardado em `timestamp without time
 * zone`. O Prisma serializa esse valor naive como se fosse UTC — o candle das 15:30 da B3
 * chega aqui como `2026-08-07T15:30:00.000Z`. O `Z` está mentindo: não é 15:30 UTC, é
 * 15:30 em São Paulo.
 *
 * Renderizar isso com o fuso do navegador subtrai 3 horas e o gráfico marca 12:30 num
 * candle das 15:30. Ler os componentes em UTC devolve exatamente o número que o operador
 * vê no MetaTrader.
 *
 * A alternativa — migrar a coluna para `timestamptz` — foi descartada por ora: obrigaria
 * migração de dados e o motor em Python trata `ts` como naive em toda a pipeline.
 */
const FUSO_DO_MERCADO = 'UTC';

export function horario(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: FUSO_DO_MERCADO,
  });
}

export function dataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: FUSO_DO_MERCADO,
  });
}

/**
 * Idade de um instante DO MERCADO.
 *
 * Não dá para comparar direto com `Date.now()`: o instante da API carrega o relógio do
 * pregão rotulado como UTC, e o navegador está em −3. A subtração crua daria 3 horas a
 * mais — foi exatamente o que fez a tela anunciar "dados parados há 6 h" com candle de
 * pouco mais de 3 h. Corrige-se comparando com o agora convertido para o mesmo rótulo.
 */
export function haQuantoTempo(iso: string): string {
  const agora = new Date();
  const agoraNoRotuloDoMercado =
    agora.getTime() - agora.getTimezoneOffset() * 60_000;
  const segundos = Math.floor((agoraNoRotuloDoMercado - new Date(iso).getTime()) / 1000);
  if (segundos < 60) return 'agora';
  if (segundos < 3600) return `há ${Math.floor(segundos / 60)}min`;
  if (segundos < 86400) return `há ${Math.floor(segundos / 3600)}h`;
  return `há ${Math.floor(segundos / 86400)}d`;
}

export const ROTULO_TIMEFRAME: Record<string, string> = {
  M5: '5min',
  M15: '15min',
  M30: '30min',
  H1: '60min',
  D1: 'diário',
};

export const ROTULO_STATUS: Record<string, string> = {
  ABERTO: 'aguardando',
  ACIONADO: 'em posição',
  ALVO: 'alvo',
  STOP: 'stop',
  EXPIRADO: 'expirou',
  CANCELADO: 'cancelado',
};
