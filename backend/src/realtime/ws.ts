/**
 * WebSocket de sinais ao vivo.
 *
 * Estratégia: **polling do banco no servidor, push para os clientes**. Um único timer
 * consulta o Postgres e transmite para todos os conectados — em vez de cada aba do
 * navegador consultando a API a cada poucos segundos.
 *
 * Por que polling e não notificação do Postgres: o produtor dos sinais é o processo
 * Python, que escreve direto no banco. `LISTEN/NOTIFY` funcionaria, mas exigiria acoplar
 * o Python ao protocolo de notificação. Com granularidade de 5 segundos num produto cujo
 * candle mais rápido é de 5 minutos, o polling é suficiente e muito mais simples.
 */
import type { Server } from 'node:http';

import { WebSocketServer, type WebSocket } from 'ws';

import { env } from '../config/env.js';
import { logger } from '../shared/logger.js';
import { verificarAccessToken } from '../shared/tokens.js';
import * as sinais from '../modules/sinais/sinais.service.js';

interface Cliente extends WebSocket {
  vivo?: boolean;
  usuarioId?: string;
}

export function montarWebSocket(servidor: Server): () => void {
  const wss = new WebSocketServer({ server: servidor, path: '/ws' });
  let ultimoEnvio = new Date(0);

  wss.on('connection', (socket: Cliente, req) => {
    // Autenticação por query param: a API de WebSocket do navegador não permite
    // definir cabeçalhos. O token é de vida curta (15min) e a conexão é local.
    const url = new URL(req.url ?? '/ws', 'http://localhost');
    const token = url.searchParams.get('token');

    try {
      socket.usuarioId = verificarAccessToken(token ?? '').sub;
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

  /** Derruba conexões mortas — sem isto, aba fechada abruptamente fica pendurada. */
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
    if (wss.clients.size === 0) return;
    try {
      const abertos = await sinais.abertos(20);
      const novos = abertos.filter((s) => new Date(s.criadoEm as string) > ultimoEnvio);
      if (novos.length > 0) {
        ultimoEnvio = new Date();
        transmitir(wss, { tipo: 'sinais.novos', dados: novos });
      }
      transmitir(wss, { tipo: 'sinais.abertos', dados: abertos });
    } catch (erro) {
      logger.warn({ err: erro }, 'falha no polling de sinais');
    }
  }, env.WS_INTERVALO_MS);

  return () => {
    clearInterval(ping);
    clearInterval(pesquisa);
    wss.close();
  };
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
