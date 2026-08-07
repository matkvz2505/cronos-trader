"""Retrações e projeções de Fibonacci sobre a última perna de movimento.

Fibonacci não prevê nada sozinho — é um **mapa de onde há ordem no book**. Muita gente
opera esses níveis, então eles viram suporte e resistência por profecia auto-realizável.
É exatamente por isso que servem ao motor: não como sinal, mas como filtro de *lugar*.

A regra do produto: um martelo em 61.8% de retração vale muito mais que um martelo no
meio do nada. Aqui só se calcula o mapa; quem pontua é `confluencia.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .indicadores import swings_confirmados
from .limiares import PADRAO, Limiares
from .tipos import Direcao, Serie

RETRACOES = (0.236, 0.382, 0.5, 0.618, 0.786)
"""Níveis de retração. 0.5 não é de Fibonacci — é a metade — mas é dos mais respeitados
na prática, e o ebook usa a mesma ideia de "metade do corpo" em vários padrões."""

PROJECOES = (1.272, 1.618, 2.0, 2.618)
"""Níveis de projeção, usados como alvo em `decisao.py`."""

NIVEIS_NOBRES = (0.382, 0.5, 0.618)
"""A "zona de ouro" da literatura. Mantida como referência **a priori** — e o estudo
abaixo mostra que ela não se sustenta como se acredita."""


# ---------------------------------------------------------------------------
# Níveis medidos — evidência no lugar de folclore
# ---------------------------------------------------------------------------
#
# Medido com `scripts/estudo_fibonacci.py` sobre 60.000 candles de M5 de cada ativo
# (jun/2024 a ago/2026): ~2.400 correções com virada clara por ativo.
#
# O teste é local e por isso honesto: em bins finos de 2%, a taxa de virada no bin do
# nível é comparada com a dos vizinhos imediatos. Um nível que o mercado enxerga produz
# **pico local**; um número sem significado produz curva lisa.
#
# Métricas por faixa larga (as que circulam por aí) enganam: a probabilidade de a
# correção terminar na próxima faixa cresce com a profundidade de qualquer jeito, porque
# ela precisa terminar em algum lugar antes de 100%. A rampa monotônica que aparece nessas
# métricas é o resultado esperado do acaso.
#
# O que a medição encontrou:
#
#   WDO M5   0.500 → 1.34x os vizinhos   PICO REAL
#            0.382 → 0.89x · 0.618 → 1.14x · 0.786 → 1.01x   sem destaque
#   WIN M5   nenhum nível produz pico     (0.618 chega a 1.19x, abaixo do corte de 1.25)
#
# Também mediu, e vale registrar: a faixa dos 30% é o **oposto** de suporte nos dois
# ativos (0.79x no WDO, 0.74x no WIN) — é onde o preço menos costuma parar.

RAZAO_MINIMA_PICO = 1.25
"""Quanto o nível precisa superar a vizinhança para contar como respeitado."""

NIVEIS_RESPEITADOS: dict[str, dict[float, float]] = {
    # ativo → {nível: razão medida contra os vizinhos}
    "WDO": {0.500: 1.34},
    "WIN": {},
}


def relevancia(ativo: str, razao_fib: float) -> float:
    """0..1 — quanto este nível vale **neste ativo**, segundo a medição.

    Devolve 0 para tudo que não foi medido como pico, inclusive os níveis "nobres" da
    literatura. É deliberado: dar bônus a um nível que os dados dizem ser indiferente é
    inventar confluência, e confluência inventada vira sinal ruim com aparência de bom.
    """
    medidos = NIVEIS_RESPEITADOS.get(ativo.strip().upper()[:3], {})
    razao = medidos.get(round(razao_fib, 3))
    if razao is None:
        return 0.0
    # 1.25x (o corte) vale 0.5; 1.75x ou mais vale 1.0.
    return min(1.0, 0.5 + (razao - RAZAO_MINIMA_PICO) / 1.0)


def ativo_usa_fibonacci(ativo: str) -> bool:
    """Se algum nível se comprovou neste ativo.

    O WIN, hoje, não usa: nenhum nível passou no teste do pico em M5. Isso não é um
    defeito do motor — é o motor se recusando a pontuar por um fator que não mediu.
    """
    return bool(NIVEIS_RESPEITADOS.get(ativo.strip().upper()[:3], {}))


@dataclass(frozen=True, slots=True)
class Perna:
    """Um movimento direcional entre um fundo e um topo confirmados."""

    indice_inicio: int
    indice_fim: int
    preco_inicio: float
    preco_fim: float

    @property
    def direcao(self) -> Direcao:
        return Direcao.ALTA if self.preco_fim > self.preco_inicio else Direcao.BAIXA

    @property
    def amplitude(self) -> float:
        return abs(self.preco_fim - self.preco_inicio)

    @property
    def duracao(self) -> int:
        return self.indice_fim - self.indice_inicio


@dataclass(frozen=True, slots=True)
class NivelFib:
    razao: float
    preco: float
    nobre: bool

    @property
    def rotulo(self) -> str:
        return f"fib {self.razao:.3f}".rstrip("0").rstrip(".")


def ultima_perna(serie: Serie, i: int, lim: Limiares = PADRAO) -> Perna | None:
    """A perna mais recente confirmada até o candle `i`.

    Usa `swings_confirmados`, que por construção só devolve pivôs já estabelecidos em
    `i`. A perna nunca inclui o movimento em curso — o que é correto: você não traça
    Fibonacci de um topo que ainda não é topo.
    """
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)
    if not topos or not fundos:
        return None

    ultimo_topo = topos[-1]
    ultimo_fundo = fundos[-1]

    if ultimo_topo[0] > ultimo_fundo[0]:
        # O último pivô foi um topo: a perna subiu do fundo até ele.
        return Perna(ultimo_fundo[0], ultimo_topo[0], ultimo_fundo[1], ultimo_topo[1])
    return Perna(ultimo_topo[0], ultimo_fundo[0], ultimo_topo[1], ultimo_fundo[1])


def retracoes(perna: Perna) -> list[NivelFib]:
    """Níveis de correção **contra** a perna.

    Perna de alta corrige para baixo a partir do topo; perna de baixa corrige para cima
    a partir do fundo. Errar esse sinal inverte todo o mapa.
    """
    sentido = -1.0 if perna.direcao is Direcao.ALTA else 1.0
    return [
        NivelFib(r, perna.preco_fim + sentido * r * perna.amplitude, r in NIVEIS_NOBRES)
        for r in RETRACOES
    ]


def projecoes(perna: Perna) -> list[NivelFib]:
    """Níveis de extensão **a favor** da perna, medidos a partir do início.

    São os alvos naturais quando o preço retoma a direção original.
    """
    sentido = 1.0 if perna.direcao is Direcao.ALTA else -1.0
    return [
        NivelFib(p, perna.preco_inicio + sentido * p * perna.amplitude, False)
        for p in PROJECOES
    ]


def nivel_proximo(
    preco: float, niveis: list[NivelFib], atr: float, lim: Limiares = PADRAO
) -> NivelFib | None:
    """O nível de Fibonacci mais próximo de `preco`, se estiver dentro da tolerância.

    Tolerância em ATR, não em pontos: uma distância de 30 pontos é encostar num dia
    volátil e é longe num dia parado.
    """
    if atr <= 0 or not niveis:
        return None
    tolerancia = lim.tolerancia_zona_atr * atr
    candidato = min(niveis, key=lambda n: abs(n.preco - preco))
    if abs(candidato.preco - preco) > tolerancia:
        return None
    return candidato


def alvo_por_projecao(
    perna: Perna, direcao: Direcao, razao: float = 1.618
) -> float | None:
    """Alvo de Fibonacci para uma operação na direção informada.

    Só devolve alvo quando a direção da operação bate com a da perna — projetar um alvo
    de compra a partir de uma perna de baixa daria um número, mas não um número que
    signifique alguma coisa.
    """
    if perna.direcao is not direcao:
        return None
    sentido = 1.0 if direcao is Direcao.ALTA else -1.0
    return perna.preco_inicio + sentido * razao * perna.amplitude
