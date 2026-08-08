import { useEffect, useMemo, useRef, useState } from 'react';

import { CartaoSinal } from '../components/CartaoSinal';
import { PregaoDeHoje } from '../components/PregaoDeHoje';
import { Alerta as Caixa, Botao } from '../components/ui';
import { api } from '../lib/api';
import { emR, horario, percentual, preco } from '../lib/formato';
import { useSinaisAoVivo } from '../lib/useSinaisAoVivo';
import type { Alerta, DesempenhoPadrao, TipoAlerta } from '../lib/tipos';

type Qualidade = 'medido' | 'score' | 'tudo';

const CONFIG: Record<TipoAlerta, { rotulo: string; cor: string; icone: string }> = {
  'sinal.novo': { rotulo: 'Entrada aprovada', cor: 'text-marca', icone: '◆' },
  'entrada.acionada': { rotulo: 'Entrada acionada', cor: 'text-alta', icone: '▶' },
  'saida.alvo': { rotulo: 'Alvo atingido', cor: 'text-alta', icone: '✓' },
  'saida.stop': { rotulo: 'Stop', cor: 'text-baixa', icone: '✕' },
  'sinal.expirado': { rotulo: 'Expirou sem acionar', cor: 'text-texto-fraco', icone: '−' },
};

/**
 * Alertas ao vivo — o que aconteceu enquanto você não estava olhando.
 *
 * A decisão de design mais importante aqui é **qual métrica filtra**. O pedido natural é
 * "só me mostre o que acerta mais de 50%", e essa é a pergunta errada: taxa de acerto
 * sozinha não diz se a operação ganha dinheiro.
 *
 * O Engolfo de Alta acerta 47,6% e tem expectância **positiva** (+0,18R), porque o R:R
 * mínimo de 1,5 garante que os acertos sejam maiores que os erros. Um filtro de "acerto >
 * 50%" excluiria justamente o único padrão com vantagem medida.
 *
 * Por isso o filtro padrão é **expectância medida**, e a taxa de acerto aparece ao lado
 * dela — visível, para quem quiser conferir, mas não no comando.
 */
export function Alertas() {
  const { alertas, estado, limparAlertas } = useSinaisAoVivo();
  const [qualidade, setQualidade] = useState<Qualidade>('medido');
  const [desempenho, setDesempenho] = useState<DesempenhoPadrao[]>([]);
  const [som, setSom] = useState(false);
  const contagemAnterior = useRef(0);

  useEffect(() => {
    api.get<DesempenhoPadrao[]>('/sinais/desempenho').then(setDesempenho).catch(() => {});
  }, []);

  const porPadrao = useMemo(
    () => new Map(desempenho.map((d) => [d.padraoId, d])),
    [desempenho],
  );

  const filtrados = useMemo(
    () => alertas.filter((a) => passaNoFiltro(a, qualidade, porPadrao)),
    [alertas, qualidade, porPadrao],
  );

  // Bipe curto via WebAudio: um alerta que só aparece na tela não serve para quem está
  // olhando o book da corretora. Sem arquivo de áudio — a CSP e o tamanho não valem.
  useEffect(() => {
    if (!som || filtrados.length <= contagemAnterior.current) {
      contagemAnterior.current = filtrados.length;
      return;
    }
    contagemAnterior.current = filtrados.length;
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const ganho = ctx.createGain();
      osc.connect(ganho);
      ganho.connect(ctx.destination);
      osc.frequency.value = 880;
      ganho.gain.setValueAtTime(0.12, ctx.currentTime);
      ganho.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.start();
      osc.stop(ctx.currentTime + 0.25);
    } catch {
      // Navegador pode bloquear áudio sem interação. Silêncio é aceitável.
    }
  }, [filtrados.length, som]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Alertas ao vivo</h1>
          <p className="mt-0.5 text-sm text-texto-suave">
            Entradas aprovadas, acionamentos e saídas — empurrados pelo servidor, sem recarregar.
          </p>
        </div>
        <span className="flex items-center gap-1.5 text-xs text-texto-fraco">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              estado === 'conectado'
                ? 'bg-alta'
                : estado === 'conectando'
                  ? 'animate-pulse bg-aviso'
                  : 'bg-baixa'
            }`}
          />
          {estado === 'conectado' ? 'recebendo' : estado}
        </span>
      </header>

      {/*
        Vem ANTES do feed de propósito. O feed só tem o que aconteceu desde que a aba
        abriu; quem senta na mesa às 15h veria uma tela vazia e concluiria que o dia não
        teve entrada. O extrato do banco responde primeiro.
      */}
      <PregaoDeHoje />

      <Caixa tom="info">
        <strong>Por que o filtro não é "acerto acima de 50%".</strong> Taxa de acerto sozinha
        não diz se a operação ganha dinheiro. O Engolfo de Alta acerta <strong>47,6%</strong> e
        tem expectância <strong>positiva</strong> (+0,18R), porque o R:R mínimo de 1,5 faz os
        acertos serem maiores que os erros. Um filtro de "acerto &gt; 50%" excluiria o único
        padrão com vantagem medida. Aqui o corte é por <strong>expectância</strong>, e o acerto
        aparece do lado para conferência.
      </Caixa>

      <div className="cartao flex flex-wrap items-center gap-4 px-4 py-3">
        <div className="flex gap-0.5 rounded-lg border border-borda bg-fundo/60 p-0.5">
          {(
            [
              ['medido', 'Só o que mede bem', 'expectância > 0 com amostra'],
              ['score', 'Score alto', 'score ≥ 0,70'],
              ['tudo', 'Tudo', 'sem filtro'],
            ] as const
          ).map(([id, titulo, sub]) => (
            <button
              key={id}
              onClick={() => setQualidade(id)}
              className={`rounded-md px-3 py-1.5 text-left transition-colors ${
                qualidade === id ? 'bg-superficie-topo text-texto' : 'text-texto-suave hover:text-texto'
              }`}
              title={sub}
            >
              <span className="block text-sm">{titulo}</span>
            </button>
          ))}
        </div>

        <label className="flex cursor-pointer items-center gap-2 text-sm text-texto-suave">
          <input
            type="checkbox"
            checked={som}
            onChange={(e) => setSom(e.target.checked)}
            className="accent-marca"
          />
          bipe ao chegar
        </label>

        <span className="numerico ml-auto text-xs text-texto-fraco">
          {filtrados.length} de {alertas.length}
        </span>
        {alertas.length > 0 && (
          <Botao variante="neutro" onClick={limparAlertas}>
            Limpar
          </Botao>
        )}
      </div>

      {filtrados.length === 0 ? (
        <div className="cartao px-6 py-12 text-center">
          <p className="text-sm font-medium text-texto-suave">
            {alertas.length === 0
              ? 'Nenhum alerta desde que esta aba abriu'
              : `${alertas.length} alerta(s) filtrado(s) pelo critério de qualidade`}
          </p>
          <p className="mx-auto mt-1.5 max-w-lg text-xs leading-relaxed text-texto-fraco">
            {alertas.length === 0
              ? 'O servidor empurra assim que um sinal nasce, aciona ou fecha. Deixe a aba aberta durante o pregão.'
              : 'Afrouxe o filtro para ver os demais. Eles existem — só não passaram no corte de expectância medida.'}
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {filtrados.map((a) => (
            <LinhaAlerta key={`${a.id}-${a.tipo}-${a.em}`} alerta={a} medido={porPadrao.get(a.sinal.padraoId)} />
          ))}
        </ul>
      )}
    </div>
  );
}

function passaNoFiltro(
  a: Alerta,
  qualidade: Qualidade,
  porPadrao: Map<string, DesempenhoPadrao>,
): boolean {
  if (qualidade === 'tudo') return true;
  if (qualidade === 'score') return a.sinal.score >= 0.7;

  // 'medido': exige evidência de vantagem, não promessa. Sem operações encerradas do
  // padrão, não há o que medir — e o alerta não passa.
  const d = porPadrao.get(a.sinal.padraoId);
  return Boolean(d && d.ocorrencias > 0 && d.expectanciaR > 0);
}

function LinhaAlerta({ alerta, medido }: { alerta: Alerta; medido?: DesempenhoPadrao }) {
  const [aberto, setAberto] = useState(false);
  const cfg = CONFIG[alerta.tipo];
  const s = alerta.sinal;

  return (
    <li className="cartao surge overflow-hidden">
      <button
        onClick={() => setAberto((v) => !v)}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-3 text-left"
      >
        <span className={`text-base font-bold ${cfg.cor}`}>{cfg.icone}</span>
        <span className={`text-sm font-semibold ${cfg.cor}`}>{cfg.rotulo}</span>

        <span className="text-sm text-texto-suave">
          {s.ativo} · {s.padraoNome}
        </span>
        <span
          className={`text-xs font-bold ${s.direcao === 'ALTA' ? 'text-alta' : 'text-baixa'}`}
        >
          {s.direcao === 'ALTA' ? '▲ compra' : '▼ venda'}
        </span>

        <span className="numerico text-xs text-texto-fraco">
          {preco(s.entrada, s.ativo)} → {preco(s.alvo, s.ativo)} · R:R {s.rr.toFixed(2)}
        </span>

        {medido && medido.ocorrencias > 0 && (
          <span className="numerico text-xs" title={`${medido.ocorrencias} operações encerradas`}>
            <span className={medido.expectanciaR >= 0 ? 'text-alta' : 'text-baixa'}>
              {emR(medido.expectanciaR)}
            </span>
            <span className="ml-1.5 text-texto-fraco">
              acerto {percentual(medido.taxaAcerto, 0)} · n={medido.ocorrencias}
            </span>
            {!medido.suficiente && <span className="ml-1 text-aviso">n baixo</span>}
          </span>
        )}

        <span className="numerico ml-auto text-xs text-texto-fraco">{horario(alerta.em)}</span>
      </button>

      {aberto && (
        <div className="border-t border-borda p-3">
          <CartaoSinal sinal={s} compacto />
        </div>
      )}
    </li>
  );
}
