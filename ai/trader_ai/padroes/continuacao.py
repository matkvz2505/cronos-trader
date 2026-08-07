"""Padrões de continuação — ebook p.19–21.

Família menor e mais delicada de operar: o sinal aqui é "a tendência que já existe vai
seguir", então a entrada é sempre a favor do movimento — e o risco é entrar tarde, perto
da exaustão. Todos exigem tendência definida; nenhum vale em mercado lateral.

O ebook é honesto sobre o Strike em particular: *"não duvide da força vendedora após um
candle desse tamanho. O famoso 'medo de perder' pode se transformar em pânico em massa"*.
"""

from __future__ import annotations

from ..limiares import Limiares
from ..normalizacao import (
    coincidem,
    combinar,
    e_candle_forca,
    gap_extremo_alta,
    gap_extremo_baixa,
    satisfaz,
    satisfaz_max,
)
from ..tipos import Candle, Contexto, Direcao, Familia, Tendencia
from .base import PRIOR_BAIXA, PRIOR_NEUTRO, padrao

# ===========================================================================
# Linha de Separação — p.19
# ===========================================================================


@padrao(
    id="linha_separacao_alta",
    nome="Linha de Separação de Alta",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=19,
    tendencia=Tendencia.ALTA,
)
def linha_separacao_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho de força e verde de força abrindo no mesmo preço.

    O ebook lê como *"resposta rápida da força compradora à tentativa dos ursos de
    reverter"*: os vendedores conseguiram um candle inteiro, e no seguinte o preço abriu
    exatamente onde eles começaram — como se a queda não tivesse acontecido.
    """
    c1, c2 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.BAIXA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.ALTA),
        coincidem(c1.abertura, c2.abertura, ctx.atr, lim),
    )


@padrao(
    id="linha_separacao_baixa",
    nome="Linha de Separação de Baixa",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=19,
    tendencia=Tendencia.BAIXA,
)
def linha_separacao_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Verde de força e vermelho de força abrindo no mesmo preço."""
    c1, c2 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.ALTA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.BAIXA),
        coincidem(c1.abertura, c2.abertura, ctx.atr, lim),
    )


# ===========================================================================
# Strike — p.19–20
# ===========================================================================


@padrao(
    id="strike_alta",
    nome="Strike de Alta",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.ALTA,
    n_candles=4,
    confiabilidade=PRIOR_BAIXA,
    pagina=19,
    tendencia=Tendencia.ALTA,
)
def strike_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três verdes ascendentes e um quarto candle que devolve tudo de uma vez.

    Parece reversão e o ebook diz que é continuação: a leitura é de **realização de
    lucro** — quem comprou embaixo vendeu, o preço despencou pela oferta e voltou a
    ficar atrativo. Prior baixo porque distinguir realização de virada real, no
    intraday, é exatamente o problema difícil.
    """
    c1, c2, c3, c4 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_alta),
        satisfaz(c3.e_alta),
        satisfaz(c2.abertura > c1.abertura and c3.abertura > c2.abertura),
        satisfaz(c2.fechamento > c1.fechamento and c3.fechamento > c2.fechamento),
        satisfaz(c4.e_baixa),
        satisfaz(c4.abertura > c3.fechamento),
        satisfaz(c4.fechamento < c1.abertura),
    )


@padrao(
    id="strike_baixa",
    nome="Strike de Baixa",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.BAIXA,
    n_candles=4,
    confiabilidade=PRIOR_BAIXA,
    pagina=20,
    tendencia=Tendencia.BAIXA,
)
def strike_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três vermelhos descendentes e um verde que engolfa os três corpos.

    Mesma lógica invertida: o preço caiu muito, ficou atrativo, quem estava vendido
    realizou — e o ebook espera que os operadores usem a subida para vender de novo.
    """
    c1, c2, c3, c4 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        satisfaz(c2.e_baixa),
        satisfaz(c3.e_baixa),
        # Cada vermelho abre dentro do corpo do anterior e fecha mais embaixo.
        satisfaz(c1.base_corpo <= c2.abertura <= c1.topo_corpo),
        satisfaz(c2.fechamento < c1.fechamento),
        satisfaz(c2.base_corpo <= c3.abertura <= c2.topo_corpo),
        satisfaz(c3.fechamento < c2.fechamento),
        satisfaz(c4.e_alta),
        satisfaz(
            c4.base_corpo <= min(c1.base_corpo, c2.base_corpo, c3.base_corpo)
            and c4.topo_corpo >= max(c1.topo_corpo, c2.topo_corpo, c3.topo_corpo)
        ),
    )


# ===========================================================================
# Gap Tasuki — p.20
# ===========================================================================


@padrao(
    id="gap_tasuki_alta",
    nome="Gap Tasuki de Alta",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=20,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
)
def gap_tasuki_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois verdes de força com gap entre si, e um vermelho que tenta fechar o gap e falha.

    O padrão inteiro é sobre a **falha**: o ebook chama de *"derrota da força vendedora
    ao tentar fechar o gap"*. Se o vermelho fechasse o gap, não haveria sinal nenhum —
    por isso a condição de não-fechamento é obrigatória, não decorativa.
    """
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.ALTA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.ALTA),
        gap_extremo_alta(c1, c2, ctx.atr, lim),
        satisfaz(c3.e_baixa),
        satisfaz(c3.fechamento < c2.abertura),
        satisfaz(c3.fechamento > c1.fechamento),
    )


@padrao(
    id="gap_tasuki_baixa",
    nome="Gap Tasuki de Baixa",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=20,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
    observacao=(
        "ERRATA item 4 — o ebook repete literalmente a redação da versão de alta para o "
        "terceiro candle. Implementado como espelho: o verde de correção fecha ACIMA da "
        "abertura do segundo e permanece ABAIXO do fechamento do primeiro."
    ),
)
def gap_tasuki_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois vermelhos de força com gap, e um verde que tenta fechar o gap e falha."""
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.BAIXA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.BAIXA),
        gap_extremo_baixa(c1, c2, ctx.atr, lim),
        satisfaz(c3.e_alta),
        satisfaz(c3.fechamento > c2.abertura),
        satisfaz(c3.fechamento < c1.fechamento),
    )


# ===========================================================================
# Linhas brancas lado a lado — p.21
# ===========================================================================


@padrao(
    id="linhas_brancas_alta",
    nome="Linhas Brancas Lado a Lado (Alta)",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=21,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
    observacao="O ebook classifica como 'incidência rara'.",
)
def linhas_brancas_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Verde, gap de alta, e dois verdes gêmeos lado a lado."""
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_alta),
        gap_extremo_alta(c1, c2, ctx.atr, lim),
        satisfaz_max(c2.sombra_sup_pct + c2.sombra_inf_pct, 0.40, 0.30),
        satisfaz(c3.e_alta),
        # "Níveis de abertura e fechamento muito próximos" entre o 2º e o 3º.
        coincidem(c2.abertura, c3.abertura, ctx.atr, lim),
        coincidem(c2.fechamento, c3.fechamento, ctx.atr, lim),
    )


@padrao(
    id="linhas_brancas_baixa",
    nome="Linhas Brancas Lado a Lado (Baixa)",
    familia=Familia.CONTINUACAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=21,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
    observacao=(
        "ERRATA item 8 — o ebook mede o gap pelo FECHAMENTO do segundo candle aqui, e "
        "pela abertura/mínima na versão de alta. Implementado pela abertura nas duas, "
        "por consistência com o resto do catálogo."
    ),
)
def linhas_brancas_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho, gap de baixa, e dois verdes gêmeos — e ainda assim é continuação de queda.

    O ebook antecipa o estranhamento: *"isso mesmo, parece estranho, mas os dois candles
    são verdes"*. A leitura é que a subida dos dois verdes acontece inteiramente **dentro
    do gap de baixa** — é repique dentro da queda, não retomada.
    """
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        satisfaz(c2.e_alta),
        gap_extremo_baixa(c1, c2, ctx.atr, lim),
        satisfaz(c3.e_alta),
        coincidem(c2.abertura, c3.abertura, ctx.atr, lim),
        coincidem(c2.fechamento, c3.fechamento, ctx.atr, lim),
    )
