"""Padrões isolados — ebook p.5–6.

O ebook é direto sobre o valor deles: *"tem confiabilidade baixa, como todos os padrões de
candlestick isolados"* (p.6) e *"são mais importantes quando formam padrões de 2 ou mais
candlesticks"* (p.5).

Por isso todos entram com `PRIOR_INDECISAO`. Eles existem no catálogo não para gerar sinal
sozinhos — quase nunca passam do score mínimo — mas porque são **blocos de construção**
dos padrões compostos e porque marcar um doji no gráfico é informação visual legítima
para quem opera olhando a tela.
"""

from __future__ import annotations

from ..limiares import Limiares
from ..normalizacao import (
    combinar,
    e_doji,
    e_marubozu,
    e_spinning_top,
    razao_sombra_corpo,
    satisfaz_max,
    satisfaz_min,
)
from ..tipos import Candle, Contexto, Direcao, Familia, Tendencia
from .base import PRIOR_INDECISAO, padrao


@padrao(
    id="doji",
    nome="Doji",
    familia=Familia.ISOLADO,
    direcao=Direcao.NEUTRA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=5,
)
def doji(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Corpo desprezível: abertura e fechamento praticamente no mesmo preço.

    Neutralidade ou indecisão do mercado — touros e ursos empataram no período.
    """
    return e_doji(janela[0], lim)


@padrao(
    id="doji_libelula",
    nome="Doji Libélula",
    familia=Familia.ISOLADO,
    direcao=Direcao.ALTA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=5,
    tendencia=Tendencia.BAIXA,
)
def doji_libelula(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Abertura, fechamento e máxima praticamente iguais, com sombra inferior longa.

    O preço afundou durante o período e voltou inteiro — rejeição do nível mais baixo.
    O ebook: *"pode representar uma reversão após longa tendência de baixa"*.
    """
    c = janela[0]
    return combinar(
        e_doji(c, lim),
        satisfaz_max(c.sombra_sup_pct, lim.sombra_curta_pct_max, lim.sombra_curta_pct_max),
        satisfaz_min(c.sombra_inf_pct, 0.60, 0.30),
    )


@padrao(
    id="doji_lapide",
    nome="Doji Lápide",
    familia=Familia.ISOLADO,
    direcao=Direcao.BAIXA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=5,
    tendencia=Tendencia.ALTA,
)
def doji_lapide(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Espelho da libélula: corpo colado na mínima, sombra superior longa.

    O ebook: *"tem mais relevância se surgir no final de uma tendência de alta"*.
    """
    c = janela[0]
    return combinar(
        e_doji(c, lim),
        satisfaz_max(c.sombra_inf_pct, lim.sombra_curta_pct_max, lim.sombra_curta_pct_max),
        satisfaz_min(c.sombra_sup_pct, 0.60, 0.30),
    )


@padrao(
    id="marubozu_alta",
    nome="Marubozu de Alta",
    familia=Familia.ISOLADO,
    direcao=Direcao.ALTA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=5,
    observacao=(
        "Leitura depende do contexto: em tendência de alta sugere continuidade; "
        "depois de um movimento longo de baixa, possível reversão. A camada de "
        "confluência resolve isso — o detector só afirma a geometria."
    ),
)
def marubozu_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Corpo verde grande, sem sombras: compradores mandaram do início ao fim."""
    return e_marubozu(janela[0], lim, Direcao.ALTA)


@padrao(
    id="marubozu_baixa",
    nome="Marubozu de Baixa",
    familia=Familia.ISOLADO,
    direcao=Direcao.BAIXA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=6,
)
def marubozu_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    return e_marubozu(janela[0], lim, Direcao.BAIXA)


@padrao(
    id="spinning_top",
    nome="Spinning Top",
    familia=Familia.ISOLADO,
    direcao=Direcao.NEUTRA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=6,
)
def spinning_top(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Corpo pequeno espremido entre duas sombras longas.

    Briga sem vencedor: o preço subiu e caiu bastante e terminou onde começou. O ebook
    ressalva que a sombra ser exatamente 2× o corpo *"não é característica obrigatória"*
    — por isso `sombra_longa_ratio` é limiar calibrável e não regra fixa.
    """
    return e_spinning_top(janela[0], lim)


@padrao(
    id="martelo_isolado",
    nome="Candle de Rejeição",
    familia=Familia.ISOLADO,
    direcao=Direcao.NEUTRA,
    n_candles=1,
    confiabilidade=PRIOR_INDECISAO,
    pagina=4,
    observacao=(
        "Não é um padrão nomeado no ebook. Marca qualquer candle com sombra muito "
        "desproporcional, que a p.4 define como o núcleo da leitura: 'as sombras "
        "representam a força do lado oposto, ou a rejeição do preço naquele nível'. "
        "Útil como marcação visual e como insumo de suporte/resistência."
    ),
)
def candle_rejeicao(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Uma sombra dominando o candle — o preço foi até um nível e foi devolvido."""
    c = janela[0]
    if c.amplitude <= 0:
        return None
    maior = max(c.sombra_superior, c.sombra_inferior)
    return combinar(
        satisfaz_min(maior / c.amplitude, 0.60, 0.30),
        satisfaz_min(razao_sombra_corpo(maior, c.corpo), 2.5, 3.0),
    )
