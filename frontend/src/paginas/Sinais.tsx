import { useEffect, useState } from 'react';

import { CartaoSinal } from '../components/CartaoSinal';
import { Alerta, Botao, Carregando, Vazio } from '../components/ui';
import { api } from '../lib/api';
import type { Sinal, StatusSinal } from '../lib/tipos';

const FILTROS_STATUS: Array<{ valor: StatusSinal | ''; rotulo: string }> = [
  { valor: '', rotulo: 'Todos' },
  { valor: 'ABERTO', rotulo: 'Aguardando' },
  { valor: 'ACIONADO', rotulo: 'Em posição' },
  { valor: 'ALVO', rotulo: 'Alvo' },
  { valor: 'STOP', rotulo: 'Stop' },
  { valor: 'EXPIRADO', rotulo: 'Expirados' },
];

export function Sinais() {
  const [filtros, setFiltros] = useState({
    ativo: '' as '' | 'WIN' | 'WDO',
    status: '' as StatusSinal | '',
    scoreMinimo: 0,
    limite: 50,
  });
  const [dados, setDados] = useState<{ total: number; itens: Sinal[] } | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    api
      .get<{ total: number; itens: Sinal[] }>(
        api.comFiltros('/sinais', {
          ativo: filtros.ativo,
          status: filtros.status,
          scoreMinimo: filtros.scoreMinimo || undefined,
          limite: filtros.limite,
        }),
      )
      .then((r) => ativo && setDados(r))
      .catch((e) => ativo && setErro(e instanceof Error ? e.message : 'Falha ao carregar'))
      .finally(() => ativo && setCarregando(false));
    return () => {
      ativo = false;
    };
  }, [filtros]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Sinais</h1>
        <p className="text-sm text-texto-suave">
          Histórico completo, com a explicação do score de cada um.
        </p>
      </div>

      <div className="cartao flex flex-wrap items-end gap-4 p-4">
        <label className="text-sm">
          <span className="mb-1 block text-xs text-texto-fraco">Ativo</span>
          <select
            className="campo w-32"
            value={filtros.ativo}
            onChange={(e) => setFiltros({ ...filtros, ativo: e.target.value as never })}
          >
            <option value="">Todos</option>
            <option value="WIN">WIN</option>
            <option value="WDO">WDO</option>
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-xs text-texto-fraco">Status</span>
          <select
            className="campo w-40"
            value={filtros.status}
            onChange={(e) => setFiltros({ ...filtros, status: e.target.value as never })}
          >
            {FILTROS_STATUS.map((f) => (
              <option key={f.valor} value={f.valor}>
                {f.rotulo}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-xs text-texto-fraco">
            Score mínimo: <span className="numerico">{filtros.scoreMinimo.toFixed(2)}</span>
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            className="w-40 accent-marca"
            value={filtros.scoreMinimo}
            onChange={(e) => setFiltros({ ...filtros, scoreMinimo: Number(e.target.value) })}
          />
        </label>

        <div className="ml-auto flex items-center gap-3">
          {dados && (
            <span className="text-xs text-texto-fraco">
              {dados.itens.length} de {dados.total}
            </span>
          )}
          <Botao
            variante="neutro"
            onClick={() => setFiltros({ ativo: '', status: '', scoreMinimo: 0, limite: 50 })}
          >
            Limpar
          </Botao>
        </div>
      </div>

      {erro && <Alerta tom="erro">{erro}</Alerta>}

      {carregando ? (
        <Carregando />
      ) : !dados || dados.itens.length === 0 ? (
        <Vazio
          titulo="Nenhum sinal com esses filtros"
          detalhe="Se o banco ainda está vazio, ligue o coletor. Se há candles mas nenhum sinal, os filtros do motor estão fazendo o trabalho deles — a maior parte das detecções não deve virar operação."
        />
      ) : (
        <div className="space-y-3">
          {dados.itens.map((sinal) => (
            <CartaoSinal key={sinal.id} sinal={sinal} />
          ))}
          {dados.total > dados.itens.length && (
            <div className="pt-2 text-center">
              <Botao
                variante="neutro"
                onClick={() => setFiltros({ ...filtros, limite: filtros.limite + 50 })}
              >
                Carregar mais
              </Botao>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
