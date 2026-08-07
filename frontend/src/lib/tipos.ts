/** Contratos da API. Espelham o que o backend devolve — mudou lá, muda aqui. */

export type Ativo = 'WIN' | 'WDO';
export type Timeframe = 'M5' | 'M15' | 'M30' | 'H1' | 'D1';
export type Direcao = 'ALTA' | 'BAIXA';
export type StatusSinal = 'ABERTO' | 'ACIONADO' | 'ALVO' | 'STOP' | 'EXPIRADO' | 'CANCELADO';

export interface Usuario {
  id: string;
  nome: string;
  email: string;
  papel: 'USUARIO' | 'ADMIN';
  capital: number;
  criadoEm: string;
  ultimoLogin: string | null;
}

export interface Sessao {
  usuario: Usuario;
  accessToken: string;
  refreshToken: string;
  expiraEm: string;
}

export interface Fator {
  nome: string;
  multiplicador: number;
  detalhe: string;
}

/**
 * A tese do sinal — o dossiê que responde por quê, quando, onde e o que invalida.
 *
 * Congelada no momento da emissão: reconstruí-la depois daria outra resposta, porque o
 * mercado já andou. É o registro do que se sabia na hora de decidir.
 */
export interface Tese {
  onde: string;
  quando: string;
  porque: string[];
  contra: string[];
  invalidacao: string;
  confianca: 'alta' | 'media' | 'baixa';
  confiancaMotivo: string;
}

export interface Sinal {
  id: string;
  tese: Tese | null;
  ativo: Ativo;
  timeframe: Timeframe;
  ts: string;
  direcao: Direcao;
  padraoId: string;
  padraoNome: string;
  entrada: number;
  stop: number;
  alvo: number;
  origemAlvo: string;
  riscoPontos: number;
  retornoPontos: number;
  rr: number;
  contratos: number;
  score: number;
  confiabilidade: number;
  fatores: Fator[];
  observacoes: string[];
  zonaQuente: boolean;
  viesMtf: string | null;
  status: StatusSinal;
  precoSaida: number | null;
  resultadoPontos: number | null;
  fechadoEm: string | null;
  criadoEm: string;
}

export interface Candle {
  ts: string;
  abertura: number;
  maxima: number;
  minima: number;
  fechamento: number;
  volume: number;
}

export interface Deteccao {
  ts: string;
  padraoId: string;
  padraoNome: string;
  direcao: string;
  forca: number;
  scoreBruto: number;
}

/**
 * Uma conta que o motor fez, com procedência.
 *
 * `formula` não é decoração: é a diferença entre "força 0,72" e "força 0,72 = média
 * harmônica de (0,9 · 0,6)". Número sem procedência na tela é pedido de fé.
 */
export interface Conta {
  rotulo: string;
  valor: string;
  formula: string;
  veredito: string;
  tom: 'neutro' | 'favoravel' | 'contrario';
}

export interface LeituraTimeframe {
  timeframe: string;
  tendencia: 'alta' | 'baixa' | 'lateral';
  forcaTendencia: number;
  fechamento: number;
  atr: number;
  regimeMedias: string;
  direcaoMedias: string;
  alinhamento: number;
  contas: Conta[];
}

/**
 * Um padrão que apareceu e **não** virou sinal.
 *
 * É o coração da Sala. Um operador aprende mais vendo por que 40 setups foram recusados
 * do que vendo os 2 aprovados — e é a recusa explicada que separa esta ferramenta de um
 * robô que pede fé.
 */
export interface Vigilancia {
  padrao: string;
  direcao: string;
  forca: number;
  score: number;
  motivo: string;
  faltou: string;
}

export interface NivelAtivo {
  preco: number;
  rotulo: string;
  origem: 'fibonacci' | 'media' | 'estrutura';
  peso: number;
  nota: string;
}

export interface Raciocinio {
  ativo: Ativo;
  momento: string;
  preco: number;
  variacaoDia: number;
  vies: string;
  viesDirecao: 'alta' | 'baixa' | 'neutra';
  alinhado: boolean;
  janelaPregao: string;
  operaAgora: boolean;
  veredito: string;
  timeframes: LeituraTimeframe[];
  estrutura: Estrutura;
  niveis: NivelAtivo[];
  vigiando: Vigilancia[];
  sinal: (Record<string, unknown> & { resumo: string; explicacao: string }) | null;
}

/** Um ponto de reta no espaço (tempo, preço). */
export interface PontoReta {
  ts: string | null;
  preco: number;
}

export interface Reta {
  de: PontoReta;
  ate: PontoReta;
  inclinacao: number;
}

/**
 * O desenho do gráfico — o que um analista rabisca por cima antes de decidir.
 *
 * Zonas são **faixas**, não linhas: o preço não reage num tick exato, reage numa região.
 * Desenhar linha daria a falsa precisão de "o nível é 63.400" quando é "entre 63.350 e
 * 63.450".
 */
export interface Estrutura {
  resumo: string;
  canal: {
    tipo: 'ascendente' | 'descendente' | 'lateral';
    topo: Reta;
    fundo: Reta;
    toques: number;
    larguraAtr: number;
  } | null;
  rompimentos: Array<{
    ts: string | null;
    preco: number;
    direcao: 'alta' | 'baixa';
    forcaAtr: number;
  }>;
  faixas: Array<{
    tipo: 'oferta' | 'demanda';
    precoMin: number;
    precoMax: number;
    toques: number;
    forca: number;
  }>;
  linhaTendencia: Reta | null;
  pivos: Array<{ ts: string | null; preco: number; tipo: 'topo' | 'fundo' }>;
}

export interface PadraoCatalogo {
  id: string;
  nome: string;
  familia: 'isolado' | 'reversao' | 'continuacao';
  direcao: string;
  n_candles: number;
  tendencia_requerida: string | null;
  confiabilidade_ebook: number;
  confiabilidade_medida: number | null;
  ocorrencias_medidas: number;
  pagina_ebook: number;
  exige_gap: boolean;
  derivado_por_simetria: boolean;
  observacao: string;
}

export interface ResumoSinais {
  abertos: number;
  emitidosHoje: number;
  encerrados: number;
  taxaAcerto: number;
  expectanciaR: number;
  amostraSuficiente: boolean;
}

export interface DesempenhoPadrao {
  padraoId: string;
  nome: string;
  ocorrencias: number;
  acertos: number;
  taxaAcerto: number;
  expectanciaR: number;
  suficiente: boolean;
}

export interface Saude {
  ok: boolean;
  banco: boolean;
  motor:
    | {
        ok: boolean;
        versao?: string;
        padroes?: number;
        banco?: boolean;
        bancoDetalhe?: string;
        /** `emContainer` distingue "MT5 fora" de "MT5 não pode estar aqui, por desenho". */
        mt5?: { disponivel: boolean; detalhe: string; emContainer?: boolean };
        candles?: Array<{ ativo: string; timeframe: string; total: number; ultimo: string | null }>;
      }
    | { ok: false; erro: string };
  candles: Array<{ ativo: string; timeframe: string; total: number; ultimo: string | null }> | null;
}

export interface JanelaWalkForward {
  indice: number;
  treinoExpectanciaR: number;
  testeExpectanciaR: number;
  testeTaxaAcerto: number;
  testeResultadoReais: number;
  padroesCalibrados: number;
}

export interface ResultadoBacktest {
  id: string;
  modo: 'backtest' | 'walkforward';
  expectanciaMediaForaDaAmostra?: number;
  temEdge?: boolean;
  janelas?: JanelaWalkForward[];
  sinaisGerados?: number;
  acionados?: number;
  taxaAcerto?: number;
  expectanciaR?: number;
  resultadoReais?: number;
  rebaixamentoMax?: number;
  aviso?: string;
  relatorio: string;
}
