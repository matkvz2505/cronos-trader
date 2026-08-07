import { useState } from 'react';

import { Alerta, Botao, Cartao, Metrica, Titulo } from '../components/ui';
import { api, ErroApi } from '../lib/api';
import { emR, percentual, reais } from '../lib/formato';
import type { Ativo, ResultadoBacktest, Timeframe } from '../lib/tipos';

export function Backtest() {
  const [config, setConfig] = useState({
    ativo: 'WIN' as Ativo,
    timeframe: 'M5' as Timeframe,
    capital: 20_000,
    modo: 'walkforward' as 'backtest' | 'walkforward',
    janelas: 4,
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
      setErro(e instanceof ErroApi ? e.message : 'Falha ao rodar o backtest');
    } finally {
      setRodando(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Backtest</h1>
        <p className="text-sm text-texto-suave">
          Descobre quais padrões funcionam em WIN e WDO — e apaga os que não funcionam.
        </p>
      </div>

      <Alerta tom="info">
        <strong>Walk-forward é o modo que vale.</strong> O backtest simples calibra e mede na
        mesma série, o que é memorização, não evidência. O walk-forward calibra numa janela e
        mede na seguinte: só o resultado <em>fora da amostra</em> diz alguma coisa sobre o
        futuro.
      </Alerta>

      <Cartao className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-xs text-texto-fraco">Ativo</span>
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
          <span className="mb-1 block text-xs text-texto-fraco">Timeframe</span>
          <select
            className="campo w-32"
            value={config.timeframe}
            onChange={(e) => setConfig({ ...config, timeframe: e.target.value as Timeframe })}
          >
            <option value="M5">5min</option>
            <option value="M15">15min</option>
            <option value="M30">30min</option>
            <option value="H1">60min</option>
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-xs text-texto-fraco">Capital</span>
          <input
            type="number"
            step={1000}
            min={1000}
            className="campo numerico w-36"
            value={config.capital}
            onChange={(e) => setConfig({ ...config, capital: Number(e.target.value) })}
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-xs text-texto-fraco">Modo</span>
          <select
            className="campo w-40"
            value={config.modo}
            onChange={(e) => setConfig({ ...config, modo: e.target.value as never })}
          >
            <option value="walkforward">Walk-forward</option>
            <option value="backtest">Backtest simples</option>
          </select>
        </label>

        {config.modo === 'walkforward' && (
          <label className="text-sm">
            <span className="mb-1 block text-xs text-texto-fraco">Janelas</span>
            <input
              type="number"
              min={2}
              max={12}
              className="campo numerico w-24"
              value={config.janelas}
              onChange={(e) => setConfig({ ...config, janelas: Number(e.target.value) })}
            />
          </label>
        )}

        <Botao onClick={rodar} disabled={rodando} className="ml-auto">
          {rodando ? 'Rodando…' : 'Rodar'}
        </Botao>
      </Cartao>

      {rodando && (
        <p className="text-sm text-texto-fraco">
          Simulando candle a candle sem look-ahead. Uma série longa pode levar alguns minutos.
        </p>
      )}

      {erro && <Alerta tom="erro">{erro}</Alerta>}

      {resultado?.modo === 'walkforward' && <ResultadoWalkForward resultado={resultado} />}
      {resultado?.modo === 'backtest' && <ResultadoSimples resultado={resultado} />}
    </div>
  );
}

function ResultadoWalkForward({ resultado }: { resultado: ResultadoBacktest }) {
  const media = resultado.expectanciaMediaForaDaAmostra ?? 0;

  return (
    <div className="space-y-4">
      <Metrica
        rotulo="Expectância fora da amostra"
        valor={emR(media)}
        detalhe={
          resultado.temEdge
            ? 'positiva — há sinal de edge nesta série'
            : 'negativa ou nula — sem edge nesta configuração'
        }
        tom={resultado.temEdge ? 'alta' : 'baixa'}
      />

      {!resultado.temEdge && (
        <Alerta tom="aviso">
          Expectância não positiva <strong>é informação, não falha</strong>. Significa que a
          configuração atual não tem vantagem nesta série. Caminhos: ajustar limiares, reduzir o
          catálogo aos padrões que medem bem, ou aceitar que este timeframe não serve para este
          ativo.
        </Alerta>
      )}

      <section>
        <Titulo>Janelas</Titulo>
        <Cartao className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-borda text-left text-xs tracking-wide text-texto-fraco uppercase">
                <th className="px-4 py-3 font-medium">Janela</th>
                <th className="px-3 py-3 text-right font-medium">Treino</th>
                <th className="px-3 py-3 text-right font-medium">Teste</th>
                <th className="px-3 py-3 text-right font-medium">Acerto (teste)</th>
                <th className="px-3 py-3 text-right font-medium">Resultado</th>
                <th className="px-4 py-3 text-right font-medium">Calibrados</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borda">
              {(resultado.janelas ?? []).map((j) => (
                <tr key={j.indice}>
                  <td className="px-4 py-2.5">#{j.indice + 1}</td>
                  <td className="numerico px-3 py-2.5 text-right text-texto-fraco">
                    {emR(j.treinoExpectanciaR)}
                  </td>
                  <td
                    className={`numerico px-3 py-2.5 text-right font-semibold ${
                      j.testeExpectanciaR >= 0 ? 'text-alta' : 'text-baixa'
                    }`}
                  >
                    {emR(j.testeExpectanciaR)}
                  </td>
                  <td className="numerico px-3 py-2.5 text-right">
                    {percentual(j.testeTaxaAcerto)}
                  </td>
                  <td
                    className={`numerico px-3 py-2.5 text-right ${
                      j.testeResultadoReais >= 0 ? 'text-alta' : 'text-baixa'
                    }`}
                  >
                    {reais(j.testeResultadoReais)}
                  </td>
                  <td className="numerico px-4 py-2.5 text-right text-texto-fraco">
                    {j.padroesCalibrados}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Cartao>
      </section>

      <Relatorio texto={resultado.relatorio} />
    </div>
  );
}

function ResultadoSimples({ resultado }: { resultado: ResultadoBacktest }) {
  return (
    <div className="space-y-4">
      {resultado.aviso && <Alerta tom="aviso">{resultado.aviso}</Alerta>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Metrica rotulo="Sinais" valor={String(resultado.sinaisGerados ?? 0)} />
        <Metrica rotulo="Acionados" valor={String(resultado.acionados ?? 0)} />
        <Metrica rotulo="Acerto" valor={percentual(resultado.taxaAcerto ?? 0)} />
        <Metrica
          rotulo="Expectância"
          valor={emR(resultado.expectanciaR ?? 0)}
          tom={(resultado.expectanciaR ?? 0) >= 0 ? 'alta' : 'baixa'}
        />
        <Metrica
          rotulo="Rebaixamento máx."
          valor={reais(resultado.rebaixamentoMax ?? 0)}
          tom="baixa"
          detalhe="pico ao vale"
        />
      </div>
      <Relatorio texto={resultado.relatorio} />
    </div>
  );
}

function Relatorio({ texto }: { texto: string }) {
  return (
    <section>
      <Titulo>Relatório completo</Titulo>
      <Cartao>
        <pre className="numerico overflow-x-auto text-xs leading-relaxed text-texto-suave">
          {texto}
        </pre>
      </Cartao>
    </section>
  );
}
