"""Registro do catálogo de padrões e a mecânica comum aos detectores.

Um padrão é declarado com o decorator `@padrao(...)`, que registra a especificação em
`CATALOGO` e deixa a função de detecção intacta (dá para testar direto, sem o registro).

Assinatura de todo detector:

    (janela: list[Candle], ctx: Contexto, lim: Limiares) -> float | None

`janela` já vem com exatamente `n_candles`, mais antigo primeiro. `None` significa "não
é este padrão"; um float em 0..1 é a força da formação.

Um detector **não sabe o que é entrada, stop ou lucro**. Ele afirma apenas que uma
geometria ocorreu, com que qualidade. A tradução disso em operação é de `decisao.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..limiares import PADRAO, Limiares
from ..tipos import Candle, Contexto, Deteccao, Direcao, Familia, Serie, Tendencia

# ---------------------------------------------------------------------------
# Priors do ebook
# ---------------------------------------------------------------------------
# O ebook classifica explicitamente a confiabilidade de vários padrões, em vez de vender
# todos como infalíveis. Esses julgamentos viram peso INICIAL. O backtest (Sprint 4) os
# substitui por taxa medida em WIN/WDO assim que houver amostra.
# Ver docs/ERRATA-EBOOK.md, seção final.

PRIOR_ALTA = 0.70
"""Ebook diz "alta confiabilidade"."""

PRIOR_NEUTRO = 0.50
"""Ebook não qualifica."""

PRIOR_BAIXA = 0.35
"""Ebook diz "baixa confiabilidade"."""

PRIOR_INDECISAO = 0.25
"""Padrões isolados — o próprio ebook avisa que valem pouco sozinhos."""


Detector = Callable[[list[Candle], Contexto, Limiares], float | None]


@dataclass(frozen=True, slots=True)
class EspecPadrao:
    id: str
    nome: str
    familia: Familia
    direcao: Direcao
    n_candles: int
    confiabilidade_ebook: float
    pagina_ebook: int
    detector: Detector
    tendencia_requerida: Tendencia | None = None
    """`None` = vale em qualquer contexto. Só os padrões que o ebook explicitamente diz
    independerem da tendência anterior (Chute, 3 Soldados/Corvos) usam isso."""

    exige_gap: bool = False
    """Marcado para o backtest poder isolar o efeito de `tolerancia_gap_atr` — é o
    limiar mais sensível do motor."""

    derivado_por_simetria: bool = False
    """O ebook descreve só uma direção; o espelho foi inferido. Ver ERRATA item 9."""

    observacao: str = ""


CATALOGO: dict[str, EspecPadrao] = {}

CALIBRACAO: dict[str, tuple[float, int, float]] = {}
"""Preenchido pelo backtest: `padrao_id -> (taxa_acerto, n_ocorrencias, expectancia_r)`.

A expectância entrou junto porque taxa de acerto sozinha não decide nada: um padrão pode
acertar 55% e perder dinheiro, e o `tres_por_dentro_baixa` do WDO acerta 50% com −0,300R.

Enquanto vazio, todo padrão vale `confiabilidade_sem_medicao` — não o prior do ebook.
"""


def padrao(
    id: str,
    nome: str,
    familia: Familia,
    direcao: Direcao,
    n_candles: int,
    confiabilidade: float,
    pagina: int,
    tendencia: Tendencia | None = None,
    exige_gap: bool = False,
    derivado: bool = False,
    observacao: str = "",
):
    """Registra o detector no catálogo e devolve a função original."""

    def registrar(fn: Detector) -> Detector:
        if id in CATALOGO:
            raise ValueError(f"padrão duplicado no catálogo: {id}")
        CATALOGO[id] = EspecPadrao(
            id=id,
            nome=nome,
            familia=familia,
            direcao=direcao,
            n_candles=n_candles,
            confiabilidade_ebook=confiabilidade,
            pagina_ebook=pagina,
            detector=fn,
            tendencia_requerida=tendencia,
            exige_gap=exige_gap,
            derivado_por_simetria=derivado,
            observacao=observacao,
        )
        return fn

    return registrar


def foi_medida(spec: EspecPadrao, lim: Limiares = PADRAO) -> bool:
    """Existe medição deste padrão NESTE ativo, com amostra que sustente conclusão."""
    medida = CALIBRACAO.get(spec.id)
    return medida is not None and medida[1] >= lim.amostra_minima_confiabilidade


def expectancia_medida(spec: EspecPadrao, lim: Limiares = PADRAO) -> float | None:
    """Expectância em R medida no ativo, ou `None` se não há amostra que sustente."""
    medida = CALIBRACAO.get(spec.id)
    if medida is None or len(medida) < 3 or medida[1] < lim.amostra_minima_confiabilidade:
        return None
    return medida[2]


def confiabilidade_de(spec: EspecPadrao, lim: Limiares = PADRAO) -> float:
    """Taxa medida quando há amostra suficiente; senão, **neutro** — não o ebook.

    O piso de amostra existe para não transformar 4 acertos em 3 tentativas numa
    "confiabilidade de 75%" que a tela mostraria como se fosse evidência.

    **Sem medição o retorno é `confiabilidade_sem_medicao` (0,50), e não o prior do
    ebook.** O prior é um palpite de livro sobre o mercado americano de ações; usá-lo
    como peso empurra para cima o score de padrões sobre os quais não se sabe nada. Em
    10/08/2026 a Nuvem Negra entrou numa venda de WDO com "confiabilidade 70%" — número
    do ebook, zero medições em WDO — e o sinal passou o corte por 0,0003.

    O prior continua no catálogo (`spec.confiabilidade_ebook`) como referência de
    leitura. O que ele não faz mais é valer ponto.
    """
    sem_medicao = (
        spec.confiabilidade_ebook
        if lim.confiabilidade_sem_medicao is None
        else lim.confiabilidade_sem_medicao
    )
    medida = CALIBRACAO.get(spec.id)
    if medida is None:
        return sem_medicao
    taxa, n = medida[0], medida[1]
    if n < lim.amostra_minima_confiabilidade:
        return sem_medicao
    return taxa


def contexto_compativel(spec: EspecPadrao, ctx: Contexto) -> bool:
    if spec.tendencia_requerida is None:
        return True
    return ctx.tendencia is spec.tendencia_requerida


def _extremos(janela: Iterable[Candle]) -> tuple[float, float]:
    candles = list(janela)
    return max(c.maxima for c in candles), min(c.minima for c in candles)


def detectar_em(
    serie: Serie,
    i: int,
    ctx: Contexto,
    lim: Limiares = PADRAO,
    apenas: Iterable[str] | None = None,
) -> list[Deteccao]:
    """Roda o catálogo inteiro no candle `i`. Ordena por score bruto decrescente.

    Vários padrões podem disparar no mesmo candle — um Engolfo de Alta é também um
    "3 por fora" em formação, e um Harami é o começo de um "3 por dentro". Isso é
    esperado: a confluência decide qual vale mais, não o detector.
    """
    ids = set(apenas) if apenas is not None else None
    achados: list[Deteccao] = []

    for spec in CATALOGO.values():
        if ids is not None and spec.id not in ids:
            continue
        if not contexto_compativel(spec, ctx):
            continue
        janela = serie.janela(i, spec.n_candles)
        if not janela:
            continue

        forca = spec.detector(janela, ctx, lim)
        if forca is None:
            continue

        superior, inferior = _extremos(janela)
        achados.append(
            Deteccao(
                padrao_id=spec.id,
                nome=spec.nome,
                familia=spec.familia,
                direcao=spec.direcao,
                indice_fim=i,
                n_candles=spec.n_candles,
                forca=float(min(1.0, max(0.0, forca))),
                confiabilidade=confiabilidade_de(spec, lim),
                extremo_superior=superior,
                extremo_inferior=inferior,
                preco_referencia=janela[-1].fechamento,
                pagina_ebook=spec.pagina_ebook,
                detalhes={
                    "familia": spec.familia.value,
                    "exige_gap": spec.exige_gap,
                    "derivado_por_simetria": spec.derivado_por_simetria,
                    "tendencia": ctx.tendencia.value,
                    "janela_pregao": ctx.janela_pregao,
                },
            )
        )

    achados.sort(key=lambda d: d.score_bruto, reverse=True)
    return achados


def varrer(
    serie: Serie, lim: Limiares = PADRAO, inicio: int | None = None
) -> list[Deteccao]:
    """Percorre a série inteira detectando padrões. Usado pelo backtest e pela CLI.

    Importante: usa `contexto.ler(serie, i)`, que só olha para trás. Não há atalho de
    "calcular tudo vetorizado" aqui — seria fácil vazar informação futura e o resultado
    ficaria bom demais para ser verdade.
    """
    from .. import contexto as ctx_mod

    comeco = inicio if inicio is not None else lim.tendencia_min_candles
    fora: list[Deteccao] = []
    for i in range(comeco, len(serie)):
        ctx = ctx_mod.ler(serie, i, lim)
        fora.extend(detectar_em(serie, i, ctx, lim))
    return fora


def catalogo_ordenado() -> list[EspecPadrao]:
    return sorted(CATALOGO.values(), key=lambda s: (s.familia.value, s.pagina_ebook, s.id))
