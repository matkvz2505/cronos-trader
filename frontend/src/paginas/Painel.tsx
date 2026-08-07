import { useEffect, useMemo, useState } from 'react';

import { CartaoSinal } from '../components/CartaoSinal';
import { Alerta, Botao, Cartao, Carregando, Desempenho, Titulo } from '../components/ui';
import { api, ErroApi } from '../lib/api';
import { useAuth } from '../lib/auth';
import { emR, haQuantoTempo, percentual, reais } from '../lib/formato';
import { useSinaisAoVivo } from '../lib/useSinaisAoVivo';
import type { Ativo, DesempenhoPadrao, Saude, Sinal } from '../lib/tipos';

/**
 * O painel responde uma pergunta, em ordem: **o que eu faço agora?**
 *
 * Por isso a operação aberta vem antes das métricas, e as métricas vêm antes da
 * infraestrutura. Um dashboard que abre com "uptime do serviço" está organizado pela
 * arquitetura, não pelo trabalho de quem opera.
 *
 * Sinais de convicção baixa ficam separados e recolhidos por padrão. Não são escondidos —
 * são despriorizados, que é diferente: continuam auditáveis, mas não competem com o que
 * merece atenção.
 */
export function Painel() {
  const { usuario } = useAuth();
  const { abertos, resumo, estado } = useSinaisAoVivo();
  const [saude, setSaude] = useState<Saude | null>(null);
  const [desempenho, setDesempenho] = useState<DesempenhoPadrao[]>([]);
  const [analisando, setAnalisando] = useState<Ativo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [verFracos, setVerFracos] = useState(false);

  useEffect(() => {
    api.get<Saude>('/mercado/saude').then(setSaude).catch(() => {});
    api.get<DesempenhoPadrao[]>('/sinais/desempenho').then(setDesempenho).catch(() => {});
  }, []);

  const { fortes, fracos } = useMemo(() => separar(abertos), [abertos]);

  async function analisar(ativo: Ativo) {
    setAnalisando(ativo);
    setAviso(null);
    try {
      const r = await api.post<{ sinaisNovos: number; resumo: string }>('/sinais/analisar', {
        ativo,
        timeframe: 'M5',
      });
      setAviso(
        r.sinaisNovos > 0 ? `${r.sinaisNovos} sinal(is) novo(s) — ${r.resumo}` : r.resumo,
      );
    } catch (e) {
      setAviso(e instanceof ErroApi ? e.message : 'Falha ao analisar');
    } finally {
      setAnalisando(null);
    }
  }

  const semCandles = (saude?.candles ?? []).length === 0;

  return (
    <div className="space-y-7">
      <header className="surge flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rotulo">{new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}</p>
          <h1 className="mt-1 text-2xl font-semibold">
            Bom pregão, {usuario?.nome.split(' ')[0]}
          </h1>
          <p className="mt-1 text-sm text-texto-suave">
            Gatilho em 5min, viés em 15/30/60min. O motor sugere — você aperta o botão.
          </p>
        </div>
        <div className="flex gap-2">
          {(['WIN', 'WDO'] as Ativo[]).map((a) => (
            <Botao key={a} variante="neutro" onClick={() => analisar(a)} disabled={!!analisando}>
              {analisando === a ? 'Analisando…' : `Analisar ${a}`}
            </Botao>
          ))}
        </div>
      </header>

      {aviso && <Alerta tom="info">{aviso}</Alerta>}

      {semCandles && saude && (
        <Alerta tom="aviso">
          <strong>Nenhum candle no banco.</strong> Ligue o coletor com o MetaTrader 5 aberto
          — <code className="text-xs">.\cronos.ps1 coletor</code> — ou carregue dados
          sintéticos com <code className="text-xs">.\cronos.ps1 amostra</code>.
        </Alerta>
      )}

      {/* --- o que fazer agora --- */}
      <section className="surge">
        <Titulo
          acao={
            <span className="flex items-center gap-1.5 text-xs text-texto-fraco">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  estado === 'conectado' ? 'bg-alta pulsa' : 'bg-baixa'
                }`}
              />
              {estado === 'conectado' ? 'ao vivo' : 'sem conexão'}
            </span>
          }
        >
          Operações abertas
        </Titulo>

        {estado === 'conectando' && abertos.length === 0 ? (
          <Carregando texto="conectando ao fluxo de sinais…" />
        ) : abertos.length === 0 ? (
          <Cartao className="px-6 py-10 text-center">
            <p className="text-sm font-medium text-texto-suave">Nenhuma operação aberta</p>
            <p className="mx-auto mt-2 max-w-lg text-[13px] leading-relaxed text-texto-fraco">
              Isto é o esperado, e é o produto funcionando. Confluência, R:R mínimo e viés
              multi-timeframe descartam a maior parte das detecções por construção — um
              motor que aprova tudo o que detecta é um motor que perde dinheiro.
            </p>
          </Cartao>
        ) : (
          <div className="space-y-4">
            {fortes.map((s) => (
              <CartaoSinal key={s.id} sinal={s} compacto />
            ))}

            {fortes.length === 0 && (
              <Alerta tom="aviso">
                Nenhum sinal de convicção alta ou média no momento. Os {fracos.length} abaixo
                têm ressalvas relevantes — vale ler a tese antes de considerar qualquer um.
              </Alerta>
            )}

            {fracos.length > 0 && (
              <div className="space-y-3">
                <button
                  onClick={() => setVerFracos((v) => !v)}
                  className="flex w-full items-center gap-2 rounded-xl border border-borda bg-superficie/60 px-4 py-2.5 text-left text-sm text-texto-suave transition-colors hover:border-borda-forte"
                >
                  <span className="text-texto-fraco">{verFracos ? '▾' : '▸'}</span>
                  {fracos.length} sinal(is) de convicção baixa
                  <span className="ml-auto text-xs text-texto-fraco">
                    {verFracos ? 'recolher' : 'mostrar mesmo assim'}
                  </span>
                </button>
                {verFracos && fracos.map((s) => <CartaoSinal key={s.id} sinal={s} compacto />)}
              </div>
            )}
          </div>
        )}
      </section>

      {/* --- como a conta está indo --- */}
      <section className="surge">
        <Titulo>Como a conta está indo</Titulo>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metrica
            rotulo="Abertos"
            valor={String(resumo?.abertos ?? abertos.length)}
            detalhe={`${fortes.length} com convicção`}
            tom="marca"
          />
          <Metrica rotulo="Emitidos hoje" valor={String(resumo?.emitidosHoje ?? 0)} />
          <Metrica
            rotulo="Taxa de acerto"
            valor={percentual(resumo?.taxaAcerto ?? 0)}
            detalhe={`${resumo?.encerrados ?? 0} encerradas`}
            insuficiente={!resumo?.amostraSuficiente}
          />
          <Metrica
            rotulo="Expectância"
            valor={emR(resumo?.expectanciaR ?? 0)}
            detalhe="por operação"
            tom={(resumo?.expectanciaR ?? 0) >= 0 ? 'alta' : 'baixa'}
            insuficiente={!resumo?.amostraSuficiente}
          />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <section className="surge">
          <Titulo>Padrões que estão pagando</Titulo>
          <Cartao className="p-0">
            {desempenho.length === 0 ? (
              <p className="px-5 py-8 text-center text-[13px] text-texto-fraco">
                Sem operações encerradas ainda. Este placar é o que decide qual padrão fica
                e qual sai do catálogo.
              </p>
            ) : (
              <ul className="divide-y divide-borda">
                {desempenho.slice(0, 8).map((p) => (
                  <li key={p.padraoId} className="flex items-center justify-between gap-3 px-5 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm">{p.nome}</p>
                      <p className="text-xs text-texto-fraco">{p.ocorrencias} operações</p>
                    </div>
                    <Desempenho
                      taxa={p.taxaAcerto}
                      expectancia={p.expectanciaR}
                      suficiente={p.suficiente}
                    />
                  </li>
                ))}
              </ul>
            )}
          </Cartao>
        </section>

        {saude && <PainelInfra saude={saude} capital={usuario?.capital ?? 0} />}
      </div>
    </div>
  );
}

/** Convicção alta ou média de um lado; baixa (e sem tese) do outro. */
function separar(sinais: Sinal[]): { fortes: Sinal[]; fracos: Sinal[] } {
  const fortes: Sinal[] = [];
  const fracos: Sinal[] = [];
  for (const s of sinais) {
    if (!s.tese || s.tese.confianca === 'baixa') fracos.push(s);
    else fortes.push(s);
  }
  return { fortes, fracos };
}

function Metrica({
  rotulo,
  valor,
  detalhe,
  tom = 'neutro',
  insuficiente = false,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  tom?: 'neutro' | 'alta' | 'baixa' | 'marca';
  insuficiente?: boolean;
}) {
  const cor = { neutro: 'text-texto', alta: 'text-alta', baixa: 'text-baixa', marca: 'text-marca' }[
    tom
  ];
  return (
    <div className="cartao px-4 py-3.5">
      <p className="rotulo">{rotulo}</p>
      <p className={`numerico mt-1 text-2xl font-semibold ${cor}`}>{valor}</p>
      {detalhe && <p className="mt-0.5 text-xs text-texto-fraco">{detalhe}</p>}
      {insuficiente && (
        <p className="mt-1.5 text-xs text-aviso" title="Menos de 30 operações encerradas">
          amostra insuficiente
        </p>
      )}
    </div>
  );
}

function PainelInfra({ saude, capital }: { saude: Saude; capital: number }) {
  const motor = saude.motor;
  const mt5 = 'mt5' in motor ? motor.mt5 : undefined;
  const candles = saude.candles ?? [];
  const maisRecente = candles
    .map((c) => c.ultimo)
    .filter((t): t is string => Boolean(t))
    .sort()
    .at(-1);
  const minutos = maisRecente ? (Date.now() - new Date(maisRecente).getTime()) / 60_000 : Infinity;

  return (
    <section className="surge">
      <Titulo>Estado da operação</Titulo>
      <Cartao className="space-y-2.5 text-[13px]">
        <Item rotulo="Capital configurado" ok detalhe={reais(capital)} />
        <Item
          rotulo="Dados de mercado"
          ok={minutos < 15}
          detalhe={maisRecente ? haQuantoTempo(maisRecente) : 'sem candles'}
        />
        <Item
          rotulo="Coletor MT5"
          ok={mt5?.disponivel ?? false}
          detalhe={mt5?.emContainer ? 'roda no host' : (mt5?.detalhe ?? '—')}
        />
        <Item rotulo="Motor" ok={'ok' in motor && motor.ok} detalhe={
          'padroes' in motor && motor.padroes ? `${motor.padroes} padrões` : 'fora'
        } />

        {candles.length > 0 && (
          <>
            <div className="divisor my-1" />
            <ul className="space-y-1">
              {candles.map((c) => (
                <li key={`${c.ativo}-${c.timeframe}`} className="flex justify-between text-xs">
                  <span className="text-texto-suave">
                    {c.ativo} {c.timeframe}
                  </span>
                  <span className="numerico text-texto-fraco">
                    {c.total.toLocaleString('pt-BR')}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </Cartao>
    </section>
  );
}

function Item({ rotulo, ok, detalhe }: { rotulo: string; ok: boolean; detalhe: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-texto-suave">{rotulo}</span>
      <span className="flex min-w-0 items-center gap-2">
        <span className="truncate text-texto-fraco" title={detalhe}>
          {detalhe}
        </span>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ok ? 'bg-alta' : 'bg-baixa'}`} />
      </span>
    </div>
  );
}
