import { useState } from 'react';

import { api } from '../lib/api';
import type { Ativo, Narrativa } from '../lib/tipos';

/**
 * A leitura da IA sobre o dossiê que o motor já produziu.
 *
 * **Sob demanda, não automática.** Cada leitura custa ~25 mil tokens e alguns segundos;
 * disparar sozinha a cada candle gastaria dinheiro para reescrever o mesmo texto enquanto
 * o operador olha outra tela. O botão também deixa claro de quem é a iniciativa.
 *
 * O que esta caixa mostra e a Sala não mostra: o **contra-argumento** e as
 * **incoerências**. O resto do dossiê é o motor explicando por que aprovou; aqui é a
 * leitura de tudo junto, incluindo onde a própria tese não fecha com o que foi medido.
 */
export function LeituraDaIA({ ativo }: { ativo: Ativo }) {
  const [narrativa, setNarrativa] = useState<Narrativa | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pedir = async () => {
    setCarregando(true);
    setErro(null);
    try {
      setNarrativa(await api.get<Narrativa>(api.comFiltros('/mercado/narrativa', { ativo })));
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Falha ao consultar a IA');
    } finally {
      setCarregando(false);
    }
  };

  return (
    <section className="cartao px-5 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="titulo-secao mb-0">
            Leitura da IA{' '}
            <span className="text-xs font-normal text-texto-fraco">
              o dossiê do motor, lido por inteiro
            </span>
          </h2>
          <p className="mt-1 text-xs text-texto-fraco">
            A IA <strong>não decide</strong> entrada, stop nem alvo — esses números vêm do
            motor determinístico. Ela lê tudo junto, monta o caso contra e aponta onde a
            tese não bate com o que foi medido.
          </p>
        </div>
        <button
          onClick={() => void pedir()}
          disabled={carregando}
          className="rounded-lg border border-borda px-3 py-1.5 text-sm text-texto-suave transition-colors hover:border-borda-forte hover:text-texto disabled:opacity-50"
        >
          {carregando ? 'analisando…' : narrativa ? 'reanalisar' : 'analisar agora'}
        </button>
      </div>

      {erro && <p className="mt-3 text-sm text-baixa">{erro}</p>}

      {narrativa && !narrativa.disponivel && (
        <p className="mt-3 text-sm text-aviso">
          IA indisponível — o motor segue funcionando normalmente.{' '}
          <span className="text-texto-fraco">{narrativa.motivo}</span>
        </p>
      )}

      {narrativa?.disponivel && (
        <div className="mt-4 space-y-4">
          <p className="text-sm leading-relaxed">{narrativa.leitura}</p>

          {narrativa.incoerencias.length > 0 && (
            <Bloco
              titulo="Incoerências encontradas"
              nota="onde a tese não fecha com o que foi medido"
              itens={narrativa.incoerencias}
              tom="aviso"
            />
          )}
          {narrativa.contra.length > 0 && (
            <Bloco
              titulo="O caso contra a operação"
              nota="montado dos fatores que pesaram para baixo"
              itens={narrativa.contra}
              tom="baixa"
            />
          )}
          {narrativa.atencao.length > 0 && (
            <Bloco titulo="Vigiar nos próximos candles" itens={narrativa.atencao} />
          )}

          <p className="border-t border-borda pt-3 text-[11px] text-texto-fraco">
            {narrativa.modelo} · {narrativa.tokens.toLocaleString('pt-BR')} tokens ·
            rastreado no Langfuse
          </p>
        </div>
      )}
    </section>
  );
}

function Bloco({
  titulo,
  nota,
  itens,
  tom,
}: {
  titulo: string;
  nota?: string;
  itens: string[];
  tom?: 'aviso' | 'baixa';
}) {
  const cor = tom === 'aviso' ? 'border-aviso/40' : tom === 'baixa' ? 'border-baixa/40' : 'border-borda';
  return (
    <div className={`rounded-lg border ${cor} px-3 py-2.5`}>
      <p className="rotulo">
        {titulo}
        {nota && <span className="ml-2 font-normal normal-case text-texto-fraco">{nota}</span>}
      </p>
      <ul className="mt-1.5 space-y-1">
        {itens.map((item, i) => (
          <li key={i} className="text-sm leading-relaxed text-texto-suave">
            <span className="mr-1.5 text-texto-fraco">·</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
