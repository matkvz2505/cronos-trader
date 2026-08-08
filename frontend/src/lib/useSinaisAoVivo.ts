import { useCallback, useEffect, useState } from 'react';

import { lerSessao } from './api';
import type { Alerta, Ativo, ResumoSinais, Sinal, TickMercado } from './tipos';

type Estado = 'conectando' | 'conectado' | 'desconectado';

interface Mensagem {
  tipo: 'estado.inicial' | 'sinais.abertos' | 'alertas' | 'mercado.tick' | 'mercado.candle';
  dados: unknown;
}

const MAX_ALERTAS = 60;

interface Instantaneo {
  estado: Estado;
  abertos: Sinal[];
  resumo: ResumoSinais | null;
  alertas: Alerta[];
  ticks: Partial<Record<Ativo, TickMercado>>;
}

/**
 * Estado do fluxo ao vivo, fora do React.
 *
 * **Uma conexão para a aba inteira**, não uma por componente. Antes o hook abria um
 * WebSocket por chamada: com a Mesa e a Sala montadas juntas seriam dois sockets
 * recebendo o mesmo tráfego, dois backoffs independentes e dois pontos onde a
 * reconexão pode divergir. O servidor transmite para todos os clientes conectados, então
 * o custo era real.
 *
 * O objeto é substituído a cada mudança (nunca mutado) porque os assinantes comparam por
 * identidade para decidir se re-renderizam.
 */
let atual: Instantaneo = {
  estado: 'conectando',
  abertos: [],
  resumo: null,
  alertas: [],
  ticks: {},
};

const assinantes = new Set<() => void>();
let socket: WebSocket | null = null;
let tentativas = 0;
let timer: number | null = null;

function publicar(mudanca: Partial<Instantaneo>): void {
  atual = { ...atual, ...mudanca };
  for (const avisar of assinantes) avisar();
}

function conectar(): void {
  const token = lerSessao()?.accessToken;
  if (!token || socket) return;

  const protocolo = window.location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(
    `${protocolo}://${window.location.host}/ws?token=${encodeURIComponent(token)}`,
  );
  publicar({ estado: 'conectando' });

  socket.onopen = () => {
    tentativas = 0;
    publicar({ estado: 'conectado' });
  };

  socket.onmessage = (evento) => {
    try {
      const mensagem = JSON.parse(evento.data as string) as Mensagem;

      if (mensagem.tipo === 'estado.inicial') {
        const d = mensagem.dados as {
          abertos: Sinal[];
          resumo: ResumoSinais;
          ticks?: TickMercado[];
        };
        publicar({ abertos: d.abertos, resumo: d.resumo, ticks: indexar(d.ticks ?? []) });
      } else if (mensagem.tipo === 'sinais.abertos') {
        publicar({ abertos: mensagem.dados as Sinal[] });
      } else if (mensagem.tipo === 'mercado.tick') {
        publicar({ ticks: indexar(mensagem.dados as TickMercado[]) });
      } else if (mensagem.tipo === 'alertas') {
        const novos = mensagem.dados as Alerta[];
        if (novos.length > 0) {
          publicar({ alertas: [...novos, ...atual.alertas].slice(0, MAX_ALERTAS) });
        }
      }
      // `mercado.candle` não precisa de tratamento próprio: o `ts` dentro de `ticks` já
      // mudou, e é ele que os consumidores observam para refazer o trabalho caro.
    } catch {
      // Mensagem malformada não pode derrubar a assinatura.
    }
  };

  socket.onclose = () => {
    socket = null;
    publicar({ estado: 'desconectado' });
    if (assinantes.size === 0) return;
    // Backoff exponencial com teto de 30s. Sem teto, um backend fora por dez minutos
    // faria o navegador tentar de hora em hora; sem backoff, centenas de vezes por
    // minuto. O contador zera na primeira conexão bem-sucedida.
    const espera = Math.min(30_000, 1000 * 2 ** tentativas);
    tentativas += 1;
    timer = window.setTimeout(conectar, espera);
  };

  socket.onerror = () => socket?.close();
}

function indexar(ticks: TickMercado[]): Partial<Record<Ativo, TickMercado>> {
  const mapa: Partial<Record<Ativo, TickMercado>> = {};
  for (const t of ticks) mapa[t.ativo as Ativo] = t;
  return mapa;
}

/**
 * Assinatura do fluxo ao vivo: sinais abertos, alertas de transição e preço por ativo.
 *
 * Os alertas ficam num buffer local, não no banco: são um feed do que aconteceu desde que
 * a aba abriu. Recarregar limpa — e isso é correto, porque um alerta de entrada acionada
 * há três horas não é mais um alerta, é histórico. Para o que aconteceu antes de a aba
 * abrir existe `/mercado/pregao`, que lê do banco.
 */
export function useSinaisAoVivo() {
  const [, forcar] = useState(0);

  useEffect(() => {
    const avisar = () => forcar((n) => n + 1);
    assinantes.add(avisar);
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    conectar();

    return () => {
      assinantes.delete(avisar);
      // A última aba a sair fecha a porta. Sem isto o socket sobreviveria ao logout.
      if (assinantes.size === 0) {
        if (timer) window.clearTimeout(timer);
        timer = null;
        socket?.close();
        socket = null;
      }
    };
  }, []);

  const limparAlertas = useCallback(() => publicar({ alertas: [] }), []);

  return {
    estado: atual.estado,
    abertos: atual.abertos,
    resumo: atual.resumo,
    alertas: atual.alertas,
    ticks: atual.ticks,
    limparAlertas,
  };
}

/**
 * O preço ao vivo de um ativo, e o `ts` do candle que o produziu.
 *
 * O `ts` é o gatilho de recálculo do resto da tela: enquanto ele não muda, nada de novo
 * aconteceu no mercado e refazer o dossiê do motor seria trabalho jogado fora. Use-o como
 * dependência de efeito em vez de um `setInterval`.
 */
export function useTickAoVivo(ativo: Ativo): TickMercado | undefined {
  const { ticks } = useSinaisAoVivo();
  return ticks[ativo];
}
