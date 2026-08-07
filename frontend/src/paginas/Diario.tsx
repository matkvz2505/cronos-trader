import { useEffect, useState } from 'react';

import { Alerta, Carregando } from '../components/ui';
import { api } from '../lib/api';
import { emR, percentual, preco, reais } from '../lib/formato';
import type { Ativo, Fechamento, PeriodoDiario } from '../lib/tipos';

const ATIVOS: Ativo[] = ['WIN', 'WDO'];
const NOME: Record<Ativo, string> = { WIN: 'Mini-índice', WDO: 'Mini-dólar' };

const PERIODOS: Array<{ id: PeriodoDiario; titulo: string; sub: string }> = [
  { id: 'dia', titulo: 'Pregão', sub: 'o que aconteceu hoje' },
  { id: 'semana', titulo: 'Semana', sub: 'está se repetindo?' },
  { id: 'mes', titulo: 'Mês', sub: 'fechamento' },
];

/**
 * Diário — fechar o dia com número, abrir o seguinte com plano.
 *
 * É a rotina que separa quem opera de quem aposta, e as duas metades precisam de telas
 * diferentes: o fechamento olha para trás e é feito de contagem; a preparação olha para
 * frente e é feita de níveis. Misturar as duas produz um relatório que ninguém lê.
 */
export function Diario() {
  const [ativo, setAtivo] = useState<Ativo>('WIN');
  const [periodo, setPeriodo] = useState<PeriodoDiario>('dia');
  const [dados, setDados] = useState<Fechamento | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    setErro(null);
    api
      .get<Fechamento>(api.comFiltros('/mercado/diario', { ativo, periodo }))
      .then((d) => vivo && setDados(d))
      .catch((e) => vivo && setErro(e instanceof Error ? e.message : 'Falha ao montar o diário'))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, [ativo, periodo]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Diário</h1>
          <p className="mt-0.5 text-sm text-texto-suave">
            Fechamento do período e o que o próximo pregão começa olhando.
          </p>
        </div>
        <div className="flex gap-0.5 rounded-xl border border-borda bg-superficie/60 p-0.5">
          {ATIVOS.map((a) => (
            <button
              key={a}
              onClick={() => setAtivo(a)}
              className={`rounded-lg px-4 py-1.5 text-sm transition-colors ${
                ativo === a ? 'bg-superficie-topo text-texto' : 'text-texto-suave hover:text-texto'
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      </header>

      <nav className="flex gap-0.5 rounded-xl border border-borda bg-superficie/60 p-1">
        {PERIODOS.map((p) => (
          <button
            key={p.id}
            onClick={() => setPeriodo(p.id)}
            className={`flex-1 rounded-lg px-4 py-2.5 text-left transition-colors ${
              periodo === p.id ? 'bg-superficie-topo text-texto' : 'text-texto-suave hover:text-texto'
            }`}
          >
            <span className="block text-sm font-medium">{p.titulo}</span>
            <span className="block text-[11px] text-texto-fraco">{p.sub}</span>
          </button>
        ))}
      </nav>

      {erro && <Alerta tom="erro">{erro}</Alerta>}
      {carregando && <Carregando texto={`fechando o ${periodo} de ${NOME[ativo]}…`} />}

      {!carregando && dados && (
        <>
          <Movimento dados={dados} ativo={ativo} />
          <Placar dados={dados} />
          {dados.destaques.length > 0 && <Destaques itens={dados.destaques} />}

          <div className="grid gap-5 lg:grid-cols-2">
            <Tabela titulo="Por padrão" linhas={dados.porPadrao} vazio="Nenhuma operação encerrada no período." />
            <Tabela titulo="Por janela do pregão" linhas={dados.porJanela} vazio="Sem operações com janela registrada." />
          </div>

          <Preparacao dados={dados} ativo={ativo} />
          <Rotina />
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Movimento({ dados, ativo }: { dados: Fechamento; ativo: Ativo }) {
  const m = dados.movimento;
  if (!m) {
    return (
      <Alerta tom="aviso">
        Sem candles no período. O coletor não estava rodando — não há o que fechar.
      </Alerta>
    );
  }

  const subiu = m.variacaoPct >= 0;
  return (
    <section className="cartao surge px-6 py-5">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <p className="rotulo">Fechamento</p>
          <div className="mt-1 flex items-baseline gap-3">
            <span className="numerico text-3xl font-semibold tracking-tight">
              {preco(m.fechamento, ativo)}
            </span>
            <span className={`numerico text-lg font-semibold ${subiu ? 'text-alta' : 'text-baixa'}`}>
              {subiu ? '+' : ''}
              {m.variacaoPct.toFixed(2)}%
            </span>
          </div>
        </div>
        <Campo rotulo="Abertura" valor={preco(m.abertura, ativo)} />
        <Campo rotulo="Máxima" valor={preco(m.maxima, ativo)} tom="alta" />
        <Campo rotulo="Mínima" valor={preco(m.minima, ativo)} tom="baixa" />
        <Campo
          rotulo="Amplitude"
          valor={`${preco(m.amplitude, ativo)} · ${m.amplitudeAtr.toFixed(1)} ATR`}
        />
        <Campo
          rotulo="Cobertura"
          valor={`${m.candles} candles · ${m.pregoes} pregão(ões)`}
        />
      </div>
    </section>
  );
}

function Campo({
  rotulo,
  valor,
  tom = 'neutro',
}: {
  rotulo: string;
  valor: string;
  tom?: 'neutro' | 'alta' | 'baixa';
}) {
  const cor = { neutro: 'text-texto', alta: 'text-alta', baixa: 'text-baixa' }[tom];
  return (
    <div>
      <p className="rotulo">{rotulo}</p>
      <p className={`numerico mt-1 text-sm font-medium ${cor}`}>{valor}</p>
    </div>
  );
}

function Placar({ dados }: { dados: Fechamento }) {
  const p = dados.placar;
  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-6">
      <Numero rotulo="Emitidos" valor={String(p.emitidos)} />
      <Numero
        rotulo="Acionados"
        valor={String(p.acionados)}
        detalhe={p.emitidos > 0 ? percentual(p.taxaAcionamento, 0) : undefined}
      />
      <Numero rotulo="No alvo" valor={String(p.alvo)} tom="alta" />
      <Numero rotulo="No stop" valor={String(p.stop)} tom="baixa" />
      <Numero
        rotulo="Expectância"
        valor={p.encerrados > 0 ? emR(p.expectanciaR) : '—'}
        tom={p.expectanciaR >= 0 ? 'alta' : 'baixa'}
        aviso={p.encerrados > 0 && !p.amostraSuficiente}
      />
      <Numero
        rotulo="Resultado"
        valor={p.encerrados > 0 ? reais(p.resultadoReais) : '—'}
        tom={p.resultadoReais >= 0 ? 'alta' : 'baixa'}
      />
    </section>
  );
}

function Numero({
  rotulo,
  valor,
  detalhe,
  tom = 'neutro',
  aviso = false,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  tom?: 'neutro' | 'alta' | 'baixa';
  aviso?: boolean;
}) {
  const cor = { neutro: 'text-texto', alta: 'text-alta', baixa: 'text-baixa' }[tom];
  return (
    <div className="cartao px-4 py-3">
      <p className="rotulo">{rotulo}</p>
      <p className={`numerico mt-0.5 text-xl font-semibold ${cor}`}>{valor}</p>
      {detalhe && <p className="numerico text-[11px] text-texto-fraco">{detalhe}</p>}
      {aviso && <p className="mt-0.5 text-[11px] text-aviso">n &lt; 30</p>}
    </div>
  );
}

function Destaques({ itens }: { itens: string[] }) {
  return (
    <section>
      <h2 className="titulo-secao">O que os números dizem</h2>
      <ul className="cartao space-y-2 px-5 py-4">
        {itens.map((t) => (
          <li key={t} className="flex gap-2.5 text-[13px] leading-relaxed text-texto-suave">
            <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-marca" />
            <span>{t}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Tabela({
  titulo,
  linhas,
  vazio,
}: {
  titulo: string;
  linhas: Fechamento['porPadrao'];
  vazio: string;
}) {
  return (
    <section>
      <h2 className="titulo-secao">{titulo}</h2>
      <div className="cartao p-0">
        {linhas.length === 0 ? (
          <p className="px-5 py-8 text-center text-xs text-texto-fraco">{vazio}</p>
        ) : (
          <ul className="divide-y divide-borda">
            {linhas.map((l) => (
              <li key={l.chave} className="flex items-center gap-3 px-4 py-2.5">
                <span className="min-w-0 flex-1 truncate text-sm">{l.chave}</span>
                <span className="numerico text-xs text-texto-fraco">
                  {l.acertos}/{l.n} · {percentual(l.taxa, 0)}
                </span>
                <span
                  className={`numerico w-16 text-right text-sm font-semibold ${
                    l.expectanciaR >= 0 ? 'text-alta' : 'text-baixa'
                  }`}
                >
                  {emR(l.expectanciaR)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/** A metade que olha para frente: os preços que amanhã começa observando. */
function Preparacao({ dados, ativo }: { dados: Fechamento; ativo: Ativo }) {
  const cores: Record<string, string> = {
    pregao: 'bg-marca',
    media: 'bg-neutro',
    estrutura: 'bg-alta',
    fibonacci: 'bg-baixa',
  };

  const dataProximo = new Date(`${dados.proximoPregao}T00:00:00`).toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: '2-digit',
    month: '2-digit',
  });

  return (
    <section>
      <h2 className="titulo-secao">
        Preparação para {dataProximo}
        <span className="ml-2 text-xs font-normal text-texto-fraco">
          níveis ordenados por distância do fechamento
        </span>
      </h2>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="cartao p-0">
          {dados.niveisAmanha.length === 0 ? (
            <p className="px-5 py-8 text-center text-xs text-texto-fraco">
              Sem níveis mapeados — histórico insuficiente.
            </p>
          ) : (
            <ul className="divide-y divide-borda">
              {dados.niveisAmanha.map((n) => (
                <li key={`${n.origem}-${n.rotulo}-${n.preco}`} className="flex items-center gap-3 px-4 py-2.5">
                  <span className={`h-6 w-0.5 rounded-full ${cores[n.origem] ?? 'bg-neutro'}`} />
                  <div className="min-w-0">
                    <p className="truncate text-sm">{n.rotulo}</p>
                    {n.nota && <p className="text-[11px] text-texto-fraco">{n.nota}</p>}
                  </div>
                  <span className="numerico ml-auto text-sm font-medium">
                    {preco(n.preco, ativo)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="cartao space-y-2.5 text-[13px]">
          <p className="rotulo">Como o mercado chegou aqui</p>
          {dados.contextoAtual.tendencia ? (
            <>
              <p className="text-texto-suave">
                Tendência <span className="text-texto">{dados.contextoAtual.tendencia}</span> com{' '}
                {percentual(dados.contextoAtual.forcaTendencia ?? 0, 0)} de força.
              </p>
              <p className="text-texto-suave">{dados.contextoAtual.regimeMedias}</p>
              <p className="numerico text-texto-fraco">
                ATR de referência: {dados.contextoAtual.atr?.toLocaleString('pt-BR')}
              </p>
              <p className="border-t border-borda pt-2.5 text-xs text-texto-fraco">
                Use o ATR para dimensionar o stop: a folga padrão do motor é 0,25 ATR além do
                extremo do padrão.
              </p>
            </>
          ) : (
            <p className="text-texto-fraco">Histórico insuficiente para descrever o contexto.</p>
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * A rotina — ancorada no que foi medido **neste projeto**, não em conselho genérico.
 *
 * Cada item traz o número que o sustenta. Regra sem número é opinião, e opinião é o que
 * este produto existe para substituir.
 */
function Rotina() {
  const itens = [
    {
      titulo: 'Antes de abrir a tela',
      corpo:
        'Confirme que o coletor está rodando e que a idade do candle é de segundos. Tela "ao vivo" com dado de ontem é o erro mais caro possível — ela parece certa.',
    },
    {
      titulo: 'Evite as 10h–12h',
      corpo:
        'Medido em 205 operações de WIN: −0,28R por operação, −R$ 11.948 no período. É a pior janela do dia, e era justamente a que eu tinha priorizado por intuição antes de medir.',
    },
    {
      titulo: 'A janela que rende é 14h–16h',
      corpo:
        'Abertura americana: 115 operações, 58,3% de acerto, +0,40R. É a única janela claramente positiva na série de 2 anos.',
    },
    {
      titulo: 'Não filtre por taxa de acerto',
      corpo:
        'O Engolfo de Alta acerta 47,6% e tem expectância positiva (+0,18R) porque o R:R mínimo de 1,5 faz os acertos serem maiores que os erros. Filtrar por "acerto > 50%" excluiria o único padrão com vantagem medida.',
    },
    {
      titulo: 'Respeite o limite diário',
      corpo:
        'Seis operações por dia e 3% de perda máxima. O teto de trades é o freio menos intuitivo e o mais útil: over-trading é a causa mais comum de ruína, e nenhum score alto justifica o sétimo trade.',
    },
    {
      titulo: 'Feche o dia aqui',
      corpo:
        'Registre o que operou e o que ignorou. O placar por padrão só vira evidência com 30+ operações — até lá cada dia é uma amostra a mais, não um veredito.',
    },
  ];

  return (
    <section>
      <h2 className="titulo-secao">
        Rotina
        <span className="ml-2 text-xs font-normal text-texto-fraco">
          cada regra com o número que a sustenta
        </span>
      </h2>
      <ol className="grid gap-2 md:grid-cols-2">
        {itens.map((i, idx) => (
          <li key={i.titulo} className="cartao px-4 py-3.5">
            <p className="flex items-baseline gap-2 text-sm font-semibold">
              <span className="numerico text-xs text-marca">{String(idx + 1).padStart(2, '0')}</span>
              {i.titulo}
            </p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-texto-suave">{i.corpo}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
