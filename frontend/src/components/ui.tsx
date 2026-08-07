import type { ReactNode } from 'react';

import { emR, percentual } from '../lib/formato';
import type { Direcao, StatusSinal } from '../lib/tipos';

export function Cartao({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`cartao p-5 ${className}`}>{children}</div>;
}

export function Titulo({ children, acao }: { children: ReactNode; acao?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-4">
      <h2 className="text-sm font-semibold tracking-wide text-texto-suave uppercase">
        {children}
      </h2>
      {acao}
    </div>
  );
}

export function Botao({
  children,
  variante = 'primario',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: 'primario' | 'neutro' | 'perigo';
}) {
  const estilos = {
    primario: 'bg-marca text-fundo hover:bg-marca-forte font-semibold',
    neutro: 'bg-superficie-alta text-texto hover:bg-borda border border-borda',
    perigo: 'bg-baixa/15 text-baixa hover:bg-baixa/25 border border-baixa/40',
  }[variante];

  return (
    <button
      {...props}
      className={`rounded-lg px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${estilos} ${props.className ?? ''}`}
    >
      {children}
    </button>
  );
}

/** Rótulo de direção. Cor + texto, nunca só cor — ver a nota de daltonismo em index.css. */
export function Direcional({ direcao }: { direcao: Direcao }) {
  const alta = direcao === 'ALTA';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold tracking-wide ${
        alta ? 'bg-alta-fundo text-alta' : 'bg-baixa-fundo text-baixa'
      }`}
    >
      {alta ? '▲' : '▼'} {alta ? 'COMPRA' : 'VENDA'}
    </span>
  );
}

/**
 * Selo de confiança do sinal.
 *
 * Nunca aparece sem o motivo no `title`: um rótulo "alta confiança" sozinho é uma
 * afirmação que o operador não tem como auditar, e é exatamente esse tipo de número sem
 * procedência que faz alguém entrar num trade que não entendeu.
 */
export function SeloConfianca({
  nivel,
  motivo,
}: {
  nivel: 'alta' | 'media' | 'baixa';
  motivo: string;
}) {
  const cfg = {
    alta: { classe: 'bg-alta-fundo text-alta border-alta/35', texto: 'convicção alta' },
    media: { classe: 'bg-marca-fundo text-marca border-marca/35', texto: 'convicção média' },
    baixa: {
      classe: 'bg-superficie-topo text-texto-fraco border-borda',
      texto: 'convicção baixa',
    },
  }[nivel];

  return (
    <span
      className={`rounded-md border px-2 py-1 text-[11px] font-semibold ${cfg.classe}`}
      title={motivo}
    >
      {cfg.texto}
    </span>
  );
}

const CORES_STATUS: Record<StatusSinal, string> = {
  ABERTO: 'bg-marca/15 text-marca',
  ACIONADO: 'bg-neutro/20 text-texto',
  ALVO: 'bg-alta/15 text-alta',
  STOP: 'bg-baixa/15 text-baixa',
  EXPIRADO: 'bg-superficie-alta text-texto-fraco',
  CANCELADO: 'bg-superficie-alta text-texto-fraco',
};

export function Etiqueta({ status, texto }: { status: StatusSinal; texto: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${CORES_STATUS[status]}`}>
      {texto}
    </span>
  );
}

/**
 * Métrica de destaque.
 *
 * `insuficiente` existe porque taxa de acerto sobre 4 operações não é evidência — e a
 * tela precisa dizer isso, em vez de exibir "75%" com a mesma confiança de um número
 * medido sobre 300 trades.
 */
export function Metrica({
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
  const cor = {
    neutro: 'text-texto',
    alta: 'text-alta',
    baixa: 'text-baixa',
    marca: 'text-marca',
  }[tom];

  return (
    <div className="cartao p-4">
      <p className="text-xs tracking-wide text-texto-fraco uppercase">{rotulo}</p>
      <p className={`numerico mt-1 text-2xl font-semibold ${cor}`}>{valor}</p>
      {detalhe && <p className="mt-1 text-xs text-texto-fraco">{detalhe}</p>}
      {insuficiente && (
        <p className="mt-2 text-xs text-aviso" title="Menos de 30 operações encerradas">
          amostra insuficiente
        </p>
      )}
    </div>
  );
}

export function BarraScore({ score }: { score: number }) {
  const tom = score >= 0.7 ? 'bg-alta' : score >= 0.5 ? 'bg-marca' : 'bg-neutro';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-superficie-alta">
        <div className={`h-full ${tom}`} style={{ width: `${Math.round(score * 100)}%` }} />
      </div>
      <span className="numerico text-xs text-texto-suave">{score.toFixed(2)}</span>
    </div>
  );
}

export function Vazio({ titulo, detalhe }: { titulo: string; detalhe?: string }) {
  return (
    <div className="cartao flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="text-sm font-medium text-texto-suave">{titulo}</p>
      {detalhe && <p className="max-w-md text-xs leading-relaxed text-texto-fraco">{detalhe}</p>}
    </div>
  );
}

export function Carregando({ texto = 'carregando…' }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-texto-fraco">
      <span className="h-2 w-2 animate-pulse rounded-full bg-marca" />
      {texto}
    </div>
  );
}

export function Alerta({
  tom = 'aviso',
  children,
  className = '',
}: {
  tom?: 'aviso' | 'erro' | 'info';
  children: ReactNode;
  className?: string;
}) {
  const estilo = {
    aviso: 'border-aviso/35 bg-aviso/8 text-aviso',
    erro: 'border-baixa/40 bg-baixa-fundo/40 text-baixa',
    info: 'border-borda bg-superficie-alta/60 text-texto-suave',
  }[tom];
  return (
    <div className={`rounded-xl border px-4 py-3 text-[13px] leading-relaxed ${estilo} ${className}`}>
      {children}
    </div>
  );
}

/** Taxa de acerto + expectância lado a lado — os dois números que decidem se um padrão fica. */
export function Desempenho({
  taxa,
  expectancia,
  suficiente,
}: {
  taxa: number;
  expectancia: number;
  suficiente: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="numerico text-sm">{percentual(taxa)}</span>
      <span
        className={`numerico text-sm font-semibold ${expectancia >= 0 ? 'text-alta' : 'text-baixa'}`}
      >
        {emR(expectancia)}
      </span>
      {!suficiente && (
        <span className="text-xs text-aviso" title="Menos de 30 ocorrências">
          n baixo
        </span>
      )}
    </div>
  );
}
