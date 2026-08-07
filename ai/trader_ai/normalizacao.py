"""Predicados de geometria e a mecânica de força das detecções.

Duas responsabilidades:

**1. Vocabulário do ebook virado em código.** "corpo pequeno", "sombra longa", "candle de
força", "abre em gap de alta" — cada expressão vira uma função, uma vez só. Sem isto, cada
um dos ~40 detectores reimplementaria "corpo pequeno" com um número ligeiramente diferente.

**2. Força contínua em vez de booleano.** Um engolfo que cobre o candle anterior por 5% e
outro que cobre por 300% não são o mesmo sinal, e um detector que devolve `True` para os
dois joga fora a informação que mais importa.

Convenção: todo predicado devolve `float | None`.

- `None` — a condição **falhou**, o padrão não existe ali.
- `float` em `[MARGEM_MINIMA, 1.0]` — passou, e o valor diz com que folga.

`combinar()` junta as margens por média harmônica: a condição mais fraca domina o
resultado. É deliberado — um padrão só é tão bom quanto seu elo mais frouxo.
"""

from __future__ import annotations

from .limiares import PADRAO, Limiares
from .tipos import Candle, Direcao

MARGEM_MINIMA = 0.35
"""Piso de uma condição que passou raspando. Não é zero porque passar raspando ainda é
passar — quem decide se isso basta é o score final, não o detector."""

_EPS = 1e-9


# ---------------------------------------------------------------------------
# Mecânica de margem
# ---------------------------------------------------------------------------


def satisfaz_min(valor: float, limiar: float, escala: float) -> float | None:
    """Condição `valor >= limiar`.

    `escala` é quanto de excesso conta como folga total. Ex.: exigindo corpo >= 0.8 ATR
    com escala 0.8, um corpo de 1.6 ATR devolve 1.0.
    """
    if valor < limiar:
        return None
    if escala <= _EPS:
        return 1.0
    return MARGEM_MINIMA + (1.0 - MARGEM_MINIMA) * min(1.0, (valor - limiar) / escala)


def satisfaz_max(valor: float, limiar: float, escala: float) -> float | None:
    """Condição `valor <= limiar`. Quanto mais abaixo, maior a margem."""
    if valor > limiar:
        return None
    if escala <= _EPS:
        return 1.0
    return MARGEM_MINIMA + (1.0 - MARGEM_MINIMA) * min(1.0, (limiar - valor) / escala)


def satisfaz(condicao: bool, margem: float = 0.7) -> float | None:
    """Condição booleana sem noção de folga (cor do candle, ordem temporal…)."""
    return margem if condicao else None


def combinar(*margens: float | None) -> float | None:
    """Média harmônica das margens. `None` se qualquer condição falhou.

    Harmônica, não aritmética: com uma condição em 0.35 e outra em 1.0, a aritmética
    devolveria 0.67 — otimista demais para uma formação que mal se qualificou de um
    lado. A harmônica devolve 0.52.
    """
    if any(m is None for m in margens):
        return None
    valores = [max(float(m), _EPS) for m in margens]  # type: ignore[arg-type]
    if not valores:
        return None
    return len(valores) / sum(1.0 / v for v in valores)


# ---------------------------------------------------------------------------
# Geometria do candle isolado
# ---------------------------------------------------------------------------


def razao_sombra_corpo(sombra: float, corpo: float) -> float:
    """Sombra dividida pelo corpo, tratando corpo nulo como razão muito grande.

    Um doji com sombra longa tem corpo ~0; matematicamente a razão é infinita, e
    conceitualmente está certo — a sombra domina completamente.
    """
    if corpo <= _EPS:
        return 999.0 if sombra > _EPS else 0.0
    return sombra / corpo


def e_doji(c: Candle, lim: Limiares = PADRAO) -> float | None:
    """Corpo desprezível diante da amplitude (ebook p.5)."""
    if c.amplitude <= _EPS:
        return None
    return satisfaz_max(c.corpo_pct, lim.doji_corpo_pct_max, lim.doji_corpo_pct_max)


def e_corpo_pequeno(c: Candle, lim: Limiares = PADRAO) -> float | None:
    if c.amplitude <= _EPS:
        return None
    return satisfaz_max(c.corpo_pct, lim.corpo_pequeno_pct_max, lim.corpo_pequeno_pct_max)


def e_corpo_longo(c: Candle, atr: float, lim: Limiares = PADRAO) -> float | None:
    """'Corpo longo' — medido em ATR, não em fração da amplitude.

    A distinção importa: um candle de amplitude minúscula pode ter corpo_pct = 1.0 e
    ainda ser irrelevante. Corpo longo é sobre tamanho absoluto relativo à volatilidade.
    """
    if atr <= _EPS:
        return None
    return satisfaz_min(c.corpo / atr, lim.corpo_longo_atr_min, lim.corpo_longo_atr_min)


def e_marubozu(c: Candle, lim: Limiares = PADRAO, direcao: Direcao | None = None) -> float | None:
    """Corpo grande, praticamente sem sombras (ebook p.5)."""
    if c.amplitude <= _EPS:
        return None
    if direcao is not None and c.direcao is not direcao:
        return None
    return combinar(
        satisfaz_min(c.corpo_pct, lim.marubozu_corpo_pct_min, 1.0 - lim.marubozu_corpo_pct_min),
        satisfaz_max(c.sombra_sup_pct, lim.marubozu_sombra_pct_max, lim.marubozu_sombra_pct_max),
        satisfaz_max(c.sombra_inf_pct, lim.marubozu_sombra_pct_max, lim.marubozu_sombra_pct_max),
    )


def e_spinning_top(c: Candle, lim: Limiares = PADRAO) -> float | None:
    """Corpo pequeno com sombras grandes dos dois lados (ebook p.6)."""
    if c.amplitude <= _EPS:
        return None
    return combinar(
        e_corpo_pequeno(c, lim),
        satisfaz_min(razao_sombra_corpo(c.sombra_superior, c.corpo), lim.sombra_longa_ratio, 2.0),
        satisfaz_min(razao_sombra_corpo(c.sombra_inferior, c.corpo), lim.sombra_longa_ratio, 2.0),
    )


def e_candle_forca(
    c: Candle, atr: float, lim: Limiares = PADRAO, direcao: Direcao | None = None
) -> float | None:
    """'Candle de força': amplitude grande **e** corpo dominando essa amplitude.

    As duas condições juntas de propósito. Amplitude grande com corpo pequeno é
    indecisão volátil (briga entre touros e ursos) — o oposto de força direcional.
    """
    if atr <= _EPS or c.amplitude <= _EPS:
        return None
    if direcao is not None and c.direcao is not direcao:
        return None
    return combinar(
        satisfaz_min(c.amplitude / atr, lim.candle_forca_atr_min, lim.candle_forca_atr_min),
        satisfaz_min(
            c.corpo_pct, lim.candle_forca_corpo_pct_min, 1.0 - lim.candle_forca_corpo_pct_min
        ),
    )


def e_martelo_geometrico(c: Candle, lim: Limiares = PADRAO) -> float | None:
    """Corpo pequeno no topo, sombra inferior longa, pouca sombra superior.

    Geometria compartilhada por **martelo** (em tendência de baixa) e **enforcado** (em
    tendência de alta). O ebook (p.8) é explícito: "o candle é morfologicamente igual ao
    enforcado, o que muda é a posição no gráfico". Por isso a geometria é uma função só
    e o contexto separa os dois nomes.
    """
    if c.amplitude <= _EPS:
        return None
    return combinar(
        e_corpo_pequeno(c, lim),
        satisfaz_min(razao_sombra_corpo(c.sombra_inferior, c.corpo), lim.sombra_longa_ratio, 2.0),
        satisfaz_max(c.sombra_sup_pct, lim.sombra_curta_pct_max, lim.sombra_curta_pct_max),
    )


def e_martelo_invertido_geometrico(c: Candle, lim: Limiares = PADRAO) -> float | None:
    """Espelho do anterior: sombra superior longa, pouca sombra inferior.

    Compartilhada por **martelo invertido** (tendência de baixa) e **estrela cadente**
    (tendência de alta). Ver docs/ERRATA-EBOOK.md item 5 — o ebook chama a versão de
    topo de "enforcado", que é o nome errado.
    """
    if c.amplitude <= _EPS:
        return None
    return combinar(
        e_corpo_pequeno(c, lim),
        satisfaz_min(razao_sombra_corpo(c.sombra_superior, c.corpo), lim.sombra_longa_ratio, 2.0),
        satisfaz_max(c.sombra_inf_pct, lim.sombra_curta_pct_max, lim.sombra_curta_pct_max),
    )


# ---------------------------------------------------------------------------
# Relações entre candles
# ---------------------------------------------------------------------------


def _gap(distancia: float, atr: float, lim: Limiares) -> float | None:
    """Avalia uma distância de gap já orientada (positiva = gap existe).

    A folga de `tolerancia_gap_atr` desloca o corte: intraday o preço é contínuo e um
    gap estrito quase nunca ocorre. Ver docs/ERRATA-EBOOK.md item 10.
    """
    if atr <= _EPS:
        return None
    folga = lim.tolerancia_gap_atr * atr
    if distancia <= -folga:
        return None
    return satisfaz_min(distancia + folga, 0.0, max(folga, 0.15 * atr))


# Três sabores de gap, porque o ebook usa os três e confundi-los quebra o detector:
#
#   extremo   — o candle INTEIRO fica além do anterior (Bebê Abandonado, Estrela Tripla)
#   abertura  — só a ABERTURA fica além do extremo anterior (Linha de Perfuração, Nuvem Negra)
#   corpo     — a abertura fica além do CORPO anterior; sombras podem sobrepor (Chute, 2 Corvos)
#
# Do mais restritivo ao mais permissivo. Usar "extremo" onde o ebook pede "abertura"
# produz um detector que nunca dispara — a Linha de Perfuração, por definição, sobe
# através do candle anterior depois de abrir abaixo dele.


def gap_extremo_alta(
    anterior: Candle, atual: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    """O range inteiro de `atual` fica acima da máxima de `anterior`."""
    return _gap(atual.minima - anterior.maxima, atr, lim)


def gap_extremo_baixa(
    anterior: Candle, atual: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    return _gap(anterior.minima - atual.maxima, atr, lim)


def gap_abertura_alta(
    anterior: Candle, atual: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    """A abertura de `atual` fica acima da máxima de `anterior`.

    O candle pode (e costuma) voltar para dentro do range anterior depois — é
    exatamente o que a Nuvem Negra descreve: abre acima da máxima e afunda até abaixo
    da metade do corpo.
    """
    return _gap(atual.abertura - anterior.maxima, atr, lim)


def gap_abertura_baixa(
    anterior: Candle, atual: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    """A abertura de `atual` fica abaixo da mínima de `anterior` (Linha de Perfuração)."""
    return _gap(anterior.minima - atual.abertura, atr, lim)


def gap_corpo_alta(
    anterior: Candle, atual: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    """A abertura de `atual` fica acima do corpo de `anterior`; a sombra pode sobrepor.

    Variante mais permissiva, usada no Chute de Alta ("abertura acima do corpo do
    anterior", p.16) e nos 2 Corvos. O próprio ebook admite a sobreposição de sombra na
    Interrupção de alta (p.14).
    """
    return _gap(atual.abertura - anterior.topo_corpo, atr, lim)


def gap_corpo_baixa(
    anterior: Candle, atual: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    return _gap(anterior.base_corpo - atual.abertura, atr, lim)


def coincidem(a: float, b: float, atr: float, lim: Limiares = PADRAO) -> float | None:
    """Dois preços 'coincidem' se distam menos que `coincidencia_atr` ATR.

    O ebook exige fechamentos iguais no Alinhamento na baixa/alta e nas Linhas de
    Reunião. Igualdade exata em float — com tick de 5 pontos no WIN — seria um detector
    que nunca dispara. Aqui a coincidência é uma vizinhança, e a margem cai conforme a
    distância cresce.
    """
    if atr <= _EPS:
        return None
    tolerancia = lim.coincidencia_atr * atr
    distancia = abs(a - b)
    return satisfaz_max(distancia, tolerancia, tolerancia)


def engolfa_corpo(
    envolvente: Candle, envolvido: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    """Corpo de `envolvente` cobre inteiramente o corpo de `envolvido` (ebook p.9).

    A margem cresce com o quanto sobra além do corpo coberto — engolfo folgado vale
    mais que engolfo raspando.
    """
    if atr <= _EPS:
        return None
    if not envolvente.contem_corpo(envolvido):
        return None
    sobra = (envolvido.base_corpo - envolvente.base_corpo) + (
        envolvente.topo_corpo - envolvido.topo_corpo
    )
    return satisfaz_min(sobra / atr, 0.0, 0.5)


def dentro_do_corpo(
    externo: Candle, interno: Candle, atr: float, lim: Limiares = PADRAO
) -> float | None:
    """Inverso de `engolfa_corpo` — base do Harami. Margem maior quanto menor o bebê."""
    if atr <= _EPS:
        return None
    if not externo.contem_corpo(interno):
        return None
    if externo.corpo <= _EPS:
        return None
    proporcao = interno.corpo / externo.corpo
    return satisfaz_max(proporcao, 1.0, 0.7)
