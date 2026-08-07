"""Tipos base do motor — candle, série, contexto e detecção.

Vocabulário em pt-BR por convenção do repositório. Nada aqui depende de I/O, de banco
ou de MetaTrader: são estruturas puras, para que detectores e backtest rodem em qualquer
ambiente (inclusive nos testes, sem corretora).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np


class Direcao(Enum):
    """Direção de um candle ou de um sinal."""

    ALTA = "alta"
    BAIXA = "baixa"
    NEUTRA = "neutra"

    @property
    def oposta(self) -> Direcao:
        if self is Direcao.ALTA:
            return Direcao.BAIXA
        if self is Direcao.BAIXA:
            return Direcao.ALTA
        return Direcao.NEUTRA


class Tendencia(Enum):
    """Contexto de mercado. LATERAL não é 'neutro fraco' — é ausência de tendência.

    A distinção importa: padrão de reversão exige algo para reverter. Num mercado
    lateral, um engolfo de alta não reverte nada, só marca o topo de uma oscilação.
    """

    ALTA = "alta"
    BAIXA = "baixa"
    LATERAL = "lateral"


class Familia(Enum):
    ISOLADO = "isolado"
    REVERSAO = "reversao"
    CONTINUACAO = "continuacao"


class Timeframe(Enum):
    """Timeframes do escopo. O valor é a duração em minutos."""

    M5 = 5
    M15 = 15
    M30 = 30
    H1 = 60
    D1 = 1440

    @property
    def rotulo(self) -> str:
        return {5: "5min", 15: "15min", 30: "30min", 60: "60min", 1440: "diário"}[self.value]

    @property
    def e_intraday(self) -> bool:
        """Intraday muda o tratamento de gap: dentro do pregão o preço é contínuo.

        Ver docs/ERRATA-EBOOK.md item 10 — sem isso, todo padrão que exige gap
        (Bebê Abandonado, Chute, Tasuki…) nunca dispararia em 5 minutos.
        """
        return self.value < 1440


@dataclass(frozen=True, slots=True)
class Candle:
    """Um candle OHLCV. Imutável: detectores nunca alteram a série que recebem."""

    ts: datetime
    abertura: float
    maxima: float
    minima: float
    fechamento: float
    volume: float = 0.0

    # --- geometria bruta ---------------------------------------------------

    @property
    def corpo(self) -> float:
        """Tamanho do corpo, sempre positivo."""
        return abs(self.fechamento - self.abertura)

    @property
    def amplitude(self) -> float:
        """Máxima menos mínima. Pode ser zero num candle sem negociação."""
        return self.maxima - self.minima

    @property
    def topo_corpo(self) -> float:
        return max(self.abertura, self.fechamento)

    @property
    def base_corpo(self) -> float:
        return min(self.abertura, self.fechamento)

    @property
    def meio_corpo(self) -> float:
        """Metade do corpo — referência de várias regras do ebook ('fecha acima da
        metade do corpo do primeiro')."""
        return (self.abertura + self.fechamento) / 2.0

    @property
    def sombra_superior(self) -> float:
        return self.maxima - self.topo_corpo

    @property
    def sombra_inferior(self) -> float:
        return self.base_corpo - self.minima

    # --- geometria relativa ------------------------------------------------
    # Tudo daqui para baixo é adimensional: é o que deixa o mesmo limiar valer
    # para WIN (pontos) e WDO (reais), e para 5min e 60min.

    @property
    def corpo_pct(self) -> float:
        """Fração da amplitude ocupada pelo corpo. 1.0 = marubozu, 0.0 = doji."""
        if self.amplitude <= 0:
            return 0.0
        return self.corpo / self.amplitude

    @property
    def sombra_sup_pct(self) -> float:
        if self.amplitude <= 0:
            return 0.0
        return self.sombra_superior / self.amplitude

    @property
    def sombra_inf_pct(self) -> float:
        if self.amplitude <= 0:
            return 0.0
        return self.sombra_inferior / self.amplitude

    @property
    def direcao(self) -> Direcao:
        if self.fechamento > self.abertura:
            return Direcao.ALTA
        if self.fechamento < self.abertura:
            return Direcao.BAIXA
        return Direcao.NEUTRA

    @property
    def e_alta(self) -> bool:
        return self.fechamento > self.abertura

    @property
    def e_baixa(self) -> bool:
        return self.fechamento < self.abertura

    @property
    def posicao_fechamento(self) -> float:
        """Onde o fechamento caiu dentro da amplitude: 0.0 = na mínima, 1.0 = na máxima.

        O ebook (p.4) trata isso como a informação mais importante do candle:
        'quanto mais próximo o fechamento estiver da máxima, mais fortes os touros'.
        """
        if self.amplitude <= 0:
            return 0.5
        return (self.fechamento - self.minima) / self.amplitude

    def contem_corpo(self, outro: Candle) -> bool:
        """True se o corpo de `outro` está inteiramente dentro do corpo deste.

        Base do Harami e derivados. Usa <= para aceitar coincidência exata de preço,
        que é comum no WIN por causa do tick de 5 pontos.
        """
        return self.base_corpo <= outro.base_corpo and outro.topo_corpo <= self.topo_corpo


@dataclass
class Serie:
    """Sequência de candles de um ativo num timeframe, com arrays numpy em cache.

    Detectores trabalham com `Candle`; indicadores trabalham com os arrays. Manter os
    dois na mesma estrutura evita converter ida e volta a cada chamada — o backtest
    percorre a série dezenas de milhares de vezes.
    """

    ativo: str
    timeframe: Timeframe
    candles: list[Candle]
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    def __len__(self) -> int:
        return len(self.candles)

    def __getitem__(self, i):
        return self.candles[i]

    def __iter__(self):
        return iter(self.candles)

    def _coluna(self, nome: str, extrator) -> np.ndarray:
        if nome not in self._cache:
            self._cache[nome] = np.array([extrator(c) for c in self.candles], dtype=float)
        return self._cache[nome]

    @property
    def abertura(self) -> np.ndarray:
        return self._coluna("abertura", lambda c: c.abertura)

    @property
    def maxima(self) -> np.ndarray:
        return self._coluna("maxima", lambda c: c.maxima)

    @property
    def minima(self) -> np.ndarray:
        return self._coluna("minima", lambda c: c.minima)

    @property
    def fechamento(self) -> np.ndarray:
        return self._coluna("fechamento", lambda c: c.fechamento)

    @property
    def volume(self) -> np.ndarray:
        return self._coluna("volume", lambda c: c.volume)

    def memo(self, chave: str, calcular):
        """Cache genérico para indicadores derivados (ATR, EMA, ADX…).

        Indicadores são recalculados a cada candle durante o backtest; sem memo, o
        custo vira quadrático.
        """
        if chave not in self._cache:
            self._cache[chave] = calcular()
        return self._cache[chave]

    def invalidar_cache(self) -> None:
        """Chamar depois de anexar candles novos (ingestão ao vivo)."""
        self._cache.clear()

    def janela(self, fim: int, tamanho: int) -> list[Candle]:
        """Os `tamanho` candles que terminam em `fim` (inclusive).

        Devolve lista vazia se não houver histórico suficiente — o chamador não
        precisa checar limites.
        """
        inicio = fim - tamanho + 1
        if inicio < 0 or fim >= len(self.candles):
            return []
        return self.candles[inicio : fim + 1]

    def fatiar(self, ate: int) -> Serie:
        """Série truncada em `ate` (inclusive), sem os candles futuros.

        É a defesa contra look-ahead no backtest: o motor só enxerga o que existiria
        naquele instante. Cache novo de propósito.
        """
        return Serie(self.ativo, self.timeframe, self.candles[: ate + 1])


@dataclass(frozen=True, slots=True)
class Contexto:
    """Leitura de mercado no instante de um candle. Entrada obrigatória dos detectores."""

    tendencia: Tendencia
    forca_tendencia: float
    """0..1 — derivada do ADX. Abaixo do limiar de lateralidade, vira LATERAL."""

    atr: float
    """ATR(14) no candle. Unidade do ativo; é o denominador de toda normalização."""

    regime_volatilidade: float
    """ATR atual / média do ATR. >1 = mercado mais agitado que o normal."""

    janela_pregao: str
    """Rótulo da janela do pregão (abertura, tendência, almoço, EUA, fechamento…)."""

    peso_horario: float
    """Multiplicador de confluência da janela atual."""

    indice: int
    """Posição do candle na série — útil para rastrear a detecção de volta."""


@dataclass(frozen=True, slots=True)
class Deteccao:
    """Uma ocorrência de padrão. Ainda não é um trade: não tem entrada nem stop.

    Quem transforma isto em operação é `decisao.py`, depois de passar pela confluência.
    """

    padrao_id: str
    nome: str
    familia: Familia
    direcao: Direcao
    indice_fim: int
    """Índice do ÚLTIMO candle do padrão na série."""

    n_candles: int
    forca: float
    """0..1 — quão limpa foi a formação. Não é probabilidade de acerto."""

    confiabilidade: float
    """Prior do ebook, ou taxa medida pelo backtest quando houver amostra."""

    extremo_superior: float
    """Máxima de toda a formação — base do stop em operação vendida."""

    extremo_inferior: float
    """Mínima de toda a formação — base do stop em operação comprada."""

    preco_referencia: float
    """Fechamento do último candle do padrão."""

    pagina_ebook: int = 0
    detalhes: dict = field(default_factory=dict)

    @property
    def amplitude(self) -> float:
        return self.extremo_superior - self.extremo_inferior

    @property
    def score_bruto(self) -> float:
        """Força × confiabilidade, antes de qualquer confluência.

        Ponto de partida do score final. Uma formação perfeita de um padrão que o
        histórico mostra ser ruim continua valendo pouco — e vice-versa.
        """
        return self.forca * self.confiabilidade
