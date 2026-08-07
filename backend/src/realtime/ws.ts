/**
 * WebSocket de alertas ao vivo.
 *
 * Estratégia: **um timer no servidor consulta o banco e transmite para todos**, em vez de
 * cada aba do navegador consultando a API. O produtor dos sinais é o processo Python, que
 * escreve direto no Postgres; `LISTEN/NOTIFY` funcionaria, mas acoplaria o Python ao
 * protocolo de notificação. Com candle mínimo de 5 minutos, um ciclo de 5 segundos é
 * folgado.
 *
 * O que muda em relação a só empurrar a lista de abertos: aqui o servidor guarda o
 * **status anterior de cada sinal** e detecta as transições. Sem isso a tela receberia
 * "estes são os abertos agora" e teria que adivinhar o que mudou — e um sinal que abre e
 * fecha entre dois ciclos passaria despercebido.
 */
import type { Server } from 'node:http';

import { WebSocketServer, type WebSocket } from 'ws';

import { env } from '../config/env.js';
import * as sinais from '../modules/sinais/sinais.service.js';
import { logger } from '../shared/logger.js';
import { numero, prisma } from '../shared/prisma.js';
import { verificarAccessToken } from '../shared/tokens.js';

interface Cliente extends WebSocket {
  vivo?: boolean;
  usuarioId?: string;
}

/** Um evento que merece interromper o que o operador está fazendo. */
type TipoAlerta = 'sinal.novo' | 'entrada.acionada' | 'saida.alvo' | 'saida.stop' | 'sinal.expirado';

interface Alerta {
  id: string;
  tipo: TipoAlerta;
  em: string;
  sinal: Record<string, unknown>;
}

const TRANSICOES: Record<string, TipoAlerta> = {
  ACIONADO: 'entrada.acionada',
  ALVO: 'saida.alvo',
  STOP: 'saida.stop',
  EXPIRADO: 'sinal.expirado',
};

export function montarWebSocket(servidor: Server): () => void {
  const wss = new WebSocketServer({ server: servidor, path: '/ws' });

  /**
   * Último status conhecido de cada sinal. Em memória de propósito: é cache de
   * transição, não estado de negócio — se o processo reiniciar, o pior que acontece é
   * não emitir um alerta de transição que ocorreu durante a queda.
   */
  const statusAnterior = new Map<string, string>();
  let iniciado = false;

  wss.on('connection', (socket: Cliente, req) => {
    // Autenticação por query param: a API de WebSocket do navegador não permite definir
    // cabeçalhos. O token é de vida curta (15min) e a conexão é local.
    const url = new URL(req.url ?? '/ws', 'http://localhost');
    try {
      socket.usuarioId = verificarAccessToken(url.searchParams.get('token') ?? '').sub;
    } catch {
      socket.close(4001, 'token inválido');
      return;
    }

    socket.vivo = true;
    socket.on('pong', () => {
      socket.vivo = true;
    });

    logger.debug({ usuarioId: socket.usuarioId }, 'ws conectado');
    void enviarEstadoInicial(socket);
  });

  /** Derruba conexões mortas — aba fechada abruptamente fica pendurada sem isto. */
  const ping = setInterval(() => {
    for (const cliente of wss.clients as Set<Cliente>) {
      if (!cliente.vivo) {
        cliente.terminate();
        continue;
      }
      cliente.vivo = false;
      cliente.ping();
    }
  }, 30_000);

  const pesquisa = setInterval(async () => {
    try {
      const alertas = await detectarTransicoes(statusAnterior, iniciado);
      iniciado = true;

      if (wss.clients.size === 0) return;

      if (alertas.length > 0) {
        transmitir(wss, { tipo: 'alertas', dados: alertas });
      }
      transmitir(wss, { tipo: 'sinais.abertos', dados: await sinais.abertos(20) });
    } catch (erro) {
      logger.warn({ err: erro }, 'falha no ciclo de alertas');
    }
  }, env.WS_INTERVALO_MS);

  return () => {
    clearInterval(ping);
    clearInterval(pesquisa);
    wss.close();
  };
}

/**
 * Compara o status atual de cada sinal com o da última passada.
 *
 * O primeiro ciclo só popula o mapa e **não emite nada**: sem isso, subir o servidor com
 * o banco cheio dispararia um alerta para cada sinal histórico de uma vez.
 */
async function detectarTransicoes(
  anterior: Map<string, string>,
  jaIniciado: boolean,
): Promise<Alerta[]> {
  const recentes = await prisma.sinal.findMany({
    where: { ts: { gte: new Date(Date.now() - 36 * 3_600_000) } },
    orderBy: { ts: 'desc' },
    take: 200,
  });

  const alertas: Alerta[] = [];

  for (const s of recentes) {
    const conhecido = anterior.get(s.id);
    anterior.set(s.id, s.status);
    if (!jaIniciado) continue;

    if (conhecido === undefined) {
      if (s.status === 'ABERTO') {
        alertas.push({ id: s.id, tipo: 'sinal.novo', em: new Date().toISOString(), sinal: serializar(s) });
      }
      continue;
    }

    if (conhecido !== s.status) {
      const tipo = TRANSICOES[s.status];
      if (tipo) {
        alertas.push({ id: s.id, tipo, em: new Date().toISOString(), sinal: serializar(s) });
      }
    }
  }

  // Impede o mapa de crescer sem limite num processo de vida longa.
  if (anterior.size > 1000) {
    const vivos = new Set(recentes.map((s) => s.id));
    for (const id of anterior.keys()) {
      if (!vivos.has(id)) anterior.delete(id);
    }
  }

  return alertas;
}

function serializar(s: Record<string, unknown>): Record<string, unknown> {
  const decimais = [
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
  ];
  const saida: Record<string, unknown> = { ...s };
  for (const campo of decimais) {
    if (saida[campo] !== null && saida[campo] !== undefined) saida[campo] = numero(saida[campo]);
  }
  return saida;
}

async function enviarEstadoInicial(socket: Cliente): Promise<void> {
  try {
    const [abertos, resumo] = await Promise.all([sinais.abertos(20), sinais.resumo()]);
    enviar(socket, { tipo: 'estado.inicial', dados: { abertos, resumo } });
  } catch (erro) {
    logger.warn({ err: erro }, 'falha ao enviar estado inicial');
  }
}

function enviar(socket: WebSocket, mensagem: unknown): void {
  if (socket.readyState === socket.OPEN) socket.send(JSON.stringify(mensagem));
}

function transmitir(wss: WebSocketServer, mensagem: unknown): void {
  const texto = JSON.stringify(mensagem);
  for (const cliente of wss.clients) {
    if (cliente.readyState === cliente.OPEN) cliente.send(texto);
  }
}
