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

const ATIVOS = ['WIN', 'WDO'] as const;

/**
 * Preço e frescura de um ativo. É o que muda entre um candle e outro.
 *
 * `ts` sai como ISO do timestamp naive — o mesmo rótulo com `Z` que o resto da API usa.
 * A tela lê os componentes em UTC e recupera o relógio do pregão; ver
 * `frontend/src/lib/formato.ts`.
 */
interface TickMercado {
  ativo: string;
  ts: string | null;
  preco: number | null;
  aberturaDia: number | null;
  variacaoDia: number | null;
  idadeMinutos: number | null;
}

/**
 * Último candle de cada ativo, direto do banco.
 *
 * Query barata de propósito: roda a cada ciclo de WebSocket e não pode custar o que custa
 * um dossiê do motor. O dossiê caro só é recalculado quando o candle vira — e quem decide
 * isso é `mercado.candle`, não um timer.
 */
async function lerTicks(): Promise<TickMercado[]> {
  const agora = Date.now();

  return Promise.all(
    ATIVOS.map(async (ativo) => {
      const ultimo = await prisma.candle.findFirst({
        where: { ativo, timeframe: 'M5' },
        orderBy: { ts: 'desc' },
      });
      if (!ultimo) {
        return { ativo, ts: null, preco: null, aberturaDia: null, variacaoDia: null, idadeMinutos: null };
      }

      // Abertura do dia do próprio candle: o pregão começa às 9h e o primeiro candle do
      // dia é a referência da variação. Usar o fechamento do dia anterior daria o número
      // do home broker, mas o operador de day trade mede a partir da abertura.
      const inicioDoDia = new Date(ultimo.ts);
      inicioDoDia.setUTCHours(0, 0, 0, 0);
      const primeiro = await prisma.candle.findFirst({
        where: { ativo, timeframe: 'M5', ts: { gte: inicioDoDia } },
        orderBy: { ts: 'asc' },
      });

      const preco = numero(ultimo.fechamento);
      const abertura = primeiro ? numero(primeiro.abertura) : null;

      // O `ts` é naive gravado como relógio do pregão; o Prisma o devolve rotulado como
      // UTC. O processo Node roda em America/Sao_Paulo, então comparar `getTime()` cru
      // com `Date.now()` erraria em 3 h — a mesma armadilha que fez a Mesa anunciar
      // "dados parados há 6 h" com candle de 3h20.
      const rotuloDoAgora = agora - new Date().getTimezoneOffset() * 60_000;
      const idade = (rotuloDoAgora - ultimo.ts.getTime()) / 60_000;

      return {
        ativo,
        ts: ultimo.ts.toISOString(),
        preco,
        aberturaDia: abertura,
        variacaoDia: abertura ? ((preco - abertura) / abertura) * 100 : null,
        idadeMinutos: Math.max(0, idade),
      };
    }),
  );
}

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

  /**
   * Último candle transmitido por ativo, para detectar virada.
   *
   * É o que transforma polling em push: em vez de a tela perguntar "mudou?" de tempos em
   * tempos, o servidor avisa quando mudou. A tela só refaz o trabalho caro — dossiê do
   * motor, estrutura, gráfico — nesse momento.
   */
  const ultimoCandle = new Map<string, string>();

  const pesquisa = setInterval(async () => {
    try {
      const alertas = await detectarTransicoes(statusAnterior, iniciado);
      iniciado = true;

      if (wss.clients.size === 0) return;

      if (alertas.length > 0) {
        transmitir(wss, { tipo: 'alertas', dados: alertas });
      }
      transmitir(wss, { tipo: 'sinais.abertos', dados: await sinais.abertos(20) });

      const ticks = await lerTicks();
      transmitir(wss, { tipo: 'mercado.tick', dados: ticks });

      // Um evento por ativo que virou candle. Separado do tick porque o custo do que ele
      // dispara na tela é outra ordem de grandeza: o tick move um número, isto refaz o
      // dossiê inteiro.
      const viraram = ticks.filter((t) => t.ts !== null && ultimoCandle.get(t.ativo) !== t.ts);
      for (const t of viraram) {
        ultimoCandle.set(t.ativo, t.ts as string);
      }
      if (viraram.length > 0) {
        transmitir(wss, {
          tipo: 'mercado.candle',
          dados: viraram.map((t) => ({ ativo: t.ativo, ts: t.ts })),
        });
      }
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

/**
 * O que a aba precisa saber no instante em que conecta.
 *
 * Inclui os ticks: sem eles a tela ficaria com os campos vazios até o primeiro ciclo do
 * timer, e uma tela que nasce vazia parece quebrada mesmo quando não está.
 */
async function enviarEstadoInicial(socket: Cliente): Promise<void> {
  try {
    const [abertos, resumo, ticks] = await Promise.all([
      sinais.abertos(20),
      sinais.resumo(),
      lerTicks(),
    ]);
    enviar(socket, { tipo: 'estado.inicial', dados: { abertos, resumo, ticks } });
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
