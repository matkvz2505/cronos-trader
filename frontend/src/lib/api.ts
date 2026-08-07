/**
 * Cliente HTTP com renovação automática de sessão.
 *
 * O access token vive 15 minutos. Sem renovação transparente, o usuário seria deslogado
 * no meio do pregão — que é exatamente o pior momento. Quando uma chamada volta 401, o
 * cliente troca o refresh por um par novo e **repete a requisição original**.
 *
 * A renovação é serializada numa promise única (`renovacaoEmCurso`): a tela dispara
 * várias chamadas em paralelo, e sem isso cinco delas tentariam renovar ao mesmo tempo —
 * a primeira rotacionaria o refresh e as outras quatro receberiam 401 com um token que
 * acabou de ser revogado.
 */
import type { Sessao } from './tipos';

const CHAVE_SESSAO = 'cronos-trader.sessao';

export class ErroApi extends Error {
  constructor(
    readonly status: number,
    mensagem: string,
    readonly codigo?: string,
    readonly campos?: Array<{ campo: string; mensagem: string }>,
  ) {
    super(mensagem);
    this.name = 'ErroApi';
  }
}

export function lerSessao(): Sessao | null {
  const bruto = localStorage.getItem(CHAVE_SESSAO);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto) as Sessao;
  } catch {
    localStorage.removeItem(CHAVE_SESSAO);
    return null;
  }
}

export function salvarSessao(sessao: Sessao): void {
  localStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao));
}

export function limparSessao(): void {
  localStorage.removeItem(CHAVE_SESSAO);
}

let renovacaoEmCurso: Promise<Sessao | null> | null = null;

async function renovar(): Promise<Sessao | null> {
  const sessao = lerSessao();
  if (!sessao?.refreshToken) return null;

  const resposta = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ refreshToken: sessao.refreshToken }),
  });

  if (!resposta.ok) {
    limparSessao();
    return null;
  }
  const nova = (await resposta.json()) as Sessao;
  salvarSessao(nova);
  return nova;
}

async function renovarUmaVez(): Promise<Sessao | null> {
  renovacaoEmCurso ??= renovar().finally(() => {
    renovacaoEmCurso = null;
  });
  return renovacaoEmCurso;
}

async function requisitar<T>(
  caminho: string,
  opcoes: RequestInit = {},
  tentarRenovar = true,
): Promise<T> {
  const sessao = lerSessao();
  const cabecalhos: Record<string, string> = {
    'content-type': 'application/json',
    ...(opcoes.headers as Record<string, string> | undefined),
  };
  if (sessao?.accessToken) cabecalhos.authorization = `Bearer ${sessao.accessToken}`;

  const resposta = await fetch(`/api/v1${caminho}`, { ...opcoes, headers: cabecalhos });

  if (resposta.status === 401 && tentarRenovar) {
    const nova = await renovarUmaVez();
    if (nova) return requisitar<T>(caminho, opcoes, false);
    limparSessao();
    window.dispatchEvent(new CustomEvent('cronos:sessao-expirada'));
    throw new ErroApi(401, 'Sessão expirada. Faça login novamente.');
  }

  if (!resposta.ok) {
    const corpo = (await resposta.json().catch(() => ({}))) as {
      erro?: string;
      codigo?: string;
      campos?: Array<{ campo: string; mensagem: string }>;
    };
    throw new ErroApi(
      resposta.status,
      corpo.erro ?? `Erro ${resposta.status}`,
      corpo.codigo,
      corpo.campos,
    );
  }

  if (resposta.status === 204) return undefined as T;
  return (await resposta.json()) as T;
}

const get = <T>(caminho: string) => requisitar<T>(caminho);
const post = <T>(caminho: string, corpo?: unknown) =>
  requisitar<T>(caminho, { method: 'POST', body: corpo ? JSON.stringify(corpo) : undefined });
const patch = <T>(caminho: string, corpo: unknown) =>
  requisitar<T>(caminho, { method: 'PATCH', body: JSON.stringify(corpo) });

function comFiltros(base: string, filtros: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor !== undefined && valor !== null && valor !== '') params.set(chave, String(valor));
  }
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

export const api = {
  get,
  post,
  patch,
  comFiltros,
};
