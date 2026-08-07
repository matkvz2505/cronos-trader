"""Padrões de reversão — ebook p.7–19.

O grosso do catálogo. A ordem segue o ebook, e cada detector cita a página.

Onde o código diverge da fonte, o docstring aponta o item de `docs/ERRATA-EBOOK.md` —
o ebook tem erros de copy-paste reais (cor de candle trocada, tendência invertida,
parágrafo não espelhado), e implementar o texto ao pé da letra produziria detectores
que nunca disparam ou que disparam no contexto errado.
"""

from __future__ import annotations

from ..limiares import Limiares
from ..normalizacao import (
    coincidem,
    combinar,
    dentro_do_corpo,
    e_candle_forca,
    e_corpo_longo,
    e_corpo_pequeno,
    e_doji,
    e_martelo_geometrico,
    e_martelo_invertido_geometrico,
    e_marubozu,
    engolfa_corpo,
    gap_abertura_alta,
    gap_abertura_baixa,
    gap_corpo_alta,
    gap_corpo_baixa,
    gap_extremo_alta,
    gap_extremo_baixa,
    satisfaz,
    satisfaz_max,
    satisfaz_min,
)
from ..tipos import Candle, Contexto, Direcao, Familia, Tendencia
from .base import PRIOR_ALTA, PRIOR_BAIXA, PRIOR_NEUTRO, padrao

# ===========================================================================
# Harami — p.7
# ===========================================================================


@padrao(
    id="harami_alta",
    nome="Harami de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=7,
    tendencia=Tendencia.BAIXA,
    observacao=(
        "O ebook é explícito sobre a fragilidade deste: 'na prática você perceberá que "
        "isso muitas vezes não acontece... não confie cegamente nele'. Prior baixo por "
        "recomendação da própria fonte."
    ),
)
def harami_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Corpo vermelho longo seguido de corpo verde inteiramente dentro dele.

    A "mulher grávida": mãe vermelha, bebê verde. A venda perdeu amplitude de um candle
    para o outro — não é reversão confirmada, é perda de força.
    """
    mae, bebe = janela
    return combinar(
        satisfaz(mae.e_baixa),
        satisfaz(bebe.e_alta),
        e_corpo_longo(mae, ctx.atr, lim),
        dentro_do_corpo(mae, bebe, ctx.atr, lim),
    )


@padrao(
    id="harami_baixa",
    nome="Harami de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=7,
    tendencia=Tendencia.ALTA,
)
def harami_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Corpo verde longo seguido de corpo vermelho inteiramente dentro dele."""
    mae, bebe = janela
    return combinar(
        satisfaz(mae.e_alta),
        satisfaz(bebe.e_baixa),
        e_corpo_longo(mae, ctx.atr, lim),
        dentro_do_corpo(mae, bebe, ctx.atr, lim),
    )


# ===========================================================================
# Martelo / Enforcado / Martelo Invertido / Estrela Cadente — p.8–9
# ===========================================================================
# Duas geometrias, quatro nomes. O que separa cada par é exclusivamente a tendência
# anterior — o ebook diz isso com todas as letras: "o candle é morfologicamente igual
# ao enforcado, o que muda é a posição no gráfico".
# Ver ERRATA item 5: o ebook chama de "enforcado" a versão de topo com sombra SUPERIOR,
# que é a estrela cadente.


@padrao(
    id="martelo",
    nome="Martelo",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=1,
    confiabilidade=PRIOR_BAIXA,
    pagina=8,
    tendencia=Tendencia.BAIXA,
)
def martelo(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Sombra inferior longa no fim de uma queda: o fundo foi testado e rejeitado.

    A cor do corpo é irrelevante — o ebook insiste nisso. O que importa é a sombra.
    """
    return e_martelo_geometrico(janela[0], lim)


@padrao(
    id="enforcado",
    nome="Enforcado",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=1,
    confiabilidade=PRIOR_BAIXA,
    pagina=8,
    tendencia=Tendencia.ALTA,
)
def enforcado(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Mesma geometria do martelo, mas no topo de uma alta.

    A leitura muda completamente: houve venda forte durante o período e ela foi
    absorvida — mas o fato de ter aparecido vendedor agressivo num topo é o alerta.
    """
    return e_martelo_geometrico(janela[0], lim)


@padrao(
    id="martelo_invertido",
    nome="Martelo Invertido",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=1,
    confiabilidade=PRIOR_BAIXA,
    pagina=9,
    tendencia=Tendencia.BAIXA,
)
def martelo_invertido(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Sombra superior longa no fim de uma queda: apareceu comprador testando acima."""
    return e_martelo_invertido_geometrico(janela[0], lim)


@padrao(
    id="estrela_cadente",
    nome="Estrela Cadente",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=1,
    confiabilidade=PRIOR_BAIXA,
    pagina=9,
    tendencia=Tendencia.ALTA,
    observacao="ERRATA item 5 — o ebook rotula esta formação como 'enforcado'.",
)
def estrela_cadente(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Sombra superior longa no topo: o preço subiu e foi devolvido inteiro."""
    return e_martelo_invertido_geometrico(janela[0], lim)


# ===========================================================================
# Cinto de Segurança — p.9
# ===========================================================================


@padrao(
    id="cinto_seguranca_alta",
    nome="Cinto de Segurança de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=1,
    confiabilidade=PRIOR_BAIXA,
    pagina=9,
    tendencia=Tendencia.BAIXA,
)
def cinto_seguranca_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Candle de alta grande cuja abertura coincide com a mínima.

    Não houve um único momento de venda: abriu no fundo e só subiu. O ebook resume como
    *"basicamente um Marubozu verde no fim de uma tendência de baixa"* — a diferença é
    que aqui só a sombra inferior precisa ser nula; a superior pode existir.
    """
    c = janela[0]
    return combinar(
        satisfaz(c.e_alta),
        e_corpo_longo(c, ctx.atr, lim),
        satisfaz_max(c.sombra_inf_pct, lim.marubozu_sombra_pct_max, lim.marubozu_sombra_pct_max),
        satisfaz_max(c.sombra_sup_pct, lim.sombra_curta_pct_max, lim.sombra_curta_pct_max),
    )


@padrao(
    id="cinto_seguranca_baixa",
    nome="Cinto de Segurança de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=1,
    confiabilidade=PRIOR_BAIXA,
    pagina=9,
    tendencia=Tendencia.ALTA,
)
def cinto_seguranca_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Abertura coincide com a máxima: vendeu do primeiro ao último negócio."""
    c = janela[0]
    return combinar(
        satisfaz(c.e_baixa),
        e_corpo_longo(c, ctx.atr, lim),
        satisfaz_max(c.sombra_sup_pct, lim.marubozu_sombra_pct_max, lim.marubozu_sombra_pct_max),
        satisfaz_max(c.sombra_inf_pct, lim.sombra_curta_pct_max, lim.sombra_curta_pct_max),
    )


# ===========================================================================
# Engolfo — p.9–10
# ===========================================================================


@padrao(
    id="engolfo_alta",
    nome="Engolfo de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_NEUTRO,
    pagina=9,
    tendencia=Tendencia.BAIXA,
)
def engolfo_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Corpo verde cobrindo inteiramente o corpo vermelho anterior.

    Toda a venda do período anterior foi recomprada e ainda sobrou. O ebook observa que
    *"o tamanho das sombras não é importante"* — o que conta é a cobertura dos corpos.
    """
    anterior, atual = janela
    return combinar(
        satisfaz(anterior.e_baixa),
        satisfaz(atual.e_alta),
        engolfa_corpo(atual, anterior, ctx.atr, lim),
    )


@padrao(
    id="engolfo_baixa",
    nome="Engolfo de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_NEUTRO,
    pagina=9,
    tendencia=Tendencia.ALTA,
)
def engolfo_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    anterior, atual = janela
    return combinar(
        satisfaz(anterior.e_alta),
        satisfaz(atual.e_baixa),
        engolfa_corpo(atual, anterior, ctx.atr, lim),
    )


# ===========================================================================
# Estrela da Manhã / da Noite — p.10
# ===========================================================================


@padrao(
    id="estrela_manha",
    nome="Estrela da Manhã",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=10,
    tendencia=Tendencia.BAIXA,
)
def estrela_manha(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho, corpo isolado embaixo (qualquer cor), verde retomando mais da metade.

    A estrela do meio é o momento em que a venda parou de conseguir empurrar. O terceiro
    candle é a confirmação — sem ele fechar acima da metade do primeiro corpo, não há
    padrão.
    """
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        # O corpo da estrela precisa estar abaixo dos corpos dos dois vizinhos.
        satisfaz(c2.topo_corpo < c1.base_corpo),
        satisfaz(c2.topo_corpo < c3.base_corpo),
        e_corpo_pequeno(c2, lim),
        satisfaz(c3.e_alta),
        satisfaz_min((c3.fechamento - c1.meio_corpo) / ctx.atr, 0.0, 0.5)
        if ctx.atr > 0
        else None,
    )


@padrao(
    id="estrela_noite",
    nome="Estrela da Noite",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=10,
    tendencia=Tendencia.ALTA,
)
def estrela_noite(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.base_corpo > c1.topo_corpo),
        satisfaz(c2.base_corpo > c3.topo_corpo),
        e_corpo_pequeno(c2, lim),
        satisfaz(c3.e_baixa),
        satisfaz_min((c1.meio_corpo - c3.fechamento) / ctx.atr, 0.0, 0.5)
        if ctx.atr > 0
        else None,
    )


# ===========================================================================
# Pombo-correio / Falcão Descendente — p.11
# ===========================================================================
# Harami com os dois candles da mesma cor. O ebook comenta que muitos autores chamam
# tudo de Harami, "no mínimo sensato, afinal a interpretação é a mesma" — mantemos
# separado para o backtest poder medir se a cor do bebê muda alguma coisa na prática.


@padrao(
    id="pombo_correio",
    nome="Pombo-correio",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=11,
    tendencia=Tendencia.BAIXA,
)
def pombo_correio(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Harami de dois vermelhos: a queda continuou, mas com muito menos amplitude."""
    mae, bebe = janela
    return combinar(
        satisfaz(mae.e_baixa),
        satisfaz(bebe.e_baixa),
        e_corpo_longo(mae, ctx.atr, lim),
        dentro_do_corpo(mae, bebe, ctx.atr, lim),
    )


@padrao(
    id="falcao_descendente",
    nome="Falcão Descendente",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=11,
    tendencia=Tendencia.ALTA,
    derivado=True,
    observacao="ERRATA item 9 — o ebook descreve só a versão em tendência de baixa.",
)
def falcao_descendente(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Harami de dois verdes no topo: a alta seguiu, mas encolhendo."""
    mae, bebe = janela
    return combinar(
        satisfaz(mae.e_alta),
        satisfaz(bebe.e_alta),
        e_corpo_longo(mae, ctx.atr, lim),
        dentro_do_corpo(mae, bebe, ctx.atr, lim),
    )


# ===========================================================================
# Alinhamento na baixa / na alta — p.11–12
# ===========================================================================


@padrao(
    id="alinhamento_baixa",
    nome="Alinhamento na Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=11,
    tendencia=Tendencia.BAIXA,
    observacao="O ebook pede confirmação num terceiro candle: 'muitas vezes a tendência continua'.",
)
def alinhamento_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois vermelhos longos fechando exatamente no mesmo preço.

    Duas tentativas de furar o mesmo nível, duas falhas — um piso que o vendedor não
    conseguiu romper. A ausência de sombra inferior nos dois reforça, mas o próprio
    ebook diz que é raro e nem todos os autores exigem: entra como bônus, não requisito.
    """
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        satisfaz(c2.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        e_corpo_longo(c2, ctx.atr, lim),
        coincidem(c1.fechamento, c2.fechamento, ctx.atr, lim),
    )


@padrao(
    id="alinhamento_alta",
    nome="Alinhamento na Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=12,
    tendencia=Tendencia.ALTA,
    observacao=(
        "ERRATA item 11 — o ebook pede coincidência de ABERTURA aqui, mas de FECHAMENTO "
        "no alinhamento de baixa. Implementado por fechamento nos dois, que é o espelho "
        "coerente: com dois candles verdes sem sombra superior, o fechamento é o teto "
        "testado."
    ),
)
def alinhamento_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois verdes longos fechando no mesmo preço: um teto testado duas vezes."""
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        e_corpo_longo(c2, ctx.atr, lim),
        coincidem(c1.fechamento, c2.fechamento, ctx.atr, lim),
    )


# ===========================================================================
# Linhas de Reunião — p.12
# ===========================================================================


@padrao(
    id="linha_reuniao_alta",
    nome="Linha de Reunião de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=12,
    tendencia=Tendencia.BAIXA,
)
def linha_reuniao_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho longo e verde longo terminando no mesmo preço.

    Diferente do engolfo: aqui o verde não cobre o vermelho, só o encontra. Por isso o
    ebook manda aguardar o terceiro candle antes de confirmar.
    """
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        satisfaz(c2.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        e_corpo_longo(c2, ctx.atr, lim),
        coincidem(c1.fechamento, c2.fechamento, ctx.atr, lim),
    )


@padrao(
    id="linha_reuniao_baixa",
    nome="Linha de Reunião de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=12,
    tendencia=Tendencia.ALTA,
)
def linha_reuniao_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        e_corpo_longo(c2, ctx.atr, lim),
        coincidem(c1.fechamento, c2.fechamento, ctx.atr, lim),
    )


# ===========================================================================
# Sanduíche de Graveto — p.12
# ===========================================================================


@padrao(
    id="sanduiche_graveto_alta",
    nome="Sanduíche de Graveto de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=12,
    tendencia=Tendencia.BAIXA,
)
def sanduiche_graveto_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois vermelhos de força fechando no mesmo nível, com um verde no meio.

    O ebook lê o nível repetido como *"um suporte importante"* — e é essa a informação
    aproveitável: o mercado voltou duas vezes ao mesmo preço e parou.
    """
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.BAIXA),
        satisfaz(c2.e_alta),
        satisfaz(c2.fechamento > c1.fechamento),
        satisfaz(c2.minima >= c1.fechamento),
        e_candle_forca(c3, ctx.atr, lim, Direcao.BAIXA),
        engolfa_corpo(c3, c2, ctx.atr, lim),
        coincidem(c3.fechamento, c1.fechamento, ctx.atr, lim),
    )


@padrao(
    id="sanduiche_graveto_baixa",
    nome="Sanduíche de Graveto de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=12,
    tendencia=Tendencia.ALTA,
    derivado=True,
    observacao="ERRATA item 9 — espelho inferido; o ebook só descreve a versão de alta.",
)
def sanduiche_graveto_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.ALTA),
        satisfaz(c2.e_baixa),
        satisfaz(c2.fechamento < c1.fechamento),
        satisfaz(c2.maxima <= c1.fechamento),
        e_candle_forca(c3, ctx.atr, lim, Direcao.ALTA),
        engolfa_corpo(c3, c2, ctx.atr, lim),
        coincidem(c3.fechamento, c1.fechamento, ctx.atr, lim),
    )


# ===========================================================================
# 3 Estrelas do Sul / Bloqueio Avançado — p.13
# ===========================================================================


@padrao(
    id="tres_estrelas_sul",
    nome="3 Estrelas do Sul",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=13,
    tendencia=Tendencia.BAIXA,
)
def tres_estrelas_sul(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três vermelhos com corpos encolhendo dentro do range anterior.

    A queda continua, mas cada vez com menos convicção. O ebook: *"os corpos estão
    ficando menores, indicando perda de momentum da força vendedora"*. É um padrão de
    exaustão, não de virada — a reversão ainda precisa de confirmação.
    """
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        satisfaz(c2.e_baixa),
        satisfaz(c3.e_baixa),
        satisfaz_min(c1.sombra_inf_pct, 0.25, 0.35),
        satisfaz(c2.abertura < c1.abertura),
        satisfaz(c2.minima > c1.minima),
        e_marubozu(c3, lim, Direcao.BAIXA),
        satisfaz(c3.maxima <= c2.maxima and c3.minima >= c2.minima),
        # Corpos estritamente decrescentes — é o núcleo do padrão.
        satisfaz(c2.corpo < c1.corpo and c3.corpo < c2.corpo),
    )


@padrao(
    id="bloqueio_avancado",
    nome="Bloqueio Avançado",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=13,
    tendencia=Tendencia.ALTA,
)
def bloqueio_avancado(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três verdes subindo, mas com corpos menores e sombras superiores maiores.

    O preço ainda faz máximas mais altas — na tela parece força. O que denuncia a
    fraqueza é a proporção: cada candle sobe menos e é rejeitado mais no topo.
    """
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_alta),
        satisfaz(c3.e_alta),
        satisfaz(c2.maxima > c1.maxima and c3.maxima > c2.maxima),
        satisfaz(c2.minima > c1.minima and c3.minima > c2.minima),
        satisfaz(c2.corpo < c1.corpo and c3.corpo < c2.corpo),
        satisfaz(
            c2.sombra_superior > c1.sombra_superior
            and c3.sombra_superior > c2.sombra_superior
        ),
    )


# ===========================================================================
# Estrela Tripla — p.13
# ===========================================================================


@padrao(
    id="estrela_tripla_fundo",
    nome="Estrela Tripla de Fundo",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=13,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
    observacao="O ebook classifica como 'pouco comum'. Em intraday, mais raro ainda.",
)
def estrela_tripla_fundo(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três dojis, o do meio isolado abaixo dos outros dois por gap."""
    c1, c2, c3 = janela
    return combinar(
        e_doji(c1, lim),
        e_doji(c2, lim),
        e_doji(c3, lim),
        gap_extremo_baixa(c1, c2, ctx.atr, lim),
        gap_extremo_alta(c2, c3, ctx.atr, lim),
    )


@padrao(
    id="estrela_tripla_topo",
    nome="Estrela Tripla de Topo",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=13,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
)
def estrela_tripla_topo(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3 = janela
    return combinar(
        e_doji(c1, lim),
        e_doji(c2, lim),
        e_doji(c3, lim),
        gap_extremo_alta(c1, c2, ctx.atr, lim),
        gap_extremo_baixa(c2, c3, ctx.atr, lim),
    )


# ===========================================================================
# 3 Rios — p.14
# ===========================================================================


@padrao(
    id="tres_rios_alta",
    nome="3 Rios de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=14,
    tendencia=Tendencia.BAIXA,
    observacao="O ebook classifica como 'padrão raro'.",
)
def tres_rios_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho longo, martelo, e um verde pequeno que não fura as mínimas."""
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        e_martelo_geometrico(c2, lim),
        satisfaz(c3.e_alta),
        satisfaz(c3.topo_corpo < c2.base_corpo),
        satisfaz(c3.minima >= min(c1.minima, c2.minima)),
    )


@padrao(
    id="tres_rios_baixa",
    nome="3 Rios de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=14,
    tendencia=Tendencia.ALTA,
    derivado=True,
    observacao="ERRATA item 9 — espelho inferido.",
)
def tres_rios_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        e_martelo_invertido_geometrico(c2, lim),
        satisfaz(c3.e_baixa),
        satisfaz(c3.base_corpo > c2.topo_corpo),
        satisfaz(c3.maxima <= max(c1.maxima, c2.maxima)),
    )


# ===========================================================================
# 2 Corvos — p.14
# ===========================================================================


@padrao(
    id="dois_corvos",
    nome="2 Corvos",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=14,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
)
def dois_corvos(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Verde, vermelho abrindo em gap de alta, e um segundo vermelho comendo o gap.

    O gap de alta é a euforia; os dois vermelhos são a devolução. Fechar abaixo do
    fechamento do primeiro candle apaga toda a alta do dia anterior.
    """
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_baixa),
        e_corpo_pequeno(c2, lim),
        gap_corpo_alta(c1, c2, ctx.atr, lim),
        satisfaz(c3.e_baixa),
        satisfaz(c3.maxima <= c2.abertura),
        satisfaz(c3.fechamento < c1.fechamento),
    )


# ===========================================================================
# Interrupção de alta / baixa — p.14
# ===========================================================================
# Cinco candles. O ebook chama de "raríssimos". Mantidos no catálogo porque o custo de
# um detector a mais é nulo e porque o backtest precisa de contagem para provar que são
# raros — em vez de assumirmos.


@padrao(
    id="interrupcao_alta",
    nome="Interrupção de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=5,
    confiabilidade=PRIOR_NEUTRO,
    pagina=14,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
)
def interrupcao_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Quatro candles afundando em gap e um quinto verde longo que não fecha o gap."""
    c1, c2, c3, c4, c5 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.e_baixa),
        gap_corpo_baixa(c1, c2, ctx.atr, lim),
        satisfaz(c3.abertura < c2.abertura),
        satisfaz(c4.e_baixa),
        satisfaz(c4.abertura < c3.abertura),
        satisfaz(c5.e_alta),
        e_corpo_longo(c5, ctx.atr, lim),
        satisfaz(c5.abertura > c4.abertura),
        satisfaz(c5.fechamento > c2.abertura),
        # "não pode fechar o gap": o quinto não pode voltar ao corpo do primeiro.
        satisfaz(c5.fechamento < c1.base_corpo),
    )


@padrao(
    id="interrupcao_baixa",
    nome="Interrupção de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=5,
    confiabilidade=PRIOR_NEUTRO,
    pagina=14,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
)
def interrupcao_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3, c4, c5 = janela
    return combinar(
        satisfaz(c1.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.e_alta),
        gap_corpo_alta(c1, c2, ctx.atr, lim),
        satisfaz(c3.abertura > c2.abertura),
        satisfaz(c4.e_alta),
        satisfaz(c4.abertura > c3.abertura),
        satisfaz(c5.e_baixa),
        e_corpo_longo(c5, ctx.atr, lim),
        satisfaz(c5.abertura > c4.abertura),
        satisfaz(c5.fechamento < c2.abertura),
        satisfaz(c5.fechamento > c1.topo_corpo),
    )


# ===========================================================================
# Escada de alta / baixa — p.15
# ===========================================================================


@padrao(
    id="escada_alta",
    nome="Escada de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=5,
    confiabilidade=PRIOR_NEUTRO,
    pagina=15,
    tendencia=Tendencia.BAIXA,
)
def escada_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três vermelhos de força descendo em degraus, um martelo invertido, e a virada.

    O ebook dá o atalho prático de leitura: *"preste atenção no fato de ser um martelo
    invertido/enforcado seguido de um importante candle de força"*. É essa a assinatura;
    o resto é enquadramento.
    """
    c1, c2, c3, c4, c5 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.BAIXA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.BAIXA),
        e_candle_forca(c3, ctx.atr, lim, Direcao.BAIXA),
        satisfaz(c2.abertura < c1.abertura and c3.abertura < c2.abertura),
        satisfaz(c2.fechamento < c1.fechamento and c3.fechamento < c2.fechamento),
        e_martelo_invertido_geometrico(c4, lim),
        e_candle_forca(c5, ctx.atr, lim, Direcao.ALTA),
        satisfaz(c5.fechamento > c3.abertura),
    )


@padrao(
    id="escada_baixa",
    nome="Escada de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=5,
    confiabilidade=PRIOR_NEUTRO,
    pagina=15,
    tendencia=Tendencia.ALTA,
    observacao=(
        "ERRATA item 3 — o ebook diz 'tendência de baixa' e 'aberturas e fechamentos "
        "cada vez menores' para os três candles VERDES, o que é incoerente. Implementado "
        "como espelho correto: tendência de alta, três verdes ascendentes."
    ),
)
def escada_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três verdes de força subindo em degraus, um martelo invertido, e a virada."""
    c1, c2, c3, c4, c5 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.ALTA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.ALTA),
        e_candle_forca(c3, ctx.atr, lim, Direcao.ALTA),
        satisfaz(c2.abertura > c1.abertura and c3.abertura > c2.abertura),
        satisfaz(c2.fechamento > c1.fechamento and c3.fechamento > c2.fechamento),
        e_martelo_invertido_geometrico(c4, lim),
        e_candle_forca(c5, ctx.atr, lim, Direcao.BAIXA),
        satisfaz(c5.fechamento < c3.abertura),
    )


# ===========================================================================
# Linha de Perfuração / Nuvem Negra — p.16
# ===========================================================================
# Os dois padrões que o ebook chama de "simples e de alta confiabilidade". São também os
# mais úteis em intraday: a geometria é robusta e não depende de gap grande.


@padrao(
    id="linha_perfuracao",
    nome="Linha de Perfuração",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_ALTA,
    pagina=16,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
)
def linha_perfuracao(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho longo, e um verde que abre abaixo dele e recupera mais da metade.

    O verde abre no pior lugar possível — abaixo da mínima anterior — e ainda assim
    devolve mais de metade da queda. É a definição de comprador agressivo.
    """
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.e_alta),
        e_corpo_longo(c2, ctx.atr, lim),
        # Gap medido na ABERTURA: o candle abre abaixo da mínima anterior e depois sobe
        # através dela. Exigir gap de range inteiro aqui tornaria o padrão impossível.
        gap_abertura_baixa(c1, c2, ctx.atr, lim),
        # "Perfura" o candle anterior: fecha acima da metade do corpo, sem chegar a
        # engolfar — se engolfasse, o padrão seria outro.
        satisfaz(c2.fechamento > c1.meio_corpo),
        satisfaz(c2.fechamento < c1.abertura),
    )


@padrao(
    id="nuvem_negra",
    nome="Nuvem Negra",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_ALTA,
    pagina=16,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
)
def nuvem_negra(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Verde longo, e um vermelho que abre acima dele e devolve mais da metade."""
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.e_baixa),
        e_corpo_longo(c2, ctx.atr, lim),
        gap_abertura_alta(c1, c2, ctx.atr, lim),
        satisfaz(c2.fechamento < c1.meio_corpo),
        satisfaz(c2.fechamento > c1.abertura),
    )


# ===========================================================================
# Chute de Alta / de Baixa — p.16–17
# ===========================================================================
# Único par do catálogo sem tendência requerida. O ebook: "a tendência anterior à sua
# formação não é importante... pode ser um padrão de reversão ou de continuação".


@padrao(
    id="chute_alta",
    nome="Chute de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=16,
    exige_gap=True,
)
def chute_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Marubozu vermelho e marubozu verde separados por um gap de alta.

    Dois candles sem sombra nenhuma e um salto entre eles: mudança abrupta de mão. O
    ebook classifica como baixa confiabilidade — e em intraday depende inteiramente da
    tolerância de gap, o que o torna um bom canário para calibração.
    """
    c1, c2 = janela
    return combinar(
        e_marubozu(c1, lim, Direcao.BAIXA),
        e_marubozu(c2, lim, Direcao.ALTA),
        e_corpo_longo(c1, ctx.atr, lim),
        e_corpo_longo(c2, ctx.atr, lim),
        gap_corpo_alta(c1, c2, ctx.atr, lim),
    )


@padrao(
    id="chute_baixa",
    nome="Chute de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=2,
    confiabilidade=PRIOR_BAIXA,
    pagina=17,
    exige_gap=True,
)
def chute_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2 = janela
    return combinar(
        e_marubozu(c1, lim, Direcao.ALTA),
        e_marubozu(c2, lim, Direcao.BAIXA),
        e_corpo_longo(c1, ctx.atr, lim),
        e_corpo_longo(c2, ctx.atr, lim),
        gap_corpo_baixa(c1, c2, ctx.atr, lim),
    )


# ===========================================================================
# Bebê Abandonado — p.17
# ===========================================================================


@padrao(
    id="bebe_abandonado_alta",
    nome="Bebê Abandonado de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_ALTA,
    pagina=17,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
)
def bebe_abandonado_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Vermelho de força, doji isolado por gap abaixo de tudo, verde de força.

    O doji não encosta em nenhum dos vizinhos — daí "abandonado". O ebook classifica
    como raro e de alta confiabilidade, e é o padrão onde a tolerância de gap mais
    importa: com folga demais, deixa de ser abandonado.
    """
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.BAIXA),
        e_corpo_pequeno(c2, lim),
        gap_extremo_baixa(c1, c2, ctx.atr, lim),
        gap_extremo_alta(c2, c3, ctx.atr, lim),
        e_candle_forca(c3, ctx.atr, lim, Direcao.ALTA),
    )


@padrao(
    id="bebe_abandonado_baixa",
    nome="Bebê Abandonado de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_ALTA,
    pagina=17,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
    observacao=(
        "ERRATA item 1 — o ebook diz que o primeiro candle é vermelho, copiando o texto "
        "da versão de alta. Num topo, o primeiro candle é o último impulso comprador e "
        "tem que ser verde."
    ),
)
def bebe_abandonado_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Verde de força, doji isolado por gap acima de tudo, vermelho de força."""
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.ALTA),
        e_corpo_pequeno(c2, lim),
        gap_extremo_alta(c1, c2, ctx.atr, lim),
        gap_extremo_baixa(c2, c3, ctx.atr, lim),
        e_candle_forca(c3, ctx.atr, lim, Direcao.BAIXA),
    )


# ===========================================================================
# 3 Por Dentro / 3 Por Fora — p.16–18
# ===========================================================================
# Harami e Engolfo com um terceiro candle de confirmação. O ebook nota o óbvio e o
# importante: "obviamente tem maior confiabilidade do que o Harami, afinal existe um
# terceiro candle reforçando". Por isso entram com prior acima dos padrões-base.


@padrao(
    id="tres_por_dentro_alta",
    nome="3 Por Dentro de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=16,
    tendencia=Tendencia.BAIXA,
)
def tres_por_dentro_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Harami de alta confirmado por um verde que rompe a máxima dos dois."""
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.e_alta),
        dentro_do_corpo(c1, c2, ctx.atr, lim),
        satisfaz(c3.e_alta),
        satisfaz(c3.fechamento > max(c1.maxima, c2.maxima)),
    )


@padrao(
    id="tres_por_dentro_baixa",
    nome="3 Por Dentro de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=16,
    tendencia=Tendencia.ALTA,
)
def tres_por_dentro_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        e_corpo_longo(c1, ctx.atr, lim),
        satisfaz(c2.e_baixa),
        dentro_do_corpo(c1, c2, ctx.atr, lim),
        satisfaz(c3.e_baixa),
        satisfaz(c3.fechamento < min(c1.minima, c2.minima)),
    )


@padrao(
    id="tres_por_fora_alta",
    nome="3 Por Fora de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=18,
    tendencia=Tendencia.BAIXA,
)
def tres_por_fora_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Engolfo de alta confirmado por um terceiro candle de alta."""
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        satisfaz(c2.e_alta),
        engolfa_corpo(c2, c1, ctx.atr, lim),
        satisfaz(c3.e_alta),
        satisfaz(c3.fechamento > c2.fechamento),
    )


@padrao(
    id="tres_por_fora_baixa",
    nome="3 Por Fora de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=18,
    tendencia=Tendencia.ALTA,
    derivado=True,
    observacao="ERRATA item 9 — o ebook descreve só a versão de alta.",
)
def tres_por_fora_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    c1, c2, c3 = janela
    return combinar(
        satisfaz(c1.e_alta),
        satisfaz(c2.e_baixa),
        engolfa_corpo(c2, c1, ctx.atr, lim),
        satisfaz(c3.e_baixa),
        satisfaz(c3.fechamento < c2.fechamento),
    )


# ===========================================================================
# 3 Soldados / 3 Corvos — p.18
# ===========================================================================


@padrao(
    id="tres_soldados",
    nome="3 Soldados de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=18,
    observacao=(
        "Sem tendência requerida por decisão do ebook: 'o preço deve seguir na mesma "
        "direção dos 3 candles, independente da tendência anterior'. Em tendência de "
        "alta é continuação; em tendência de baixa, reversão. Quem resolve o significado "
        "é a confluência, não o detector."
    ),
)
def tres_soldados(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três candles de alta seguidos, corpo grande, quase sem sombra."""
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.ALTA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.ALTA),
        e_candle_forca(c3, ctx.atr, lim, Direcao.ALTA),
        satisfaz(c2.fechamento > c1.fechamento and c3.fechamento > c2.fechamento),
        satisfaz_max(
            max(c1.sombra_sup_pct, c2.sombra_sup_pct, c3.sombra_sup_pct),
            lim.sombra_curta_pct_max * 2,
            lim.sombra_curta_pct_max,
        ),
    )


@padrao(
    id="tres_corvos",
    nome="3 Corvos de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=3,
    confiabilidade=PRIOR_NEUTRO,
    pagina=18,
    observacao=(
        "ERRATA item 2 — o ebook descreve este padrão como 'formado por 3 candles de "
        "ALTA consecutivos', repetindo o texto dos 3 Soldados. Três corvos são, por "
        "definição, três candles de baixa."
    ),
)
def tres_corvos(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Três candles de baixa seguidos, corpo grande, quase sem sombra."""
    c1, c2, c3 = janela
    return combinar(
        e_candle_forca(c1, ctx.atr, lim, Direcao.BAIXA),
        e_candle_forca(c2, ctx.atr, lim, Direcao.BAIXA),
        e_candle_forca(c3, ctx.atr, lim, Direcao.BAIXA),
        satisfaz(c2.fechamento < c1.fechamento and c3.fechamento < c2.fechamento),
        satisfaz_max(
            max(c1.sombra_inf_pct, c2.sombra_inf_pct, c3.sombra_inf_pct),
            lim.sombra_curta_pct_max * 2,
            lim.sombra_curta_pct_max,
        ),
    )


# ===========================================================================
# Bebê Engolido — p.19
# ===========================================================================


@padrao(
    id="bebe_engolido_alta",
    nome="Bebê Engolido de Alta",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=4,
    confiabilidade=PRIOR_ALTA,
    pagina=19,
    tendencia=Tendencia.BAIXA,
    exige_gap=True,
    observacao=(
        "Contraintuitivo: o último candle é vermelho e o sinal é de alta. O ebook "
        "explica — o martelo invertido abriu em gap de baixa e subiu quase até a máxima "
        "anterior, e o quarto candle abre em forte gap de alta. A força compradora está "
        "nos gaps, não na cor."
    ),
)
def bebe_engolido_alta(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois marubozu vermelhos, um martelo invertido, e um vermelho que o engole."""
    c1, c2, c3, c4 = janela
    return combinar(
        e_marubozu(c1, lim, Direcao.BAIXA),
        e_marubozu(c2, lim, Direcao.BAIXA),
        e_martelo_invertido_geometrico(c3, lim),
        gap_corpo_baixa(c2, c3, ctx.atr, lim),
        e_marubozu(c4, lim, Direcao.BAIXA),
        # "engolfando completamente": o corpo do quarto cobre o range inteiro do terceiro.
        satisfaz(c4.topo_corpo >= c3.maxima and c4.base_corpo <= c3.minima),
    )


@padrao(
    id="bebe_engolido_baixa",
    nome="Bebê Engolido de Baixa",
    familia=Familia.REVERSAO,
    direcao=Direcao.BAIXA,
    n_candles=4,
    confiabilidade=PRIOR_ALTA,
    pagina=19,
    tendencia=Tendencia.ALTA,
    exige_gap=True,
)
def bebe_engolido_baixa(janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None:
    """Dois marubozu verdes, um enforcado, e um verde que o engole."""
    c1, c2, c3, c4 = janela
    return combinar(
        e_marubozu(c1, lim, Direcao.ALTA),
        e_marubozu(c2, lim, Direcao.ALTA),
        e_martelo_geometrico(c3, lim),
        gap_corpo_alta(c2, c3, ctx.atr, lim),
        e_marubozu(c4, lim, Direcao.ALTA),
        satisfaz(c4.topo_corpo >= c3.maxima and c4.base_corpo <= c3.minima),
    )
