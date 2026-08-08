import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import { emR, preco, reais } from '../lib/formato';
import type { Ativo, EntradaPregao, Pregao } from '../lib/tipos';
import { useSinaisAoVivo } from '../lib/useSinaisAoVivo';

const ATIVOS: Ativo[] = ['WIN', 'WDO'];

/**
 * O extrato do dia — o que o motor emitiu antes de você sentar na mesa.
 *
 * Os alertas do WebSocket são um feed do que aconteceu **desde que a aba abriu**. Quem
 * chega às 15h não viu nada da manhã, e para essa pessoa a tela de alertas vazia comunica
 * exatamente a coisa errada: "não houve entrada". Isto lê do banco e mostra que houve.
 *
 * A distinção que o painel faz questão de manter é entre **emitido** e **acionado**. Um
 * sinal que expirou sem o preço chegar na entrada não foi trade nenhum, e somá-lo ao
 * placar inflaria a amostra com operações que não existiram — é assim que produto de sinal
 * costuma parecer melhor do que é.
 */
export function PregaoDeHoje() {
  const [pregoes, setPregoes] = useState<Pregao[]>([]);
  const [carregando, setCarregando] = useState(true);
  const { ticks } = useSinaisAoVivo();

  // Recarrega quando o candle vira: é quando um sinal pode ter nascido, sido acionado ou
  // batido alvo/stop. Entre candles nada aqui muda.
  const gatilho = `${ticks.WIN?.ts ?? ''}|${ticks.WDO?.ts ?? ''}`;

  useEffect(() => {
    let vivo = true;
    Promise.all(
      ATIVOS.map((ativo) =>
        api.get<Pregao>(api.comFiltros('/mercado/pregao', { ativo })).catch(() => null),
      ),
    ).then((resultados) => {
      if (!vivo) return;
      setPregoes(resultados.filter((p): p is Pregao => p !== null));
      setCarregando(false);
    });
    return () => {
      vivo = false;
    };
  }, [gatilho]);

  const entradas = pregoes
    .flatMap((p) => p.entradas)
    .sort((a, b) => a.ts.localeCompare(b.ts));

  const emitidos = pregoes.reduce((s, p) => s + p.placar.emitidos, 0);
  const acionados = pregoes.reduce((s, p) => s + p.placar.acionados, 0);
  const encerrados = pregoes.reduce((s, p) => s + p.placar.encerrados, 0);
  const alvo = pregoes.reduce((s, p) => s + p.placar.alvo, 0);
  const dinheiro = pregoes.reduce((s, p) => s + p.placar.resultadoReais, 0);
  const resultadoR = pregoes.reduce((s, p) => s + p.placar.resultadoR, 0);
  const emCurso = pregoes.some((p) => p.aberto);

  if (carregando) {
    return <p className="text-sm text-texto-fraco">lendo o pregão de hoje…</p>;
  }

  return (
    <section className="cartao px-5 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="titulo-secao mb-0">
          Entradas de hoje{' '}
          <span className="text-xs font-normal text-texto-fraco">
            o que o motor emitiu antes de você chegar
          </span>
        </h2>
        {emCurso && (
          <span className="text-xs text-texto-fraco">
            pregão em curso — parcial, não resultado
          </span>
        )}
      </div>

      {emitidos === 0 ? (
        <p className="mt-3 text-sm text-texto-fraco">
          Nenhuma entrada hoje. Em dois anos de medição, <strong>99,1% das detecções são
          recusadas</strong> — dia sem sinal é o caso comum, não falha da coleta.
        </p>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Numero rotulo="emitidos" valor={String(emitidos)} />
            <Numero
              rotulo="viraram trade"
              valor={String(acionados)}
              nota={acionados < emitidos ? `${emitidos - acionados} não acionaram` : undefined}
            />
            <Numero
              rotulo="encerrados"
              valor={encerrados > 0 ? `${alvo}/${encerrados} no alvo` : '—'}
            />
            <Numero
              rotulo="resultado"
              valor={encerrados > 0 ? reais(dinheiro) : '—'}
              nota={encerrados > 0 ? `${emR(resultadoR)} · já com custo` : undefined}
              tom={encerrados === 0 ? undefined : dinheiro >= 0 ? 'alta' : 'baixa'}
            />
          </div>

          <ol className="mt-4 space-y-2">
            {entradas.map((e) => (
              <LinhaEntrada key={e.id} entrada={e} />
            ))}
          </ol>

          {/*
            O aviso não é disclaimer decorativo. Entre o sinal e a ordem existem deslize,
            liquidez no preço de entrada e a decisão humana de apertar o botão — e sem
            dizer isso o número acima vira promessa de quanto o operador "teria ganhado".
          */}
          <p className="mt-4 border-t border-borda pt-3 text-xs leading-relaxed text-texto-fraco">
            Números do motor sobre os candles que existiam no instante de cada emissão — a
            pipeline é testada contra look-ahead. <strong>Não é o que você teria
            capturado:</strong> falta o deslize da execução, a liquidez no preço da entrada
            e a decisão de operar. O custo por contrato já está descontado.
          </p>
        </>
      )}
    </section>
  );
}

function Numero({
  rotulo,
  valor,
  nota,
  tom,
}: {
  rotulo: string;
  valor: string;
  nota?: string;
  tom?: 'alta' | 'baixa';
}) {
  return (
    <div>
      <p className="rotulo">{rotulo}</p>
      <p
        className={`numerico text-lg font-semibold ${
          tom === 'alta' ? 'text-alta' : tom === 'baixa' ? 'text-baixa' : ''
        }`}
      >
        {valor}
      </p>
      {nota && <p className="text-[11px] text-texto-fraco">{nota}</p>}
    </div>
  );
}

const TOM_STATUS: Record<string, string> = {
  ALVO: 'border-alta/40 bg-alta-fundo/40 text-alta',
  STOP: 'border-baixa/40 bg-baixa-fundo/40 text-baixa',
  ACIONADO: 'border-marca/40 text-marca',
  ABERTO: 'border-borda text-texto-fraco',
  EXPIRADO: 'border-borda text-texto-fraco',
};

const ROTULO_STATUS: Record<string, string> = {
  ALVO: 'alvo',
  STOP: 'stop',
  ACIONADO: 'em curso',
  ABERTO: 'aguardando',
  EXPIRADO: 'não acionou',
};

function LinhaEntrada({ entrada: e }: { entrada: EntradaPregao }) {
  const alta = e.direcao === 'ALTA';

  return (
    <li className="rounded-lg border border-borda px-3 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="numerico text-sm font-semibold">{e.hora}</span>
        <span className="rotulo">{e.ativo}</span>
        <span className={`text-xs font-semibold ${alta ? 'text-alta' : 'text-baixa'}`}>
          {alta ? 'compra' : 'venda'}
        </span>
        <span className="text-sm">{e.padrao}</span>

        <span
          className={`ml-auto rounded-md border px-2 py-0.5 text-xs font-semibold ${
            TOM_STATUS[e.status] ?? 'border-borda text-texto-fraco'
          }`}
        >
          {ROTULO_STATUS[e.status] ?? e.status.toLowerCase()}
          {e.resultadoReais !== null && ` · ${reais(e.resultadoReais)}`}
        </span>
      </div>

      <div className="numerico mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-texto-fraco">
        <span>entrada {preco(e.entrada, e.ativo)}</span>
        <span>stop {preco(e.stop, e.ativo)}</span>
        <span>alvo {preco(e.alvo, e.ativo)}</span>
        <span>R:R {e.rr.toFixed(2)}</span>
        <span>
          {e.contratos} {e.contratos === 1 ? 'contrato' : 'contratos'}
        </span>
        {e.resultadoR !== null && <span>{emR(e.resultadoR)}</span>}
      </div>

      <p className="mt-1 text-xs text-texto-fraco">{e.observacao}</p>
    </li>
  );
}
