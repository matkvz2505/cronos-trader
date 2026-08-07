import { useCallback, useEffect, useRef, useState } from 'react';

import { lerSessao } from './api';
import type { Alerta, ResumoSinais, Sinal } from './tipos';

type Estado = 'conectando' | 'conectado' | 'desconectado';

interface Mensagem {
  tipo: 'estado.inicial' | 'sinais.abertos' | 'alertas';
  dados: unknown;
}

const MAX_ALERTAS = 60;

/**
 * Assinatura do fluxo ao vivo: sinais abertos + alertas de transição.
 *
 * Reconexão com backoff exponencial limitado a 30s. Sem teto, um backend fora por dez
 * minutos faria o navegador tentar de hora em hora; sem backoff, faria centenas de
 * tentativas por minuto. O contador zera na primeira conexão bem-sucedida.
 *
 * Os alertas ficam num buffer local, não no banco: são um feed do que aconteceu desde
 * que a aba abriu. Recarregar a página limpa — e isso é correto, porque um alerta de
 * entrada acionada há três horas não é mais um alerta, é histórico.
 */
export function useSinaisAoVivo() {
  const [estado, setEstado] = useState<Estado>('conectando');
  const [abertos, setAbertos] = useState<Sinal[]>([]);
  const [resumo, setResumo] = useState<ResumoSinais | null>(null);
  const [alertas, setAlertas] = useState<Alerta[]>([]);

  const tentativas = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);

  const limparAlertas = useCallback(() => setAlertas([]), []);

  useEffect(() => {
    let desmontado = false;

    function conectar() {
      const token = lerSessao()?.accessToken;
      if (!token || desmontado) return;

      const protocolo = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const socket = new WebSocket(
        `${protocolo}://${window.location.host}/ws?token=${encodeURIComponent(token)}`,
      );
      socketRef.current = socket;
      setEstado('conectando');

      socket.onopen = () => {
        tentativas.current = 0;
        setEstado('conectado');
      };

      socket.onmessage = (evento) => {
        try {
          const mensagem = JSON.parse(evento.data as string) as Mensagem;

          if (mensagem.tipo === 'estado.inicial') {
            const d = mensagem.dados as { abertos: Sinal[]; resumo: ResumoSinais };
            setAbertos(d.abertos);
            setResumo(d.resumo);
          } else if (mensagem.tipo === 'sinais.abertos') {
            setAbertos(mensagem.dados as Sinal[]);
          } else if (mensagem.tipo === 'alertas') {
            const novos = mensagem.dados as Alerta[];
            if (novos.length > 0) {
              setAlertas((atuais) => [...novos, ...atuais].slice(0, MAX_ALERTAS));
            }
          }
        } catch {
          // Mensagem malformada não pode derrubar a assinatura.
        }
      };

      socket.onclose = () => {
        setEstado('desconectado');
        if (desmontado) return;
        const espera = Math.min(30_000, 1000 * 2 ** tentativas.current);
        tentativas.current += 1;
        timerRef.current = window.setTimeout(conectar, espera);
      };

      socket.onerror = () => socket.close();
    }

    conectar();

    return () => {
      desmontado = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      socketRef.current?.close();
    };
  }, []);

  return { estado, abertos, resumo, alertas, limparAlertas };
}
