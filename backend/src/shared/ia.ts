/**
 * Cliente do serviço de IA (Python, :1841).
 *
 * O backend **não** reimplementa nenhuma regra do motor. Toda detecção de padrão,
 * confluência e decisão acontece do lado Python — aqui só há transporte, timeout e
 * tradução de falha. Se alguém precisar de "só uma checagenzinha de padrão" em
 * TypeScript, a resposta é não: duas implementações divergem em uma semana.
 */
import { env } from '../config/env.js';
import { MotorIndisponivel } from './erros.js';
import { logger } from './logger.js';

async function chamar<T>(caminho: string, init?: RequestInit): Promise<T> {
  const controlador = new AbortController();
  const timeout = setTimeout(() => controlador.abort(), env.IA_TIMEOUT_MS);

  try {
    const resposta = await fetch(`${env.IA_URL}${caminho}`, {
      ...init,
      signal: controlador.signal,
      headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    });

    if (!resposta.ok) {
      const corpo = await resposta.text().catch(() => '');
      throw new MotorIndisponivel(`Motor respondeu ${resposta.status}: ${corpo.slice(0, 300)}`);
    }
    return (await resposta.json()) as T;
  } catch (erro) {
    if (erro instanceof MotorIndisponivel) throw erro;
    const motivo = erro instanceof Error ? erro.message : String(erro);
    logger.warn({ caminho, motivo }, 'falha ao falar com o motor de IA');
    throw new MotorIndisponivel(
      `Não foi possível falar com o motor em ${env.IA_URL}. ` +
        'Ele está no ar? (cd ai && python -m trader_ai.servico)',
    );
  } finally {
    clearTimeout(timeout);
  }
}

export interface PadraoCatalogo {
  id: string;
  nome: string;
  familia: string;
  direcao: string;
  n_candles: number;
  tendencia_requerida: string | null;
  confiabilidade_ebook: number;
  pagina_ebook: number;
  exige_gap: boolean;
  derivado_por_simetria: boolean;
  observacao: string;
}

export interface SaudeMotor {
  ok: boolean;
  versao: string;
  padroes: number;
  banco: boolean;
  mt5: { disponivel: boolean; detalhe: string };
}

export interface AnaliseResposta {
  ativo: string;
  timeframe: string;
  candles: number;
  sinais: unknown[];
  deteccoes: unknown[];
  contexto: Record<string, unknown> | null;
}

export const ia = {
  saude: () => chamar<SaudeMotor>('/saude'),

  catalogo: () => chamar<{ total: number; padroes: PadraoCatalogo[] }>('/catalogo'),

  /** As medições que sustentam os pesos do motor — Fibonacci, médias, janelas. */
  estudos: () => chamar<Record<string, unknown>>('/estudos'),

  /** Fechamento do período e os níveis que o próximo pregão começa olhando. */
  diario: (ativo: string, periodo: 'dia' | 'semana' | 'mes') =>
    chamar<Record<string, unknown>>('/diario', {
      method: 'POST',
      body: JSON.stringify({ ativo, periodo }),
    }),

  /**
   * O extrato do dia: cada entrada, na ordem, com o que aconteceu depois dela.
   *
   * Vive no motor e não aqui porque converter pontos em reais é regra de instrumento —
   * WIN e WDO têm valor de ponto e custo diferentes, e duas implementações da mesma
   * conta divergem na primeira mudança de tabela da B3.
   */
  pregao: (ativo: string, dia?: string) =>
    chamar<Record<string, unknown>>('/pregao', {
      method: 'POST',
      body: JSON.stringify({ ativo, dia: dia ?? null }),
    }),

  /** O que o motor está pensando agora — alimenta a Sala de Operações. */
  raciocinio: (ativo: string, capital: number) =>
    chamar<Record<string, unknown>>('/raciocinio', {
      method: 'POST',
      body: JSON.stringify({ ativo, capital }),
    }),

  /** O desenho do gráfico: canal, pivôs, rompimentos, zonas de oferta e demanda. */
  estrutura: (ativo: string, timeframe: string, candles = 600) =>
    chamar<Record<string, unknown>>('/estrutura', {
      method: 'POST',
      body: JSON.stringify({ ativo, timeframe, candles }),
    }),

  /** Roda o motor sobre os candles já persistidos e devolve sinais + detecções. */
  analisar: (ativo: string, timeframe: string, capital: number, persistir = true) =>
    chamar<AnaliseResposta>('/analisar', {
      method: 'POST',
      body: JSON.stringify({ ativo, timeframe, capital, persistir }),
    }),

  backtest: (payload: {
    ativo: string;
    timeframe: string;
    capital: number;
    janelas?: number;
    modo: 'backtest' | 'walkforward';
  }) => chamar<Record<string, unknown>>('/backtest', { method: 'POST', body: JSON.stringify(payload) }),
};
