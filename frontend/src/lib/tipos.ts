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

export type PeriodoDiario = 'dia' | 'semana' | 'mes';

export interface LinhaDesempenhoPeriodo {
  chave: string;
  n: number;
  acertos: number;
  taxa: number;
  expectanciaR: number;
  resultadoR: number;
}

/** Fechamento de período + a preparação do próximo pregão. */
export interface Fechamento {
  ativo: Ativo;
  periodo: PeriodoDiario;
  inicio: string;
  fim: string;
  proximoPregao: string;
  movimento: {
    abertura: number;
    maxima: number;
    minima: number;
    fechamento: number;
    variacaoPct: number;
    amplitude: number;
    amplitudeAtr: number;
    candles: number;
    pregoes: number;
  } | null;
  placar: {
    emitidos: number;
    acionados: number;
    alvo: number;
    stop: number;
    expirados: number;
    abertos: number;
    encerrados: number;
    taxaAcerto: number;
    taxaAcionamento: number;
    expectanciaR: number;
    resultadoR: number;
    resultadoReais: number;
    amostraSuficiente: boolean;
  };
  porPadrao: LinhaDesempenhoPeriodo[];
  porJanela: LinhaDesempenhoPeriodo[];
  destaques: string[];
  niveisAmanha: Array<{ preco: number; rotulo: string; origem: string; nota: string }>;
  contextoAtual: {
    tendencia?: string;
    forcaTendencia?: number;
    atr?: number;
    regimeMedias?: string;
    ultimoCandle?: string;
  };
}

/** Um evento que merece interromper o que o operador está fazendo. */
export type TipoAlerta =
  | 'sinal.novo'
  | 'entrada.acionada'
  | 'saida.alvo'
  | 'saida.stop'
  | 'sinal.expirado';

export interface Alerta {
  id: string;
  tipo: TipoAlerta;
  em: string;
  sinal: Sinal;
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
  /** Timestamp do último candle — **não** é a hora atual. */
  momento: string;
  /**
   * Minutos desde o último candle. É o número que diz se a tela está de fato ao vivo:
   * sem ele, uma leitura de ontem às 15h30 tem a mesma cara de uma leitura de agora.
   */
  idadeMinutos: number;
  dadosFrescos: boolean;
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

/**
 * Preço ao vivo de um ativo, empurrado pelo WebSocket.
 *
 * `idadeMinutos` é a distância entre o candle e agora, e é o campo que decide se a tela
 * pode se apresentar como tempo real. `ts` é o relógio do pregão rotulado como UTC —
 * formate com os helpers de `formato.ts`, nunca com `toLocaleString` cru.
 */
export interface TickMercado {
  ativo: Ativo;
  ts: string | null;
  preco: number | null;
  aberturaDia: number | null;
  variacaoDia: number | null;
  idadeMinutos: number | null;
}

/** Uma entrada do dia, do ponto de vista de quem operaria. Vem de `/mercado/pregao`. */
export interface EntradaPregao {
  id: string;
  ativo: Ativo;
  hora: string;
  ts: string;
  direcao: Direcao;
  padrao: string;
  janela: string;
  entrada: number;
  stop: number;
  alvo: number;
  rr: number;
  contratos: number;
  riscoPontos: number;
  score: number;
  confiabilidade: number;
  status: StatusSinal;
  resultadoPontos: number | null;
  resultadoReais: number | null;
  resultadoR: number | null;
  acionada: boolean;
  encerrada: boolean;
  observacao: string;
}

export interface PlacarPregao {
  emitidos: number;
  acionados: number;
  alvo: number;
  stop: number;
  abertos: number;
  expirados: number;
  encerrados: number;
  taxaAcerto: number;
  expectanciaR: number;
  resultadoReais: number;
  resultadoR: number;
  custoTotal: number;
}

export interface Pregao {
  dia: string;
  ativo: Ativo;
  /** O dia ainda está em curso — o placar é parcial, não resultado. */
  aberto: boolean;
  placar: PlacarPregao;
  entradas: EntradaPregao[];
}

/**
 * A leitura da IA sobre o dossiê do motor.
 *
 * `disponivel: false` não é erro — é o gateway fora, e a tela segue inteira sem isto.
 */
export interface Narrativa {
  disponivel: boolean;
  motivo?: string;
  leitura: string;
  contra: string[];
  /** Onde a tese não bate com o que foi medido. Vazio é o resultado esperado. */
  incoerencias: string[];
  atencao: string[];
  modelo: string;
  tokens: number;
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
