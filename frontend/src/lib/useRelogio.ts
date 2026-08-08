import { useEffect, useState } from 'react';

/**
 * Relógio que corre de verdade — um tick por segundo.
 *
 * Existe porque "ao vivo" com um número congelado é pior que não mostrar nada: o operador
 * lê o horário do último fetch como se fosse o relógio, e conclui que a tela travou.
 *
 * O componente que usa isto deve exibir **idade** ("há 12s"), não **horário**. Idade
 * corre sozinha e denuncia dado velho; horário fica igual e engana.
 */
export function useRelogio(intervaloMs = 1000): Date {
  const [agora, setAgora] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setAgora(new Date()), intervaloMs);
    return () => window.clearInterval(timer);
  }, [intervaloMs]);

  return agora;
}

/**
 * `há 12s`, `há 4min`, `há 2h` — sempre relativo ao agora que corre.
 *
 * **O tipo do argumento decide o fuso, e essa distinção não é cosmética.**
 *
 * - `Date` — instante de verdade, criado no navegador (o horário do último fetch).
 *   Compara direto.
 * - `string` — ISO vindo da API, que carrega o relógio de parede do pregão rotulado como
 *   UTC (o Prisma serializa `timestamp without time zone` assim). Comparar cru com o
 *   relógio local subtrai o offset duas vezes: num navegador em −3, um candle de 3h20
 *   aparece como "há 6h". Foi exatamente o que a Mesa mostrou. A correção é medir o agora
 *   no mesmo rótulo. Ver `formato.ts`.
 */
export function idadeDe(instante: string | Date | null, agora: Date): string {
  if (!instante) return '—';

  const alvo = typeof instante === 'string' ? new Date(instante) : instante;
  const referencia =
    typeof instante === 'string'
      ? agora.getTime() - agora.getTimezoneOffset() * 60_000
      : agora.getTime();

  const segundos = Math.max(0, Math.floor((referencia - alvo.getTime()) / 1000));

  if (segundos < 60) return `há ${segundos}s`;
  if (segundos < 3600) return `há ${Math.floor(segundos / 60)}min`;
  if (segundos < 86_400) return `há ${Math.floor(segundos / 3600)}h`;
  return `há ${Math.floor(segundos / 86_400)}d`;
}
