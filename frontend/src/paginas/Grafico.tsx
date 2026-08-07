import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Alerta, Cartao, Carregando, Titulo, Vazio } from '../components/ui';
import { api } from '../lib/api';
import { preco, ROTULO_TIMEFRAME } from '../lib/formato';
import type { Ativo, Candle, Deteccao, Estrutura, Sinal, Timeframe } from '../lib/tipos';

const ATIVOS: Ativo[] = ['WIN', 'WDO'];
const TIMEFRAMES: Timeframe[] = ['M5', 'M15', 'M30', 'H1'];

/** Paleta do gráfico. Espelha os tokens do CSS — o canvas não lê custom properties. */
const CORES = {
  alta: '#3fd6b0',
  baixa: '#f2657a',
  marca: '#e0b862',
  texto: '#a5b0bd',
  grade: 'rgba(255,255,255,0.035)',
  borda: 'rgba(255,255,255,0.09)',
  canal: '#f2657a',
  demanda: '#3fd6b0',
} as const;

export function Grafico() {
  const [ativo, setAtivo] = useState<Ativo>('WIN');
  const [timeframe, setTimeframe] = useState<Timeframe>('M5');
  const [candles, setCandles] = useState<Candle[]>([]);
  const [deteccoes, setDeteccoes] = useState<Deteccao[]>([]);
  const [sinais, setSinais] = useState<Sinal[]>([]);
  const [estrutura, setEstrutura] = useState<Estrutura | null>(null);
  const [selecionado, setSelecionado] = useState<Sinal | null>(null);
  const [mostrar, setMostrar] = useState({ canal: true, zonas: true, padroes: true });
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    setErro(null);
    setSelecionado(null);

    const filtros = { ativo, timeframe, limite: 600 };
    Promise.all([
      api.get<{ candles: Candle[] }>(api.comFiltros('/mercado/candles', filtros)),
      api.get<Deteccao[]>(api.comFiltros('/mercado/deteccoes', { ...filtros, limite: 300 })),
      api.get<{ itens: Sinal[] }>(api.comFiltros('/sinais', { ativo, timeframe, limite: 60 })),
      api
        .get<Estrutura>(api.comFiltros('/mercado/estrutura', filtros))
        .catch(() => null),
    ])
      .then(([c, d, s, e]) => {
        if (!vivo) return;
        setCandles(c.candles);
        setDeteccoes(d);
        setSinais(s.itens);
        setEstrutura(e);
      })
      .catch((e) => vivo && setErro(e instanceof Error ? e.message : 'Falha ao carregar'))
      .finally(() => vivo && setCarregando(false));

    return () => {
      vivo = false;
    };
  }, [ativo, timeframe]);

  return (
    <div className="space-y-4">
      <header className="surge flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Gráfico</h1>
        <Grupo>
          {ATIVOS.map((a) => (
            <Aba key={a} ativa={ativo === a} onClick={() => setAtivo(a)}>
              {a}
            </Aba>
          ))}
        </Grupo>
        <Grupo>
          {TIMEFRAMES.map((tf) => (
            <Aba key={tf} ativa={timeframe === tf} onClick={() => setTimeframe(tf)}>
              {ROTULO_TIMEFRAME[tf]}
            </Aba>
          ))}
        </Grupo>

        <div className="ml-auto flex flex-wrap items-center gap-3 text-xs">
          {(
            [
              ['canal', 'canal e rompimentos'],
              ['zonas', 'oferta e demanda'],
              ['padroes', 'padrões'],
            ] as const
          ).map(([chave, rotulo]) => (
            <label key={chave} className="flex cursor-pointer items-center gap-1.5 text-texto-suave">
              <input
                type="checkbox"
                checked={mostrar[chave]}
                onChange={(e) => setMostrar({ ...mostrar, [chave]: e.target.checked })}
                className="accent-marca"
              />
              {rotulo}
            </label>
          ))}
        </div>
      </header>

      {erro && <Alerta tom="erro">{erro}</Alerta>}

      {estrutura?.resumo && (
        <Alerta tom="info">
          <strong>Leitura da estrutura:</strong> {estrutura.resumo}
        </Alerta>
      )}

      {carregando ? (
        <Carregando texto="carregando candles e estrutura…" />
      ) : candles.length === 0 ? (
        <Vazio
          titulo={`Sem candles de ${ativo} ${ROTULO_TIMEFRAME[timeframe]}`}
          detalhe="Ligue o coletor com o MetaTrader 5 aberto: .\cronos.ps1 coletor"
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_330px]">
          <Cartao className="overflow-hidden p-0">
            <Velas
              candles={candles}
              deteccoes={mostrar.padroes ? deteccoes : []}
              estrutura={mostrar.canal || mostrar.zonas ? estrutura : null}
              mostrar={mostrar}
              sinal={selecionado}
              ativo={ativo}
            />
            <Legenda estrutura={estrutura} />
          </Cartao>

          <aside className="space-y-4">
            {estrutura && (
              <PainelEstrutura estrutura={estrutura} ativo={ativo} timeframe={timeframe} />
            )}

            <section>
              <Titulo>Sinais neste gráfico</Titulo>
              {sinais.length === 0 ? (
                <p className="cartao px-4 py-6 text-center text-xs text-texto-fraco">
                  Nenhum sinal emitido para {ativo} {ROTULO_TIMEFRAME[timeframe]} ainda.
                </p>
              ) : (
                <ul className="space-y-2">
                  {sinais.map((s) => (
                    <li key={s.id}>
                      <button
                        onClick={() => setSelecionado(selecionado?.id === s.id ? null : s)}
                        className={`w-full rounded-xl border px-3.5 py-2.5 text-left transition-colors ${
                          selecionado?.id === s.id
                            ? 'border-marca bg-superficie-alta'
                            : 'border-borda bg-superficie hover:border-borda-forte'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm">{s.padraoNome}</span>
                          <span
                            className={`text-xs font-bold ${
                              s.direcao === 'ALTA' ? 'text-alta' : 'text-baixa'
                            }`}
                          >
                            {s.direcao === 'ALTA' ? '▲' : '▼'}
                          </span>
                        </div>
                        <p className="numerico mt-0.5 text-xs text-texto-fraco">
                          {preco(s.entrada, s.ativo)} → {preco(s.alvo, s.ativo)} · R:R{' '}
                          {s.rr.toFixed(2)}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}

function Grupo({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-0.5 rounded-xl border border-borda bg-superficie/60 p-0.5">
      {children}
    </div>
  );
}

function Aba({
  ativa,
  onClick,
  children,
}: {
  ativa: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-[10px] px-3 py-1.5 text-sm transition-colors ${
        ativa ? 'bg-superficie-topo text-texto' : 'text-texto-suave hover:text-texto'
      }`}
    >
      {children}
    </button>
  );
}

function Legenda({ estrutura }: { estrutura: Estrutura | null }) {
  if (!estrutura) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-borda px-4 py-2.5 text-xs text-texto-fraco">
      {estrutura.canal && (
        <Item cor={CORES.canal} texto={`canal ${estrutura.canal.tipo}`} />
      )}
      {estrutura.linhaTendencia && <Item cor={CORES.demanda} texto="linha de tendência" />}
      <Item cor={CORES.baixa} texto="zona de oferta" />
      <Item cor={CORES.alta} texto="zona de demanda" />
      <Item cor={CORES.marca} texto="pivô / rompimento" />
    </div>
  );
}

function Item({ cor, texto }: { cor: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-0.5 w-4 rounded-full" style={{ background: cor }} />
      {texto}
    </span>
  );
}

function PainelEstrutura({
  estrutura,
  ativo,
  timeframe,
}: {
  estrutura: Estrutura;
  ativo: Ativo;
  timeframe: Timeframe;
}) {
  const ofertas = estrutura.faixas.filter((f) => f.tipo === 'oferta');
  const demandas = estrutura.faixas.filter((f) => f.tipo === 'demanda');

  return (
    <section>
      <Titulo>Estrutura</Titulo>
      <Cartao className="space-y-3 text-[13px]">
        {estrutura.canal ? (
          <div>
            <p className="rotulo mb-1">Canal</p>
            <p className="text-texto-suave">
              <span className="font-semibold text-texto">{estrutura.canal.tipo}</span> ·{' '}
              {estrutura.canal.toques} toques · largura {estrutura.canal.larguraAtr.toFixed(1)} ATR
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <p className="rotulo">Canal</p>
            <p className="text-texto-fraco">
              Nenhum canal aqui — os pivôs não se alinham o bastante para traçar duas bordas
              que contenham o preço.
            </p>
            {timeframe === 'M5' && (
              <p className="text-texto-fraco">
                Esperado em 5 minutos: medido em 2 anos de WIN, só{' '}
                <span className="text-texto-suave">3,6%</span> das janelas de 5min formam
                canal, contra <span className="text-texto-suave">31%</span> em 60min. Canal é
                figura de timeframe maior.
              </p>
            )}
          </div>
        )}

        {estrutura.rompimentos.length > 0 && (
          <div>
            <p className="rotulo mb-1">Rompimentos</p>
            <ul className="space-y-0.5">
              {estrutura.rompimentos.slice(-3).map((r) => (
                <li key={r.ts} className="text-texto-suave">
                  <span className={r.direcao === 'alta' ? 'text-alta' : 'text-baixa'}>
                    {r.direcao}
                  </span>{' '}
                  em <span className="numerico">{preco(r.preco, ativo)}</span> ·{' '}
                  {r.forcaAtr.toFixed(1)} ATR além da borda
                </li>
              ))}
            </ul>
          </div>
        )}

        {(ofertas.length > 0 || demandas.length > 0) && (
          <div>
            <p className="rotulo mb-1">Zonas</p>
            <ul className="space-y-1">
              {[...ofertas, ...demandas].map((f) => (
                <li key={`${f.tipo}-${f.precoMin}`} className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-sm ${
                      f.tipo === 'oferta' ? 'bg-baixa' : 'bg-alta'
                    }`}
                  />
                  <span className="numerico text-texto-suave">
                    {preco(f.precoMin, ativo)} – {preco(f.precoMax, ativo)}
                  </span>
                  <span className="ml-auto text-xs text-texto-fraco">{f.toques} toques</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Cartao>
    </section>
  );
}

/**
 * Gráfico de candles anotado — canal, pivôs, rompimentos, zonas e níveis do sinal.
 *
 * `lightweight-charts` é imperativo e não reage a props: o gráfico é criado uma vez e
 * atualizado por efeito. Recriá-lo a cada render perderia o zoom e o posicionamento do
 * usuário a cada atualização de dados, o que é inaceitável em algo que se fica olhando.
 *
 * As anotações usam três mecanismos diferentes, cada um pela razão certa:
 * - **séries de linha** para canal e tendência, que precisam ser inclinadas;
 * - **price lines** para zonas e níveis do sinal, que são horizontais e ganham rótulo no eixo;
 * - **markers** para pivôs e rompimentos, que são eventos num candle específico.
 */
function Velas({
  candles,
  deteccoes,
  estrutura,
  mostrar,
  sinal,
  ativo,
}: {
  candles: Candle[];
  deteccoes: Deteccao[];
  estrutura: Estrutura | null;
  mostrar: { canal: boolean; zonas: boolean; padroes: boolean };
  sinal: Sinal | null;
  ativo: Ativo;
}) {
  const container = useRef<HTMLDivElement>(null);
  const grafico = useRef<IChartApi | null>(null);
  const velas = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const linhas = useRef<ISeriesApi<'Line'>[]>([]);
  const niveis = useRef<ReturnType<ISeriesApi<'Candlestick'>['createPriceLine']>[]>([]);

  useEffect(() => {
    if (!container.current) return;

    const chart = createChart(container.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: CORES.texto,
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CORES.grade },
        horzLines: { color: CORES.grade },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: CORES.borda, scaleMargins: { top: 0.12, bottom: 0.12 } },
      timeScale: { borderColor: CORES.borda, timeVisible: true, secondsVisible: false },
      localization: { locale: 'pt-BR', priceFormatter: (v: number) => preco(v, ativo) },
      height: 620,
    });

    const serie = chart.addCandlestickSeries({
      upColor: CORES.alta,
      downColor: CORES.baixa,
      borderUpColor: CORES.alta,
      borderDownColor: CORES.baixa,
      wickUpColor: CORES.alta,
      wickDownColor: CORES.baixa,
    });

    grafico.current = chart;
    velas.current = serie;

    const observador = new ResizeObserver(() => {
      if (container.current) chart.applyOptions({ width: container.current.clientWidth });
    });
    observador.observe(container.current);

    return () => {
      observador.disconnect();
      chart.remove();
      grafico.current = null;
      velas.current = null;
      linhas.current = [];
      niveis.current = [];
    };
  }, [ativo]);

  const dados = useMemo(
    () =>
      candles.map((c) => ({
        time: (new Date(c.ts).getTime() / 1000) as UTCTimestamp,
        open: c.abertura,
        high: c.maxima,
        low: c.minima,
        close: c.fechamento,
      })),
    [candles],
  );

  useEffect(() => {
    velas.current?.setData(dados);
    grafico.current?.timeScale().fitContent();
  }, [dados]);

  // --- canal, linha de tendência e rompimentos ---
  useEffect(() => {
    const chart = grafico.current;
    const serie = velas.current;
    if (!chart || !serie) return;

    for (const l of linhas.current) chart.removeSeries(l);
    linhas.current = [];
    if (!estrutura) return;

    const segundos = (iso: string) => (new Date(iso).getTime() / 1000) as UTCTimestamp;

    const desenharReta = (
      reta: NonNullable<Estrutura['linhaTendencia']>,
      cor: string,
      titulo: string,
      tracejado = false,
    ) => {
      if (!reta.de.ts || !reta.ate.ts) return;
      const linha = chart.addLineSeries({
        color: cor,
        lineWidth: 2,
        lineStyle: tracejado ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        title: titulo,
      });
      linha.setData([
        { time: segundos(reta.de.ts), value: reta.de.preco },
        { time: segundos(reta.ate.ts), value: reta.ate.preco },
      ]);
      linhas.current.push(linha);
    };

    if (mostrar.canal && estrutura.canal) {
      const { canal } = estrutura;
      desenharReta(canal.topo, CORES.canal, `canal ${canal.tipo}`);
      desenharReta(canal.fundo, CORES.canal, '');
    }
    if (mostrar.canal && estrutura.linhaTendencia) {
      desenharReta(estrutura.linhaTendencia, CORES.demanda, 'tendência', true);
    }
  }, [estrutura, mostrar.canal]);

  // --- zonas de oferta/demanda e níveis do sinal ---
  useEffect(() => {
    const serie = velas.current;
    if (!serie) return;

    for (const n of niveis.current) serie.removePriceLine(n);
    niveis.current = [];

    if (estrutura && mostrar.zonas) {
      for (const f of estrutura.faixas) {
        const cor = f.tipo === 'oferta' ? CORES.baixa : CORES.alta;
        // Duas linhas por zona — a faixa entre elas é a região, não um preço exato.
        for (const [preco_, rotulo] of [
          [f.precoMax, f.tipo === 'oferta' ? 'oferta' : ''],
          [f.precoMin, f.tipo === 'demanda' ? 'demanda' : ''],
        ] as const) {
          niveis.current.push(
            serie.createPriceLine({
              price: preco_,
              color: cor,
              lineWidth: 1,
              lineStyle: LineStyle.Dotted,
              axisLabelVisible: Boolean(rotulo),
              title: rotulo,
            }),
          );
        }
      }
    }

    if (sinal) {
      for (const n of [
        { price: sinal.entrada, color: CORES.marca, title: 'entrada' },
        { price: sinal.stop, color: CORES.baixa, title: 'stop' },
        { price: sinal.alvo, color: CORES.alta, title: 'alvo' },
      ]) {
        niveis.current.push(
          serie.createPriceLine({
            price: n.price,
            color: n.color,
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: n.title,
          }),
        );
      }
    }
  }, [estrutura, mostrar.zonas, sinal]);

  // --- marcadores: pivôs, rompimentos e padrões ---
  useEffect(() => {
    const serie = velas.current;
    if (!serie) return;

    type Marca = Parameters<typeof serie.setMarkers>[0][number];
    const marcas: Marca[] = [];
    const segundos = (iso: string) => (new Date(iso).getTime() / 1000) as UTCTimestamp;

    if (estrutura && mostrar.canal) {
      for (const p of estrutura.pivos.slice(-24)) {
        if (!p.ts) continue;
        marcas.push({
          time: segundos(p.ts),
          position: p.tipo === 'topo' ? 'aboveBar' : 'belowBar',
          color: CORES.marca,
          shape: 'circle',
          text: 'pivô',
        });
      }
      for (const r of estrutura.rompimentos.slice(-6)) {
        if (!r.ts) continue;
        marcas.push({
          time: segundos(r.ts),
          position: r.direcao === 'alta' ? 'belowBar' : 'aboveBar',
          color: r.direcao === 'alta' ? CORES.alta : CORES.baixa,
          shape: r.direcao === 'alta' ? 'arrowUp' : 'arrowDown',
          text: 'ROMPIMENTO',
        });
      }
    }

    if (mostrar.padroes) {
      // Teto de 90: acima disso o gráfico vira uma sopa de setas e nenhuma comunica nada.
      for (const d of deteccoes.slice(-90)) {
        marcas.push({
          time: segundos(d.ts),
          position: d.direcao === 'alta' ? 'belowBar' : 'aboveBar',
          color: d.direcao === 'alta' ? CORES.alta : d.direcao === 'baixa' ? CORES.baixa : CORES.texto,
          shape: d.direcao === 'alta' ? 'arrowUp' : 'arrowDown',
          text: d.padraoNome,
        });
      }
    }

    marcas.sort((a, b) => (a.time as number) - (b.time as number));
    serie.setMarkers(marcas);
  }, [deteccoes, estrutura, mostrar.canal, mostrar.padroes]);

  return <div ref={container} className="w-full" />;
}
