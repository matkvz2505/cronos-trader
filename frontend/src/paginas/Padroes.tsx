import { useEffect, useMemo, useState } from 'react';

import { Alerta, Cartao, Carregando } from '../components/ui';
import { api } from '../lib/api';
import { percentual } from '../lib/formato';
import type { PadraoCatalogo } from '../lib/tipos';

const FAMILIAS = [
  { id: '', rotulo: 'Todos' },
  { id: 'reversao', rotulo: 'Reversão' },
  { id: 'continuacao', rotulo: 'Continuação' },
  { id: 'isolado', rotulo: 'Isolados' },
] as const;

export function Padroes() {
  const [padroes, setPadroes] = useState<PadraoCatalogo[]>([]);
  const [familia, setFamilia] = useState<string>('');
  const [busca, setBusca] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ total: number; padroes: PadraoCatalogo[] }>('/mercado/padroes')
      .then((r) => setPadroes(r.padroes))
      .catch((e) => setErro(e instanceof Error ? e.message : 'Motor de análise fora do ar'))
      .finally(() => setCarregando(false));
  }, []);

  const filtrados = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return padroes.filter(
      (p) =>
        (!familia || p.familia === familia) &&
        (!termo || p.nome.toLowerCase().includes(termo) || p.id.includes(termo)),
    );
  }, [padroes, familia, busca]);

  if (carregando) return <Carregando texto="carregando catálogo…" />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Catálogo de padrões</h1>
        <p className="text-sm text-texto-suave">
          {padroes.length} detectores extraídos do ebook, com as correções documentadas na errata.
        </p>
      </div>

      {erro && <Alerta tom="erro">{erro}</Alerta>}

      <Alerta tom="info">
        <strong>Confiabilidade do ebook é palpite inicial, não evidência.</strong> A coluna
        "medida" só aparece depois que o walk-forward acumular 30+ ocorrências do padrão em
        WIN/WDO. Até lá, o motor usa o prior — e a tela diz isso.
      </Alerta>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {FAMILIAS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFamilia(f.id)}
              className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                familia === f.id
                  ? 'bg-superficie-alta text-texto'
                  : 'text-texto-suave hover:bg-superficie'
              }`}
            >
              {f.rotulo}
            </button>
          ))}
        </div>
        <input
          className="campo ml-auto w-64"
          placeholder="Buscar padrão…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <Cartao className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-borda text-left text-xs tracking-wide text-texto-fraco uppercase">
              <th className="px-4 py-3 font-medium">Padrão</th>
              <th className="px-3 py-3 font-medium">Direção</th>
              <th className="px-3 py-3 font-medium">Exige</th>
              <th className="px-3 py-3 text-right font-medium">Prior (ebook)</th>
              <th className="px-3 py-3 text-right font-medium">Medida</th>
              <th className="px-4 py-3 font-medium">Notas</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borda">
            {filtrados.map((p) => (
              <tr key={p.id} className="align-top hover:bg-superficie-alta/40">
                <td className="px-4 py-3">
                  <p className="font-medium">{p.nome}</p>
                  <p className="text-xs text-texto-fraco">
                    {p.n_candles} candle{p.n_candles > 1 ? 's' : ''} · p.{p.pagina_ebook}
                  </p>
                </td>
                <td className="px-3 py-3">
                  <span
                    className={`text-xs font-semibold ${
                      p.direcao === 'alta'
                        ? 'text-alta'
                        : p.direcao === 'baixa'
                          ? 'text-baixa'
                          : 'text-texto-fraco'
                    }`}
                  >
                    {p.direcao}
                  </span>
                </td>
                <td className="px-3 py-3 text-xs text-texto-suave">
                  {p.tendencia_requerida ?? 'qualquer'}
                  {p.exige_gap && <span className="ml-1 text-aviso" title="Depende de gap">gap</span>}
                </td>
                <td className="numerico px-3 py-3 text-right text-texto-suave">
                  {p.confiabilidade_ebook.toFixed(2)}
                </td>
                <td className="numerico px-3 py-3 text-right">
                  {p.confiabilidade_medida !== null ? (
                    <span className={p.confiabilidade_medida >= 0.5 ? 'text-alta' : 'text-baixa'}>
                      {percentual(p.confiabilidade_medida)}
                      <span className="ml-1 text-xs text-texto-fraco">
                        n={p.ocorrencias_medidas}
                      </span>
                    </span>
                  ) : (
                    <span className="text-xs text-texto-fraco">sem amostra</span>
                  )}
                </td>
                <td className="max-w-md px-4 py-3 text-xs leading-relaxed text-texto-fraco">
                  {p.derivado_por_simetria && (
                    <span className="mr-1 rounded bg-superficie-alta px-1.5 py-0.5 text-texto-suave">
                      espelhado
                    </span>
                  )}
                  {p.observacao}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtrados.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-texto-fraco">
            Nenhum padrão com esses filtros.
          </p>
        )}
      </Cartao>
    </div>
  );
}
