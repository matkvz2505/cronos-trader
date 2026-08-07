import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { CartaoSinal } from '../components/CartaoSinal';
import { Alerta, Carregando } from '../components/ui';
import { api } from '../lib/api';
import { emR, percentual, preco } from '../lib/formato';
import { useAuth } from '../lib/auth';
import { useSinaisAoVivo } from '../lib/useSinaisAoVivo';
import type { Ativo, Raciocinio, Saude } from '../lib/tipos';

const ATIVOS: Ativo[] = ['WIN', 'WDO'];
const NOME: Record<Ativo, string> = { WIN: 'Mini-índice', WDO: 'Mini-dólar' };

/**
 * A Mesa — visão dos dois ativos lado a lado.
 *
 * Existe para responder uma pergunta só: **para onde eu olho agora?** Daqui se entra na
 * Sala do ativo que está pedindo atenção. Tudo que não ajuda nessa decisão foi movido
 * para outra tela.
 */
export function Mesa() {
  const { usuario } = useAuth();
  const { abertos, resumo, estado } = useSinaisAoVivo();
  const [leituras, setLeituras] = useState<Record<string, Raciocinio | null>>({});
  const [saude, setSaude] = useState<Saude | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let vivo = true;

    const carregar = async () => {
      const [win, wdo, s] = await Promise.all([
        api.get<Raciocinio>(api.comFiltros('/mercado/raciocinio', { ativo: 'WIN' })).catch(() => null),
        api.get<Raciocinio>(api.comFiltros('/mercado/raciocinio', { ativo: 'WDO' })).catch(() => null),
        api.get<Saude>('/mercado/saude').catch(() => null),
      ]);
      if (!vivo) return;
      setLeituras({ WIN: win, WDO: wdo });
      setSaude(s);
      setCarregando(false);
    };

    void carregar();
    const timer = window.setInterval(() => void carregar(), 30_000);
    return () => {
      vivo = false;
      window.clearInterval(timer);
    };
  }, []);

  const semCandles = (saude?.candles ?? []).length === 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Bom pregão, {usuario?.nome.split(' ')[0]}
          </h1>
          <p className="mt-0.5 text-sm text-texto-suave">
            Gatilho em 5min, viés em 15/30/60min. O motor sinaliza — você opera.
          </p>
        </div>
        <span className="flex items-center gap-1.5 text-xs text-texto-fraco">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              estado === 'conectado' ? 'bg-alta' : estado === 'conectando' ? 'animate-pulse bg-aviso' : 'bg-baixa'
            }`}
          />
          {estado === 'conectado' ? 'ao vivo' : estado}
        </span>
      </header>

      {semCandles && saude && (
        <Alerta tom="aviso">
          <strong>Nenhum candle no banco.</strong> O motor não tem o que ler. Ligue o coletor
          com o MetaTrader 5 aberto: <code>.\cronos.ps1 coletor</code>
        </Alerta>
      )}

      {carregando ? (
        <Carregando texto="lendo os dois mercados…" />
      ) : (
        <section className="grid gap-4 lg:grid-cols-2">
          {ATIVOS.map((a) => (
            <CartaoAtivo key={a} ativo={a} raciocinio={leituras[a] ?? null} />
          ))}
        </section>
      )}

      <section>
        <h2 className="titulo-secao">
          Sinais abertos
          {abertos.length > 0 && (
            <span className="ml-2 rounded-md bg-marca-fundo px-2 py-0.5 text-xs font-semibold text-marca">
              {abertos.length}
            </span>
          )}
        </h2>

        {abertos.length === 0 ? (
          <div className="cartao px-6 py-10 text-center">
            <p className="text-sm font-medium text-texto-suave">Nenhuma entrada aprovada agora</p>
            <p className="mx-auto mt-1.5 max-w-lg text-xs leading-relaxed text-texto-fraco">
              É a resposta certa na maior parte do tempo. Entre na Sala de cada ativo para ver
              quais padrões estão sendo recusados e por quê — é ali que o critério fica visível.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {abertos.map((s) => (
              <CartaoSinal key={s.id} sinal={s} compacto />
            ))}
          </div>
        )}
      </section>

      {resumo && (
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Numero rotulo="Emitidos hoje" valor={String(resumo.emitidosHoje)} />
          <Numero rotulo="Encerrados" valor={String(resumo.encerrados)} />
          <Numero
            rotulo="Taxa de acerto"
            valor={percentual(resumo.taxaAcerto)}
            aviso={!resumo.amostraSuficiente}
          />
          <Numero
            rotulo="Expectância"
            valor={emR(resumo.expectanciaR)}
            tom={resumo.expectanciaR >= 0 ? 'alta' : 'baixa'}
            aviso={!resumo.amostraSuficiente}
          />
        </section>
      )}
    </div>
  );
}

/** Cartão de um ativo: preço, viés, e o que está sendo vigiado. Leva à Sala. */
function CartaoAtivo({ ativo, raciocinio }: { ativo: Ativo; raciocinio: Raciocinio | null }) {
  if (!raciocinio) {
    return (
      <div className="cartao px-5 py-6">
        <p className="rotulo">{NOME[ativo]}</p>
        <p className="mt-2 text-sm text-texto-fraco">Sem dados suficientes para ler.</p>
      </div>
    );
  }

  const subiu = raciocinio.variacaoDia >= 0;
  const temSinal = Boolean(raciocinio.sinal);

  return (
    <Link
      to={`/sala/${ativo.toLowerCase()}`}
      className={`cartao surge block px-5 py-5 transition-colors hover:border-borda-forte ${
        temSinal ? 'cartao-destaque' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="rotulo">{NOME[ativo]}</p>
          <div className="mt-1 flex items-baseline gap-2.5">
            <span className="numerico text-3xl font-semibold tracking-tight">
              {preco(raciocinio.preco, ativo)}
            </span>
            <span className={`numerico text-sm font-semibold ${subiu ? 'text-alta' : 'text-baixa'}`}>
              {subiu ? '+' : ''}
              {raciocinio.variacaoDia.toFixed(2)}%
            </span>
          </div>
        </div>

        {temSinal ? (
          <span className="flex items-center gap-1.5 rounded-lg border border-alta/40 bg-alta-fundo/50 px-2.5 py-1 text-xs font-semibold text-alta">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-alta opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-alta" />
            </span>
            entrada
          </span>
        ) : (
          <span className="rounded-lg bg-superficie-topo px-2.5 py-1 text-xs text-texto-fraco">
            aguardando
          </span>
        )}
      </div>

      <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-texto-suave">
        {raciocinio.veredito}
      </p>

      <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-borda pt-3 text-xs text-texto-fraco">
        <span>
          viés{' '}
          <span
            className={
              raciocinio.viesDirecao === 'alta'
                ? 'text-alta'
                : raciocinio.viesDirecao === 'baixa'
                  ? 'text-baixa'
                  : 'text-texto-suave'
            }
          >
            {raciocinio.viesDirecao}
          </span>
        </span>
        <span>{raciocinio.janelaPregao}</span>
        {raciocinio.vigiando.length > 0 && (
          <span>{raciocinio.vigiando.length} sob vigilância</span>
        )}
        <span className="ml-auto text-marca">abrir sala →</span>
      </div>
    </Link>
  );
}

function Numero({
  rotulo,
  valor,
  tom = 'neutro',
  aviso = false,
}: {
  rotulo: string;
  valor: string;
  tom?: 'neutro' | 'alta' | 'baixa';
  aviso?: boolean;
}) {
  const cor = { neutro: 'text-texto', alta: 'text-alta', baixa: 'text-baixa' }[tom];
  return (
    <div className="cartao px-4 py-3.5">
      <p className="rotulo">{rotulo}</p>
      <p className={`numerico mt-1 text-2xl font-semibold ${cor}`}>{valor}</p>
      {aviso && (
        <p className="mt-1 text-[11px] text-aviso" title="Menos de 30 operações encerradas">
          amostra insuficiente
        </p>
      )}
    </div>
  );
}
