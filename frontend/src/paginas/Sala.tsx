import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

import { CartaoSinal } from '../components/CartaoSinal';
import { Alerta, Carregando } from '../components/ui';
import { api } from '../lib/api';
import { dataHora, preco } from '../lib/formato';
import { idadeDe, useRelogio } from '../lib/useRelogio';
import { useSinaisAoVivo } from '../lib/useSinaisAoVivo';
import type {
  Ativo,
  Conta,
  LeituraTimeframe,
  Raciocinio,
  Sinal,
  TickMercado,
  Vigilancia,
} from '../lib/tipos';

const NOME: Record<Ativo, string> = { WIN: 'Mini-índice', WDO: 'Mini-dólar' };

/**
 * Rede de segurança para quando o WebSocket não estiver entregando.
 *
 * Longo de propósito: com o push funcionando o dossiê é recarregado quando o candle vira,
 * e este timer nunca traz novidade. Ele existe só para a tela não congelar se a conexão
 * cair sem reconectar.
 */
const INTERVALO_MS = 60_000;

/**
 * Sala de Operações — uma por ativo.
 *
 * A tela responde três perguntas, nessa ordem, porque é a ordem em que a decisão acontece:
 *
 * 1. **Tem entrada agora?** — grande, no topo, impossível de não ver.
 * 2. **Se não tem, por quê?** — a lista de padrões recusados com o motivo exato.
 * 3. **O que sustenta essa leitura?** — as contas, por timeframe, com fórmula.
 *
 * A pergunta 2 é o produto. Um robô que só mostra as aprovações pede fé; um que mostra as
 * recusas ensina a operar. Em 60 mil candles, 99,1% das detecções foram recusadas — essa
 * é a informação que o operador precisa ver para confiar quando o motor finalmente aprova.
 */
export function Sala() {
  const { ativo: param } = useParams<{ ativo: string }>();
  const ativo = (param?.toUpperCase() === 'WDO' ? 'WDO' : 'WIN') as Ativo;

  const [raciocinio, setRaciocinio] = useState<Raciocinio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [atualizando, setAtualizando] = useState(false);
  const [ultimaAtualizacao, setUltimaAtualizacao] = useState<Date | null>(null);
  const primeiraCarga = useRef(true);

  const { abertos, ticks } = useSinaisAoVivo();
  const sinaisDoAtivo = abertos.filter((s) => s.ativo === ativo);
  const tick = ticks[ativo];

  const carregar = useCallback(async () => {
    setAtualizando(true);
    try {
      const r = await api.get<Raciocinio>(api.comFiltros('/mercado/raciocinio', { ativo }));
      setRaciocinio(r);
      setUltimaAtualizacao(new Date());
      setErro(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Falha ao ler o motor');
    } finally {
      setAtualizando(false);
      primeiraCarga.current = false;
    }
  }, [ativo]);

  useEffect(() => {
    primeiraCarga.current = true;
    setRaciocinio(null);
  }, [ativo]);

  /**
   * Recarrega o dossiê quando o candle vira — não a cada N segundos.
   *
   * `tick.ts` só muda quando o motor tem algo novo para dizer: o dossiê é derivado do
   * último candle fechado, então recalculá-lo antes disso devolve exatamente a mesma
   * resposta. O preço e a idade que correm no cabeçalho vêm do tick, que o servidor
   * empurra a cada ciclo — é ali que a tela fica viva, e não num `setInterval` que
   * atropela o motor com o mesmo pedido.
   *
   * `tick.ts` é `undefined` até o WebSocket entregar o primeiro estado; a primeira carga
   * acontece nesse momento, ou pelo fallback abaixo se a conexão não subir.
   */
  useEffect(() => {
    void carregar();
  }, [carregar, tick?.ts]);

  /**
   * Rede de segurança para WebSocket fora do ar.
   *
   * Intervalo folgado de propósito: com o push funcionando isto nunca traz novidade, e
   * existe só para a tela não congelar caso a conexão caia sem reconectar.
   */
  useEffect(() => {
    const timer = window.setInterval(() => void carregar(), INTERVALO_MS);
    return () => window.clearInterval(timer);
  }, [carregar]);

  if (primeiraCarga.current && !raciocinio && !erro) {
    return <Carregando texto={`lendo o mercado de ${NOME[ativo]}…`} />;
  }

  return (
    <div className="space-y-5">
      <Cabecalho
        ativo={ativo}
        raciocinio={raciocinio}
        tick={tick}
        atualizando={atualizando}
        ultimaAtualizacao={ultimaAtualizacao}
      />

      {erro && <Alerta tom="erro">{erro}</Alerta>}

      {raciocinio && !raciocinio.dadosFrescos && (
        <Alerta tom="aviso">
          <strong>Esta tela não é o mercado agora.</strong> O candle mais recente tem{' '}
          {raciocinio.idadeMinutos >= 60
            ? `${(raciocinio.idadeMinutos / 60).toFixed(0)} horas`
            : `${raciocinio.idadeMinutos.toFixed(0)} minutos`}
          . Tudo abaixo — contas, níveis, vigilância — descreve aquele instante, não este.{' '}
          {raciocinio.operaAgora
            ? 'Com o pregão aberto, isto quase sempre significa que o MetaTrader 5 está fechado. Abra o terminal: a coleta religa sozinha em até um minuto.'
            : 'O pregão está fechado — a coleta reinicia sozinha às 9h.'}
        </Alerta>
      )}

      {raciocinio && (
        <>
          <Veredito raciocinio={raciocinio} sinais={sinaisDoAtivo} />

          <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
            <div className="space-y-5">
              <PainelVigilancia vigiando={raciocinio.vigiando} />
              <PainelContas timeframes={raciocinio.timeframes} />
            </div>
            <div className="space-y-5">
              <PainelNiveis raciocinio={raciocinio} />
              <PainelEstrutura raciocinio={raciocinio} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Cabecalho({
  ativo,
  raciocinio,
  tick,
  atualizando,
  ultimaAtualizacao,
}: {
  ativo: Ativo;
  raciocinio: Raciocinio | null;
  tick: TickMercado | undefined;
  atualizando: boolean;
  ultimaAtualizacao: Date | null;
}) {
  const agora = useRelogio();

  /**
   * Preço e variação saem do TICK, não do dossiê.
   *
   * O dossiê é recalculado só quando o candle vira — a cada 5 minutos. Se o preço viesse
   * dele, o número no topo da tela ficaria parado cinco minutos e o operador leria como
   * tela travada. O tick chega a cada ciclo do WebSocket e é a coisa mais viva que a
   * plataforma tem. O dossiê continua mandando em tudo que exige o motor.
   */
  const precoAgora = tick?.preco ?? raciocinio?.preco ?? null;
  const variacao = tick?.variacaoDia ?? raciocinio?.variacaoDia ?? null;
  const subiu = (variacao ?? 0) >= 0;

  // Frescura também pelo tick: ela muda a cada segundo, e o dossiê congelaria a resposta
  // no instante do último recálculo.
  const idade = tick?.idadeMinutos ?? raciocinio?.idadeMinutos ?? null;
  const frescos = idade !== null ? idade < 15 : (raciocinio?.dadosFrescos ?? false);

  return (
    <header className="cartao surge flex flex-wrap items-end gap-x-8 gap-y-4 px-6 py-5">
      <div>
        <p className="rotulo">{NOME[ativo]}</p>
        <div className="mt-1 flex items-baseline gap-3">
          <span
            className={`numerico text-4xl font-semibold tracking-tight ${
              frescos ? '' : 'text-texto-suave'
            }`}
          >
            {precoAgora !== null ? preco(precoAgora, ativo) : '—'}
          </span>
          {variacao !== null && (
            <span
              className={`numerico text-lg font-semibold ${subiu ? 'text-alta' : 'text-baixa'}`}
            >
              {subiu ? '+' : ''}
              {variacao.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      {raciocinio && (
        <>
          <Indicador rotulo="Viés" valor={raciocinio.viesDirecao} destaque={raciocinio.alinhado} />
          <Indicador
            rotulo="Pregão"
            valor={raciocinio.operaAgora ? `aberto · ${raciocinio.janelaPregao}` : 'fechado'}
            tom={raciocinio.operaAgora ? 'alta' : 'fraco'}
          />
        </>
      )}

      {/*
        O que corre aqui é a IDADE do último candle, não o horário do último fetch.
        Horário fica congelado entre atualizações e o operador lê como tela travada;
        idade corre sozinha e denuncia dado velho — que é a informação que importa.
      */}
      <div className="ml-auto text-right">
        <span
          className={`flex items-center justify-end gap-1.5 text-xs ${
            frescos ? 'text-texto-fraco' : 'text-aviso'
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              atualizando
                ? 'animate-pulse bg-marca'
                : frescos
                  ? 'animate-pulse bg-alta'
                  : 'bg-aviso'
            }`}
          />
          {atualizando ? 'lendo…' : frescos ? 'ao vivo' : 'dados parados'}
        </span>
        {(tick?.ts ?? raciocinio?.momento) && (
          <span
            className={`numerico mt-0.5 block text-xs ${
              frescos ? 'text-texto-fraco' : 'text-aviso'
            }`}
            title={`Último candle: ${dataHora((tick?.ts ?? raciocinio?.momento) as string)}`}
          >
            candle {idadeDe((tick?.ts ?? raciocinio?.momento) as string, agora)}
          </span>
        )}
        {ultimaAtualizacao && (
          <span className="numerico mt-0.5 block text-[11px] text-texto-fraco opacity-70">
            lido {idadeDe(ultimaAtualizacao, agora)}
          </span>
        )}
      </div>
    </header>
  );
}

function Indicador({
  rotulo,
  valor,
  tom = 'neutro',
  destaque = false,
}: {
  rotulo: string;
  valor: string;
  tom?: 'neutro' | 'alta' | 'fraco';
  destaque?: boolean;
}) {
  const cor = { neutro: 'text-texto', alta: 'text-alta', fraco: 'text-texto-fraco' }[tom];
  return (
    <div>
      <p className="rotulo">{rotulo}</p>
      <p className={`mt-1 text-sm font-medium ${cor}`}>
        {valor}
        {destaque && <span className="ml-1.5 text-xs text-marca">alinhado</span>}
      </p>
    </div>
  );
}

/**
 * O veredito. É a primeira coisa que se lê, e na maior parte do tempo dirá "não entre".
 *
 * Isso é o produto funcionando, não uma tela vazia — e o texto precisa deixar isso óbvio,
 * senão o operador interpreta ausência de sinal como defeito e vai procurar entrada em
 * outro lugar.
 */
function Veredito({ raciocinio, sinais }: { raciocinio: Raciocinio; sinais: Sinal[] }) {
  const temSinal = Boolean(raciocinio.sinal) || sinais.length > 0;

  if (temSinal) {
    return (
      <section className="space-y-3">
        <div className="flex items-center gap-2.5 rounded-xl border border-alta/40 bg-alta-fundo/40 px-5 py-3.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-alta opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-alta" />
          </span>
          <p className="font-semibold text-alta">Entrada aprovada</p>
          <p className="text-sm text-texto-suave">passou por todos os filtros</p>
        </div>
        {sinais.map((s) => (
          <CartaoSinal key={s.id} sinal={s} />
        ))}
      </section>
    );
  }

  return (
    <section className="cartao px-6 py-5">
      <div className="flex items-start gap-3.5">
        <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-texto-fraco" />
        <div>
          <p className="text-lg font-semibold">Sem entrada agora</p>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-texto-suave">
            {raciocinio.veredito}
          </p>
          <p className="mt-2.5 max-w-2xl text-xs leading-relaxed text-texto-fraco">
            Ficar de fora é a resposta na maior parte do tempo. Medido em 2 anos:{' '}
            <strong className="text-texto-suave">99,1% das detecções são recusadas</strong>.
            Abaixo está o motivo de cada uma — é ali que se aprende o critério.
          </p>
        </div>
      </div>
    </section>
  );
}

function PainelVigilancia({ vigiando }: { vigiando: Vigilancia[] }) {
  return (
    <section>
      <h2 className="titulo-secao">
        Sob vigilância
        <span className="ml-2 text-xs font-normal text-texto-fraco">
          padrões na tela e por que ainda não são entrada
        </span>
      </h2>

      {vigiando.length === 0 ? (
        <div className="cartao px-5 py-8 text-center">
          <p className="text-sm text-texto-suave">Nenhum padrão formado neste candle.</p>
          <p className="mt-1 text-xs text-texto-fraco">
            O motor reavalia a cada candle de 5 minutos.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {vigiando.map((v) => (
            <li key={`${v.padrao}-${v.motivo}`} className="cartao px-4 py-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span
                  className={`text-sm font-bold ${
                    v.direcao === 'alta' ? 'text-alta' : v.direcao === 'baixa' ? 'text-baixa' : 'text-texto-fraco'
                  }`}
                >
                  {v.direcao === 'alta' ? '▲' : v.direcao === 'baixa' ? '▼' : '•'}
                </span>
                <span className="font-medium">{v.padrao}</span>
                <span className="numerico text-xs text-texto-fraco">
                  força {v.forca.toFixed(2)} · score {v.score.toFixed(2)}
                </span>
                <span className="ml-auto rounded-md bg-superficie-topo px-2 py-0.5 text-[11px] font-medium text-texto-suave">
                  {v.motivo}
                </span>
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-texto-fraco">{v.faltou}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** As contas por timeframe. Toda `formula` é a procedência do número ao lado. */
function PainelContas({ timeframes }: { timeframes: LeituraTimeframe[] }) {
  const [aberto, setAberto] = useState<string>(timeframes[0]?.timeframe ?? '');

  if (timeframes.length === 0) return null;
  const atual = timeframes.find((t) => t.timeframe === aberto) ?? timeframes[0]!;

  return (
    <section>
      <h2 className="titulo-secao">
        A conta
        <span className="ml-2 text-xs font-normal text-texto-fraco">
          o número, a fórmula e o que ele significa
        </span>
      </h2>

      <div className="cartao overflow-hidden p-0">
        <div className="flex gap-0.5 border-b border-borda p-1.5">
          {timeframes.map((t) => (
            <button
              key={t.timeframe}
              onClick={() => setAberto(t.timeframe)}
              className={`flex-1 rounded-lg px-3 py-2 text-sm transition-colors ${
                t.timeframe === atual.timeframe
                  ? 'bg-superficie-topo text-texto'
                  : 'text-texto-suave hover:text-texto'
              }`}
            >
              <span className="block font-medium">{t.timeframe}</span>
              <span
                className={`block text-[11px] ${
                  t.tendencia === 'alta'
                    ? 'text-alta'
                    : t.tendencia === 'baixa'
                      ? 'text-baixa'
                      : 'text-texto-fraco'
                }`}
              >
                {t.tendencia}
              </span>
            </button>
          ))}
        </div>

        <div className="border-b border-borda px-5 py-3">
          <p className="text-sm text-texto-suave">{atual.regimeMedias}</p>
          <p className="numerico mt-0.5 text-xs text-texto-fraco">
            ATR {atual.atr.toLocaleString('pt-BR')} · força da tendência{' '}
            {(atual.forcaTendencia * 100).toFixed(0)}%
          </p>
        </div>

        <ul className="divide-y divide-borda">
          {atual.contas.map((c) => (
            <ContaLinha key={c.rotulo} conta={c} />
          ))}
        </ul>
      </div>
    </section>
  );
}

function ContaLinha({ conta }: { conta: Conta }) {
  const cor = {
    favoravel: 'text-alta',
    contrario: 'text-baixa',
    neutro: 'text-texto',
  }[conta.tom];

  return (
    <li className="px-5 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <span className="text-sm text-texto-suave">{conta.rotulo}</span>
        <span className={`numerico text-base font-semibold ${cor}`}>{conta.valor}</span>
        {conta.veredito && (
          <span className="ml-auto text-xs text-texto-fraco">{conta.veredito}</span>
        )}
      </div>
      {conta.formula && (
        <p className="numerico mt-1 text-[11px] text-texto-fraco opacity-80">= {conta.formula}</p>
      )}
    </li>
  );
}

/** Níveis ordenados por distância do preço — os que o preço vai encontrar primeiro. */
function PainelNiveis({ raciocinio }: { raciocinio: Raciocinio }) {
  const cores: Record<string, string> = {
    fibonacci: 'bg-marca',
    media: 'bg-neutro',
    estrutura: 'bg-alta',
  };

  return (
    <section>
      <h2 className="titulo-secao">
        Níveis à frente
        <span className="ml-2 text-xs font-normal text-texto-fraco">por distância do preço</span>
      </h2>

      <div className="cartao p-0">
        {raciocinio.niveis.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-texto-fraco">
            Nenhum nível relevante mapeado ainda.
          </p>
        ) : (
          <ul className="divide-y divide-borda">
            {raciocinio.niveis.map((n) => {
              const acima = n.preco > raciocinio.preco;
              const distancia = Math.abs(n.preco - raciocinio.preco);
              return (
                <li key={`${n.origem}-${n.rotulo}-${n.preco}`} className="flex items-center gap-3 px-4 py-2.5">
                  <span className={`h-6 w-0.5 rounded-full ${cores[n.origem] ?? 'bg-neutro'}`} />
                  <div className="min-w-0">
                    <p className="truncate text-sm">{n.rotulo}</p>
                    {n.nota && <p className="truncate text-[11px] text-texto-fraco">{n.nota}</p>}
                  </div>
                  <div className="ml-auto text-right">
                    <p className="numerico text-sm font-medium">
                      {preco(n.preco, raciocinio.ativo)}
                    </p>
                    <p className="numerico text-[11px] text-texto-fraco">
                      {acima ? '↑' : '↓'} {preco(distancia, raciocinio.ativo)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

function PainelEstrutura({ raciocinio }: { raciocinio: Raciocinio }) {
  const { estrutura } = raciocinio;
  return (
    <section>
      <h2 className="titulo-secao">Estrutura</h2>
      <div className="cartao space-y-3 text-[13px]">
        <p className="text-texto-suave">{estrutura.resumo}</p>

        {estrutura.canal ? (
          <p className="text-texto-fraco">
            Canal <span className="text-texto">{estrutura.canal.tipo}</span> ·{' '}
            {estrutura.canal.toques} toques · largura {estrutura.canal.larguraAtr.toFixed(1)} ATR
          </p>
        ) : (
          <p className="text-texto-fraco">
            Sem canal em 5 minutos — medido, só 3,6% das janelas de 5min formam canal, contra
            31% em 60min. Canal é figura de timeframe maior.
          </p>
        )}

        {estrutura.rompimentos.length > 0 && (
          <div>
            <p className="rotulo mb-1">Rompimentos recentes</p>
            {estrutura.rompimentos.slice(-3).map((r) => (
              <p key={r.ts} className="text-texto-suave">
                <span className={r.direcao === 'alta' ? 'text-alta' : 'text-baixa'}>
                  {r.direcao}
                </span>{' '}
                em {preco(r.preco, raciocinio.ativo)} · {r.forcaAtr.toFixed(1)} ATR além da borda
              </p>
            ))}
          </div>
        )}

        <p className="border-t border-borda pt-2.5 text-xs text-texto-fraco">
          Leitura do candle de{' '}
          {new Date(raciocinio.momento).toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}
          .
        </p>
      </div>
    </section>
  );
}
