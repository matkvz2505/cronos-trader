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

export function horario(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export function dataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function haQuantoTempo(iso: string): string {
  const segundos = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
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
