import { useEffect, useMemo, useState } from 'react';

import { Alerta, Botao, Carregando } from '../components/ui';
import { api, ErroApi } from '../lib/api';
import { emR, percentual } from '../lib/formato';
import type { Ativo, DesempenhoPadrao, PadraoCatalogo, ResultadoBacktest, Timeframe } from '../lib/tipos';

type Aba = 'padroes' | 'estudos' | 'validacao';

/**
 * Conhecimento — o que o motor sabe, e de onde tirou.
 *
 * Consolida três telas que antes existiam separadas (Padrões, Estudos, Backtest) e que,
 * separadas, pareciam painéis de teste: tabelões de número solto sem contexto. Juntas
 * viram uma coisa só com um propósito claro — **auditar o motor**.
 *
 * A ordem das abas é a da confiança: o que ele detecta, o que foi medido sobre isso, e
 * se sobrevive fora da amostra.
 */
export function Conhecimento() {
  const [aba, setAba] = useState<Aba>('padroes');

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Conhecimento</h1>
        <p className="mt-0.5 max-w-2xl text-sm text-texto-suave">
          O que o motor detecta, o que foi medido sobre isso, e se sobrevive fora da amostra.
          Todo número aqui é reproduzível — nada foi arbitrado.
        </p>
      </header>

      <nav className="flex gap-0.5 rounded-xl border border-borda bg-superficie/60 p-1">
        {(
          [
            ['padroes', 'Padrões', 'os 60 detectores'],
            ['estudos', 'Medições', 'o que os dados disseram'],
            ['validacao', 'Validação', 'fora da amostra'],
          ] as const
        ).map(([id, titulo, sub]) => (
          <button
            key={id}
            onClick={() => setAba(id)}
            className={`flex-1 rounded-lg px-4 py-2.5 text-left transition-colors ${
              aba === id ? 'bg-superficie-topo text-texto' : 'text-texto-suave hover:text-texto'
            }`}
          >
            <span className="block text-sm font-medium">{titulo}</span>
            <span className="block text-[11px] text-texto-fraco">{sub}</span>
          </button>
        ))}
      </nav>

      {aba === 'padroes' && <AbaPadroes />}
      {aba === 'estudos' && <AbaEstudos />}
      {aba === 'validacao' && <AbaValidacao />}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function AbaPadroes() {
  const [padroes, setPadroes] = useState<PadraoCatalogo[]>([]);
  const [desempenho, setDesempenho] = useState<DesempenhoPadrao[]>([]);
  const [familia, setFamilia] = useState('');
  const [busca, setBusca] = useState('');
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<{ padroes: PadraoCatalogo[] }>('/mercado/padroes'),
      api.get<DesempenhoPadrao[]>('/sinais/desempenho').catch(() => []),
    ])
      .then(([p, d]) => {
        setPadroes(p.padroes);
        setDesempenho(d);
      })
      .finally(() => setCarregando(false));
  }, []);

  const porId = useMemo(
    () => new Map(desempenho.map((d) => [d.padraoId, d])),
    [desempenho],
  );

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return padroes.filter(
      (p) =>
        (!familia || p.familia === familia) &&
        (!termo || p.nome.toLowerCase().includes(termo)),
    );
  }, [padroes, familia, busca]);

  if (carregando) return <Carregando texto="carregando catálogo…" />;

  return (
    <div className="space-y-4">
      <Alerta tom="info">
        <strong>Confiabilidade do ebook é palpite, não evidência.</strong> A coluna "medido" só
        aparece quando há 30+ operações encerradas daquele padrão. Até lá o motor usa o palpite
        — e a tela diz que é palpite.
      </Alerta>

      <div className="flex flex-wrap items-center gap-2">
        {[
          ['', 'Todos'],
          ['reversao', 'Reversão'],
          ['continuacao', 'Continuação'],
          ['isolado', 'Isolados'],
        ].map(([id, rotulo]) => (
          <button
            key={id}
            onClick={() => setFamilia(id!)}
            className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
              familia === id ? 'bg-superficie-topo text-texto' : 'text-texto-suave hover:text-texto'
            }`}
          >
            {rotulo}
          </button>
        ))}
        <input
          className="campo ml-auto w-56"
          placeholder="Buscar padrão…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <ul className="grid gap-2 md:grid-cols-2">
        {filtrados.map((p) => {
          const medido = porId.get(p.id);
          return (
            <li key={p.id} className="cartao px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{p.nome}</p>
                  <p className="mt-0.5 text-[11px] text-texto-fraco">
                    {p.n_candles} candle{p.n_candles > 1 ? 's' : ''} ·{' '}
                    {p.tendencia_requerida ?? 'qualquer tendência'} · p.{p.pagina_ebook}
                  </p>
                </div>
                <span
                  className={`shrink-0 text-xs font-bold ${
                    p.direcao === 'alta' ? 'text-alta' : p.direcao === 'baixa' ? 'text-baixa' : 'text-texto-fraco'
                  }`}
                >
                  {p.direcao === 'alta' ? '▲' : p.direcao === 'baixa' ? '▼' : '•'}
                </span>
              </div>

              <div className="mt-2.5 flex items-center gap-4 border-t border-borda pt-2 text-xs">
                <span className="text-texto-fraco">
                  palpite <span className="numerico text-texto-suave">{p.confiabilidade_ebook.toFixed(2)}</span>
                </span>
                {medido && medido.ocorrencias > 0 ? (
                  <span className="text-texto-fraco">
                    medido{' '}
                    <span
                      className={`numerico ${medido.expectanciaR >= 0 ? 'text-alta' : 'text-baixa'}`}
                    >
                      {emR(medido.expectanciaR)}
                    </span>{' '}
                    <span className="text-texto-fraco">n={medido.ocorrencias}</span>
                    {!medido.suficiente && <span className="ml-1 text-aviso">·  n baixo</span>}
                  </span>
                ) : (
                  <span className="text-texto-fraco">sem operações ainda</span>
                )}
                {p.exige_gap && <span className="ml-auto text-aviso">gap</span>}
              </div>

              {p.observacao && (
                <p className="mt-2 text-[11px] leading-relaxed text-texto-fraco">{p.observacao}</p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function AbaEstudos() {
  const [estudos, setEstudos] = useState<Record<string, unknown> | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    api
      .get<Record<string, unknown>>('/mercado/estudos')
      .then(setEstudos)
      .catch(() => {})
      .finally(() => setCarregando(false));
  }, []);

  if (carregando) return <Carregando />;

  const fib = (estudos?.fibonacci ?? {}) as Record<string, Record<string, number>>;
  const janelas = (estudos?.janelas ?? {}) as Record<string, { n: number; expectanciaR: number }>;

  return (
    <div className="space-y-5">
      <section>
        <h2 className="titulo-secao">
          Fibonacci
          <span className="ml-2 text-xs font-normal text-texto-fraco">
            quanto cada nível se destaca da vizinhança
          </span>
        </h2>
        <div className="cartao space-y-3">
          <p className="text-[13px] leading-relaxed text-texto-suave">
            A literatura repete 38,2 / 50 / 61,8 para tudo. Medido em ~2.400 correções por ativo,
            só um nível se destaca de verdade — e não é nenhum dos dois mais citados.
          </p>
          {Object.entries(fib).map(([ativo, niveis]) => (
            <div key={ativo}>
              <p className="rotulo mb-1.5">{ativo}</p>
              {Object.keys(niveis).length === 0 ? (
                <p className="text-xs text-texto-fraco">
                  Nenhum nível passou no corte. O motor não dá bônus de Fibonacci a este ativo.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(niveis).map(([nivel, razao]) => (
                    <span
                      key={nivel}
                      className="numerico rounded-lg bg-marca-fundo px-2.5 py-1 text-xs text-marca"
                    >
                      {nivel} · {razao.toFixed(2)}×
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {Object.keys(janelas).length > 0 && (
        <section>
          <h2 className="titulo-secao">
            Janelas do pregão
            <span className="ml-2 text-xs font-normal text-texto-fraco">medido em WIN</span>
          </h2>
          <div className="cartao p-0">
            <ul className="divide-y divide-borda">
              {Object.entries(janelas)
                .sort((a, b) => b[1].expectanciaR - a[1].expectanciaR)
                .map(([nome, d]) => (
                  <li key={nome} className="flex items-center gap-3 px-4 py-2.5">
                    <span className="text-sm">{nome}</span>
                    <span className="text-xs text-texto-fraco">n={d.n}</span>
                    <span
                      className={`numerico ml-auto text-sm font-semibold ${
                        d.expectanciaR >= 0 ? 'text-alta' : 'text-baixa'
                      }`}
                    >
                      {emR(d.expectanciaR)}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
          {typeof estudos?.avisoJanelas === 'string' && (
            <Alerta tom="aviso" className="mt-3">
              {estudos.avisoJanelas}
            </Alerta>
          )}
        </section>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function AbaValidacao() {
  const [config, setConfig] = useState({
    ativo: 'WIN' as Ativo,
    timeframe: 'M5' as Timeframe,
    capital: 20_000,
    modo: 'walkforward' as const,
    janelas: 5,
  });
  const [resultado, setResultado] = useState<ResultadoBacktest | null>(null);
  const [rodando, setRodando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function rodar() {
    setRodando(true);
    setErro(null);
    setResultado(null);
    try {
      setResultado(await api.post<ResultadoBacktest>('/backtest', config));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : 'Falha ao validar');
    } finally {
      setRodando(false);
    }
  }

  return (
    <div className="space-y-4">
      <Alerta tom="info">
        <strong>Walk-forward é o único modo que vale.</strong> Calibrar e medir na mesma série é
        memorização, não evidência. Aqui o motor treina numa janela e mede na seguinte — só o
        resultado <em>fora da amostra</em> diz algo sobre o futuro.
      </Alerta>

      <div className="cartao flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="rotulo mb-1 block">Ativo</span>
          <select
            className="campo w-28"
            value={config.ativo}
            onChange={(e) => setConfig({ ...config, ativo: e.target.value as Ativo })}
          >
            <option value="WIN">WIN</option>
            <option value="WDO">WDO</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="rotulo mb-1 block">Janelas</span>
          <input
            type="number"
            min={2}
            max={12}
            className="campo numerico w-24"
            value={config.janelas}
            onChange={(e) => setConfig({ ...config, janelas: Number(e.target.value) })}
          />
        </label>
        <Botao onClick={rodar} disabled={rodando} className="ml-auto">
          {rodando ? 'Validando…' : 'Rodar validação'}
        </Botao>
      </div>

      {rodando && (
        <p className="text-sm text-texto-fraco">
          Simulando candle a candle, sem look-ahead. Uma série de 2 anos leva alguns minutos.
        </p>
      )}
      {erro && <Alerta tom="erro">{erro}</Alerta>}

      {resultado && (
        <>
          <div className="cartao px-5 py-4">
            <p className="rotulo">Expectância fora da amostra</p>
            <p
              className={`numerico mt-1 text-3xl font-semibold ${
                resultado.temEdge ? 'text-alta' : 'text-baixa'
              }`}
            >
              {emR(resultado.expectanciaMediaForaDaAmostra ?? 0)}
            </p>
            <p className="mt-1.5 text-sm text-texto-suave">
              {resultado.temEdge
                ? 'Positiva — há indício de vantagem nesta série.'
                : 'Não positiva — a configuração atual não tem vantagem comprovada aqui.'}
            </p>
          </div>

          {!resultado.temEdge && (
            <Alerta tom="aviso">
              Expectância não positiva <strong>é informação, não falha</strong>. Significa que
              esta configuração não tem vantagem nesta série. Caminhos: ajustar limiares,
              reduzir o catálogo aos padrões que medem bem, ou aceitar que este timeframe não
              serve para este ativo.
            </Alerta>
          )}

          {resultado.janelas && (
            <div className="cartao overflow-x-auto p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-borda text-left">
                    <th className="rotulo px-4 py-2.5">Janela</th>
                    <th className="rotulo px-3 py-2.5 text-right">Treino</th>
                    <th className="rotulo px-3 py-2.5 text-right">Teste</th>
                    <th className="rotulo px-4 py-2.5 text-right">Acerto</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda">
                  {resultado.janelas.map((j) => (
                    <tr key={j.indice}>
                      <td className="px-4 py-2">#{j.indice + 1}</td>
                      <td className="numerico px-3 py-2 text-right text-texto-fraco">
                        {emR(j.treinoExpectanciaR)}
                      </td>
                      <td
                        className={`numerico px-3 py-2 text-right font-semibold ${
                          j.testeExpectanciaR >= 0 ? 'text-alta' : 'text-baixa'
                        }`}
                      >
                        {emR(j.testeExpectanciaR)}
                      </td>
                      <td className="numerico px-4 py-2 text-right">
                        {percentual(j.testeTaxaAcerto)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
