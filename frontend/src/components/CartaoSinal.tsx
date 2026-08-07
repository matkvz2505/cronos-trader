import { useState } from 'react';

import {
  dataHora,
  haQuantoTempo,
  preco,
  pontos,
  reais,
  ROTULO_STATUS,
  ROTULO_TIMEFRAME,
} from '../lib/formato';
import type { Sinal } from '../lib/tipos';
import { Direcional, Etiqueta, SeloConfianca } from './ui';

/**
 * O elemento central do produto.
 *
 * A hierarquia responde à ordem em que a decisão é tomada, não à ordem em que os dados
 * existem:
 *
 * 1. **Entrada, stop e alvo** — é o que se digita na corretora. Lido em dois segundos.
 * 2. **A tese** — onde, quando, por quê. É o que justifica clicar.
 * 3. **O argumento contra** — sempre visível, nunca escondido atrás de um "ver mais".
 * 4. **A invalidação** — o preço que prova a leitura errada, dito em palavras.
 *
 * O item 3 é o que separa isto de um alerta de robô. Um cartão que só lista o que
 * favorece a operação não é análise, é propaganda — e o operador que confia nele uma vez
 * não confia duas.
 */
export function CartaoSinal({ sinal, compacto = false }: { sinal: Sinal; compacto?: boolean }) {
  const [verTudo, setVerTudo] = useState(!compacto);
  const alta = sinal.direcao === 'ALTA';
  const vivo = sinal.status === 'ABERTO' || sinal.status === 'ACIONADO';
  const tese = sinal.tese;

  return (
    <article className={`cartao surge overflow-hidden ${vivo ? 'cartao-destaque' : ''}`}>
      {/* --- cabeçalho --- */}
      <header className="flex flex-wrap items-center gap-3 px-5 py-3.5">
        <Direcional direcao={sinal.direcao} />
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold">{sinal.padraoNome}</h3>
          <p className="text-xs text-texto-fraco">
            {sinal.ativo} · {ROTULO_TIMEFRAME[sinal.timeframe]} · {dataHora(sinal.ts)} ·{' '}
            {haQuantoTempo(sinal.criadoEm)}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2.5">
          {sinal.zonaQuente && (
            <span
              className="rounded-md bg-marca-fundo px-2 py-1 text-[11px] font-semibold text-marca"
              title="Fibonacci, média e suporte/resistência apontando o mesmo preço"
            >
              zona quente
            </span>
          )}
          {tese && <SeloConfianca nivel={tese.confianca} motivo={tese.confiancaMotivo} />}
          <Etiqueta status={sinal.status} texto={ROTULO_STATUS[sinal.status] ?? sinal.status} />
        </div>
      </header>

      {/* --- os três preços: o que se digita na corretora --- */}
      <div className="grid grid-cols-3 border-y border-borda bg-fundo/40">
        <Nivel rotulo="Entrada" valor={preco(sinal.entrada, sinal.ativo)} />
        <Nivel rotulo="Stop" valor={preco(sinal.stop, sinal.ativo)} tom="baixa" borda />
        <Nivel rotulo="Alvo" valor={preco(sinal.alvo, sinal.ativo)} tom="alta" borda />
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 px-5 py-2.5 text-xs">
        <Chip rotulo="R:R" valor={sinal.rr.toFixed(2)} destaque={sinal.rr >= 2} />
        <Chip rotulo="contratos" valor={String(sinal.contratos)} />
        <Chip
          rotulo="risco"
          valor={reais(sinal.riscoPontos * sinal.contratos * (sinal.ativo === 'WIN' ? 0.2 : 10))}
          tom="baixa"
        />
        <span className="text-texto-fraco">alvo: {sinal.origemAlvo}</span>
        <span className="numerico ml-auto text-texto-suave">score {sinal.score.toFixed(2)}</span>
      </div>

      {/* --- a tese --- */}
      {tese && (
        <div className="space-y-3.5 border-t border-borda px-5 py-4">
          <Bloco rotulo="Onde" texto={tese.onde} />
          <Bloco rotulo="Quando" texto={tese.quando} />

          <div>
            <p className="rotulo mb-1.5">Por que</p>
            <ul className="space-y-1">
              {(verTudo ? tese.porque : tese.porque.slice(0, 3)).map((r) => (
                <li key={r} className="flex gap-2 text-[13px] leading-relaxed text-texto-suave">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-alta" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Sempre visível. É o que separa análise de propaganda. */}
          <div className="rounded-lg border border-baixa/25 bg-baixa-fundo/35 px-3.5 py-3">
            <p className="rotulo mb-1.5 text-baixa">O que pesa contra</p>
            <ul className="space-y-1">
              {(verTudo ? tese.contra : tese.contra.slice(0, 2)).map((c) => (
                <li key={c} className="flex gap-2 text-[13px] leading-relaxed text-texto-suave">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-baixa" />
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-lg border border-borda bg-superficie-alta/50 px-3.5 py-3">
            <p className="rotulo mb-1.5">Invalidação</p>
            <p className="text-[13px] leading-relaxed text-texto-suave">{tese.invalidacao}</p>
          </div>

          {compacto && (
            <button
              onClick={() => setVerTudo((v) => !v)}
              className="text-xs text-marca transition-opacity hover:opacity-75"
            >
              {verTudo ? 'menos detalhe' : 'ver tese completa'}
            </button>
          )}
        </div>
      )}

      {/* --- fatores de confluência --- */}
      {verTudo && sinal.fatores.length > 0 && (
        <div className="border-t border-borda px-5 py-3.5">
          <p className="rotulo mb-2">Como o score foi construído</p>
          <div className="flex flex-wrap gap-1.5">
            {sinal.fatores.map((f) => (
              <span
                key={f.nome}
                className={`numerico rounded-md px-2 py-1 text-[11px] ${
                  f.multiplicador >= 1
                    ? 'bg-alta-fundo/60 text-alta'
                    : 'bg-baixa-fundo/60 text-baixa'
                }`}
                title={f.detalhe}
              >
                {f.nome} ×{f.multiplicador.toFixed(2)}
              </span>
            ))}
          </div>
          {sinal.viesMtf && (
            <p className="mt-2.5 text-xs text-texto-fraco">
              Multi-timeframe: <span className="text-texto-suave">{sinal.viesMtf}</span>
            </p>
          )}
          {sinal.observacoes.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {sinal.observacoes.map((o) => (
                <li key={o} className="text-xs text-aviso">
                  · {o}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* --- desfecho --- */}
      {sinal.resultadoPontos !== null && (
        <footer
          className={`flex items-center gap-2 border-t px-5 py-2.5 text-xs ${
            sinal.resultadoPontos >= 0
              ? 'border-alta/25 bg-alta-fundo/30 text-alta'
              : 'border-baixa/25 bg-baixa-fundo/30 text-baixa'
          }`}
        >
          <span>{alta ? 'Compra' : 'Venda'} encerrada em {preco(sinal.precoSaida, sinal.ativo)}</span>
          <strong className="numerico ml-auto">
            {sinal.resultadoPontos >= 0 ? '+' : ''}
            {pontos(sinal.resultadoPontos)} pts
          </strong>
        </footer>
      )}
    </article>
  );
}

function Nivel({
  rotulo,
  valor,
  tom = 'neutro',
  borda = false,
}: {
  rotulo: string;
  valor: string;
  tom?: 'neutro' | 'alta' | 'baixa';
  borda?: boolean;
}) {
  const cor = { neutro: 'text-texto', alta: 'text-alta', baixa: 'text-baixa' }[tom];
  return (
    <div className={`px-5 py-3.5 ${borda ? 'border-l border-borda' : ''}`}>
      <p className="rotulo">{rotulo}</p>
      <p className={`numerico mt-0.5 text-xl font-semibold ${cor}`}>{valor}</p>
    </div>
  );
}

function Chip({
  rotulo,
  valor,
  tom = 'neutro',
  destaque = false,
}: {
  rotulo: string;
  valor: string;
  tom?: 'neutro' | 'baixa';
  destaque?: boolean;
}) {
  const cor = destaque ? 'text-alta' : tom === 'baixa' ? 'text-baixa' : 'text-texto';
  return (
    <span className="text-texto-fraco">
      {rotulo} <strong className={`numerico font-semibold ${cor}`}>{valor}</strong>
    </span>
  );
}

function Bloco({ rotulo, texto }: { rotulo: string; texto: string }) {
  // A tese usa **negrito** em markdown leve para destacar a zona quente.
  const partes = texto.split(/(\*\*[^*]+\*\*)/g);
  return (
    <div>
      <p className="rotulo mb-1">{rotulo}</p>
      <p className="text-[13px] leading-relaxed text-texto-suave">
        {partes.map((p, i) =>
          p.startsWith('**') ? (
            <strong key={i} className="font-semibold text-marca">
              {p.slice(2, -2)}
            </strong>
          ) : (
            <span key={i}>{p}</span>
          ),
        )}
      </p>
    </div>
  );
}
