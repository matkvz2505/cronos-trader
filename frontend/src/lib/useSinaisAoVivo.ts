import { useEffect, useRef, useState } from 'react';

import { lerSessao } from './api';
import type { ResumoSinais, Sinal } from './tipos';

type Estado = 'conectando' | 'conectado' | 'desconectado';

interface Mensagem {
  tipo: 'estado.inicial' | 'sinais.abertos' | 'sinais.novos';
  dados: unknown;
}

/**
 * Assinatura do WebSocket de sinais ao vivo.
 *
 * Reconexão com backoff exponencial limitado a 30s: sem teto, um backend fora do ar por
 * dez minutos faria o navegador tentar de hora em hora; sem backoff, faria centenas de
 * tentativas por minuto. O contador zera na primeira conexão bem-sucedida.
 */
export function useSinaisAoVivo() {
  const [estado, setEstado] = useState<Estado>('conectando');
  const [abertos, setAbertos] = useState<Sinal[]>([]);
  const [resumo, setResumo] = useState<ResumoSinais | null>(null);
  const [ultimoNovo, setUltimoNovo] = useState<Sinal | null>(null);

  const tentativas = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);

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
            const dados = mensagem.dados as { abertos: Sinal[]; resumo: ResumoSinais };
            setAbertos(dados.abertos);
            setResumo(dados.resumo);
          } else if (mensagem.tipo === 'sinais.abertos') {
            setAbertos(mensagem.dados as Sinal[]);
          } else if (mensagem.tipo === 'sinais.novos') {
            const novos = mensagem.dados as Sinal[];
            if (novos.length > 0) setUltimoNovo(novos[0]!);
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

  return { estado, abertos, resumo, ultimoNovo };
}
